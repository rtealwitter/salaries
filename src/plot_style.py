"""Shared colors, college labels, and dollar axes for the four figures."""

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

RED = "#a52b45"
BLUE = "#246b88"
GRAY = "#b7c1c8"
INK = "#23313d"
FOCUS = [
    "Claremont McKenna College",
    "Harvey Mudd College",
    "Pomona College",
    "Williams College",
    "Amherst College",
    "Swarthmore College",
]
NAMES = {
    "Claremont McKenna College": "CMC",
    "Washington and Lee University": "Washington & Lee",
    "College of the Holy Cross": "Holy Cross",
    "University of Richmond": "Richmond",
}
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": INK,
        "text.color": INK,
        "axes.edgecolor": "#d2d9dd",
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.titleweight": "bold",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def name(s):
    return NAMES.get(s, s.replace(" College", "").replace(" University", ""))


def style_money(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x / 1000:,.0f}k"))
    ax.grid(axis="y", color="#edf0f2")
    ax.set_axisbelow(True)
