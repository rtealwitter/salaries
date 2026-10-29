"""Restore missing source files from the archived manifest without changing bytes.

Existing files are left alone. A download is saved only if its SHA-256 matches
our captured vintage. ZIP members are restored from the original archive.
"""

import csv
import hashlib
from pathlib import Path
from zipfile import ZipFile

import requests

from common import ROOT


def restore_source(source, archives):
    """Restore one manifest entry, downloading its parent ZIP when necessary."""
    destination = ROOT / source["path"]
    if destination.exists():
        return False

    print(f"Restoring {source['path']}", flush=True)
    if source["archive_member"]:
        archive = archives[source["url"]]
        restore_source(archive, archives)
        with ZipFile(ROOT / archive["path"]) as handle:
            payload = handle.read(source["archive_member"])
    else:
        response = requests.get(source["url"], timeout=90)
        response.raise_for_status()
        payload = response.content

    actual = hashlib.sha256(payload).hexdigest()
    if actual != source["sha256"]:
        raise ValueError(
            f"Source vintage changed: {source['url']}. "
            "Downloaded bytes do not match the archived checksum; nothing saved."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return True


def main():
    manifest = ROOT / "data/sources.csv"
    with manifest.open() as handle:
        sources = list(csv.DictReader(handle))
    # Failed access attempts remain documented in the manifest. Only successful
    # responses can be recovered reliably from their original URLs.
    sources = {
        source["path"]: source
        for source in sources
        if source["status"] == "ok" and source["sha256"]
    }
    archives = {
        source["url"]: source
        for source in sources.values()
        if not source["archive_member"]
        and Path(source["path"]).suffix.lower() == ".zip"
    }
    missing = [
        source for source in sources.values() if not (ROOT / source["path"]).exists()
    ]
    for source in missing:
        restore_source(source, archives)
    print(f"Restored {len(missing)} missing files; existing raw files unchanged.")


if __name__ == "__main__":
    main()
