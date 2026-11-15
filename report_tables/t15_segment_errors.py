"""Report Table 15: random forest error by stay type, room type and borough (test set)."""
import pandas as pd
from pyspark.sql import functions as F

from common import load_model, save, smearing, spark, train_test

spark = spark("Report-T15")
train, test = train_test(spark)
model = load_model("random_forest")
smear = smearing(model.transform(train))
pred = model.transform(test).withColumn("pred_price", F.exp("prediction") * smear).cache()

def by_segment(col):
    m = pred.groupBy(col).agg(F.mean("log_price").alias("_mean"))
    return (pred.join(m, col).groupBy(col)
            .agg(F.count("*").alias("test_listings"),
                 F.sqrt(F.mean((F.col("prediction") - F.col("log_price")) ** 2)).alias("rmse_log"),
                 (1 - F.sum((F.col("prediction") - F.col("log_price")) ** 2)
                  / F.sum((F.col("log_price") - F.col("_mean")) ** 2)).alias("r2_within"),
                 F.percentile_approx(F.abs(F.col("pred_price") - F.col("price")) / F.col("price"), 0.5, 10000).alias("median_abs_pct_error"))
            .withColumnRenamed(col, "segment").toPandas().assign(dimension=col))

save(pd.concat([by_segment(c) for c in ["stay_type", "room_type", "borough"]]), "t15_segment_errors")
spark.stop()
