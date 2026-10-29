"""Build the fixed-cohort panel from archived files only (no network)."""

import json
import re

import numpy as np
import pandas as pd

from common import OUT, RANKS, RAW, numeric, read_csv, relative, source_csv
from historical import early_salaries
from housing import build_housing
from schema import write_dictionary


def build_colleges():
    source = RAW / "rankings/kickstart_2027.html"
    tables = pd.read_html(source)
    rankings = next(
        t for t in tables if "Williams College" in t.iloc[:, 0].values
    ).rename(
        columns={
            "Institution": "college",
            "Rank (2027)": "usnews_rank_2027",
            "Rank (2026)": "usnews_rank_2026",
        }
    )
    rankings = rankings[~rankings.college.str.startswith("United States")].sort_values(
        ["usnews_rank_2027", "college"]
    )
    threshold = rankings.iloc[29].usnews_rank_2027
    rankings = rankings[rankings.usnews_rank_2027 <= threshold].copy()
    hd_path = source_csv(RAW / "ipeds/2024", "hd2024")
    hd = read_csv(hd_path)
    colleges = rankings.merge(
        hd[hd.INSTNM.isin(rankings.college)],
        left_on="college",
        right_on="INSTNM",
        how="left",
        validate="one_to_one",
    )
    assert colleges.UNITID.notna().all(), "Unmatched college name"
    colleges = colleges[
        [
            "college",
            "UNITID",
            "CITY",
            "STABBR",
            "COUNTYCD",
            "COUNTYNM",
            "CBSA",
            "CBSATYPE",
            "usnews_rank_2027",
            "usnews_rank_2026",
        ]
    ].rename(
        columns={
            "UNITID": "unitid",
            "CITY": "city",
            "STABBR": "state",
            "COUNTYCD": "county_fips",
            "COUNTYNM": "county_name",
            "CBSA": "ipeds_cbsa_2024",
            "CBSATYPE": "ipeds_cbsa_type_2024",
        }
    )
    colleges["unitid"] = colleges.unitid.astype(int)
    colleges["county_fips"] = colleges.county_fips.astype(int).astype(str).str.zfill(5)
    colleges["state_fips"] = colleges.county_fips.str[:2]
    colleges["ranking_source"] = relative(source)
    colleges["ranking_quality"] = "secondary_transcription_publisher_access_blocked"
    colleges["location_source"] = relative(hd_path)
    county_crosswalk = pd.read_excel(
        RAW / "census/list1_2023.xlsx", skiprows=2, dtype=str
    )
    county_crosswalk["county_fips"] = county_crosswalk["FIPS State Code"].fillna(
        ""
    ) + county_crosswalk["FIPS County Code"].fillna("")
    county_crosswalk = county_crosswalk[county_crosswalk.county_fips.str.len() == 5]
    assert not county_crosswalk.county_fips.duplicated().any()
    colleges = colleges.merge(
        county_crosswalk[
            [
                "county_fips",
                "CBSA Code",
                "CBSA Title",
                "Metropolitan/Micropolitan Statistical Area",
            ]
        ],
        on="county_fips",
        how="left",
        validate="many_to_one",
    )
    metro = colleges["Metropolitan/Micropolitan Statistical Area"].eq(
        "Metropolitan Statistical Area"
    )
    colleges["bea_geofips"] = np.where(
        metro, colleges["CBSA Code"], colleges.state_fips + "999"
    )
    colleges["geography_type"] = np.where(
        metro, "metropolitan", "state_nonmetropolitan"
    )
    colleges["geography_vintage"] = (
        "OMB July 2023; fixed 2024 campus county for all years"
    )
    colleges["geography_source"] = "data/raw/census/list1_2023.xlsx"
    colleges = colleges.drop(
        columns=[
            "CBSA Code",
            "CBSA Title",
            "Metropolitan/Micropolitan Statistical Area",
        ]
    )
    colleges.to_csv(OUT / "colleges.csv", index=False)
    hist = colleges[
        [
            "unitid",
            "college",
            "usnews_rank_2026",
            "usnews_rank_2027",
            "ranking_source",
            "ranking_quality",
        ]
    ].melt(
        id_vars=["unitid", "college", "ranking_source", "ranking_quality"],
        var_name="edition",
        value_name="usnews_rank",
    )
    hist["edition"] = hist.edition.str[-4:].astype(int)
    hist.to_csv(OUT / "historical_rankings.csv", index=False)
    return colleges


def build_salaries(colleges):
    records = []
    identities = []
    for year in sorted(
        int(salary_path.name)
        for salary_path in (RAW / "ipeds").iterdir()
        if salary_path.name.isdigit()
    ):
        directory = RAW / "ipeds" / str(year)
        salary_path = source_csv(directory, "sal")
        if salary_path is None:
            continue
        salary_rows = read_csv(salary_path)
        salary_rows.columns = salary_rows.columns.str.upper()
        salary_rows = salary_rows[salary_rows.UNITID.isin(colleges.unitid)]
        hp = source_csv(directory, "hd") or source_csv(directory, "ic")
        if hp is not None:
            h = read_csv(hp)
            h.columns = h.columns.str.upper()
            if "INSTNM" in h:
                for _, v in h[h.UNITID.isin(colleges.unitid)].iterrows():
                    identities.append(
                        dict(
                            year=year,
                            unitid=v.UNITID,
                            source_name=v.INSTNM,
                            source=relative(hp),
                        )
                    )
        derived_path = source_csv(directory, "drvhr")
        derived = None
        if derived_path:
            derived = read_csv(derived_path)
            derived.columns = derived.columns.str.upper()
            derived = derived.set_index("UNITID")
        if "CONTRACT" in salary_rows:
            # Official derived equated contract rows, rather than mixing 9/10 with 11/12.
            salary_rows = salary_rows[salary_rows.CONTRACT == 4]
        if "ARANK" not in salary_rows:
            raise ValueError(f"Unsupported historical schema: {salary_path}")
        salary_rows = salary_rows[salary_rows.ARANK.isin(RANKS)]
        assert not salary_rows.duplicated(["UNITID", "ARANK"]).any(), salary_path
        for _, row in salary_rows.iterrows():
            rank = RANKS[int(row.ARANK)]
            flags = []
            if year < 2012:
                salary = numeric(row.AVESALT)
                count = numeric(row.EMPCNTT)
                salary_variable = "AVESALT; CONTRACT=4"
                count_variable = "EMPCNTT; CONTRACT=4"
                method = "pre2012_grouped_contracts"
                salary_flags = str(row.get("XAVESALT", ""))
                count_flag = str(row.get("XEMPCNTT", ""))
            elif year < 2016:
                salary = (
                    numeric(row.SAOUTLT) / numeric(row.SAMNTHT) * 9
                    if numeric(row.SAMNTHT) > 0
                    else np.nan
                )
                count = numeric(row.SATOTLT)
                salary_variable = "9*SAOUTLT/SAMNTHT"
                count_variable = "SATOTLT"
                method = "2012_2015_pooled_months"
                salary_flags = (
                    str(row.get("XSAOUTLT", "")) + "|" + str(row.get("XSAMNTHT", ""))
                )
                count_flag = str(row.get("XSATOTLT", ""))
                flags.append("pooled_months_not_identical_to_2016_method")
            else:
                salary = numeric(row.SAEQ9AT)
                count = numeric(row.SATOTLT)
                salary_variable = "SAEQ9AT"
                count_variable = "SATOTLT"
                method = "2016_onward_contract_specific"
                salary_flags = str(row.get("XSAEQ9AT", ""))
                count_flag = str(row.get("XSATOTLT", ""))
            salary_source = salary_path
            if derived is not None and row.UNITID in derived.index:
                var = {3: "SALASST", 2: "SALASSC", 1: "SALPROF"}[row.ARANK]
                val = numeric(derived.loc[row.UNITID, var])
                if pd.notna(val):
                    salary = val
                    salary_variable = var
                    salary_source = derived_path
            rawsalary = salary
            if count == 0:
                salary = np.nan
                flags.append("zero_faculty_undefined_mean")
            if pd.isna(salary):
                flags.append("missing_salary")
            if pd.isna(count):
                flags.append("missing_count")
            elif 0 < count < 10:
                flags.append("small_rank_count_lt10")
            if salary == 0 and count > 0:
                flags.append("reported_zero_salary")
            if year == 2024:
                flags.append("provisional_2024")
            if any(
                x not in ["R", "Z", "A", "G", "nan", ""]
                for x in (salary_flags + "|" + count_flag).split("|")
            ):
                flags.append("check_ipeds_imputation_flag")
            records.append(
                dict(
                    **{
                        f"faculty_count_{m}_month": numeric(
                            row.get(f"SA{m:02}MCT", np.nan)
                        )
                        for m in [9, 10, 11, 12]
                    },
                    unitid=int(row.UNITID),
                    year=int(year),
                    academic_year=f"{year}–{str(year + 1)[-2:]}",
                    academic_rank=rank,
                    salary_nominal=salary,
                    faculty_count=count,
                    faculty_count_all_contracts=numeric(row.get("SAINSTT", np.nan)),
                    faculty_count_less_than_9_months=numeric(
                        row.get("SA_9MCT", np.nan)
                    ),
                    source_salary_value=rawsalary,
                    salary_method=method,
                    salary_source=relative(salary_source),
                    salary_variable=salary_variable,
                    count_source=relative(salary_path),
                    count_variable=count_variable,
                    source_row_key=f"UNITID={int(row.UNITID)};ARANK={int(row.ARANK)}"
                    + (";CONTRACT=4" if year < 2012 else ""),
                    salary_imputation_flags=salary_flags,
                    count_imputation_flag=count_flag,
                    quality_flags=";".join(flags),
                )
            )

    out = pd.DataFrame(records)
    early = early_salaries(colleges, set(out.year))
    out = pd.concat([out, early], ignore_index=True).sort_values(
        ["unitid", "year", "academic_rank"]
    )
    # Flag large changes and observed changes in reported months worked.
    groups = out.groupby(["unitid", "academic_rank"])
    previous = groups.salary_nominal.shift(1)
    adjacent = (out.year - groups.year.shift(1)).eq(1)
    out["salary_nominal_yoy_pct"] = (100 * (out.salary_nominal / previous - 1)).where(
        adjacent
    )
    countcols = [f"faculty_count_{m}_month" for m in [9, 10, 11, 12]]
    reported_months = out[countcols].notna().any(axis=1)
    out["dominant_months_worked"] = (
        out[countcols]
        .fillna(-1)
        .idxmax(axis=1)
        .where(reported_months)
        .str.extract(r"count_(\d+)_")[0]
        .astype(float)
    )
    oldmonths = out.groupby(["unitid", "academic_rank"]).dominant_months_worked.shift(1)
    changed = (
        adjacent
        & oldmonths.notna()
        & out.dominant_months_worked.notna()
        & out.dominant_months_worked.ne(oldmonths)
    )
    out.loc[changed, "quality_flags"] += ";dominant_months_worked_changed"
    out.loc[out.salary_nominal_yoy_pct.abs() > 20, "quality_flags"] += (
        ";salary_change_gt20pct_review"
    )
    out.loc[out.unitid.eq(112260) & out.year.eq(2019), "quality_flags"] += (
        ";cmc_2019_all_12_month_contracts_comparability_break"
    )
    out.to_csv(OUT / "faculty_salaries.csv", index=False)
    for ip in sorted(RAW.glob("ipeds/*/urban_directory.json")):
        payload = json.loads(ip.read_text())
        assert not payload.get("next"), "Identity response not fully paginated"
        for v in payload.get("results", []):
            identities.append(
                dict(
                    year=v["year"],
                    unitid=v["unitid"],
                    source_name=v["inst_name"],
                    source=relative(ip),
                )
            )
    pd.DataFrame(identities).drop_duplicates(["unitid", "year"]).to_csv(
        OUT / "institution_identity_audit.csv", index=False
    )
    return out


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


def write_catalog_inventory():
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup((RAW / "ipeds/catalog.html").read_bytes(), "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        year = cells[0].get_text(strip=True)
        links = tr.select("a[href]")
        if not re.fullmatch(r"\d{4}", year) or not links:
            continue
        code = links[0].get_text(strip=True)
        if re.fullmatch(
            r"(DRVHR\d{4}|SAL(?:\d{4}|\d{2})_A(?:_1|_S)?|SAL\d{4}_IS|HD\d{4}|IC(?:\d{4}|\d{2})(?:_A)?)",
            code,
            re.I,
        ):
            rows.append(
                dict(
                    year=year,
                    code=code,
                    description=cells[2].get_text(" ", strip=True),
                    url=urljoin(
                        "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=-1",
                        links[0]["href"],
                    ),
                )
            )
    pd.DataFrame(rows).drop_duplicates().to_csv(OUT / "ipeds_catalog.csv", index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_catalog_inventory()
    colleges = build_colleges()
    salary_rows = build_salaries(colleges)
    cost = build_cost_of_living()
    pce = build_inflation()
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

    housing = build_housing()
    long = long.merge(
        housing, on=["unitid", "year"], how="left", validate="many_to_one"
    )
    long = long.sort_values(["unitid", "year", "academic_rank"])
    long.to_csv(OUT / "combined_long.csv", index=False)
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
    wide.to_csv(OUT / "combined.csv", index=False)

    write_dictionary(long, wide)
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
    print(
        f"{colleges.shape[0]} colleges; {len(wide)} college-years; {long.year.min()}–{long.year.max()}"
    )
    print(
        wide[wide.year == wide.year.max()]
        .sort_values("assistant_salary_cost_adjusted_rank")[
            [
                "college",
                "assistant_salary_nominal",
                "rpp",
                "assistant_salary_cost_adjusted",
                "assistant_salary_nominal_rank",
                "assistant_salary_cost_adjusted_rank",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
