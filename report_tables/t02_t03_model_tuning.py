"""Report Tables 2 and 3: tuning grids, five-fold cross-validation results and the selected settings.

Runs the same CrossValidator searches as notebook 02 on the 15,276 training listings (about 20 minutes,
most of it the random forest).
"""
import pandas as pd
from pyspark.ml.regression import GBTRegressor, LinearRegression, RandomForestRegressor
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder

from common import CAT, EVAL, NUM, SEED, prep, save, spark, train_test

spark = spark("Report-T02-T03")
train, _ = train_test(spark)

lr = LinearRegression(featuresCol="features", labelCol="log_price", maxIter=200)
rf = RandomForestRegressor(featuresCol="features", labelCol="log_price", seed=SEED, featureSubsetStrategy="onethird")
gbt = GBTRegressor(featuresCol="features", labelCol="log_price", seed=SEED, maxIter=150, stepSize=0.1)
searches = [
    ("Elastic Net", "LinearRegression", lr, ParamGridBuilder().addGrid(lr.regParam, [0.0005, 0.002, 0.01, 0.05])
     .addGrid(lr.elasticNetParam, [0.0, 0.5, 1.0]).build(), 4),
    ("Random forest", "RandomForestRegressor", rf, ParamGridBuilder().addGrid(rf.numTrees, [100, 200])
     .addGrid(rf.maxDepth, [10, 15]).build(), 1),
    ("Gradient-boosted trees", "GBTRegressor", gbt, ParamGridBuilder().addGrid(gbt.maxDepth, [4, 6]).build(), 1),
]

cv_rows, model_rows = [], []
for name, cls, est, grid, par in searches:
    cv = CrossValidator(estimator=prep.model_pipeline(est, CAT, NUM), estimatorParamMaps=grid, evaluator=EVAL["rmse"],
                        numFolds=5, seed=SEED, parallelism=par).fit(train)
    scores = [({p.name: v for p, v in pm.items()}, m) for pm, m in zip(cv.getEstimatorParamMaps(), cv.avgMetrics)]
    for params, m in scores:
        cv_rows.append({"model": name, "setting": ", ".join(f"{k}={v}" for k, v in params.items()), "cv_rmse_log": m})
    best = min(scores, key=lambda s: s[1])[0]
    model_rows.append({"model": name, "spark_class": cls,
                       "grid": "; ".join(f"{p.name} {sorted({pm[p] for pm in grid})}" for p in grid[0]),
                       "selected": ", ".join(f"{k}={v}" for k, v in best.items())})
    print(name, "done; best", best)

models = pd.DataFrame([
    {"model": "Baseline", "spark_class": "Spark SQL group-by", "grid": "none (median log price by neighborhood x room type)", "selected": "-"},
    {"model": "OLS", "spark_class": "LinearRegression", "grid": "none", "selected": "-"},
    *model_rows,
])
save(models, "t02_models")
save(pd.DataFrame(cv_rows).sort_values(["model", "cv_rmse_log"]), "t03_cv_results")
spark.stop()
