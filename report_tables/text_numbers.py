"""Single numbers quoted in the report text (sections 1-3), recomputed from listings.csv."""
import pandas as pd
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.stat import Correlation
from pyspark.sql import functions as F

from common import DATA_PATH, listings, prep, save, spark

spark = spark("Report-Text")
raw = spark.read.option("header", True).option("multiLine", True).option("escape", '"').csv(str(DATA_PATH))
df = listings(spark).cache()
priced = df.filter(F.col("price").isNotNull()).cache()
clean, (p01, p99) = prep.analytic_sample(df)
clean = prep.add_model_features(clean).cache()
n, n_priced, n_clean = df.count(), priced.count(), clean.count()

rows = []
add = lambda item, value, section: rows.append({"item": item, "value": value, "report_section": section})
add("Listings in the raw file", raw.count(), "1.1, 2.1")
add("Columns in the raw file", len(raw.columns), "1.1, 2.1")
add("Listings with a price", n_priced, "2.1")
add("Share with a price (%)", n_priced / n * 100, "2.1")
zero = df.groupBy(F.col("price").isNotNull().alias("priced")).agg(F.avg((F.col("availability_365") == 0).cast("double")).alias("s")).toPandas().set_index("priced").s
add("Unpriced listings with zero open nights (%)", zero[False] * 100, "2.1")
add("Priced listings with zero open nights (%)", zero[True] * 100, "2.1")
add("Lower trim bound ($)", p01, "2.2")
add("Upper trim bound ($)", p99, "2.2")
add("Analytic sample", n_clean, "2.2")
add("Neighborhoods in the analytic sample", clean.select("neighbourhood").distinct().count(), "2.2")
add("Skewness of price, analytic sample", clean.select(F.skewness("price")).first()[0], "2.2")
add("Skewness of ln(price), analytic sample", clean.select(F.skewness("log_price")).first()[0], "2.2")
add("Highest price before trimming ($)", priced.agg(F.max("price")).first()[0], "2.2")
add("Median price, analytic sample ($)", clean.approxQuantile("price", [0.5], 0.0001)[0], "2.2, 3.1")
add("Share of all listings with minimum stay of exactly 30 nights (%)", df.filter(F.col("minimum_nights") == 30).count() / n * 100, "3.1")
add("Share of all listings with minimum stay of 30+ nights (%)", df.filter(F.col("minimum_nights") >= 30).count() / n * 100, "1.2, 3.1")
# Same 14 columns and complete cases as the correlation matrix of notebook 01 (Figure 2)
corr_cols = ["log_price", "accommodates", "bedrooms", "beds", "bathrooms", "amenities_count", "minimum_nights",
             "availability_365", "number_of_reviews", "number_of_reviews_ltm", "review_scores_rating",
             "calculated_host_listings_count", "hosts_time_as_host_years", "is_superhost"]
vec = VectorAssembler(inputCols=corr_cols, outputCol="v").transform(clean.select(corr_cols).na.drop()).select("v")
corr = Correlation.corr(vec, "v").first()[0].toArray()
add("Correlation of guests accommodated with beds", corr[corr_cols.index("accommodates"), corr_cols.index("beds")], "2.3")
add("Correlation of km to Times Square with ln(price)", clean.stat.corr("km_to_midtown", "log_price"), "3.1")
med = (clean.filter(F.col("room_type").isin("Entire home/apt", "Private room"))
       .groupBy("stay_type", "room_type").agg(F.percentile_approx("price", 0.5, 10000).alias("m")).toPandas()
       .set_index(["stay_type", "room_type"]).m)
for (s, r), v in med.items():
    add(f"Median price, {r}, {s} ($)", v, "3.1")
rev = clean.groupBy("is_superhost").agg(F.mean("number_of_reviews_ltm").alias("m")).toPandas().set_index("is_superhost").m
add("Mean reviews in last 12 months, Superhosts", rev[1], "3.1")
add("Mean reviews in last 12 months, other hosts", rev[0], "3.1")
add("Mean open nights, analytic sample", clean.agg(F.mean("availability_365")).first()[0], "3.4")
save(pd.DataFrame(rows), "text_numbers")
spark.stop()
