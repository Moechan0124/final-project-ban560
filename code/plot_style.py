"""Matplotlib style shared by the project figures (same palette as 01_EDA_PySpark.ipynb)."""
from pathlib import Path

import matplotlib.pyplot as plt

INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
POS, NEG = "#c62f2f", "#1c5cab"  # diverging poles for signed effects
LIGHT_BLUE = "#9ec5f4"


def apply():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 220, "savefig.bbox": "tight",
        "figure.facecolor": "white", "axes.facecolor": "white",
        "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.titlecolor": INK,
        "axes.labelcolor": INK2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True,
        "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
        "legend.frameon": False, "legend.fontsize": 9,
    })


def save(fig, fig_dir: Path, name: str):
    fig.savefig(fig_dir / f"{name}.png")
    plt.show()
