"""Report Table 1: feature families and the variables in each (44 model inputs)."""
import pandas as pd

from common import CAT, GROUPS, NUM, save

rows = [{"family": family, "variable": v, "type": "categorical" if v in CAT else "numeric"}
        for family, cols in GROUPS.items() for v in cols]
table = pd.DataFrame(rows)
assert sorted(table.variable) == sorted(CAT + NUM)
print(f"{len(table)} inputs: {sum(table.type == 'categorical')} categorical, {sum(table.type == 'numeric')} numeric")
save(table, "t01_feature_families")
