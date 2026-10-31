"""Read ACS median gross rent; keep housing separate from all-items prices."""

import csv
import re

import numpy as np
import pandas as pd

from common import OUT, RAW, ROOT, numeric, relative


def build_housing():
    mapping = pd.read_csv(ROOT / "config/housing_geographies.csv")
    wanted = set(mapping.acs_geo_id)
    rows = []
    for year in range(2009, 2025):
        directory = RAW / "census" / str(year)
        if year >= 2021:
            source = directory / f"acsdt5y{year}-b25064.dat"
            if not source.exists():
                continue
            observations = read_table(source, wanted)
        else:
            if not (directory / "sequence_lookup.txt").exists():
                continue
            observations = read_sequences(directory, year, wanted)
        for geography in mapping.itertuples():
            observation = observations.get(geography.acs_geo_id)
            rows.append(housing_record(geography, year, observation))
    housing = pd.DataFrame(rows)
    housing.to_csv(OUT / "city_housing.csv", index=False)
    return housing


def read_table(path, wanted):
    """2021 onward: one national table with named estimate and margin columns."""
    table = pd.read_csv(path, sep="|", dtype=str)
    observations = {}
    for row in table[table.GEO_ID.isin(wanted)].itertuples():
        observations[row.GEO_ID] = dict(
            estimate=row.B25064_E001,
            margin=row.B25064_M001,
            source=relative(path),
            row_key="GEO_ID=" + row.GEO_ID,
            variable="B25064_E001;B25064_M001",
        )
    return observations


def read_geography_links(path, wanted):
    """Map state LOGRECNO keys to selected places (160) or subdivisions (060)."""
    links = {}
    with path.open(encoding="latin1") as handle:
        if path.suffix == ".csv":
            for fields in csv.reader(handle):
                if (
                    len(fields) < 5
                    or fields[2] not in ["060", "160"]
                    or fields[3] != "00"
                ):
                    continue
                geo = next(
                    (
                        value
                        for value in fields
                        if re.fullmatch(r"(060|160)00US\d+", value)
                    ),
                    None,
                )
                if geo:
                    links[fields[4]] = geo
        else:
            # The 2009 geography file uses fixed-width fields, not CSV columns.
            for line in handle:
                if line[8:11] not in ["060", "160"] or line[11:13] != "00":
                    continue
                match = re.search(r"(060|160)00US\d+", line)
                if match:
                    links[line[13:20]] = match.group()
    # Sequence files use 16000US; newer table files use 1600000US.
    links = {key: geo[:3] + "0000US" + geo.split("US")[1] for key, geo in links.items()}
    return {key: geo for key, geo in links.items() if geo in wanted}


def read_sequence_column(path, position, links):
    """Select a single estimate or margin column by its lookup-file position."""
    with path.open(encoding="latin1") as handle:
        return {
            fields[5]: fields[position]
            for fields in csv.reader(handle)
            if fields[5] in links
        }


def read_sequences(directory, year, wanted):
    """2009–2020: join separate geography, estimate, and margin files by LOGRECNO."""
    lookup = pd.read_csv(
        directory / "sequence_lookup.txt", encoding="latin1", dtype=str
    )
    lookup = lookup.rename(
        columns={"seq": "Sequence Number", "position": "Start Position"}
    )
    rent = lookup[
        (lookup["Table ID"] == "B25064") & lookup["Start Position"].notna()
    ].iloc[0]
    sequence = rent["Sequence Number"].zfill(4)
    position = int(rent["Start Position"]) - 1
    observations = {}
    geography_paths = list(directory.glob(f"g{year}5*.csv")) + list(
        directory.glob(f"g{year}5*.txt")
    )
    for geography_path in geography_paths:
        state = geography_path.stem[-2:]
        links = read_geography_links(geography_path, wanted)
        file_stem = f"{year}5{state}{sequence}000"
        folder = directory / f"{file_stem}_files"
        estimate_path = folder / f"e{file_stem}.txt"
        margin_path = folder / f"m{file_stem}.txt"
        if not estimate_path.exists() or not margin_path.exists():
            continue
        estimates = read_sequence_column(estimate_path, position, links)
        margins = read_sequence_column(margin_path, position, links)
        for record_key, estimate in estimates.items():
            if record_key not in margins:
                continue
            observations[links[record_key]] = dict(
                estimate=estimate,
                margin=margins[record_key],
                source=";".join(
                    relative(path)
                    for path in [estimate_path, margin_path, geography_path]
                ),
                row_key=f"LOGRECNO={record_key};sequence={sequence}",
                variable=f"B25064;column_1_based={position + 1}",
            )
    return observations


def housing_record(geography, year, observation):
    """Keep raw values and provenance alongside cleaned estimates and warnings."""
    values = observation or {}
    estimate = numeric(values.get("estimate", np.nan))
    margin = numeric(values.get("margin", np.nan))
    flags = []
    if observation is None:
        flags.append("geography_unavailable_no_substitution")
    elif pd.isna(estimate):
        flags.append("estimate_unavailable_or_suppressed")
    if pd.isna(margin):
        flags.append("moe_unavailable_or_special")
    if estimate > 0 and margin / estimate > 0.3:
        flags.append("relative_moe_gt30pct")
    return dict(
        unitid=geography.unitid,
        year=year,
        acs_geo_id=geography.acs_geo_id,
        acs_geography=geography.acs_geography,
        acs_period=f"{year - 4}–{year}",
        median_gross_rent=estimate,
        median_gross_rent_moe90=margin,
        rent_estimate_raw=values.get("estimate", ""),
        rent_moe_raw=values.get("margin", ""),
        rent_source=values.get("source", ""),
        rent_source_row_key=values.get("row_key", ""),
        rent_variable=values.get("variable", "B25064_001E;B25064_001M"),
        housing_quality_flags=";".join(flags),
        housing_geography_note=geography.housing_geography_note,
    )


if __name__ == "__main__":
    print(build_housing().groupby("year").median_gross_rent.count())
