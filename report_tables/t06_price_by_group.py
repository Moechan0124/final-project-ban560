"""Report Table 6: listings, share and median nightly price by room type, borough, stay type,
license status and Superhost status (analytic sample)."""
import pandas as pd
from pyspark.sql import functions as F

from common import analytic, save, spark

spark = spark("Report-T06")
clean = analytic(spark).cache()
total = clean.count()
parts = []
for col, label in [("room_type", "Room type"), ("borough", "Borough"), ("stay_type", "Stay type"),
                   ("license_status", "License status"), ("is_superhost", "Superhost")]:
    t = (clean.groupBy(col)
         .agg(F.count("*").alias("listings"),
              F.percentile_approx("price", 0.5, 10000).alias("median_price"),
              F.mean("number_of_reviews_ltm").alias("mean_reviews_ltm"))
         .orderBy(F.desc("listings")).toPandas()
         .rename(columns={col: "category"}))
    if col == "is_superhost":
        t["category"] = t.category.map({0: "No", 1: "Yes"})
    t.insert(0, "group", label)
    t["share_pct"] = t.listings / total * 100
    parts.append(t)
table = pd.concat(parts)[["group", "category", "listings", "share_pct", "median_price", "mean_reviews_ltm"]]
save(table, "t06_price_by_group")
spark.stop()
