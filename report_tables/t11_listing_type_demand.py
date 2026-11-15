"""Report Table 11: demand by stay type and room type (priced listings, groups with >= 50 listings)."""
from pyspark.sql import functions as F

from common import priced, save, spark

spark = spark("Report-T11")
table = (priced(spark).groupBy("stay_type", "room_type")
         .agg(F.count("*").alias("listings"),
              F.mean("availability_365").alias("mean_open_nights"),
              F.mean((F.col("number_of_reviews_ltm") > 0).cast("double")).alias("share_reviewed_12mo"),
              F.mean("estimated_occupancy_l365d").alias("mean_est_occupied_nights"),
              F.percentile_approx("price", 0.5, 10000).alias("median_price"))
         .filter(F.col("listings") >= 50)
         .orderBy("stay_type", "room_type").toPandas())
save(table, "t11_listing_type_demand")
spark.stop()
