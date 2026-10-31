"""Generate the four PNG figures for a fixed, selectable college cohort."""

import argparse
import hashlib
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adjustText import adjust_text
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

from common import ROOT
from figure_layout import audit_text, resolve_label_overlaps
from plot_style import BLUE, FOCUS, GRAY, INK, RED, name, style_money

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
    if FOCUS[0] not in set(colleges.college):
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
        relative_trends(data),
        ranking_relationship(data, year),
    ]
    (reports / "figure_layout_audit.json").write_text(
        json.dumps(audits, indent=2) + "\n"
    )
    print("Generated four main figures, as PNG.")


def finish(fig, stem, caption):
    fig.text(0.03, 0.025, caption, fontsize=12, color="#596976", va="bottom")
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


def comparison(data, year):
    latest = data[data.year == year]
    fig, axes = plt.subplots(
        1, 3, figsize=(24, max(11, data.unitid.nunique() * 0.4 + 4))
    )
    fig.subplots_adjust(left=0.11, right=0.98, bottom=0.17, top=0.73, wspace=0.65)
    for ax, rank in zip(axes, RANKS):
        order = nominal_order(data, rank, year)
        rank_data = (
            latest[latest.academic_rank == rank].set_index("college").reindex(order)
        )
        for y, (n, r) in enumerate(rank_data.iterrows()):
            col = RED if n == FOCUS[0] else BLUE
            if n == FOCUS[0]:
                ax.axhspan(y - 0.45, y + 0.45, color=RED, alpha=0.06)
            ax.plot(
                [r.salary_nominal, r.salary_cost_adjusted],
                [y, y],
                color=col,
                alpha=0.7,
                lw=2.2,
            )
            ax.scatter(
                r.salary_nominal,
                y,
                facecolor="white",
                edgecolor=col,
                s=75,
                linewidth=1.5,
                zorder=3,
            )
            ax.scatter(r.salary_cost_adjusted, y, color=col, s=75, zorder=3)
        ax.set_title(TITLES[rank], loc="left", fontsize=22, pad=42)
        cmc = rank_data.loc[FOCUS[0]]
        ax.text(
            0,
            1.02,
            f"CMC salary rank: {ordinal(cmc.salary_nominal_rank)} → {ordinal(cmc.salary_cost_adjusted_rank)}",
            transform=ax.transAxes,
            color=RED,
            fontsize=16,
            weight="bold",
        )
        ax.set_yticks(range(len(order)), [name(n) for n in order])
        ax.set_ylim(len(order) - 0.4, -0.7)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x / 1000:,.0f}k"))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.grid(axis="x", color="#edf0f2")
        ax.set_axisbelow(True)
        lo = rank_data[["salary_nominal", "salary_cost_adjusted"]].min().min()
        hi = rank_data[["salary_nominal", "salary_cost_adjusted"]].max().max()
        ax.set_xlim(lo * 0.94, hi * 1.05)
        for t, n in zip(ax.get_yticklabels(), order):
            if n == FOCUS[0]:
                t.set_color(RED)
                t.set_weight("bold")
    axes[1].set_xlabel("Annual salary (USD)", labelpad=10)
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
            label="Cost-adjusted salary",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.105, 0.875),
        ncol=2,
        frameon=False,
    )
    fig.suptitle(
        "Faculty salaries and purchasing power",
        x=0.03,
        y=0.98,
        ha="left",
        fontsize=30,
        weight="bold",
    )
    fig.text(
        0.03, 0.92, f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}", fontsize=17
    )
    return finish(
        fig,
        "current_salary_comparison",
        f"CMC ranks: nominal → cost-adjusted within {data.unitid.nunique()} colleges; 1st is highest. Rows sorted by nominal salary.\nNine-month-equivalent averages; {year} prices. Sources: IPEDS; BEA RPP; U.S. News via College Kickstart.",
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
    fig, axes = plt.subplots(3, 3, figsize=(20, 17), sharex=True)
    fig.subplots_adjust(
        left=0.075, right=0.98, bottom=0.12, top=0.82, hspace=0.40, wspace=0.23
    )
    for j, rank in enumerate(RANKS):
        rank_data = data[data.academic_rank == rank]
        upper_limit = rank_data[[column for column, _ in measures]].max().max() * 1.08
        for i, (col, _) in enumerate(measures):
            ax = axes[i, j]
            quantiles = (
                rank_data.groupby("year")[col]
                .quantile([0.1, 0.5, 0.9])
                .unstack()
                .reindex(years)
            )
            cmc = (
                rank_data[rank_data.college == FOCUS[0]]
                .set_index("year")
                .reindex(years)
            )
            ax.fill_between(
                quantiles.index, quantiles[0.1], quantiles[0.9], color="#dce7ed"
            )
            ax.plot(quantiles.index, quantiles[0.5], color=BLUE, lw=2.5)
            line = cmc[col].copy()
            line.loc[2019] = np.nan
            ax.plot(cmc.index, line, color=RED, lw=3.3)
            ax.scatter(cmc.index, line, color=RED, s=28, zorder=3)
            ax.scatter(
                [2019],
                [cmc.loc[2019, col]],
                marker="x",
                color=RED,
                s=100,
                linewidths=2.5,
                zorder=4,
            )
            for year in [2012, 2016]:
                ax.axvline(year, color="#8e9aa2", lw=0.8, ls=":")
            style_money(ax)
            if i == 0:
                ax.set_title(TITLES[rank], loc="left", fontsize=21, pad=12)
            ax.set_ylim(0, upper_limit)
            ax.set_xlim(FIRST_PLOT_YEAR - 0.5, data.year.max() + 0.5)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.set_xticks(list(range(FIRST_PLOT_YEAR, int(data.year.max()) + 1, 4)))
    for i, (_, title) in enumerate(measures):
        y = 0.88 if i == 0 else axes[i, 0].get_position().y1 + 0.018
        fig.text(0.075, y, title, fontsize=20, weight="bold")
    fig.supxlabel("Academic year beginning in", y=0.075, fontsize=17)
    fig.suptitle(
        f"CMC salaries, {FIRST_PLOT_YEAR}–{int(data.year.max())}",
        x=0.075,
        y=0.99,
        ha="left",
        fontsize=30,
        weight="bold",
    )
    fig.text(0.075, 0.95, cohort_label(data), fontsize=17)
    handles = [
        plt.Line2D([], [], color=RED, lw=2.5, label="CMC"),
        plt.Line2D([], [], color=BLUE, lw=1.6, label="Cohort median"),
        Rectangle((0, 0), 1, 1, color="#dce7ed", label="Cohort 10th–90th percentile"),
    ]
    fig.legend(
        handles=handles,
        bbox_to_anchor=(0.065, 0.935),
        loc="upper left",
        ncol=3,
        frameon=False,
    )
    return finish(
        fig,
        "historical_salary_trends",
        "× 2019 CMC reporting break; not a verified pay cut. Dotted lines: 2012/2016 conversion changes.\nNine-month-equivalent averages. Sources: NCES IPEDS; BEA RPP; PCE via FRED.",
    )


def relative_trends(data):
    rank_data = data[data.year >= FIRST_PLOT_YEAR].copy()
    rank_data["premium"] = 100 * (
        rank_data.salary_cost_adjusted
        / rank_data.groupby(["academic_rank", "year"]).salary_cost_adjusted.transform(
            "median"
        )
        - 1
    )
    latest = int(rank_data.year.max())
    years = sorted(rank_data.year.unique())
    fig, axes = plt.subplots(
        1, 3, figsize=(24, max(11, data.unitid.nunique() * 0.4 + 3))
    )
    fig.subplots_adjust(left=0.11, right=0.98, bottom=0.25, top=0.82, wspace=0.65)
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#e7e7e7")
    for ax, rank in zip(axes, RANKS):
        order = nominal_order(data, rank, latest)
        p = (
            rank_data[rank_data.academic_rank == rank]
            .pivot(index="college", columns="year", values="premium")
            .reindex(index=order, columns=years)
        )
        im = ax.imshow(
            p, aspect="auto", cmap=cmap, vmin=-30, vmax=30, interpolation="nearest"
        )
        ax.set_title(TITLES[rank], loc="left", fontsize=22, pad=15)
        ticks = [k for k, y in enumerate(years) if y in [2008, 2012, 2016, 2020, 2024]]
        ax.set_xticks(ticks, [years[k] for k in ticks])
        ax.set_yticks(range(len(order)), [name(n) for n in order])
        ax.tick_params(axis="both", length=0, pad=8)
        i = order.index(FOCUS[0])
        ax.text(
            years.index(2019),
            i,
            "×",
            ha="center",
            va="center",
            fontsize=21,
            color="black",
        )
        ax.add_patch(
            Rectangle((-0.5, i - 0.5), len(years), 1, fill=False, edgecolor=RED, lw=1.8)
        )
        for spine in ax.spines.values():
            spine.set_visible(False)
        for t, n in zip(ax.get_yticklabels(), order):
            if n == FOCUS[0]:
                t.set_color(RED)
                t.set_weight("bold")
    axes[1].set_xlabel("Academic year beginning in", labelpad=10)
    cax = fig.add_axes([0.36, 0.13, 0.4, 0.022])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend="both")
    cb.set_label("Cost-adjusted salary: % above / below cohort median", labelpad=8)
    cb.set_ticks([-30, -15, 0, 15, 30])
    fig.suptitle(
        f"Relative purchasing power, {years[0]}–{latest}",
        x=0.03,
        y=0.98,
        ha="left",
        fontsize=30,
        weight="bold",
    )
    fig.text(0.03, 0.92, cohort_label(data), fontsize=17)
    return finish(
        fig,
        "relative_purchasing_power_trends",
        f"× 2019 CMC reporting break. Gray: unavailable. Rows sorted by {latest} nominal salary.\nSources: IPEDS; BEA RPP; U.S. News via College Kickstart.",
    )


def ranking_relationship(data, year):
    cols = ["salary_nominal", "salary_cost_adjusted"]
    fig, axes = plt.subplots(2, 3, figsize=(22, 15))
    fig.subplots_adjust(
        left=0.07, right=0.98, bottom=0.12, top=0.86, hspace=0.20, wspace=0.23
    )
    for j, rank in enumerate(RANKS):
        rank_data = data[data.year.eq(year) & data.academic_rank.eq(rank)]
        low = rank_data[cols].min().min() - 10000
        high = rank_data[cols].max().max() + 12000
        for i, col in enumerate(cols):
            ax = axes[i, j]
            ax.scatter(
                rank_data.usnews_rank_2027,
                rank_data[col],
                c=[
                    RED if n == FOCUS[0] else BLUE if n in FOCUS else GRAY
                    for n in rank_data.college
                ],
                s=[110 if n in FOCUS else 65 for n in rank_data.college],
                edgecolor="white",
                lw=0.5,
                zorder=3,
            )
            ax.set(xlim=(-1, data.usnews_rank_2027.max() + 4), ylim=(low, high))
            style_money(ax)
            if i == 0:
                ax.set_title(TITLES[rank], loc="left", fontsize=22, pad=14)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            texts = [
                ax.text(
                    r.usnews_rank_2027,
                    r[col],
                    name(r.college),
                    fontsize=15,
                    weight="bold" if r.college in FOCUS else "normal",
                    color=RED if r.college == FOCUS[0] else INK,
                )
                for _, r in rank_data.iterrows()
            ]
            np.random.seed(42)
            adjust_text(
                texts, ax=ax, expand=(1.15, 1.3), force_text=(0.4, 0.7), iter_lim=1200
            )
            resolve_label_overlaps(
                ax, texts, list(zip(rank_data.usnews_rank_2027, rank_data[col]))
            )
            if j == 0:
                ax.set_ylabel(
                    "Nominal salary · dollars"
                    if i == 0
                    else "Cost-adjusted salary · dollars",
                    labelpad=12,
                )
    fig.supxlabel("U.S. News rank, 2027 (lower is better)", y=0.07, fontsize=17)
    fig.suptitle(
        "College rank and faculty salaries",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=30,
        weight="bold",
    )
    fig.text(
        0.06, 0.93, f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}", fontsize=17
    )
    return finish(
        fig,
        "college_rank_and_salary",
        f"Nine-month-equivalent averages; {year} prices. Gray lines connect labels to points.\nSources: IPEDS; BEA RPP; U.S. News via College Kickstart.",
    )


if __name__ == "__main__":
    main()
