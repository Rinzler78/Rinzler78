#!/usr/bin/env python3
"""
validate.py — Checks the integrity of the artifacts produced by generate.py.

Checks:
1. All local resources (`<img src="..."`, `srcset="..."`) referenced
   in README.md point to a file that exists.
2. All SVGs in `assets/svg/` are well-formed XML.

Exit 0 if everything is OK, non-zero otherwise. Used by the pre-commit hook.
"""

from __future__ import annotations

import pathlib
import re
import sys

import defusedxml.ElementTree as ET  # secure XML parsing (bandit B314/B405)

REPO = pathlib.Path(__file__).resolve().parent.parent
READMES = [REPO / "README.md", REPO / "README.en.md"]
SVG_DIR = REPO / "assets" / "svg"


def validate_readme_refs() -> list[str]:
    """Return the list of missing local resources across all READMEs."""
    pattern = re.compile(r'(?:src|srcset)\s*=\s*"([^"]+)"')
    missing: list[str] = []

    for readme in READMES:
        if not readme.exists():
            missing.append(f"{readme.name} not found: {readme}")
            continue
        text = readme.read_text(encoding="utf-8")
        seen: set[str] = set()
        for match in pattern.finditer(text):
            path_str = match.group(1).strip()
            if not path_str or path_str in seen:
                continue
            seen.add(path_str)
            # Ignore remote URLs (http/https/data/mailto) and anchors
            if "://" in path_str or path_str.startswith(
                ("mailto:", "data:", "#", "//")
            ):
                continue
            target = (REPO / path_str).resolve()
            try:
                target.relative_to(REPO.resolve())
            except ValueError:
                missing.append(f"{readme.name}: {path_str} (outside repo: {target})")
                continue
            if not target.exists():
                rel = target.relative_to(REPO.resolve())
                missing.append(f"{readme.name}: {path_str}  →  expected: {rel}")
    return missing


def validate_svgs() -> list[str]:
    """Return the list of malformed SVGs (empty if OK)."""
    if not SVG_DIR.exists():
        return ["assets/svg/ not found"]

    errors: list[str] = []
    for svg in sorted(SVG_DIR.rglob("*.svg")):
        try:
            ET.parse(svg)
        except ET.ParseError as e:
            errors.append(f"{svg.relative_to(REPO)}  →  {e}")
    return errors


def main() -> int:
    missing_refs = validate_readme_refs()
    bad_svgs = validate_svgs()

    if missing_refs:
        print(
            f"[validate.py] ✗ {len(missing_refs)} missing resource(s) in READMEs:",
            file=sys.stderr,
        )
        for m in missing_refs:
            print(f"    - {m}", file=sys.stderr)

    if bad_svgs:
        print(f"[validate.py] ✗ {len(bad_svgs)} malformed SVG(s):", file=sys.stderr)
        for e in bad_svgs:
            print(f"    - {e}", file=sys.stderr)

    if missing_refs or bad_svgs:
        print("[validate.py] FAILED", file=sys.stderr)
        return 1

    print("[validate.py] OK — README references and SVGs validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
