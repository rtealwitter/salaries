"""Human-readable column dictionary generated for both panel formats."""

import pandas as pd

from common import OUT, ROOT


def write_dictionary(long, wide):
    reference = pd.read_csv(
        ROOT / "config/column_definitions.csv", keep_default_na=False
    )
    definitions = {
        row.column: (row.units, row.definition) for row in reference.itertuples()
    }
    records = []
    for table, frame in [("combined_long.csv", long), ("combined.csv", wide)]:
        for col in frame:
            stem = col
            for rank in ["assistant", "associate", "full"]:
                if stem.startswith(rank + "_"):
                    stem = stem[len(rank) + 1 :]
                    break
            if stem in definitions:
                units, definition = definitions[stem]
            elif stem.endswith("_source"):
                units, definition = (
                    "relative path",
                    "Archived source path(s); join to data/sources.csv for URL, timestamp and SHA-256.",
                )
            elif stem.startswith("faculty_count_") and stem.endswith("_month"):
                units, definition = (
                    "people",
                    "Headcount at this rank with the stated months worked; source SAxxMCT.",
                )
            else:
                units, definition = "text", "Source/context metadata."
            records.append(
                dict(table=table, column=col, units=units, definition=definition)
            )
    pd.DataFrame(records).to_csv(OUT / "data_dictionary.csv", index=False)
