"""Shared colors, college labels, and dollar axes for the three figures."""

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


def style_money(ax, axis="y"):
    money_axis = ax.xaxis if axis == "x" else ax.yaxis
    money_axis.set_major_formatter(FuncFormatter(lambda x, p: f"${x / 1000:,.0f}k"))
    ax.grid(axis=axis, color="#edf0f2")
    ax.set_axisbelow(True)


def college_ticks(ax, colleges):
    """Label every college, with CMC as the sole visual highlight."""
    ax.set_yticks(range(len(colleges)), [name(college) for college in colleges])
    for label, college in zip(ax.get_yticklabels(), colleges):
        if college == CMC:
            label.set_color(RED)
            label.set_weight("bold")


def figure_heading(fig, title, subtitle):
    """Use the same physical header spacing, even when figure heights differ."""
    height = fig.get_figheight()
    fig.suptitle(
        title,
        x=0.045,
        y=1 - 0.25 / height,
        ha="left",
        va="top",
        fontsize=30,
        weight="bold",
    )
    fig.text(0.045, 1 - 0.80 / height, subtitle, fontsize=17, va="top")


def column_heading(ax, title, rank_label=None):
    fig = ax.figure
    height = fig.get_figheight()
    left = ax.get_position().x0
    fig.text(left, 1 - 1.80 / height, title, fontsize=22, weight="bold", va="top")
    if rank_label:
        fig.text(
            left,
            1 - 2.20 / height,
            rank_label,
            fontsize=16,
            color=RED,
            weight="bold",
            va="top",
        )


def row_heading(ax, title):
    fig = ax.figure
    position = ax.get_position()
    fig.text(
        position.x0,
        position.y1 + 0.16 / fig.get_figheight(),
        title,
        fontsize=20,
        weight="bold",
        va="bottom",
    )
