#!/usr/bin/env python3
"""Move `as_of` in data/config.json forward to today.

The generation derives hours, scores and recency from a committed reference
date so that a revision pins its own output (see `scripts.generate.
reference_date`). Something has to move that date deliberately: this script,
run by the weekly refresh workflow, is that something.

Exit 0 whether or not the file changed; the caller commits only on a diff.
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import date

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "data" / "config.json"


def bump(today: date) -> bool:
    """Set `as_of` to ``today``. Returns whether the file changed."""
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    new = today.isoformat()
    if config.get("as_of") == new:
        return False
    config["as_of"] = new
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    changed = bump(date.today())
    print(f"[bump_as_of.py] {'bumped' if changed else 'already current'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
