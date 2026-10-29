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
from figure_layout import audit_text
from plot_style import BLUE, FOCUS, GRAY, INK, RED, name, style_money

FIG = ROOT / "figures"

TITLES = {
    "assistant": "Assistant professors",
    "associate": "Associate professors",
    "full": "Full professors",
}
RANKS = list(TITLES)
LAYOUT_AUDITS = []


def finish(fig, stem, caption):
    fig.text(0.03, 0.025, caption, fontsize=10, color="#596976", va="bottom")
    fig.set_dpi(240)
    LAYOUT_AUDITS.append(audit_text(fig, stem))
    fig.savefig(
        FIG / f"{stem}.png",
        dpi=240,
        metadata={"Creator": "Faculty salaries reproducible pipeline"},
    )
    LAYOUT_AUDITS[-1]["png_sha256"] = hashlib.sha256(
        (FIG / f"{stem}.png").read_bytes()
    ).hexdigest()
    plt.close(fig)


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


def resolve_label_overlaps(ax, texts, targets):
    """Finish automatic layout with deterministic pixel-space separation and audit."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    initial = {id(t): ax.transData.transform(t.get_position())[1] for t in texts}
    for iteration in range(600):
        overlaps = 0
        for j, a in enumerate(texts):
            for b in texts[j + 1 :]:
                aa = a.get_window_extent(renderer).expanded(1.035, 1.12)
                bb = b.get_window_extent(renderer).expanded(1.035, 1.12)
                if not aa.overlaps(bb):
                    continue
                overlaps += 1
                lower, upper = (a, b) if initial[id(a)] <= initial[id(b)] else (b, a)
                lb = lower.get_window_extent(renderer).expanded(1.035, 1.12)
                ub = upper.get_window_extent(renderer).expanded(1.035, 1.12)
                shift = (lb.y1 - ub.y0 + 1) / 2
                for t, delta in [(lower, -shift), (upper, shift)]:
                    pos = ax.transData.transform(t.get_position())
                    pos[1] += delta
                    pos[1] = np.clip(pos[1], ax.bbox.y0 + 12, ax.bbox.y1 - 12)
                    t.set_position(ax.transData.inverted().transform(pos))
        if not overlaps:
            break
    remaining = sum(
        a.get_window_extent(renderer).overlaps(b.get_window_extent(renderer))
        for j, a in enumerate(texts)
        for b in texts[j + 1 :]
    )
    if remaining:
        raise ValueError(
            f"{remaining} unresolved text overlaps in {ax.get_title(loc='left')}"
        )
    for t, target in zip(texts, targets):
        distance = np.linalg.norm(
            ax.transData.transform(t.get_position()) - ax.transData.transform(target)
        )
        if distance > 12:
            ax.annotate(
                "",
                xy=target,
                xytext=t.get_position(),
                arrowprops=dict(arrowstyle="-", color="#9ba8b1", lw=0.6),
                zorder=1,
            )
    print(
        f"Label audit: {ax.get_title(loc='left')}: {len(texts)} labels, {remaining} overlaps"
    )


def comparison(data, year):
    latest = data[data.year == year]
    fig, axes = plt.subplots(
        1, 3, figsize=(25, max(9, data.unitid.nunique() * 0.35 + 3))
    )
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.17, top=0.76, wspace=0.65)
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
                lw=1.4,
            )
            ax.scatter(
                r.salary_nominal, y, facecolor="white", edgecolor=col, s=40, zorder=3
            )
            ax.scatter(r.salary_cost_adjusted, y, color=col, s=40, zorder=3)
        ax.set_title(TITLES[rank], loc="left", fontsize=15, pad=12)
        ax.set_yticks(range(len(order)), [name(n) for n in order])
        ax.set_ylim(len(order) - 0.4, -0.7)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x / 1000:,.0f}k"))
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
            label="Nominal",
        ),
        plt.Line2D([], [], marker="o", ls="", color=BLUE, label="Cost-adjusted"),
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.085, 0.865),
        ncol=2,
        frameon=False,
    )
    fig.suptitle(
        "Faculty salaries and purchasing power",
        x=0.03,
        y=0.98,
        ha="left",
        fontsize=23,
        weight="bold",
    )
    fig.text(
        0.03, 0.91, f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}", fontsize=13
    )
    finish(
        fig,
        "current_salary_comparison",
        f"Each panel sorted by nominal salary. Nine-month-equivalent averages; regional adjustment uses {year} prices.\nSources: NCES IPEDS; BEA RPP; U.S. News via College Kickstart. Methods and limitations: README.",
    )


def long_run(data):
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.subplots_adjust(
        left=0.075, right=0.98, bottom=0.18, top=0.85, hspace=0.36, wspace=0.20
    )
    for j, rank in enumerate(RANKS):
        rank_data = data[data.academic_rank == rank]
        for i, col in enumerate(["salary_nominal", "salary_real_cost_adjusted_2024"]):
            years = range(
                int(data.year.min()) if i == 0 else 2008, int(data.year.max()) + 1
            )
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
            ax.plot(quantiles.index, quantiles[0.5], color=BLUE, lw=1.6)
            line = cmc[col].copy()
            line.loc[2019] = np.nan
            ax.plot(cmc.index, line, color=RED, lw=2.3)
            ax.scatter(cmc.index, line, color=RED, s=14, zorder=3)
            ax.scatter(
                [2019],
                [cmc.loc[2019, col]],
                marker="x",
                color=RED,
                s=55,
                linewidths=1.8,
                zorder=4,
            )
            if i == 0:
                isolated = quantiles.loc[[1980, 1984, 1985, 1987]].dropna()
                ax.vlines(
                    isolated.index,
                    isolated[0.1],
                    isolated[0.9],
                    color="#b5c8d3",
                    lw=3,
                    zorder=0,
                )
                ax.scatter(isolated.index, isolated[0.5], color=BLUE, s=12)
            for year in [2012, 2016]:
                ax.axvline(year, color="#8e9aa2", lw=0.8, ls=":")
            style_money(ax)
            if i == 0:
                ax.set_title(TITLES[rank], loc="left", fontsize=15, pad=10)
            ax.set_ylim(
                0,
                rank_data[["salary_nominal", "salary_real_cost_adjusted_2024"]]
                .max()
                .max()
                * 1.08,
            )
            if j == 0:
                ax.set_ylabel(
                    "Nominal salary"
                    if i == 0
                    else "Cost-adjusted salary · 2024 dollars"
                )
            if i == 1:
                ax.set_xticks([2008, 2012, 2016, 2020, 2024])
    fig.supxlabel("Academic year beginning in", y=0.12, fontsize=12)
    fig.suptitle(
        "CMC salaries over time", x=0.075, y=0.99, ha="left", fontsize=24, weight="bold"
    )
    fig.text(0.075, 0.945, cohort_label(data), fontsize=12)
    handles = [
        plt.Line2D([], [], color=RED, lw=2.5, label="CMC"),
        plt.Line2D([], [], color=BLUE, lw=1.6, label="Cohort median"),
        Rectangle(
            (0, 0), 1, 1, color="#dce7ed", label="10th–90th percentile across colleges"
        ),
    ]
    fig.legend(
        handles=handles,
        bbox_to_anchor=(0.065, 0.925),
        loc="upper left",
        ncol=3,
        frameon=False,
    )
    finish(
        fig,
        "historical_salary_trends",
        "× CMC’s 2019 contract-reporting break; not a verified pay cut. Dotted lines: 2012/2016 conversion changes.\nNine-month-equivalent averages. Sources: NCES IPEDS/HEGIS (early years via Urban); BEA RPP and PCE (via FRED). Methods: README.",
    )


def relative_trends(data):
    rank_data = data[data.year >= 2008].copy()
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
        1, 3, figsize=(26, max(10, data.unitid.nunique() * 0.32 + 3))
    )
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.21, top=0.81, wspace=0.65)
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
        ax.set_title(TITLES[rank], loc="left", fontsize=15, pad=15)
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
            fontsize=14,
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
    cax = fig.add_axes([0.36, 0.115, 0.4, 0.017])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend="both")
    cb.set_label("% above / below the cohort median")
    cb.set_ticks([-30, -15, 0, 15, 30])
    fig.suptitle(
        f"Relative purchasing power, {years[0]}–{latest}",
        x=0.03,
        y=0.98,
        ha="left",
        fontsize=23,
        weight="bold",
    )
    fig.text(0.03, 0.93, cohort_label(data), fontsize=13)
    finish(
        fig,
        "relative_purchasing_power_trends",
        f"× CMC’s 2019 contract-reporting break. Gray: unavailable. Each panel sorted by {latest} nominal salary.\nSources: NCES IPEDS; BEA RPP; U.S. News via College Kickstart. Methods and limitations: README.",
    )


def ranking_relationship(data, year):
    cols = ["salary_nominal", "salary_cost_adjusted"]
    fig, axes = plt.subplots(2, 3, figsize=(24, 17))
    fig.subplots_adjust(
        left=0.06, right=0.98, bottom=0.11, top=0.90, hspace=0.30, wspace=0.18
    )
    for j, rank in enumerate(RANKS):
        rank_data = data[data.year.eq(year) & data.academic_rank.eq(rank)]
        low = rank_data[cols].min().min() - 10000
        high = rank_data[cols].max().max() + 12000
        for i, (col, title) in enumerate(
            zip(cols, ["Nominal salary", "Cost-adjusted salary"])
        ):
            ax = axes[i, j]
            ax.scatter(
                rank_data.usnews_rank_2027,
                rank_data[col],
                c=[
                    RED if n == FOCUS[0] else BLUE if n in FOCUS else GRAY
                    for n in rank_data.college
                ],
                s=[70 if n in FOCUS else 35 for n in rank_data.college],
                edgecolor="white",
                lw=0.5,
                zorder=3,
            )
            ax.set(xlim=(-1, data.usnews_rank_2027.max() + 4), ylim=(low, high))
            style_money(ax)
            if i == 0:
                ax.set_title(TITLES[rank], loc="left", fontsize=16, pad=14)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            texts = [
                ax.text(
                    r.usnews_rank_2027,
                    r[col],
                    name(r.college),
                    fontsize=10,
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
                ax.set_ylabel("Nominal salary" if i == 0 else "Cost-adjusted salary")
    fig.supxlabel("U.S. News rank, 2027", y=0.065, fontsize=13)
    fig.suptitle(
        "College rank and faculty salaries",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=28,
        weight="bold",
    )
    fig.text(
        0.06, 0.945, f"{year}–{str(year + 1)[-2:]} · {cohort_label(data)}", fontsize=14
    )
    finish(
        fig,
        "college_rank_and_salary",
        f"Nine-month-equivalent averages; regional adjustment uses {year} prices. Gray lines connect labels to points.\nSources: NCES IPEDS; BEA RPP; U.S. News via College Kickstart. Methods and limitations: README.",
    )


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
    comparison(data, year)
    long_run(data)
    relative_trends(data)
    ranking_relationship(data, year)
    (reports / "figure_layout_audit.json").write_text(
        json.dumps(LAYOUT_AUDITS, indent=2) + "\n"
    )
    print("Generated four main figures, as PNG.")


if __name__ == "__main__":
    main()
