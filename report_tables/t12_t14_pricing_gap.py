"""Report Tables 12, 13 and 14: price gap against an out-of-fold fair price, demand by gap quintile,
and candidate neighborhoods for under-pricing (about 12 minutes: ten random forest fits).

Fair price model A uses every listing feature except demand signals (availability, review counts);
model B also drops location. Listings are split into five folds by a hash of their id, and each fold is
predicted by a forest trained on the other four.
"""
import pandas as pd
from pyspark.ml.regression import RandomForestRegressor
from pyspark.sql import Window, functions as F

from common import CAT, NUM, SEED, model_data, neighbourhood_demand, prep, priced, save, spark

FOLDS = 5
DEMAND_SIGNALS = {"availability_30", "availability_365", "log_reviews", "log_reviews_ltm"}
LOCATION_NUM = {"latitude", "longitude", "km_to_midtown"}
num_a = [c for c in NUM if c not in DEMAND_SIGNALS]
num_b = [c for c in num_a if c not in LOCATION_NUM]
cat_b = [c for c in CAT if c != "neighbourhood_grp"]

spark = spark("Report-T12-T14")
frame = model_data(spark).withColumn("fold", F.pmod(F.xxhash64("id", F.lit(SEED)), F.lit(FOLDS)))
for c in num_a:
    frame = frame.withColumn(c, F.col(c).cast("double"))
frame = frame.cache()

def out_of_fold(cat, num, name):
    parts = []
    for k in range(FOLDS):
        rf = RandomForestRegressor(featuresCol="features", labelCol="log_price", seed=SEED,
                                   featureSubsetStrategy="onethird", numTrees=200, maxDepth=15)
        model = prep.model_pipeline(rf, cat, num).fit(frame.filter(F.col("fold") != k))
        parts.append(model.transform(frame.filter(F.col("fold") == k)).select("id", "prediction").toPandas())
        print(name, "fold", k, "done")
    p = pd.concat(parts).rename(columns={"prediction": f"log_fair_{name}"})
    p["id"] = p["id"].astype(str)
    return p

oof = out_of_fold(CAT, num_a, "a").merge(out_of_fold(cat_b, num_b, "b"), on="id", validate="one_to_one")
scored = frame.join(spark.createDataFrame(oof), "id")
mean_log = scored.select(F.mean("log_price")).first()[0]
fit = []
for name in ["a", "b"]:
    log_col = f"log_fair_{name}"
    scored = scored.withColumn(f"fair_{name}", F.exp(log_col))  # typical (median-type) price, no smearing
    r = scored.select(
        (1 - F.sum((F.col("log_price") - F.col(log_col)) ** 2) / F.sum((F.col("log_price") - F.lit(mean_log)) ** 2)).alias("r2"),
        F.percentile_approx(F.abs(F.col("price") / F.col(f"fair_{name}") - 1), 0.5, 10000).alias("mdape")).first()
    fit.append({"model": "A (with location)" if name == "a" else "B (no location)", "oof_r2_log": r.r2, "median_abs_pct_error": r.mdape})
save(pd.DataFrame(fit), "t12_fair_price_fit")

scored = (scored.withColumn("gap_pct", F.col("price") / F.col("fair_a") - 1)
          .withColumn("location_premium", F.col("fair_a") / F.col("fair_b") - 1)
          .withColumn("gap_group", F.when(F.col("gap_pct") < -0.2, "More than 20% below")
                      .when(F.col("gap_pct") > 0.2, "More than 20% above").otherwise("Within 20%"))
          .cache())

# Table 12: share of each gap group within each stay type
t12 = (scored.groupBy("stay_type", "gap_group").count()
       .withColumn("share", F.col("count") / F.sum("count").over(Window.partitionBy("stay_type")))
       .toPandas().pivot(index="stay_type", columns="gap_group", values="share").reset_index())
save(t12[["stay_type", "More than 20% below", "Within 20%", "More than 20% above"]], "t12_gap_shares")

# Table 13: gap quintiles within each stay type
q = scored.withColumn("gap_quintile", F.ntile(5).over(Window.partitionBy("stay_type").orderBy("gap_pct")))
t13 = (q.groupBy("stay_type", "gap_quintile")
       .agg(F.percentile_approx("gap_pct", 0.5, 10000).alias("median_gap"),
            F.mean("availability_365").alias("mean_open_nights"),
            F.mean((F.col("number_of_reviews_ltm") > 0).cast("double")).alias("share_reviewed_12mo"),
            F.mean("estimated_occupancy_l365d").alias("mean_est_occupied_nights"),
            F.mean(F.col("estimated_occupancy_l365d") * F.col("price")).alias("mean_est_revenue"))
       .orderBy("stay_type", "gap_quintile").toPandas())
save(t13, "t13_gap_quintiles")

# Table 14: high demand, low location premium, no dominant host
premium = (scored.groupBy("neighbourhood")
           .agg(F.percentile_approx("location_premium", 0.5, 10000).alias("median_location_premium")).toPandas())
hoods = neighbourhood_demand(priced(spark)).merge(premium, on="neighbourhood", validate="one_to_one")
high = hoods[hoods.demand_index >= hoods.demand_index.quantile(0.75)]
t14 = high[(high.median_location_premium < -0.05) & (high.top_host_share < 0.5)].sort_values("median_location_premium")
print("corr(demand index, location premium) =", round(hoods.demand_index.corr(hoods.median_location_premium), 3))
save(t14[["neighbourhood", "borough", "listings", "demand_index", "median_price", "median_location_premium", "top_host_share"]],
     "t14_underpricing_candidates")
spark.stop()
