"""Read institution and faculty records from archived IPEDS source formats.

This module handles changes in NCES reporting. The analysis joins and salary
adjustments live in build_dataset.py.
"""

import json
import re

import numpy as np
import pandas as pd

from common import (
    OUT,
    RANKS,
    RAW,
    numeric,
    salary_quality,
    read_csv,
    relative,
    source_csv,
)
from historical import early_salaries


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


def read_ipeds_year(year, colleges):
    """Read one NCES salary file and its directory, using the year-specific definition."""
    records = []
    directory = RAW / "ipeds" / str(year)
    salary_path = source_csv(directory, "sal")
    if salary_path is None:
        return [], []
    salary_rows = read_csv(salary_path)
    salary_rows.columns = salary_rows.columns.str.upper()
    salary_rows = salary_rows[salary_rows.UNITID.isin(colleges.unitid)]
    identities = read_directory(directory, year, colleges)
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
        records.append(salary_record(row, year, salary_path, derived, derived_path))

    return records, identities


def read_directory(directory, year, colleges):
    """Retain annual names as independent evidence for each institution identifier."""
    path = source_csv(directory, "hd") or source_csv(directory, "ic")
    if path is None:
        return []
    directory_rows = read_csv(path)
    directory_rows.columns = directory_rows.columns.str.upper()
    if "INSTNM" not in directory_rows:
        return []
    return [
        dict(
            year=year, unitid=row.UNITID, source_name=row.INSTNM, source=relative(path)
        )
        for row in directory_rows[
            directory_rows.UNITID.isin(colleges.unitid)
        ].itertuples()
    ]


def salary_record(row, year, salary_path, derived, derived_path):
    """Interpret one rank's salary under the rules in effect that survey year."""
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
        salary_flags = str(row.get("XSAOUTLT", "")) + "|" + str(row.get("XSAMNTHT", ""))
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
    source_salary = salary
    salary, count_flags = salary_quality(salary, count)
    flags.extend(count_flags)
    if year == 2024:
        flags.append("provisional_2024")
    if any(
        x not in ["R", "Z", "A", "G", "nan", ""]
        for x in (salary_flags + "|" + count_flag).split("|")
    ):
        flags.append("check_ipeds_imputation_flag")
    return dict(
        **{
            f"faculty_count_{m}_month": numeric(row.get(f"SA{m:02}MCT", np.nan))
            for m in [9, 10, 11, 12]
        },
        unitid=int(row.UNITID),
        year=int(year),
        academic_year=f"{year}–{str(year + 1)[-2:]}",
        academic_rank=rank,
        salary_nominal=salary,
        faculty_count=count,
        faculty_count_all_contracts=numeric(row.get("SAINSTT", np.nan)),
        faculty_count_less_than_9_months=numeric(row.get("SA_9MCT", np.nan)),
        source_salary_value=source_salary,
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


def build_salaries(colleges):
    records = []
    identities = []
    years = sorted(
        int(path.name) for path in (RAW / "ipeds").iterdir() if path.name.isdigit()
    )
    for year in years:
        year_records, year_identities = read_ipeds_year(year, colleges)
        records.extend(year_records)
        identities.extend(year_identities)
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
    month_columns = [f"faculty_count_{m}_month" for m in [9, 10, 11, 12]]
    reported_months = out[month_columns].notna().any(axis=1)
    out["dominant_months_worked"] = (
        out[month_columns]
        .fillna(-1)
        .idxmax(axis=1)
        .where(reported_months)
        .str.extract(r"count_(\d+)_")[0]
        .astype(float)
    )
    previous_months = out.groupby(
        ["unitid", "academic_rank"]
    ).dominant_months_worked.shift(1)
    changed = (
        adjacent
        & previous_months.notna()
        & out.dominant_months_worked.notna()
        & out.dominant_months_worked.ne(previous_months)
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
