"""Report Table 16: one pooled random forest versus a separate forest for each stay type (test R², log price)."""
import pandas as pd
from pyspark.ml.regression import RandomForestRegressor
from pyspark.sql import functions as F

from common import CAT, EVAL, NUM, SEED, load_model, prep, save, spark, train_test

spark = spark("Report-T16")
train, test = train_test(spark)
pooled = load_model("random_forest")
rows = []
for seg in ["Under 30 nights", "30+ nights"]:
    tr, te = train.filter(F.col("stay_type") == seg), test.filter(F.col("stay_type") == seg)
    rf = RandomForestRegressor(featuresCol="features", labelCol="log_price", seed=SEED, featureSubsetStrategy="onethird",
                               numTrees=200, maxDepth=15)
    separate = prep.model_pipeline(rf, [c for c in CAT if c != "stay_type"], NUM).fit(tr)  # stay type is constant here
    rows.append({"stay_type": seg, "train_listings": tr.count(), "test_listings": te.count(),
                 "separate_r2": EVAL["r2"].evaluate(separate.transform(te)),
                 "pooled_r2": EVAL["r2"].evaluate(pooled.transform(te))})
save(pd.DataFrame(rows), "t16_pooled_vs_separate")
spark.stop()
