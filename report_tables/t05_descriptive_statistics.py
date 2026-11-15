"""Report Table 5: descriptive statistics of key numeric variables (analytic sample, n = 19,018)."""
from common import analytic, save, spark

COLS = {"price": "Price ($/night)", "log_price": "ln(price)", "accommodates": "Guests accommodated",
        "bedrooms": "Bedrooms", "minimum_nights": "Minimum nights", "number_of_reviews_ltm": "Reviews (last 12 months)",
        "review_scores_rating": "Overall rating (1-5)", "calculated_host_listings_count": "Host's listing count"}

spark = spark("Report-T05")
desc = (analytic(spark).select(list(COLS)).summary("count", "mean", "stddev", "min", "50%", "max")
        .toPandas().set_index("summary").T.astype(float))
desc.columns = ["n", "mean", "sd", "min", "median", "max"]
desc.insert(0, "variable", desc.index.map(COLS))
save(desc, "t05_descriptive_statistics")
spark.stop()
