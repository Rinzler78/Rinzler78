#!/usr/bin/env python3
"""
validate_data.py — Validate the data/*.json files against their JSON Schemas
and check referential integrity (all FKs point to an existing entity). Used by
the pre-commit hook.

Exit 0 if everything is OK, 1 otherwise.
"""

from __future__ import annotations

import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.data_loader import (  # noqa: E402
    DataLoadError,
    check_referential_integrity,
    load_collection,
)

DATA = _REPO_ROOT / "data"
SCHEMAS = _REPO_ROOT / "schemas"

# (data file, schema file or None)
SCHEMA_MAP = {
    "techs.json": "tech.schema.json",
    "experiences.json": "experience.schema.json",
    "projects.json": "project.schema.json",
    "timeline.json": "timeline.schema.json",
    "services.json": "service.schema.json",
    "modes.json": "mode.schema.json",
    "methodology.json": "methodology.schema.json",
}


def _schema(name: str) -> dict:
    import json

    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    bag: dict[str, list[dict]] = {}

    for data_file in sorted(DATA.glob("*.json")):
        schema_name = SCHEMA_MAP.get(data_file.name)
        schema = _schema(schema_name) if schema_name else None
        try:
            collection = load_collection(data_file, schema=schema)
        except DataLoadError as e:
            errors.append(str(e))
            continue
        if isinstance(collection, list):
            bag[data_file.stem] = collection

    if not errors:
        try:
            check_referential_integrity(bag)
        except DataLoadError as e:
            errors.append(str(e))

    if errors:
        print("[validate_data.py] ✗ data errors:", file=sys.stderr)
        for err in errors:
            print(f"    - {err}", file=sys.stderr)
        return 1

    print("[validate_data.py] OK — schemas + referential integrity validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
