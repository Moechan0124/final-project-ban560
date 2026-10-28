"""Shared PySpark data preparation for the Airbnb NYC project.

`load_clean` repeats the cleaning steps documented in 01_EDA_PySpark.ipynb (Section 3) so the
modeling notebook starts from exactly the same analytic sample. `add_model_features` adds the
extra features used only for modeling.
"""
import os

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

NUMERIC_COLS = [
    "accommodates", "bedrooms", "beds", "minimum_nights", "maximum_nights",
    "availability_30", "availability_60", "availability_90", "availability_365",
    "number_of_reviews", "number_of_reviews_ltm", "reviews_per_month",
    "review_scores_rating", "review_scores_accuracy", "review_scores_cleanliness",
    "review_scores_checkin", "review_scores_communication", "review_scores_location", "review_scores_value",
    "estimated_occupancy_l365d", "estimated_revenue_l365d",
    "calculated_host_listings_count", "hosts_time_as_host_years", "latitude", "longitude",
]

# Amenities that vary across listings (10%-70% prevalence) and plausibly affect price
AMENITY_FLAGS = {
    "am_air_conditioning": "Air conditioning",
    "am_workspace": "Dedicated workspace",
    "am_tv": "TV",
    "am_self_checkin": "Self check-in",
    "am_washer": "Washer",
    "am_dryer": "Dryer",
    "am_dishwasher": "Dishwasher",
    "am_elevator": "Elevator",
    "am_building_staff": "Building staff",
    "am_private_entrance": "Private entrance",
    "am_free_parking": "Free parking on premises",
    "am_bathtub": "Bathtub",
    "am_pets_allowed": "Pets allowed",
    "am_gym": "Gym",
    "am_bedroom_lock": "Lock on bedroom door",
    "am_outdoor_dining": "Outdoor dining area",
}

MIDTOWN_LAT, MIDTOWN_LON = 40.758, -73.9855  # Times Square


def get_spark(app_name: str) -> SparkSession:
    # Random forest CV needs a large heap in local mode; lower AIRBNB_SPARK_MEMORY on small laptops
    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.driver.memory", os.environ.get("AIRBNB_SPARK_MEMORY", "12g"))
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def _to_flag(col):
    return F.when(F.col(col) == "t", 1).when(F.col(col) == "f", 0).cast("int")


def load_listings(spark: SparkSession, path: str) -> DataFrame:
    """Read the raw CSV and apply the cleaning steps from notebook 01 (all listings, priced or not)."""
    raw = spark.read.option("header", True).option("multiLine", True).option("escape", '"').csv(path)
    bath_text = F.lower(F.col("bathrooms_text"))
    license_up = F.upper(F.col("license"))

    df = raw.select(
        "id", "host_id", "neighbourhood_cleansed", "neighbourhood_group_cleansed", "room_type", "property_type",
        "bathrooms_text", "amenities", "license", "host_is_superhost", "host_identity_verified", "price",
        *NUMERIC_COLS,
    )
    for c in NUMERIC_COLS:
        df = df.withColumn(c, F.col(c).cast("double"))

    return (
        df.withColumnRenamed("neighbourhood_cleansed", "neighbourhood")
        .withColumnRenamed("neighbourhood_group_cleansed", "borough")
        .withColumn("price", F.regexp_replace("price", r"[$,]", "").cast("double"))
        .withColumn("bathrooms", F.when(bath_text.contains("half"), 0.5)
                    .otherwise(F.regexp_extract(bath_text, r"(\d+(\.\d+)?)", 1).cast("double")))
        .withColumn("shared_bath", bath_text.contains("shared").cast("int"))
        .withColumn("amenity_list", F.from_json("amenities", T.ArrayType(T.StringType())))
        .withColumn("amenities_count", F.size("amenity_list"))
        .withColumn("is_superhost", _to_flag("host_is_superhost"))
        .withColumn("identity_verified", _to_flag("host_identity_verified"))
        .withColumn("stay_type", F.when(F.col("minimum_nights") >= 30, "30+ nights").otherwise("Under 30 nights"))
        .withColumn("license_status",
                    F.when(license_up.startswith("OSE-STRREG"), "Registered")
                    .when(license_up == "EXEMPT", "Exempt").otherwise("Not reported"))
        .drop("bathrooms_text", "amenities", "license", "host_is_superhost", "host_identity_verified")
    )


def analytic_sample(df: DataFrame):
    """Priced listings with the 1%/99% price trim; adds log_price. Returns (sample, (p01, p99))."""
    priced = df.filter(F.col("price").isNotNull())
    p01, p99 = priced.approxQuantile("price", [0.01, 0.99], 0.0001)
    sample = (
        priced.filter((F.col("price") >= p01) & (F.col("price") <= p99))
        .withColumn("log_price", F.log("price"))
    )
    return sample, (p01, p99)


def add_model_features(df: DataFrame, min_hood_listings: int = 20, top_property_types: int = 12) -> DataFrame:
    """Modeling-only features: grouped categories, log counts, distance, amenity flags."""
    hood_counts = df.groupBy("neighbourhood").count()
    keep_hoods = [r.neighbourhood for r in hood_counts.filter(F.col("count") >= min_hood_listings).collect()]
    top_types = [r.property_type for r in df.groupBy("property_type").count()
                 .orderBy(F.desc("count")).limit(top_property_types).collect()]

    out = (
        df.withColumn("neighbourhood_grp",
                      F.when(F.col("neighbourhood").isin(keep_hoods), F.col("neighbourhood"))
                      .otherwise(F.concat(F.lit("Other "), F.col("borough"))))
        .withColumn("property_grp",
                    F.when(F.col("property_type").isin(top_types), F.col("property_type")).otherwise("Other"))
        .withColumn("km_to_midtown",
                    F.sqrt(((F.col("longitude") - MIDTOWN_LON) * F.cos(F.radians(F.lit(MIDTOWN_LAT)))) ** 2
                           + (F.col("latitude") - MIDTOWN_LAT) ** 2) * 111.0)
        .withColumn("has_reviews", (F.col("number_of_reviews") > 0).cast("int"))
        .withColumn("log_min_nights", F.log1p("minimum_nights"))
        .withColumn("log_reviews", F.log1p("number_of_reviews"))
        .withColumn("log_reviews_ltm", F.log1p("number_of_reviews_ltm"))
        .withColumn("log_host_listings", F.log1p("calculated_host_listings_count"))
    )
    for col, name in AMENITY_FLAGS.items():
        out = out.withColumn(col, F.coalesce(F.array_contains("amenity_list", name).cast("int"), F.lit(0)))
    return out
