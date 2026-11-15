"""Report Table 8: permutation importance by feature family (random forest and Elastic Net, test set).

For each family, all its columns are shuffled together across test listings and the rise in test RMSE
(log price) is recorded; three shuffles per family, averaged.
"""
import numpy as np
import pandas as pd
from pyspark.sql import Window, functions as F

from common import EVAL, GROUPS, SEED, load_model, save, spark, train_test

spark = spark("Report-T08")
_, test = train_test(spark)

def permuted(df, cols, seed):
    base = df.withColumn("_rid", F.monotonically_increasing_id())
    left = base.drop(*cols).withColumn("_k", F.row_number().over(Window.orderBy("_rid")))
    right = base.select(*cols).withColumn("_k", F.row_number().over(Window.orderBy(F.rand(seed))))
    return left.join(right, "_k").drop("_k", "_rid")

rows = []
for name, path in [("Random forest", "random_forest"), ("Elastic Net", "elastic_net")]:
    model = load_model(path)
    base_rmse = EVAL["rmse"].evaluate(model.transform(test))
    for group, cols in GROUPS.items():
        scores = [EVAL["rmse"].evaluate(model.transform(permuted(test, cols, SEED + r))) for r in range(3)]
        rows.append({"family": group, "model": name, "rmse_increase": np.mean(scores) - base_rmse, "base_rmse": base_rmse})
    print(name, "done")

table = (pd.DataFrame(rows).pivot(index="family", columns="model", values="rmse_increase")
         .sort_values("Random forest", ascending=False).reset_index())
save(table[["family", "Random forest", "Elastic Net"]], "t08_permutation_importance")
spark.stop()
