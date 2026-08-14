#!/usr/bin/env python3
"""Repair corrupted data/lifelog.json using json-repair plus cleanup."""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from json_repair import repair_json
except ImportError:
    print("Install json-repair first: pip install json-repair", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
LIFELOG = ROOT / "data" / "lifelog.json"
DATE_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _entry_score(entry: dict) -> int:
    return (
        len(entry.get("journal_pages") or [])
        + len(entry.get("tasks") or [])
        + (1 if entry.get("workout") else 0)
        + (1 if (entry.get("journal") or "").strip() else 0)
    )


def main() -> int:
    if not LIFELOG.exists():
        print(f"Missing {LIFELOG}", file=sys.stderr)
        return 1

    backup = LIFELOG.with_name(
        f"lifelog.json.bak.repair.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(LIFELOG, backup)
    print(f"Backup: {backup}")

    raw = LIFELOG.read_text(encoding="utf-8")
    try:
        json.loads(raw)
        print("File is already valid JSON; no repair needed.")
        return 0
    except json.JSONDecodeError as exc:
        print(f"Repairing: {exc.msg} (line {exc.lineno}, column {exc.colno})")

    repaired = json.loads(repair_json(raw))
    clean: dict[str, dict] = {}
    for key, value in repaired.items():
        if not DATE_KEY.match(key) or not isinstance(value, dict):
            print(f"Dropping invalid top-level key: {key!r}")
            continue
        if key in clean and _entry_score(value) <= _entry_score(clean[key]):
            print(f"Keeping existing entry for duplicate date: {key}")
            continue
        if key in clean:
            print(f"Replacing entry for duplicate date with richer data: {key}")
        clean[key] = value

    LIFELOG.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    json.loads(LIFELOG.read_text(encoding="utf-8"))
    print(f"Repaired JSON written with {len(clean)} day entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
