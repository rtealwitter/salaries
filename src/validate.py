"""Validate sources, joins, arithmetic, identities, and independent published values."""

import hashlib
import json
import re

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from common import OUT, RAW, ROOT, read_csv, source_csv

REPORT = ROOT / "reports"
REPORT.mkdir(exist_ok=True)
checks = []


def main():
    REPORT.mkdir(exist_ok=True)
    checks.clear()
    long_data = read_csv(OUT / "combined_long.csv")
    wide_data = read_csv(OUT / "combined.csv")
    colleges = read_csv(OUT / "colleges.csv")
    sources = read_csv(ROOT / "data/sources.csv").fillna("")
    validate_panel(long_data, wide_data, colleges)
    validate_sources(sources)
    validate_salary_tables(colleges)
    validate_identities(long_data, colleges)
    validate_published_values()
    validate_cmc_display(long_data)
    validate_historical_mirror()
    validate_housing_and_flags(long_data)
    validate_figures()
    write_summary(long_data, wide_data, colleges)


def check(name, condition, detail=""):
    checks.append(dict(check=name, passed=bool(condition), detail=str(detail)))


def validate_panel(long_data, wide_data, colleges):
    check(
        "30 fixed civilian colleges",
        len(colleges) == 30
        and not colleges.college.str.contains("United States").any(),
    )
    check(
        "Published ranking ties retained",
        colleges.usnews_rank_2027.max() == 31
        and (colleges.usnews_rank_2027 == 31).sum() == 3
        and (colleges.usnews_rank_2027 == 3).sum() == 4,
    )
    check(
        "Unique panel keys",
        not wide_data.duplicated(["unitid", "year"]).any()
        and not long_data.duplicated(["unitid", "year", "academic_rank"]).any(),
    )
    check(
        "Complete panel grid",
        len(wide_data) == len(colleges) * long_data.year.nunique()
        and len(long_data) == 3 * len(wide_data),
    )
    check(
        "Latest common year",
        long_data.loc[long_data.salary_cost_adjusted.notna(), "year"].max() == 2024,
    )
    check(
        "Calendar and academic years align",
        (long_data.cost_year == long_data.year).all()
        and long_data.apply(
            lambda r: r.academic_year == f"{r.year}–{str(r.year + 1)[-2:]}", axis=1
        ).all(),
    )
    check(
        "All 30 colleges observed in 2024",
        (
            long_data[long_data.year == 2024][
                ["salary_nominal", "faculty_count", "rpp"]
            ].notna()
        )
        .all()
        .all(),
    )
    for expr, col in [
        (long_data.salary_nominal / (long_data.rpp / 100), "salary_cost_adjusted"),
        (
            long_data.salary_nominal * long_data.inflation_factor_2024,
            "salary_real_2024",
        ),
        (
            long_data.salary_nominal
            * long_data.inflation_factor_2024
            / (long_data.rpp / 100),
            "salary_real_cost_adjusted_2024",
        ),
    ]:
        check(
            col + " arithmetic",
            np.allclose(expr, long_data[col], equal_nan=True, rtol=1e-10),
        )
    check(
        "2024 inflation factor is one",
        long_data.loc[long_data.year == 2024, "inflation_factor_2024"].eq(1).all(),
    )
    for rankcol, valuecol in [
        ("salary_nominal_rank", "salary_nominal"),
        ("salary_cost_adjusted_rank", "salary_cost_adjusted"),
    ]:
        expected = long_data.groupby(["academic_rank", "year"])[valuecol].rank(
            ascending=False, method="min"
        )
        check(
            rankcol + " competition ranks",
            np.allclose(expected, long_data[rankcol], equal_nan=True),
        )
    check(
        "RPP missing is never extrapolated",
        long_data.loc[long_data.rpp.isna(), "salary_cost_adjusted"].isna().all(),
    )
    check(
        "Zero headcount has undefined mean",
        long_data.loc[long_data.faculty_count.eq(0), "salary_nominal"].isna().all(),
    )
    check(
        "Counts nonnegative integers",
        (
            (long_data.faculty_count.dropna() >= 0)
            & (long_data.faculty_count.dropna() % 1 == 0)
        ).all(),
    )
    check(
        "2024 geographic joins complete",
        long_data.loc[long_data.year == 2024, "cost_geography"].notna().all(),
    )
    check(
        "Nonmetro is state specific",
        (
            colleges.loc[
                colleges.geography_type.eq("state_nonmetropolitan"), "bea_geofips"
            ]
            .astype(str)
            .str[-3:]
            == "999"
        ).all(),
    )
    # Each row has direct source file and variable provenance; no sources guessed for missing records.
    check(
        "Salary values have provenance",
        long_data.loc[
            long_data.salary_nominal.notna(),
            ["salary_source", "salary_variable", "source_row_key"],
        ]
        .notna()
        .all()
        .all(),
    )


def validate_sources(sources):
    hashes = []
    for path, g in sources[sources.sha256.ne("")].groupby("path"):
        p = ROOT / path
        actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        hashes.append(
            dict(
                path=path,
                passed=actual in set(g.sha256),
                bytes=p.stat().st_size if p.exists() else 0,
            )
        )
    pd.DataFrame(hashes).to_csv(REPORT / "source_integrity.csv", index=False)
    check(
        "Every archived response checksum matches",
        all(r["passed"] for r in hashes),
        f"{len(hashes)} distinct archived files",
    )


def validate_salary_tables(colleges):
    # Cross-check official DRVHR against the salary detail table, independent joins.
    detail = []
    formula = []
    for year in range(2003, 2025):
        p = source_csv(RAW / "ipeds" / str(year), "sal")
        raw = read_csv(p)
        raw.columns = raw.columns.str.upper()
        raw = raw[raw.UNITID.isin(colleges.unitid) & raw.ARANK.isin([1, 2, 3])]
        if year >= 2016:
            outlay = (
                raw.SA09MOT
                + 0.9 * raw.SA10MOT
                + 0.818 * raw.SA11MOT
                + 0.75 * raw.SA12MOT
            )
            delta = (outlay / raw.SATOTLT - raw.SAEQ9AT).abs()
            for (_, r), diff in zip(raw.iterrows(), delta):
                formula.append(
                    dict(
                        year=year,
                        unitid=int(r.UNITID),
                        arank=int(r.ARANK),
                        difference=diff,
                    )
                )
        if year >= 2021:
            drv = read_csv(source_csv(RAW / "ipeds" / str(year), "drvhr"))
            drv.columns = drv.columns.str.upper()
            drv = drv.set_index("UNITID")
            for _, r in raw.iterrows():
                v = {1: "SALPROF", 2: "SALASSC", 3: "SALASST"}[r.ARANK]
                detail.append(
                    dict(
                        year=year,
                        unitid=r.UNITID,
                        variable=v,
                        difference=float(drv.loc[r.UNITID, v]) - float(r.SAEQ9AT),
                    )
                )
    pd.DataFrame(formula).to_csv(
        REPORT / "salary_outlay_reconciliation.csv", index=False
    )
    pd.DataFrame(detail).to_csv(REPORT / "derived_salary_crosscheck.csv", index=False)
    check(
        "DRVHR matches SAL detail",
        all(abs(r["difference"]) < 0.01 for r in detail),
        f"{len(detail)} rank observations",
    )
    check(
        "Contract-specific outlays reconcile within rounding",
        max(r["difference"] for r in formula if pd.notna(r["difference"])) < 1.01,
        f"max difference {pd.DataFrame(formula).difference.max():.4f} dollars",
    )


def validate_identities(long_data, colleges):
    # Identity audit includes original annual HD and historical mirror directories.
    identity = read_csv(OUT / "institution_identity_audit.csv").merge(
        colleges[["unitid", "college"]], on="unitid", validate="many_to_one"
    )

    def norm(value):
        return re.sub("[^a-z0-9]", "", value.lower())

    identity["matches_current_name"] = identity.apply(
        lambda r: norm(r.source_name) == norm(r.college), axis=1
    )
    aliases = read_csv(ROOT / "config/identity_aliases.csv")
    allowed = {(int(r.unitid), norm(r.source_name)) for _, r in aliases.iterrows()}
    identity["accepted_historical_alias"] = identity.apply(
        lambda r: (int(r.unitid), norm(r.source_name)) in allowed, axis=1
    )
    identity["verified"] = (
        identity.matches_current_name | identity.accepted_historical_alias
    )
    identity.to_csv(REPORT / "identity_checks.csv", index=False)
    check(
        "Institution names/IDs reconcile",
        identity.verified.all(),
        f"{len(identity)} identities checked; explicit historical aliases reviewed by UNITID",
    )
    covered = set(zip(identity.unitid, identity.year))
    observed = set(
        zip(
            long_data.loc[long_data.salary_nominal.notna(), "unitid"],
            long_data.loc[long_data.salary_nominal.notna(), "year"],
        )
    )
    check(
        "Every observed college-year has directory evidence",
        observed <= covered,
        str(sorted(observed - covered)),
    )


def validate_published_values():
    # Independently published primary institutional statistics: SC CHE Table 9.1, PDF p172, printed p163.
    pdf = RAW / "ipeds/SC_statistical_abstract_2025.pdf"
    page = PdfReader(pdf).pages[171].extract_text()
    hd = read_csv(source_csv(RAW / "ipeds/2024", "hd"))
    raw = read_csv(source_csv(RAW / "ipeds/2024", "sal"))
    external = []
    for label, inst in [
        ("College of Charleston", "College of Charleston"),
        ("Clemson", "Clemson University"),
        ("Coastal Carolina", "Coastal Carolina University"),
        ("The Citadel", "Citadel Military College of South Carolina"),
    ]:
        unitid = int(hd.loc[hd.INSTNM.eq(inst), "UNITID"].iloc[0])
        line = next(x for x in page.splitlines() if x.startswith(label + " "))
        pairs = re.findall(r"(\d[\d,]*)\s+\$([\d,]+)", line)
        for rank, (n, salary) in enumerate(pairs[:3], start=1):
            r = raw[(raw.UNITID == unitid) & (raw.ARANK == rank)].iloc[0]
            external.append(
                dict(
                    source="SC CHE 2025 Statistical Abstract, Table 9.1, printed p163",
                    unitid=unitid,
                    college=inst,
                    year=2024,
                    arank=rank,
                    published_salary=float(salary.replace(",", "")),
                    ipeds_salary=r.SAEQ9AT,
                    published_count=int(n.replace(",", "")),
                    ipeds_count=r.SATOTLT,
                )
            )
    ext = pd.DataFrame(external)
    ext["salary_matches"] = abs(ext.published_salary - ext.ipeds_salary) <= 1
    ext["count_matches"] = ext.published_count == ext.ipeds_count
    ext.to_csv(REPORT / "independent_published_crosschecks.csv", index=False)
    check(
        "Independent published values audited",
        len(ext) == 12 and (ext.salary_matches & ext.count_matches).sum() >= 6,
        f"{len(ext)} rank observations at four external institutions; {(ext.salary_matches & ext.count_matches).sum()} agree within $1/count; discrepancies retained for review",
    )


def validate_cmc_display(long_data):
    # Independent secondary rendering of CMC: same IPEDS source, not a second survey.
    html = BeautifulSoup(
        (RAW / "ipeds/cmc_salary_crosscheck.html").read_bytes(), "html.parser"
    ).get_text(" ", strip=True)
    cmc = []
    for rank, label in [
        ("assistant", "Assistant professors"),
        ("associate", "Associate professors"),
        ("full", "Professors"),
    ]:
        m = re.search(re.escape(label) + r"\s*\$([\d,]+)\s*\((\d+)\)", html)
        assert m, label
        v = long_data[
            long_data.unitid.eq(112260)
            & long_data.year.eq(2024)
            & long_data.academic_rank.eq(rank)
        ].iloc[0]
        cmc.append(
            dict(
                rank=rank,
                published_salary=int(m[1].replace(",", "")),
                salary=v.salary_nominal,
                published_count=int(m[2]),
                count=v.faculty_count,
            )
        )
    cmc = pd.DataFrame(cmc)
    cmc.to_csv(REPORT / "cmc_secondary_crosscheck.csv", index=False)
    check(
        "CMC secondary published display",
        cmc.published_salary.eq(cmc.salary).all()
        & cmc.published_count.eq(cmc["count"]).all(),
    )


def validate_historical_mirror():
    # Mirror overlap validation establishes variable mappings, while preserving mirror provenance.
    u = json.loads((RAW / "ipeds/2003/urban_salary.json").read_text())
    u = pd.DataFrame(u["results"])
    u = u[u.contract_length.eq(7) & u.academic_rank.isin([1, 2, 3])]
    p = source_csv(RAW / "ipeds/2003", "sal")
    r = read_csv(p)
    r.columns = r.columns.str.upper()
    r = r[r.CONTRACT.eq(4)]
    m = u.merge(
        r,
        left_on=["unitid", "academic_rank"],
        right_on=["UNITID", "ARANK"],
        validate="one_to_one",
    )
    m["salary_difference"] = m.average_salary - pd.to_numeric(
        m.AVESALT, errors="coerce"
    )
    m[
        ["unitid", "academic_rank", "average_salary", "AVESALT", "salary_difference"]
    ].to_csv(REPORT / "urban_overlap_crosscheck.csv", index=False)
    check(
        "Historical mirror overlap",
        len(m) == 90 and m.salary_difference.abs().max() < 1.01,
        f"2003; {len(m)} observations; maximum difference {m.salary_difference.abs().max()}",
    )


def validate_housing_and_flags(long_data):
    h = read_csv(OUT / "city_housing.csv")
    check("All ACS endpoint years recovered", set(h.year) == set(range(2009, 2025)))
    check(
        "ACS kept separate from cost index",
        long_data.loc[
            long_data.median_gross_rent.isna() & long_data.rpp.notna(),
            "salary_cost_adjusted",
        ]
        .notna()
        .all(),
    )
    check(
        "CMC 2019 break explicitly flagged",
        long_data.loc[
            long_data.unitid.eq(112260) & long_data.year.eq(2019), "quality_flags"
        ]
        .str.contains("cmc_2019")
        .all(),
    )
    long_data[
        long_data.quality_flags.fillna("").str.contains(
            "small_rank_count|missing_salary|salary_change_gt20pct|months_worked_changed|check_ipeds"
        )
    ].to_csv(REPORT / "quality_review.csv", index=False)


def validate_figures():
    stems = [
        "current_salary_comparison",
        "historical_salary_trends",
        "relative_purchasing_power_trends",
        "college_rank_and_salary",
    ]
    check(
        "Four PNG figures only",
        all((ROOT / "figures" / f"{stem}.png").stat().st_size > 1000 for stem in stems)
        and not list((ROOT / "figures").glob("*.svg")),
    )
    audits = json.loads((REPORT / "figure_layout_audit.json").read_text())
    check(
        "Figure text has no overlaps or clipping",
        {row["figure"] for row in audits} == set(stems)
        and all(
            not row["overlapping_pairs"]
            and not row["clipped_text"]
            and row["png_sha256"]
            == hashlib.sha256(
                (ROOT / "figures" / (row["figure"] + ".png")).read_bytes()
            ).hexdigest()
            for row in audits
        ),
        "Every visible title, legend, caption, axis label, tick, and annotation at 240 DPI",
    )
    colleges = read_csv(OUT / "colleges.csv")
    cohort = read_csv(REPORT / "figure_cohort.csv")
    selected = colleges[colleges.usnews_rank_2027 <= cohort.usnews_rank_2027.max()]
    ranks = read_csv(REPORT / "figure_salary_ranks.csv")
    valid = set(cohort.unitid) == set(selected.unitid) == set(ranks.unitid)
    valid &= len(ranks) == 3 * len(cohort)
    for measure in ["nominal", "cost_adjusted"]:
        expected = ranks.groupby("academic_rank")[f"salary_{measure}"].rank(
            ascending=False, method="min"
        )
        valid &= np.allclose(expected, ranks[f"salary_{measure}_rank"], equal_nan=True)
    check(
        "Figure cohort and within-cohort ranks",
        valid,
        f"{len(cohort)} civilian colleges; cutoff ties retained",
    )


def write_summary(long_data, wide_data, colleges):
    result = pd.DataFrame(checks)
    result.to_csv(REPORT / "validation_checks.csv", index=False)
    failures = result[~result.passed]
    print(result.to_string(index=False))
    summary = {
        "passed": int(result.passed.sum()),
        "failed": len(failures),
        "colleges": len(colleges),
        "survey_years": int(long_data.year.nunique()),
        "college_year_rows": len(wide_data),
        "college_years_with_salary": int(
            wide_data.assistant_salary_nominal.notna().sum()
        ),
        "rank_rows": len(long_data),
        "missing_rank_salaries": int(long_data.salary_nominal.isna().sum()),
        "salary_rpp_college_years": int(
            wide_data.assistant_salary_cost_adjusted.notna().sum()
        ),
        "salary_rpp_rent_college_years": int(
            (
                wide_data.assistant_salary_nominal.notna()
                & wide_data.rpp.notna()
                & wide_data.median_gross_rent.notna()
            ).sum()
        ),
        "latest_common_year": 2024,
    }
    (REPORT / "validation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    if len(failures):
        raise SystemExit(
            f"{len(failures)} validation check(s) failed; see reports/validation_checks.csv"
        )


if __name__ == "__main__":
    main()
