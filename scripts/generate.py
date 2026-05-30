#!/usr/bin/env python3
"""
generate.py — Génère assets/svg/*.svg et README.md depuis data/*.json + scripts/templates/*.jinja.

Lance depuis n'importe où :
    python3 scripts/generate.py

Le script est aussi appelé par le pre-commit hook (voir scripts/install-hook.sh).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import date
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    sys.stderr.write(
        "[generate.py] jinja2 manquant. Installe-le avec :\n"
        "    pip install -r scripts/requirements.txt\n"
    )
    sys.exit(1)

# Bootstrap : rend le package `scripts` importable même lancé en
# `python3 scripts/generate.py` avec un interpréteur sans install editable
# (cas du pre-commit hook git-natif).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.view_builder import build_skills  # noqa: E402


REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
TEMPLATES = REPO / "scripts" / "templates"
SVG_OUT = REPO / "assets" / "svg"
README_OUT = REPO / "README.md"


_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")


def _escape_amp(obj: Any) -> Any:
    """Échappe récursivement `&` -> `&amp;` (idempotent : ne ré-échappe pas).

    Appliqué à toutes les strings des data au chargement. Le résultat est
    valide XML (utilisé dans les SVG) ET valide markdown (le moteur GitHub
    décode `&amp;` -> `&` à l'affichage). Pas de doublonnage si la string
    est déjà échappée.
    """
    if isinstance(obj, str):
        return _AMP_RE.sub("&amp;", obj)
    if isinstance(obj, dict):
        return {k: _escape_amp(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_escape_amp(x) for x in obj]
    return obj


def load_data() -> dict[str, Any]:
    """Charge les fichiers data/*.json et échappe les `&` pour usage XML/markdown."""
    raw = {
        "profile": json.loads((DATA / "profile.json").read_text(encoding="utf-8")),
        "domains": json.loads((DATA / "domains.json").read_text(encoding="utf-8")),
        "techs": json.loads((DATA / "techs.json").read_text(encoding="utf-8")),
        "experiences": json.loads(
            (DATA / "experiences.json").read_text(encoding="utf-8")
        ),
        "timeline": json.loads((DATA / "timeline.json").read_text(encoding="utf-8")),
        "projects": json.loads((DATA / "projects.json").read_text(encoding="utf-8")),
        "theme": json.loads((DATA / "theme.json").read_text(encoding="utf-8")),
        "content": json.loads((DATA / "content.json").read_text(encoding="utf-8")),
    }
    return _escape_amp(raw)


def enrich(data: dict[str, Any], today: date) -> dict[str, Any]:
    """Remplace `techs` brut par les Skills enrichis (hours + max/current).

    Les templates consomment des techs enrichis : chaque tech porte `since`,
    `until`, `score_max`, `level_max`, `score_current`, `level_current`
    dérivés des expériences (ADR-006). Voir scripts/view_builder.py.
    """
    data["techs"] = build_skills(
        data["techs"], data["experiences"], data["projects"], today
    )
    return data


def make_env(data: dict[str, Any]) -> Environment:
    """Crée l'environnement Jinja2 avec helpers exposés aux templates."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=False,  # SVG output : on contrôle ce qu'on écrit
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    techs = data["techs"]
    domains = data["domains"]
    projects = data["projects"]

    def techs_by_domain(domain_id: str) -> list[dict]:
        return [t for t in techs if t["domain"] == domain_id]

    def domain_by_id(domain_id: str) -> dict | None:
        return next((d for d in domains if d["id"] == domain_id), None)

    def tech_by_id(tech_id: str) -> dict | None:
        # cherche d'abord par id racine
        match = next((t for t in techs if t["id"] == tech_id), None)
        if match:
            return match
        # sinon cherche par id de version
        for t in techs:
            for v in t.get("versions", []):
                if v["id"] == tech_id:
                    return {**t, "version_info": v}
        return None

    def projects_by_category(category: str) -> list[dict]:
        return [p for p in projects if p.get("category") == category]

    def projects_highlighted() -> list[dict]:
        return [p for p in projects if p.get("highlight")]

    def domains_in_id_card() -> list[dict]:
        return sorted(
            [d for d in domains if d.get("show_in_id_card")],
            key=lambda d: d["order"],
        )

    # Palette key per derived level (ADR-006 vocabulary). Falls back to the
    # theme's level_colors block when present, else a sane default key.
    _LEVEL_PALETTE = {
        "expert": "accent",
        "advanced": "info",
        "professional": "info",
        "working": "text",
        "explored": "text_dim",
    }

    def level_color(level: str) -> str:
        override = (
            data["theme"].get("patterns", {}).get("table_row", {}).get("level_colors")
        )
        if override and level in override:
            return override[level]
        return _LEVEL_PALETTE.get(level, "text")

    def level_label(level: str) -> str:
        mapping = {
            "expert": "Expert",
            "advanced": "Advanced",
            "professional": "Professional",
            "working": "Working knowledge",
            "explored": "Explored",
        }
        return mapping.get(level, level.title())

    def xml_escape(s: str | None) -> str:
        """Échappe &, <, > pour usage dans contenu SVG (entre balises)."""
        if s is None:
            return ""
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    env.filters["xml"] = xml_escape

    env.globals.update(data)
    env.globals["techs_by_domain"] = techs_by_domain
    env.globals["domain_by_id"] = domain_by_id
    env.globals["tech_by_id"] = tech_by_id
    env.globals["projects_by_category"] = projects_by_category
    env.globals["projects_highlighted"] = projects_highlighted
    env.globals["domains_in_id_card"] = domains_in_id_card
    env.globals["level_color"] = level_color
    env.globals["level_label"] = level_label
    return env


# (template_filename, output_filename, extra_context)
SVG_TARGETS: list[tuple[str, str, dict]] = [
    ("header.svg.jinja", "header.svg", {}),
    ("stack_summary.svg.jinja", "stack-summary.svg", {}),
    ("activity_stats.svg.jinja", "activity-stats.svg", {}),
    ("timeline_mini.svg.jinja", "timeline-mini.svg", {}),
    ("featured_projects.svg.jinja", "featured-projects.svg", {}),
    ("modes.svg.jinja", "modes.svg", {}),
    ("map.svg.jinja", "map.svg", {}),
]


def main() -> int:
    data = load_data()
    data = enrich(data, date.today())
    env = make_env(data)
    SVG_OUT.mkdir(parents=True, exist_ok=True)

    print(f"[generate.py] data : {len(data)} concepts chargés")
    print(f"[generate.py] cible : {SVG_OUT}/, {README_OUT}")
    print()

    # SVG single-output
    for tpl_name, out_name, ctx in SVG_TARGETS:
        tpl = env.get_template(tpl_name)
        result = tpl.render(**ctx)
        (SVG_OUT / out_name).write_text(result, encoding="utf-8")
        print(f"  ✓ assets/svg/{out_name}")

    # README
    readme_tpl = env.get_template("README.md.jinja")
    result = readme_tpl.render()
    README_OUT.write_text(result, encoding="utf-8")
    print(f"  ✓ README.md")

    print()
    print("[generate.py] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
