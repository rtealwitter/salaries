"""Separate ACS rent context; never used as an all-items deflator."""

import csv as csv_module
import re

import numpy as np
import pandas as pd

from common import OUT, RAW, ROOT, numeric, relative


def normalize_geo(s):
    # Sequence files use 16000US; table-based files use 1600000US.
    return s[:3] + "0000US" + s.split("US")[1]


def build_housing():
    mapping = pd.read_csv(ROOT / "config/housing_geographies.csv")
    wanted = set(mapping.acs_geo_id)
    rows = []
    for year in range(2009, 2025):
        directory = RAW / "census" / str(year)
        data = {}
        if year >= 2021:
            source_path = directory / f"acsdt5y{year}-b25064.dat"
            if not source_path.exists():
                continue
            table = pd.read_csv(source_path, sep="|", dtype=str)
            table = table[table.GEO_ID.isin(wanted)]
            for _, row in table.iterrows():
                data[row.GEO_ID] = (
                    row.B25064_E001,
                    row.B25064_M001,
                    relative(source_path),
                    "GEO_ID=" + row.GEO_ID,
                    "B25064_E001;B25064_M001",
                )
        else:
            lookup = directory / "sequence_lookup.txt"
            if not lookup.exists():
                continue
            table = pd.read_csv(lookup, encoding="latin1", dtype=str).rename(
                columns={"seq": "Sequence Number", "position": "Start Position"}
            )
            row = table[
                (table["Table ID"] == "B25064") & table["Start Position"].notna()
            ].iloc[0]
            sequence = row["Sequence Number"].zfill(4)
            position = int(row["Start Position"]) - 1
            for source_path in list(directory.glob(f"g{year}5*.csv")) + list(
                directory.glob(f"g{year}5*.txt")
            ):
                state = source_path.stem[-2:]
                links = {}
                if source_path.suffix == ".csv":
                    for fields in csv_module.reader(
                        source_path.open(encoding="latin1")
                    ):
                        if len(fields) < 5:
                            continue
                        if fields[2] not in ["060", "160"] or fields[3] != "00":
                            continue
                        ids = [
                            s for s in fields if re.fullmatch(r"(060|160)00US\d+", s)
                        ]
                        if not ids:
                            continue
                        geo = normalize_geo(ids[0])
                        if geo in wanted:
                            links[fields[4]] = geo
                else:
                    for line in source_path.read_text(encoding="latin1").splitlines():
                        if line[8:11] not in ["060", "160"] or line[11:13] != "00":
                            continue
                        match = re.search(r"(060|160)00US\d+", line)
                        if match:
                            geo = normalize_geo(match.group())
                            if geo in wanted:
                                links[line[13:20]] = geo
                folder = directory / f"{year}5{state}{sequence}000_files"
                estimate_path = folder / f"e{year}5{state}{sequence}000.txt"
                margin_path = folder / f"m{year}5{state}{sequence}000.txt"
                if not estimate_path.exists() or not margin_path.exists():
                    continue
                vals = {}
                for label, source in [("e", estimate_path), ("m", margin_path)]:
                    for fields in csv_module.reader(source.open(encoding="latin1")):
                        if fields[5] in links:
                            vals.setdefault(fields[5], {})[label] = fields[position]
                for log, values in vals.items():
                    if "e" in values and "m" in values:
                        data[links[log]] = (
                            values["e"],
                            values["m"],
                            relative(estimate_path)
                            + ";"
                            + relative(margin_path)
                            + ";"
                            + relative(source_path),
                            f"LOGRECNO={log};sequence={sequence}",
                            f"B25064;column_1_based={position + 1}",
                        )
        for _, geography in mapping.iterrows():
            values = data.get(geography.acs_geo_id)
            estimate = numeric(values[0]) if values else np.nan
            moe = numeric(values[1]) if values else np.nan
            flags = []
            if values is None:
                flags.append("geography_unavailable_no_substitution")
            elif pd.isna(estimate):
                flags.append("estimate_unavailable_or_suppressed")
            if pd.isna(moe):
                flags.append("moe_unavailable_or_special")
            if (
                pd.notna(moe)
                and pd.notna(estimate)
                and estimate > 0
                and moe / estimate > 0.3
            ):
                flags.append("relative_moe_gt30pct")
            rows.append(
                dict(
                    unitid=geography.unitid,
                    year=year,
                    acs_geo_id=geography.acs_geo_id,
                    acs_geography=geography.acs_geography,
                    acs_period=f"{year - 4}–{year}",
                    median_gross_rent=estimate,
                    median_gross_rent_moe90=moe,
                    rent_estimate_raw=values[0] if values else "",
                    rent_moe_raw=values[1] if values else "",
                    rent_source=values[2] if values else "",
                    rent_source_row_key=values[3] if values else "",
                    rent_variable=values[4] if values else "B25064_001E;B25064_001M",
                    housing_quality_flags=";".join(flags),
                    housing_geography_note=geography.housing_geography_note,
                )
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "city_housing.csv", index=False)
    return out


if __name__ == "__main__":
    print(build_housing().groupby("year").median_gross_rent.count())
