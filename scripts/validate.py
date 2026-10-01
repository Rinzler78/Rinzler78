#!/usr/bin/env python3
"""
validate.py — Checks the integrity of the artifacts produced by generate.py.

Checks:
1. All local resources (`<img src="..."`, `srcset="..."`) referenced
   in README.md point to a file that exists.
2. All SVGs in `assets/svg/` are well-formed XML.
3. The tile grid rules (ADR-015): no SVG root declares `width="100%"`, every
   root declares a width and a height, and no text in a front page tile is
   set under 20 units.

Exit 0 if everything is OK, non-zero otherwise. Used by the pre-commit hook.
"""

from __future__ import annotations

import pathlib
import re
import sys

import defusedxml.ElementTree as ET  # secure XML parsing (bandit B314/B405)

REPO = pathlib.Path(__file__).resolve().parent.parent
SVG_DIR = REPO / "assets" / "svg"

# src/srcset/href attributes + markdown links `](target)`. Refs are resolved
# relative to each document's own directory (pages/ use ../assets/... paths).
_REF_RE = re.compile(r'(?:src|srcset|href)\s*=\s*"([^"]+)"|\]\(([^)]+)\)')
_SKIP_PREFIXES = ("mailto:", "tel:", "data:", "#", "//")


def _docs() -> list[pathlib.Path]:
    docs = [REPO / "README.md", REPO / "README.en.md"]
    docs += sorted((REPO / "pages").rglob("*.md"))
    return docs


def validate_readme_refs() -> list[str]:
    """Return the list of missing local resources across READMEs and pages."""
    missing: list[str] = []

    for doc in _docs():
        if not doc.exists():
            missing.append(f"{doc.name} not found: {doc}")
            continue
        text = doc.read_text(encoding="utf-8")
        seen: set[str] = set()
        for match in _REF_RE.finditer(text):
            path_str = (match.group(1) or match.group(2) or "").strip()
            path_str = path_str.split("#", 1)[0]  # drop anchor fragment
            if not path_str or path_str in seen:
                continue
            seen.add(path_str)
            if "://" in path_str or path_str.startswith(_SKIP_PREFIXES):
                continue
            rel_name = doc.relative_to(REPO)
            target = (doc.parent / path_str).resolve()
            try:
                target.relative_to(REPO.resolve())
            except ValueError:
                missing.append(f"{rel_name}: {path_str} (outside repo: {target})")
                continue
            if not target.exists():
                missing.append(f"{rel_name}: {path_str}  →  not found")
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


# Front page tiles (scripts/tiles.py): the 20-unit text floor applies to them.
TILE_PREFIXES = ("identity", "figures", "oss-", "skills-", "calendar-")
MIN_TILE_FONT = 20.0


def svg_rule_errors(markup: str, tile: bool) -> list[str]:
    """The grid rules one SVG breaks; ``tile`` adds the text-size floor."""
    root = ET.fromstring(markup)
    errors = []
    width, height = root.get("width"), root.get("height")
    if width is not None and width.strip().endswith("%"):
        errors.append(f'root width="{width}": use a fixed width')
    if width is None or height is None:
        errors.append("root must declare both a width and a height")
    if tile:
        for el in root.iter():
            size = el.get("font-size")
            if size is not None and float(size) < MIN_TILE_FONT:
                errors.append(f"text at font-size {size}, under {MIN_TILE_FONT:g}")
    return errors


def validate_svg_rules() -> list[str]:
    """Grid rule violations across every generated SVG."""
    errors: list[str] = []
    for svg in sorted(SVG_DIR.rglob("*.svg")):
        tile = svg.name.startswith(TILE_PREFIXES)
        for error in svg_rule_errors(svg.read_text(encoding="utf-8"), tile):
            errors.append(f"{svg.relative_to(REPO)}  →  {error}")
    return errors


def main() -> int:
    missing_refs = validate_readme_refs()
    bad_svgs = validate_svgs()
    if not bad_svgs:
        bad_svgs = validate_svg_rules()

    if missing_refs:
        print(
            f"[validate.py] ✗ {len(missing_refs)} missing resource(s) in READMEs:",
            file=sys.stderr,
        )
        for m in missing_refs:
            print(f"    - {m}", file=sys.stderr)

    if bad_svgs:
        print(f"[validate.py] ✗ {len(bad_svgs)} SVG error(s):", file=sys.stderr)
        for e in bad_svgs:
            print(f"    - {e}", file=sys.stderr)

    if missing_refs or bad_svgs:
        print("[validate.py] FAILED", file=sys.stderr)
        return 1

    print("[validate.py] OK — README references and SVGs validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
