"""Shared paths and source-file readers for the offline pipeline."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/processed"
RANKS = {3: "assistant", 2: "associate", 1: "full"}


def read_csv(path, **kwargs):
    """Read NCES CSVs with their original encoding and trim header whitespace."""
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)
    except UnicodeDecodeError:
        frame = pd.read_csv(path, encoding="latin1", low_memory=False, **kwargs)
    frame.columns = frame.columns.str.strip()
    return frame


def source_csv(directory, prefix):
    """Find an extracted source table, preferring revised (_rv) files."""
    files = [
        p
        for p in directory.glob("*_files/*.csv")
        if p.name.lower().startswith(prefix.lower())
    ]
    if not files:
        return None
    # The archive often contains both provisional and final files. Prefer final.
    return sorted(files, key=lambda p: ("_rv" in p.stem.lower(), p.name))[-1]


def relative(path):
    return str(path.relative_to(ROOT))


def numeric(value):
    """Convert a source number, treating negative suppression codes as missing."""
    parsed = pd.to_numeric(value, errors="coerce")
    return np.nan if pd.isna(parsed) or parsed < 0 else float(parsed)
