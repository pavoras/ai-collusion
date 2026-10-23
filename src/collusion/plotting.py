"""Shared figure style for the report: validated categorical slots, thin marks, recessive axes."""

import matplotlib as mpl

# First three slots of the validated reference palette (light mode); they pass the all-pairs CVD checks.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TEXT, TEXT_MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.edgecolor": TEXT_MUTED,
        "axes.labelcolor": TEXT,
        "axes.titlesize": 9,
        "axes.titleweight": "semibold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "lines.linewidth": 1.6,
        "lines.markersize": 4,
        "legend.frameon": False,
    })
