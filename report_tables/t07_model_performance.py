"""Report Table 7: test-set performance of the five models.

Baseline and OLS are refitted here (seconds); Elastic Net, random forest and GBT are the tuned pipelines
saved by notebook 02 in models/.
"""
import pandas as pd
from pyspark.ml.regression import LinearRegression
from pyspark.sql import functions as F

from common import CAT, NUM, evaluate, load_model, prep, save, spark, train_test

spark = spark("Report-T07")
train, test = train_test(spark)

# Baseline: median log price of the training listings in the same neighborhood x room type,
# falling back to the room-type median when the cell is empty
cell_med = train.groupBy("neighbourhood_grp", "room_type").agg(F.percentile_approx("log_price", 0.5, 10000).alias("cell_pred"))
room_med = train.groupBy("room_type").agg(F.percentile_approx("log_price", 0.5, 10000).alias("room_pred"))

def baseline(df):
    return (df.join(cell_med, ["neighbourhood_grp", "room_type"], "left").join(room_med, "room_type", "left")
            .withColumn("prediction", F.coalesce("cell_pred", "room_pred")))

ols = prep.model_pipeline(LinearRegression(featuresCol="features", labelCol="log_price", regParam=0.0, solver="normal"), CAT, NUM).fit(train)
rows = [evaluate("Baseline", baseline(train), baseline(test)),
        evaluate("OLS", ols.transform(train), ols.transform(test))]
for name, path in [("Elastic Net", "elastic_net"), ("Random forest", "random_forest"), ("Gradient-boosted trees", "gbt")]:
    m = load_model(path)
    rows.append(evaluate(name, m.transform(train), m.transform(test)))
save(pd.DataFrame(rows), "t07_model_performance")
spark.stop()
