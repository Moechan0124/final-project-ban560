"""Report Table 10: neighborhood demand index (priced listings; 72 neighborhoods with >= 50 of them).

Writes all 72 neighborhoods in rank order; the report shows the top 10.
"""
from common import neighbourhood_demand, priced, save, spark

spark = spark("Report-T10")
hood = neighbourhood_demand(priced(spark))
hood.insert(0, "rank", range(1, len(hood) + 1))
save(hood[["rank", "neighbourhood", "borough", "listings", "mean_availability_365", "mean_reviews_ltm",
           "median_price", "top_host_share", "demand_index", "mean_log_reviews_ltm"]], "t10_neighbourhood_demand")
spark.stop()
