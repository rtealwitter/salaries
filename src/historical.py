"""Explicit adapters for archived Urban Institute mirrors of early IPEDS/HEGIS."""

import json

import numpy as np
import pandas as pd

from common import RANKS, RAW, numeric, relative, salary_quality


def early_salaries(colleges, official_years):
    records = []
    for path in sorted(RAW.glob("ipeds/*/urban_salary.json")):
        year = int(path.parent.name)
        if year in official_years:
            continue
        payload = json.loads(path.read_text())
        if payload.get("next"):
            raise ValueError("Unretrieved API pagination: " + str(path))
        data = pd.DataFrame(payload.get("results", []))
        if data.empty:
            continue
        assert len(data) == payload["count"]
        data = data[
            data.academic_rank.isin(RANKS)
            & data.unitid.isin(colleges.unitid)
            & data.sex.eq(99)
        ]
        for (unitid, rank), contracts in data.groupby(["unitid", "academic_rank"]):
            record = historical_record(unitid, rank, contracts, year, path)
            if record is not None:
                records.append(record)
    return pd.DataFrame(records)


def historical_record(unitid, rank, contracts, year, path):
    """Choose the documented contract population and preserve its source definition."""
    assert not contracts.contract_length.duplicated().any()
    contracts = contracts.set_index("contract_length")
    flags = [
        "urban_mirror_original_nces_download_failed",
        "historical_imputation_flags_unavailable",
    ]
    if 7 in contracts.index:
        row = contracts.loc[7]
        salary = numeric(row.average_salary)
        count = numeric(row.instruc_staff_count)
        basis = "pre2012_grouped_contracts"
        salary_variable = "average_salary; contract_length=7"
        contract_key = "7"
    elif 5 in contracts.index and 6 in contracts.index:
        # NCES legacy conversion: 11/12 month outlays multiplied by .8182.
        nine_ten_month = contracts.loc[5]
        eleven_twelve_month = contracts.loc[6]
        count = numeric(nine_ten_month.instruc_staff_count) + numeric(
            eleven_twelve_month.instruc_staff_count
        )
        short_outlays = numeric(nine_ten_month.salary_outlays)
        long_outlays = numeric(eleven_twelve_month.salary_outlays)
        salary = (
            (short_outlays + long_outlays * 0.8182) / count
            if count > 0 and pd.notna(short_outlays + long_outlays)
            else np.nan
        )
        basis = "pre2012_grouped_contracts"
        salary_variable = "(outlays_contract5+.8182*outlays_contract6)/(count5+count6)"
        contract_key = "5,6"
        flags.append("legacy_0_8182_conversion")
    else:
        if 9 in contracts.index:
            contract = 9
            basis = "9_month_only_early"
        elif 5 in contracts.index:
            contract = 5
            basis = "9_10_month_only_early"
        else:
            return None
        row = contracts.loc[contract]
        salary = numeric(row.average_salary)
        count = numeric(row.instruc_staff_count)
        salary_variable = f"average_salary; contract_length={contract}"
        contract_key = str(contract)
        flags.append("restricted_contract_population_not_all_9_to_12_months")
    source_salary = salary
    salary, count_flags = salary_quality(salary, count)
    flags.extend(count_flags)
    return dict(
        unitid=int(unitid),
        year=year,
        academic_year=f"{year}–{str(year + 1)[-2:]}",
        academic_rank=RANKS[rank],
        salary_nominal=salary,
        faculty_count=count,
        source_salary_value=source_salary,
        salary_method=basis,
        salary_source=relative(path),
        salary_variable=salary_variable,
        count_source=relative(path),
        count_variable="instruc_staff_count; contract_length=" + contract_key,
        source_row_key=f"unitid={unitid};academic_rank={rank};sex=99;contract_length={contract_key}",
        salary_imputation_flags="unavailable_in_mirror",
        count_imputation_flag="unavailable_in_mirror",
        quality_flags=";".join(flags),
    )
