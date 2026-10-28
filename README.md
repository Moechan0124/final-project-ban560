# Predicting Airbnb Listing Prices with PySpark (NYC, September 2026)

BAN5600-01-F26 Advanced Big Data Computing and Programming

The project uses Apache Spark (PySpark) to study what drives the nightly price of New York City
Airbnb listings and how well price can be predicted. It answers three research questions:

1. **RQ1:** Which listing features matter most for price?
2. **RQ2:** Can a regression model built from these features predict price reasonably well?
3. **RQ3:** Which neighborhoods and listing types show the highest demand (few open nights and many recent reviews)?

## Repository layout

```
listings.csv                    Inside Airbnb NYC detailed listings, scraped 2026-09-14/15 (input data, not in git)
code/
  01_EDA_PySpark.ipynb          cleaning, descriptive statistics, figures 1-7, neighborhood demand (RQ3)
  02_Modeling_PySpark.ipynb     baseline, OLS, Elastic Net, random forest, GBT; CV; importance (RQ1, RQ2)
  airbnb_prep.py                shared cleaning and feature engineering used by notebook 02
  plot_style.py                 shared figure style
figures/                        all PNG figures (fig1-7 from notebook 01, figM1-M6 from notebook 02)
outputs/                        CSV tables written by the notebooks
models/                         saved Spark ML pipeline models (created by notebook 02, not in git)
requirements.txt                Python package versions
```

`kafka_streaming_lab_advanced.ipynb` in this repository is a separate course lab, not part of this project.

**Large files kept out of git:**

- `listings.csv` (74 MB): download it as described under *Setup*.
- `models/` (64 MB): rebuilt by notebook 02, or download `models.zip` from the
  [models-v1 release](https://github.com/Moechan0124/final-project-ban560/releases/tag/models-v1)
  and unzip it in the project root.

## Setup

1. **Java 17.** Spark 4.x runs on Java 17 or 21. On macOS with Homebrew:
   ```bash
   brew install openjdk@17
   ```
   Make sure `java -version` prints 17 (set `JAVA_HOME` if another Java is the default).
2. **Python 3.10 or newer** (tested with 3.13, Anaconda) and the packages:
   ```bash
   pip install -r requirements.txt
   ```
3. **Data.** `listings.csv` must sit in the project root. To rebuild it, download the New York City
   "listings.csv.gz" (detailed listings) for the 2026-09 snapshot from
   <https://insideairbnb.com/get-the-data/> and unzip it here. A different snapshot will run, but the
   numbers will differ from the report.

## Running the analysis

Run the notebooks in order, from the project root or from `code/`:

```bash
jupyter nbconvert --to notebook --execute --inplace code/01_EDA_PySpark.ipynb
```

```bash
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 code/02_Modeling_PySpark.ipynb
```

Or open them in Jupyter (`jupyter notebook`) and choose *Run All*.

| Notebook | Runtime (MacBook, local[*]) | Writes |
|---|---|---|
| 01 EDA | about 15 seconds | `figures/fig1-7*.png`, `outputs/price_by_*.csv`, `descriptive_numeric.csv`, `neighbourhood_demand.csv`, `correlation_matrix.csv` |
| 02 Modeling | about 21 minutes (random forest CV is most of it) | `figures/figM1-M6*.png`, `outputs/model_comparison.csv`, `cv_results_*.csv`, `elastic_net_coefficients.csv`, `tree_feature_importance.csv`, `permutation_importance.csv`, `segment_*.csv`, `models/` |

Spark runs in local mode (`local[*]`, all CPU cores). Notebook 02 asks for a 12 GB driver heap because the random forest cross-validation is memory-hungry; on a laptop with 8 GB of RAM, set `export AIRBNB_SPARK_MEMORY=4g` before starting Jupyter, and if it still runs out of memory, remove 200 from the `numTrees` grid in Section 7 of notebook 02. To run on a cluster
(Databricks, Amazon EMR), change the `.master(...)` setting in `code/airbnb_prep.py`
(`get_spark`) and in the setup cell of notebook 01. The rest of the code uses only Spark DataFrame
and ML APIs, so nothing else needs to change.

## Reproducibility notes

- All random steps use `seed=42`: the 80/20 train/test split, cross-validation folds, random forest, and GBT.
- Preprocessing (string indexing, one-hot encoding, median imputation) is part of each Spark ML
  `Pipeline`, so it is re-fit inside every cross-validation fold and never sees test data.
- The price trim bounds (1st and 99th percentiles) are computed with `approxQuantile` at a relative
  error of 0.0001. They are $43.27 and $1,997.43 for this snapshot.
- Notebook 01 performs the cleaning inline so each step can be read. `airbnb_prep.py` repeats the same
  steps for notebook 02, so both notebooks use the same 19,018-listing analytic sample.

## Data source

Inside Airbnb. (n.d.). *Get the data*. Retrieved September 23, 2026, from https://insideairbnb.com/get-the-data/
(licensed under Creative Commons Attribution 4.0).
