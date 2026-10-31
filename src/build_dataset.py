"""Build the fixed-cohort panel from archived files only (no network)."""

import re

import numpy as np
import pandas as pd

from common import OUT, RANKS, RAW, read_csv, relative
from housing import build_housing
from ipeds import build_colleges, build_salaries, write_catalog_inventory
from schema import write_dictionary


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Read each source into a documented component table.
    colleges = build_colleges()
    salaries = build_salaries(colleges)
    regional_prices = build_cost_of_living()
    national_prices = build_inflation()
    housing = build_housing()

    # 2. Join and adjust salaries, then produce both useful table layouts.
    long = combine_sources(
        colleges, salaries, regional_prices, national_prices, housing
    )
    wide = make_wide_panel(long)
    long.to_csv(OUT / "combined_long.csv", index=False)
    wide.to_csv(OUT / "combined.csv", index=False)

    # 3. Write the documentation and coverage counts alongside the data.
    write_dictionary(long, wide)
    write_coverage(long)
    write_catalog_inventory()
    print(
        f"{len(colleges)} colleges; {len(wide)} college-years; {long.year.min()}–{long.year.max()}"
    )


def build_cost_of_living():
    parts = []
    for folder, pattern in [
        ("MARPP_files", "MARPP_MSA*.csv"),
        ("PARPP_files", "PARPP_PORT*.csv"),
    ]:
        source_path = next((RAW / "bea" / folder).glob(pattern))
        prices = read_csv(source_path)
        prices = prices[prices.LineCode == 1].copy()
        prices["bea_geofips"] = (
            prices.GeoFIPS.str.replace('"', "", regex=False).str.strip().str.zfill(5)
        )
        years = [x for x in prices if re.fullmatch(r"\d{4}", x)]
        prices = prices.melt(
            id_vars=["bea_geofips", "GeoName"],
            value_vars=years,
            var_name="cost_year",
            value_name="rpp",
        )
        prices = prices.rename(columns={"GeoName": "cost_geography"})
        prices["rpp"] = pd.to_numeric(prices.rpp, errors="coerce")
        prices["cost_year"] = prices.cost_year.astype(int)
        prices["rpp_source"] = relative(source_path)
        prices["rpp_line_code"] = 1
        parts.append(prices)
    prices = pd.concat(parts).drop_duplicates(["bea_geofips", "cost_year"])
    prices.to_csv(OUT / "cost_of_living.csv", index=False)
    return prices


def build_inflation():
    source_path = RAW / "bea/PCEPI.csv"
    monthly = read_csv(source_path)
    monthly["year"] = pd.to_datetime(monthly.iloc[:, 0]).dt.year
    monthly["PCEPI"] = pd.to_numeric(monthly.PCEPI, errors="coerce")
    annual = monthly.groupby("year").PCEPI.agg(["mean", "count"])
    annual = annual[annual["count"] == 12].rename(
        columns={"mean": "pce_price_index", "count": "months"}
    )
    annual["inflation_factor_2024"] = (
        annual.loc[2024, "pce_price_index"] / annual.pce_price_index
    )
    annual["pce_source"] = relative(source_path)
    annual = annual.reset_index()
    annual.to_csv(OUT / "inflation.csv", index=False)
    return annual


def combine_sources(colleges, salary_rows, cost, pce, housing):
    """Join by institution/year, apply price adjustments, and retain missing rows."""
    # Preserve even wholly missing school-years in each recovered survey year.
    grid = pd.MultiIndex.from_product(
        [colleges.unitid, sorted(salary_rows.year.unique()), list(RANKS.values())],
        names=["unitid", "year", "academic_rank"],
    ).to_frame(index=False)
    long = grid.merge(
        salary_rows,
        on=["unitid", "year", "academic_rank"],
        how="left",
        validate="one_to_one",
    ).merge(colleges, on="unitid", validate="many_to_one")
    long["academic_year"] = long.year.map(lambda y: f"{y}–{str(y + 1)[-2:]}")
    long["quality_flags"] = long.quality_flags.fillna("missing_salary_and_count")
    long["cost_year"] = long.year
    long = long.merge(
        cost, on=["bea_geofips", "cost_year"], how="left", validate="many_to_one"
    ).merge(pce, on="year", how="left", validate="many_to_one")
    names = (
        cost[["bea_geofips", "cost_geography"]]
        .drop_duplicates()
        .set_index("bea_geofips")
        .cost_geography
    )
    long["cost_geography"] = long.bea_geofips.map(names)
    long.loc[long.rpp.isna(), "quality_flags"] += ";rpp_unavailable"
    long.loc[long.geography_type == "state_nonmetropolitan", "quality_flags"] += (
        ";state_nonmetro_proxy"
    )
    long["salary_cost_adjusted"] = long.salary_nominal / (long.rpp / 100)
    long["salary_real_2024"] = long.salary_nominal * long.inflation_factor_2024
    long["salary_real_cost_adjusted_2024"] = (
        long.salary_cost_adjusted * long.inflation_factor_2024
    )
    for measure in ["nominal", "cost_adjusted"]:
        long[f"salary_{measure}_rank"] = long.groupby(["year", "academic_rank"])[
            f"salary_{measure}"
        ].rank(ascending=False, method="min")
    long["salary_rank_improvement"] = (
        long.salary_nominal_rank - long.salary_cost_adjusted_rank
    )
    long["historical_usnews_rank"] = (
        np.nan
    )  # historical editions 2026/27 are separate, not backfilled

    long = long.merge(
        housing, on=["unitid", "year"], how="left", validate="many_to_one"
    )
    long = long.sort_values(["unitid", "year", "academic_rank"])
    return long


def make_wide_panel(long):
    """Put the three faculty ranks side by side, preserving provenance columns."""
    rank_columns = (
        ["dominant_months_worked", "salary_nominal_yoy_pct"]
        + [f"faculty_count_{m}_month" for m in [9, 10, 11, 12]]
        + [
            "salary_nominal",
            "faculty_count",
            "faculty_count_all_contracts",
            "faculty_count_less_than_9_months",
            "source_salary_value",
            "salary_method",
            "salary_source",
            "salary_variable",
            "count_source",
            "count_variable",
            "source_row_key",
            "salary_imputation_flags",
            "count_imputation_flag",
            "quality_flags",
            "salary_cost_adjusted",
            "salary_real_2024",
            "salary_real_cost_adjusted_2024",
            "salary_nominal_rank",
            "salary_cost_adjusted_rank",
            "salary_rank_improvement",
        ]
    )
    shared_columns = [x for x in long if x not in rank_columns + ["academic_rank"]]
    wide = (
        long[shared_columns]
        .drop_duplicates(["unitid", "year"])
        .set_index(["unitid", "year"])
    )
    for rank in RANKS.values():
        rank_values = (
            long[long.academic_rank == rank]
            .set_index(["unitid", "year"])[rank_columns]
            .add_prefix(rank + "_")
        )
        wide = wide.join(rank_values, validate="one_to_one")
    wide = wide.reset_index().sort_values(["year", "usnews_rank_2027", "college"])

    return wide


def write_coverage(long):
    """Count available salaries, regional prices, and rent by year and rank."""
    long = long.copy()
    coverage = (
        long.groupby(["year", "academic_rank"])
        .agg(
            institutions=("unitid", "size"),
            salary_observations=("salary_nominal", "count"),
            rpp_observations=("salary_cost_adjusted", "count"),
            rent_observations=("median_gross_rent", "count"),
        )
        .reset_index()
    )
    long["all_three_available"] = (
        long.salary_nominal.notna() & long.rpp.notna() & long.median_gross_rent.notna()
    )
    complete_coverage = (
        long.groupby(["year", "academic_rank"]).all_three_available.sum().reset_index()
    )
    coverage.merge(complete_coverage, on=["year", "academic_rank"]).to_csv(
        OUT / "coverage.csv", index=False
    )


if __name__ == "__main__":
    main()
