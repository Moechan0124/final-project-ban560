# Report Tables: Code and Data

One script per table of the final report. Each script starts from `listings.csv`, rebuilds its table and
writes it to `data/`. Values in `data/` keep full precision; the report rounds them.

| Report item | Script | Output in `data/` | Runtime |
|---|---|---|---|
| Numbers in the text (sample sizes, trim bounds, shares, correlations, medians) | `text_numbers.py` | `text_numbers.csv` | < 1 min |
| Table 1. Feature families | `t01_feature_families.py` | `t01_feature_families.csv` | seconds |
| Table 2. Models and selected settings | `t02_t03_model_tuning.py` | `t02_models.csv` | about 20 min |
| Table 3. Cross-validation results | `t02_t03_model_tuning.py` | `t03_cv_results.csv` | (same run) |
| Table 4. Software | `t04_software.py` | `t04_software.csv` | seconds |
| Table 5. Descriptive statistics | `t05_descriptive_statistics.py` | `t05_descriptive_statistics.csv` | < 1 min |
| Table 6. Listings and median price by group | `t06_price_by_group.py` | `t06_price_by_group.csv` | < 1 min |
| Table 7. Test-set performance | `t07_model_performance.py` | `t07_model_performance.csv` | 1–2 min |
| Table 8. Permutation importance | `t08_permutation_importance.py` | `t08_permutation_importance.csv` | a few min |
| Table 9. Elastic Net effects | `t09_elastic_net_effects.py` | `t09_elastic_net_effects.csv` (15 report rows), `t09_all_coefficients.csv` | < 1 min |
| Table 10. Neighborhood demand | `t10_neighbourhood_demand.py` | `t10_neighbourhood_demand.csv` (all 72; report shows top 10) | < 1 min |
| Table 11. Demand by listing type | `t11_listing_type_demand.py` | `t11_listing_type_demand.csv` | < 1 min |
| Fair-price fit (Section 3.5) | `t12_t14_pricing_gap.py` | `t12_fair_price_fit.csv` | about 12 min |
| Table 12. Price-gap shares | `t12_t14_pricing_gap.py` | `t12_gap_shares.csv` | (same run) |
| Table 13. Gap quintiles | `t12_t14_pricing_gap.py` | `t13_gap_quintiles.csv` | (same run) |
| Table 14. Under-pricing candidates | `t12_t14_pricing_gap.py` | `t14_underpricing_candidates.csv` | (same run) |
| Table 15. Error by segment | `t15_segment_errors.py` | `t15_segment_errors.csv` | 1–2 min |
| Table 16. Pooled vs. separate models | `t16_pooled_vs_separate.py` | `t16_pooled_vs_separate.csv` | a few min |

`common.py` holds what the scripts share: the Spark session, the cleaned data (through `code/airbnb_prep.py`,
the same cleaning as the notebooks), the 80/20 split of notebook 02, model evaluation and the neighborhood
demand index.

## Running

From this folder, after the setup in the main `README.md` (Java 17, `pip install -r requirements.txt`,
`listings.csv` in the project root):

```bash
python t06_price_by_group.py
```

Tables 7, 8, 9, 15 and 16 use the tuned models saved by notebook 02 in `models/`. If that folder is missing,
run `code/02_Modeling_PySpark.ipynb` or unzip `models.zip` from the models-v1 release into the project root.

Spark memory comes from `AIRBNB_SPARK_MEMORY` (default 12g). The slow scripts were run with 48g:

```bash
AIRBNB_SPARK_MEMORY=48g python t02_t03_model_tuning.py
```

## Notes

- Medians use Spark's `percentile_approx`, which returns an actual listing value. pandas' `median()` averages
  the two middle values, so a few medians differ by a few dollars if recomputed in pandas.
- The trim bounds ($43.27 and $1,997.43) also come from Spark's approximate quantile; the exact 1%/99% values
  are $43.44 and $2,000.00, which leave the sample size unchanged at 19,018.
