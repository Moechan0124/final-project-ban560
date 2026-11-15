"""Shared setup for the report-table scripts.

Every script in this folder rebuilds one table of the final report from listings.csv and writes it to
report_tables/data/. This module holds what they share: the Spark session, the analytic sample, the
80/20 split of notebook 02, model evaluation, and the neighborhood demand index.
"""
import sys
from pathlib import Path

import pandas as pd
from pyspark.ml import PipelineModel
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql import functions as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
import airbnb_prep as prep  # noqa: E402

DATA_PATH = ROOT / "listings.csv"
MODEL_DIR = ROOT / "models"
OUT_DIR = HERE / "data"
OUT_DIR.mkdir(exist_ok=True)
SEED = 42

CAT = prep.CAT_FEATURES
NUM = prep.NUM_FEATURES
# Feature families used for permutation importance (notebook 02, Section 2)
GROUPS = {
    "Location": ["neighbourhood_grp", "latitude", "longitude", "km_to_midtown"],
    "Room & property type": ["room_type", "property_grp"],
    "Size & capacity": ["accommodates", "bedrooms", "beds", "bathrooms", "shared_bath"],
    "Amenities": ["amenities_count", *prep.AMENITY_FLAGS],
    "Booking rules (stay, availability)": ["log_min_nights", "stay_type", "availability_30", "availability_365"],
    "Reviews & ratings": ["has_reviews", "log_reviews", "log_reviews_ltm", "review_scores_rating",
                          "review_scores_cleanliness", "review_scores_location", "review_scores_value"],
    "Host attributes": ["is_superhost", "identity_verified", "hosts_time_as_host_years", "log_host_listings"],
    "License status": ["license_status"],
}
class _Evaluators(dict):
    """RegressionEvaluator per metric, created on first use because it needs a running SparkContext."""
    def __missing__(self, metric):
        self[metric] = RegressionEvaluator(labelCol="log_price", predictionCol="prediction", metricName=metric)
        return self[metric]


EVAL = _Evaluators()


def spark(name):
    return prep.get_spark(name)


def listings(spark):
    """All 29,918 listings after cleaning (notebook 01, Section 3)."""
    return prep.load_listings(spark, str(DATA_PATH))


def priced(spark):
    """The 19,406 listings with a price, before the 1%/99% trim."""
    return listings(spark).filter(F.col("price").isNotNull())


def analytic(spark):
    """The 19,018-listing analytic sample (priced, 1%/99% trimmed) with log_price."""
    sample, _ = prep.analytic_sample(listings(spark))
    return sample


def model_data(spark):
    """Analytic sample with model features (notebook 02 and 03)."""
    return prep.add_model_features(analytic(spark)).cache()


def train_test(spark):
    """The 15,276 / 3,742 split of notebook 02 (same columns, same seed, so the same rows)."""
    keep = ["id", "price", "log_price", "borough", *CAT, *NUM]
    df = model_data(spark).select(*keep)
    for c in NUM:
        df = df.withColumn(c, F.col(c).cast("double"))
    train, test = df.randomSplit([0.8, 0.2], seed=SEED)
    return train.cache(), test.cache()


def load_model(name):
    """Saved pipeline from notebook 02: elastic_net, random_forest or gbt."""
    path = MODEL_DIR / name
    if not path.exists():
        raise SystemExit(f"{path} not found: run code/02_Modeling_PySpark.ipynb or unzip models.zip from the models-v1 release")
    return PipelineModel.load(str(path))


def smearing(train_pred):
    """Mean of exp(training residuals): turns exp(log prediction) into a mean-unbiased dollar prediction."""
    return train_pred.select(F.mean(F.exp(F.col("log_price") - F.col("prediction")))).first()[0]


def evaluate(name, train_pred, test_pred):
    """Test-set metrics used in report Table 7 (same as notebook 02, Section 3)."""
    smear = smearing(train_pred)
    p = test_pred.withColumn("pred_price", F.exp("prediction") * smear)
    d = p.select(
        F.sqrt(F.mean((F.col("pred_price") - F.col("price")) ** 2)).alias("rmse"),
        F.mean(F.abs(F.col("pred_price") - F.col("price"))).alias("mae"),
        F.percentile_approx(F.abs(F.col("pred_price") - F.col("price")) / F.col("price"), 0.5, 10000).alias("mdape"),
    ).first()
    return {
        "model": name,
        "rmse_log": EVAL["rmse"].evaluate(test_pred), "r2_log": EVAL["r2"].evaluate(test_pred),
        "train_r2_log": EVAL["r2"].evaluate(train_pred), "mae_usd": d.mae, "rmse_usd": d.rmse,
        "median_abs_pct_error": d.mdape, "mae_log": EVAL["mae"].evaluate(test_pred),
    }


def neighbourhood_demand(priced_df):
    """Demand index for neighborhoods with >= 50 priced listings (notebook 01, Section 4.1), as pandas."""
    top_host = (priced_df.groupBy("neighbourhood", "host_id").count()
                .groupBy("neighbourhood").agg(F.max("count").alias("top_host_listings")))
    hood = (priced_df.groupBy("borough", "neighbourhood")
            .agg(F.count("*").alias("listings"),
                 F.mean("availability_365").alias("mean_availability_365"),
                 F.mean(F.log1p("number_of_reviews_ltm")).alias("mean_log_reviews_ltm"),
                 F.mean("number_of_reviews_ltm").alias("mean_reviews_ltm"),
                 F.percentile_approx("price", 0.5, 10000).alias("median_price"))
            .filter(F.col("listings") >= 50)
            .join(top_host, "neighbourhood")
            .withColumn("top_host_share", F.col("top_host_listings") / F.col("listings"))
            .toPandas())
    z = lambda s: (s - s.mean()) / s.std()  # sample SD, as Spark's stddev
    hood["demand_index"] = (z(hood.mean_log_reviews_ltm) - z(hood.mean_availability_365)) / 2
    return hood.sort_values("demand_index", ascending=False).reset_index(drop=True)


def save(df: pd.DataFrame, name):
    path = OUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"wrote {path.relative_to(ROOT)} ({len(df)} rows)")
    print(df.head(20).to_string(index=False))
