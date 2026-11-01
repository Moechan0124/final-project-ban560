# Analysis Corrections Log

Errors found during the project, how they were found, and what changed. Earlier results are kept in
`outputs/archive/` so each version can be compared.

## 1. Demand index included unpriced listings

- **First version:** the neighborhood demand index used all listings, priced or not
  (85 neighborhoods; `outputs/archive/neighbourhood_demand_v1_all_listings.csv`).
- **Problem:** 66.7% of the 10,512 unpriced listings have zero open nights in the next 365 days, against
  0% of priced listings. Their low availability reflects blocked calendars, not bookings, so the index
  overstated demand wherever many calendars were closed.
- **Found by:** team review of the Project Introduction.
- **Fix:** use priced listings only (72 neighborhoods; `outputs/neighbourhood_demand.csv`).
- **Effect:** Gramercy rose from 8th to 2nd and Woodhaven from 22nd to 4th. Carroll Gardens and Sunset Park
  entered the top 10; Downtown Brooklyn, Prospect Heights and South Ozone Park left it.

## 2. Pricing gap used a mean-corrected fair price

- **First version:** fair price used the smearing correction, which targets the mean price
  (`outputs/archive/pricing_gap_summary_v1_smeared.csv`).
- **Problem:** price is right-skewed, so a mean-based fair price sits about 7% above a typical price.
  That made 31% of listings look more than 20% under-priced and only 17% over-priced. The imbalance came
  from the method, not the market.
- **Found by:** checking the first full run; the middle quintile's median gap was −8% to −10%, not near zero.
- **Fix:** use exp(log prediction), a median-type estimate (`outputs/pricing_gap_summary.csv`).
- **Effect:** about 22% of listings now fall on each side. The location-premium threshold was also set to
  −5% so that differences within model noise are not flagged, which cut under-pricing candidates from 10 to 4.

The smearing correction is still used in notebook 02 for dollar accuracy metrics, where the mean is the
correct target.
