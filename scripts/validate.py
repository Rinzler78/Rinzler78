#!/usr/bin/env python3
"""
validate.py — Vérifie l'intégrité des artéfacts générés par generate.py.

Contrôles :
1. Toutes les ressources locales (`<img src="..."`, `srcset="..."`) référencées
   dans README.md pointent vers un fichier qui existe.
2. Tous les SVG de `assets/svg/` sont XML well-formed.

Exit 0 si tout est OK, non-zero sinon. Utilisé par le pre-commit hook.
"""
from __future__ import annotations

import pathlib
import re
import sys

import defusedxml.ElementTree as ET  # secure XML parsing (bandit B314/B405)

REPO = pathlib.Path(__file__).resolve().parent.parent
README = REPO / "README.md"
SVG_DIR = REPO / "assets" / "svg"


def validate_readme_refs() -> list[str]:
    """Retourne la liste des ressources locales manquantes (vide si OK)."""
    if not README.exists():
        return [f"README.md introuvable : {README}"]

    text = README.read_text(encoding="utf-8")
    # Capture src="..." et srcset="..."
    pattern = re.compile(r'(?:src|srcset)\s*=\s*"([^"]+)"')

    missing: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        path_str = match.group(1).strip()
        if not path_str or path_str in seen:
            continue
        seen.add(path_str)

        # Ignorer URLs distantes (http/https/data/mailto) et ancres
        if (
            "://" in path_str
            or path_str.startswith(("mailto:", "data:", "#", "//"))
        ):
            continue

        # Résolution relative au repo
        target = (REPO / path_str).resolve()
        try:
            target.relative_to(REPO.resolve())
        except ValueError:
            # Hors du repo — on signale par sécurité
            missing.append(f"{path_str} (hors repo : {target})")
            continue

        if not target.exists():
            rel = target.relative_to(REPO.resolve())
            missing.append(f"{path_str}  →  attendu : {rel}")
    return missing


def validate_svgs() -> list[str]:
    """Retourne la liste des SVG mal formés (vide si OK)."""
    if not SVG_DIR.exists():
        return ["assets/svg/ introuvable"]

    errors: list[str] = []
    for svg in sorted(SVG_DIR.glob("*.svg")):
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
            f"[validate.py] ✗ {len(missing_refs)} ressource(s) manquante(s) "
            "dans README.md :",
            file=sys.stderr,
        )
        for m in missing_refs:
            print(f"    - {m}", file=sys.stderr)

    if bad_svgs:
        print(f"[validate.py] ✗ {len(bad_svgs)} SVG mal formé(s) :", file=sys.stderr)
        for e in bad_svgs:
            print(f"    - {e}", file=sys.stderr)

    if missing_refs or bad_svgs:
        print("[validate.py] ÉCHEC", file=sys.stderr)
        return 1

    print("[validate.py] OK — README references and SVGs validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
