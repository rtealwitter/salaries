"""Shared colors, college labels, and dollar axes for the four figures."""

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

RED = "#a52b45"
BLUE = "#246b88"
INK = "#23313d"
CMC = "Claremont McKenna College"
NAMES = {
    "Claremont McKenna College": "CMC",
    "Washington and Lee University": "Washington & Lee",
    "College of the Holy Cross": "Holy Cross",
    "University of Richmond": "Richmond",
}
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 16,
        "xtick.labelsize": 14,
        "ytick.labelsize": 15,
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


def college_ticks(ax, colleges):
    """Label every college, with CMC as the sole visual highlight."""
    ax.set_yticks(range(len(colleges)), [name(college) for college in colleges])
    for label, college in zip(ax.get_yticklabels(), colleges):
        if college == CMC:
            label.set_color(RED)
            label.set_weight("bold")


def figure_heading(fig, title, subtitle, x=0.03, title_y=0.98, subtitle_y=0.92):
    fig.suptitle(title, x=x, y=title_y, ha="left", fontsize=30, weight="bold")
    fig.text(x, subtitle_y, subtitle, fontsize=17)
