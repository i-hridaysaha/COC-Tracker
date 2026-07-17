"""Small storage helpers shared by the village and war paths.

The one non-obvious piece is upsert_csv. Both village snapshots and war
attacks can be seen more than once (a war spans several days, a village can be
polled twice in a day). So instead of blindly appending, we replace any
existing rows that share the same key and add the rest. Re-running is always
safe and never duplicates.
"""

import csv
import json
from pathlib import Path
from typing import Iterable


def safe_tag(tag: str) -> str:
    """Turn '#ABC123' into 'ABC123' for use as a folder name."""
    return tag.lstrip("#").upper()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))


def upsert_csv(path: Path, columns: list[str], new_rows: Iterable[dict], key_fields: list[str]) -> None:
    """Merge new_rows into the CSV at path, replacing rows with matching keys."""
    new_rows = list(new_rows)
    if not new_rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)

    def key(row: dict):
        return tuple(str(row.get(k)) for k in key_fields)

    incoming_keys = {key(r) for r in new_rows}
    kept: list[dict] = []
    if path.exists():
        with path.open(newline="") as f:
            kept = [r for r in csv.DictReader(f) if key(r) not in incoming_keys]

    all_rows = kept + [{c: r.get(c) for c in columns} for r in new_rows]
    all_rows.sort(key=lambda r: tuple(str(r.get(k)) for k in key_fields))

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_rows)
