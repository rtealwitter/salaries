"""Generate the three PNG figures for a fixed, selectable college cohort."""

import argparse
import hashlib
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

from common import ROOT
from figure_layout import audit_text, resolve_label_overlaps
from plot_style import (
    BLUE,
    CMC,
    INK,
    RED,
    college_ticks,
    column_heading,
    figure_heading,
    name,
    row_heading,
    style_money,
)

FIG = ROOT / "figures"

TITLES = {
    "assistant": "Assistant professors",
    "associate": "Associate professors",
    "full": "Full professors",
}
RANKS = list(TITLES)
FIRST_PLOT_YEAR = 2008


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of civilian colleges in main figures, including ties at cutoff (default: 15).",
    )
    args = parser.parse_args()
    data, colleges = select_cohort(
        pd.read_csv(ROOT / "data/processed/combined_long.csv"), args.top_n
    )
    data = data[data.year >= FIRST_PLOT_YEAR].copy()
    if CMC not in set(colleges.college):
        parser.error("The CMC-focused figures require a cohort that includes CMC.")
    year = int(data.loc[data.salary_cost_adjusted.notna(), "year"].max())
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    colleges.to_csv(reports / "figure_cohort.csv", index=False)
    data[data.year.eq(year)][
        [
            "college",
            "unitid",
            "year",
            "academic_rank",
            "salary_nominal",
            "salary_cost_adjusted",
            "salary_nominal_rank",
            "salary_cost_adjusted_rank",
            "salary_rank_improvement",
        ]
    ].to_csv(reports / "figure_salary_ranks.csv", index=False)
    print(cohort_label(data))
    audits = [
        comparison(data, year),
        historical_trends(data),
        ranking_relationship(data, year),
    ]
    (reports / "figure_layout_audit.json").write_text(
        json.dumps(audits, indent=2) + "\n"
    )
    print("Generated three main figures, as PNG.")


def finish(fig, stem, caption):
    fig.text(
        0.045,
        0.25 / fig.get_figheight(),
        caption,
        fontsize=12,
        color="#596976",
        va="bottom",
    )
    fig.set_dpi(240)
    audit = audit_text(fig, stem)
    fig.savefig(
        FIG / f"{stem}.png",
        dpi=240,
        metadata={"Creator": "Faculty salaries reproducible pipeline"},
    )
    audit["png_sha256"] = hashlib.sha256((FIG / f"{stem}.png").read_bytes()).hexdigest()
    plt.close(fig)
    return audit


def select_cohort(data, top_n):
    """Select civilian institutions by publisher rank, keeping cutoff ties."""
    colleges = (
        data[["college", "unitid", "usnews_rank_2027"]]
        .drop_duplicates()
        .sort_values(["usnews_rank_2027", "college"])
    )
    if not 1 <= top_n <= len(colleges):
        raise ValueError(f"--top-n must be between 1 and {len(colleges)}")
    cutoff = colleges.iloc[top_n - 1].usnews_rank_2027
    colleges = colleges[colleges.usnews_rank_2027 <= cutoff].copy()
    selected = data[data.unitid.isin(colleges.unitid)].copy()
    for measure in ["nominal", "cost_adjusted"]:
        selected[f"salary_{measure}_rank"] = selected.groupby(
            ["year", "academic_rank"]
        )[f"salary_{measure}"].rank(ascending=False, method="min")
    selected["salary_rank_improvement"] = (
        selected.salary_nominal_rank - selected.salary_cost_adjusted_rank
    )
    return selected, colleges


def cohort_label(data):
    return f"Top {data.unitid.nunique()} civilian colleges · fixed 2027 cohort"


def nominal_order(data, rank, year):
    return (
        data[data.year.eq(year) & data.academic_rank.eq(rank)]
        .sort_values(
            ["salary_nominal", "college"], ascending=[False, True], na_position="last"
        )
        .college.tolist()
    )


def ordinal(value):
    """Format a salary rank for the CMC annotations."""
    if pd.isna(value):
        return "unavailable"
    number = int(value)
    suffix = (
        "th"
        if 10 <= number % 100 <= 20
        else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    )
    return f"{number}{suffix}"


def cmc_rank_label(cmc):
    return f"CMC salary rank: {ordinal(cmc.salary_nominal_rank)} → {ordinal(cmc.salary_cost_adjusted_rank)}"


def comparison(data, year):
    latest = data[data.year == year]
    height = max(12, data.unitid.nunique() * 0.4 + 5)
    fig, axes = plt.subplots(1, 3, figsize=(24, height))
    fig.subplots_adjust(
        left=0.11, right=0.98, bottom=1.35 / height, top=1 - 2.65 / height, wspace=0.65
    )
    for ax, rank in zip(axes, RANKS):
        order = nominal_order(data, rank, year)
        rank_data = (
            latest[latest.academic_rank == rank].set_index("college").reindex(order)
        )
        for y, (college, row) in enumerate(rank_data.iterrows()):
            color = RED if college == CMC else BLUE
            if college == CMC:
                ax.axhspan(y - 0.45, y + 0.45, color=RED, alpha=0.06)
            ax.plot(
                [row.salary_nominal, row.salary_cost_adjusted],
                [y, y],
                color=color,
                alpha=0.7,
                lw=2.2,
            )
            ax.scatter(
                row.salary_nominal,
                y,
                facecolor="white",
                edgecolor=color,
                s=75,
                linewidth=1.5,
                zorder=3,
            )
            ax.scatter(row.salary_cost_adjusted, y, color=color, s=75, zorder=3)
        column_heading(ax, TITLES[rank], cmc_rank_label(rank_data.loc[CMC]))
        college_ticks(ax, order)
        ax.set_ylim(len(order) - 0.4, -0.7)
        style_money(ax, axis="x")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        minimum = rank_data[["salary_nominal", "salary_cost_adjusted"]].min().min()
        maximum = rank_data[["salary_nominal", "salary_cost_adjusted"]].max().max()
        ax.set_xlim(minimum * 0.94, maximum * 1.05)
    fig.supxlabel(f"Annual salary · {year} dollars", y=0.75 / height, fontsize=17)
    handles = [
        plt.Line2D(
            [],
            [],
            marker="o",
            ls="",
            markerfacecolor="white",
            markeredgecolor=BLUE,
            label="Nominal salary",
            markersize=9,
        ),
        plt.Line2D(
            [],
            [],
            marker="o",
            ls="",
            color=BLUE,
            markersize=9,
            label="Regional purchasing power",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.045, 1 - 1.15 / height),
        ncol=2,
        frameon=False,
        borderaxespad=0,
    )
    figure_heading(
        fig,
        "Faculty salaries and purchasing power",
        f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}",
    )
    return finish(
        fig,
        "current_salary_comparison",
        f"CMC salary ranks: nominal → cost-adjusted among {data.unitid.nunique()} colleges; 1st is highest. Rows sorted by nominal salary.\nNine-month-equivalent averages. Sources: IPEDS; BEA RPP; U.S. News via College Kickstart.",
    )


def historical_trends(data):
    data = data[data.year >= FIRST_PLOT_YEAR]
    measures = [
        ("salary_nominal", "Nominal salary · dollars of each year"),
        ("salary_real_2024", "Real salary · 2024 dollars (national inflation only)"),
        (
            "salary_real_cost_adjusted_2024",
            "Regional purchasing power · 2024 dollars (regional prices + national inflation)",
        ),
    ]
    years = range(FIRST_PLOT_YEAR, int(data.year.max()) + 1)
    height = 18
    fig, axes = plt.subplots(3, 3, figsize=(24, height), sharex=True)
    fig.subplots_adjust(
        left=0.07,
        right=0.98,
        bottom=1.35 / height,
        top=1 - 2.80 / height,
        hspace=0.38,
        wspace=0.23,
    )
    for column, rank in enumerate(RANKS):
        column_heading(axes[0, column], TITLES[rank])
        rank_data = data[data.academic_rank == rank]
        upper_limit = rank_data[[measure for measure, _ in measures]].max().max() * 1.08
        for row, (measure, _) in enumerate(measures):
            ax = axes[row, column]
            draw_history_panel(ax, rank_data, measure, years)
            ax.set_ylim(0, upper_limit)
            ax.set_xlim(FIRST_PLOT_YEAR - 0.5, data.year.max() + 0.5)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.set_xticks(list(range(FIRST_PLOT_YEAR, int(data.year.max()) + 1, 4)))
    for row, (_, title) in enumerate(measures):
        row_heading(axes[row, 0], title)
    fig.supxlabel("Academic year beginning in", y=0.75 / height, fontsize=17)
    figure_heading(
        fig,
        "Faculty salaries over time",
        f"{FIRST_PLOT_YEAR}–{int(data.year.max())} · {cohort_label(data)}",
    )
    handles = [
        plt.Line2D([], [], color=RED, lw=2.5, label="CMC"),
        plt.Line2D([], [], color=BLUE, lw=1.6, label="Cohort median"),
        Rectangle((0, 0), 1, 1, color="#dce7ed", label="Cohort 10th–90th percentile"),
    ]
    fig.legend(
        handles=handles,
        bbox_to_anchor=(0.045, 1 - 1.15 / height),
        loc="upper left",
        ncol=3,
        frameon=False,
        borderaxespad=0,
    )
    return finish(
        fig,
        "historical_salary_trends",
        "× 2019 CMC reporting break; not a verified pay cut. Dotted lines: 2012/2016 conversion changes.\nNine-month-equivalent averages. Sources: IPEDS; BEA RPP; PCE via FRED; U.S. News via College Kickstart.",
    )


def draw_history_panel(ax, rank_data, measure, years):
    """Compare CMC with the cohort distribution, separating its 2019 reporting break."""
    quantiles = (
        rank_data.groupby("year")[measure]
        .quantile([0.1, 0.5, 0.9])
        .unstack()
        .reindex(years)
    )
    cmc = rank_data[rank_data.college == CMC].set_index("year").reindex(years)
    ax.fill_between(quantiles.index, quantiles[0.1], quantiles[0.9], color="#dce7ed")
    ax.plot(quantiles.index, quantiles[0.5], color=BLUE, lw=2.5)
    line = cmc[measure].copy()
    line.loc[2019] = np.nan
    ax.plot(cmc.index, line, color=RED, lw=3.3)
    ax.scatter(cmc.index, line, color=RED, s=28, zorder=3)
    ax.scatter(
        [2019],
        [cmc.loc[2019, measure]],
        marker="x",
        color=RED,
        s=100,
        linewidths=2.5,
        zorder=4,
    )
    for year in [2012, 2016]:
        ax.axvline(year, color="#8e9aa2", lw=0.8, ls=":")
    style_money(ax)


def ranking_relationship(data, year):
    measures = ["salary_nominal", "salary_cost_adjusted"]
    height = 16
    fig, axes = plt.subplots(2, 3, figsize=(24, height))
    fig.subplots_adjust(
        left=0.07,
        right=0.98,
        bottom=1.35 / height,
        top=1 - 3.15 / height,
        hspace=0.30,
        wspace=0.23,
    )
    for column, rank in enumerate(RANKS):
        rank_data = data[data.year.eq(year) & data.academic_rank.eq(rank)]
        cmc = rank_data[rank_data.college == CMC].iloc[0]
        column_heading(axes[0, column], TITLES[rank], cmc_rank_label(cmc))
        low = rank_data[measures].min().min() - 10000
        high = rank_data[measures].max().max() + 12000
        for row, measure in enumerate(measures):
            ax = axes[row, column]
            ax.scatter(
                rank_data.usnews_rank_2027,
                rank_data[measure],
                c=[RED if college == CMC else BLUE for college in rank_data.college],
                s=[110 if college == CMC else 65 for college in rank_data.college],
                edgecolor="white",
                lw=0.5,
                zorder=3,
            )
            ax.set(xlim=(-1, data.usnews_rank_2027.max() + 4), ylim=(low, high))
            style_money(ax)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            texts = [
                ax.text(
                    record.usnews_rank_2027,
                    record[measure],
                    name(record.college),
                    fontsize=15,
                    weight="bold" if record.college == CMC else "normal",
                    color=RED if record.college == CMC else INK,
                )
                for _, record in rank_data.iterrows()
            ]
            resolve_label_overlaps(
                ax, texts, list(zip(rank_data.usnews_rank_2027, rank_data[measure]))
            )
    row_titles = [
        f"Nominal salary · {year} dollars",
        f"Regional purchasing power · {year} dollars (regional prices)",
    ]
    for row, title in enumerate(row_titles):
        row_heading(axes[row, 0], title)
    fig.supxlabel(
        "U.S. News rank, 2027 (lower is better)", y=0.75 / height, fontsize=17
    )
    figure_heading(
        fig,
        "College rank and faculty salaries",
        f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}",
    )
    return finish(
        fig,
        "college_rank_and_salary",
        f"CMC salary ranks: nominal → cost-adjusted among {data.unitid.nunique()} colleges; 1st is highest.\nNine-month-equivalent averages. Gray lines connect labels to points. Sources: IPEDS; BEA RPP; U.S. News via College Kickstart.",
    )


if __name__ == "__main__":
    main()
