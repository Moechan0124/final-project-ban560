"""Report Table 9: Elastic Net effects on price (percentage change per unit, holding other features fixed).

Writes the 15 rows shown in the report and, separately, every coefficient of the saved model.
"""
import numpy as np
import pandas as pd
from pyspark.ml.stat import Summarizer
from pyspark.sql import functions as F

from common import CAT, load_model, prep, save, spark, train_test

spark = spark("Report-T09")
train, _ = train_test(spark)
model = load_model("elastic_net")
en = model.stages[-1]

assembled = model.transform(train)
meta = assembled.schema["features"].metadata["ml_attr"]["attrs"]
names = [a["name"] for a in sorted((a for kind in meta.values() for a in kind), key=lambda a: a["idx"])]

def label(name):
    for c in CAT:
        if name.startswith(f"{c}_ohe_"):
            return f"{c.replace('_grp', '').replace('_', ' ')}: {name[len(c) + 5:]}"
    n = name.removesuffix("_imp")
    if n in prep.AMENITY_FLAGS:
        return f"amenity: {prep.AMENITY_FLAGS[n].lower()}"
    n = n.replace("_ltm", " (last 12 mo)").replace("calculated_", "")
    return ("log " + n[4:] if n.startswith("log_") else n).replace("_", " ")

sd = assembled.select(Summarizer.std(F.col("features")).alias("sd")).first().sd.toArray()
coef = pd.DataFrame({"feature": [label(n) for n in names], "coef": en.coefficients.toArray(), "sd": sd})
coef["pct_effect_per_unit"] = np.expm1(coef.coef) * 100
coef["std_coef"] = coef.coef * coef.sd
coef = coef.reindex(coef.std_coef.abs().sort_values(ascending=False).index)
save(coef, "t09_all_coefficients")

REPORT_ROWS = {  # label in the model -> (row in the report, compared with)
    "stay type: 30+ nights": ("30+ night minimum stay", "Under-30-night listings"),
    "room type: Entire home/apt": ("Entire home/apt", "Shared room"),
    "room type: Private room": ("Private room", "Shared room"),
    "license status: Not reported": ("License not reported", "Registered listings"),
    "license status: Exempt": ("License exempt", "Registered listings"),
    "shared bath": ("Shared bath", "Private bath"),
    "bedrooms": ("Each extra bedroom", "Per bedroom"),
    "accommodates": ("Each extra guest", "Per guest"),
    "km to midtown": ("Distance to Times Square", "Per km"),
    "amenity: gym": ("Gym", "Listings without a gym"),
    "amenity: building staff": ("Building staff", "Listings without staff"),
    "amenity: dishwasher": ("Dishwasher", "Listings without one"),
    "amenity: elevator": ("Elevator", "Listings without one"),
    "review scores rating": ("Overall rating", "Per rating point (1-5)"),
    "is superhost": ("Superhost", "Non-superhosts"),
}
by_label = coef.set_index("feature")
table = pd.DataFrame([{"feature": row, "pct_change_in_price": by_label.loc[k, "pct_effect_per_unit"], "compared_with": ref}
                      for k, (row, ref) in REPORT_ROWS.items()])
save(table, "t09_elastic_net_effects")
spark.stop()
