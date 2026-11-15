"""Report Table 4: software versions of the running environment."""
import platform
import subprocess

import matplotlib
import pandas as pd

from common import save, spark

spark = spark("Report-T04")
java = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
table = pd.DataFrame([
    {"tool": "Apache Spark / PySpark", "version": spark.version},
    {"tool": "Python", "version": platform.python_version()},
    {"tool": "Java", "version": java},
    {"tool": "pandas", "version": pd.__version__},
    {"tool": "Matplotlib", "version": matplotlib.__version__},
])
save(table, "t04_software")
spark.stop()
