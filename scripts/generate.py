#!/usr/bin/env python3
"""
generate.py — Generates assets/svg/*.svg and README.md
from data/*.json + scripts/templates/*.jinja.

Run from anywhere:
    python3 scripts/generate.py

The script is also called by the pre-commit hook (see scripts/install-hook.sh).
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
        "[generate.py] jinja2 missing. Install it with:\n"
        "    pip install -r scripts/requirements.txt\n"
    )
    sys.exit(1)

# Bootstrap: makes the `scripts` package importable even when run as
# `python3 scripts/generate.py` with an interpreter without an editable install
# (the case of the native-git pre-commit hook).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import charts  # noqa: E402
from scripts.font_outline import outline_text  # noqa: E402
from scripts.translate import CACHE, localize_data  # noqa: E402
from scripts.view_builder import (  # noqa: E402
    build_domain_year_hours,
    build_profile_as_code,
    build_signature_arc,
    build_skills,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
TEMPLATES = REPO / "scripts" / "templates"
SVG_OUT = REPO / "assets" / "svg"
FONT_DISPLAY = str(REPO / "assets" / "fonts" / "Fraunces-Display.ttf")
README_OUT = REPO / "README.md"
README_EN_OUT = REPO / "README.en.md"
PAGES_OUT = REPO / "pages"
PAGE_TEMPLATES = [
    "stack.md.jinja",
    "journey.md.jinja",
    "projects.md.jinja",
    "working-with-me.md.jinja",
]


_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")


def _escape_amp(obj: Any) -> Any:
    """Recursively escapes `&` -> `&amp;` (idempotent: does not re-escape).

    Applied to all data strings at load time. The result is valid XML
    (used in the SVGs) AND valid markdown (the GitHub engine decodes
    `&amp;` -> `&` on display). No doubling if the string is already
    escaped.
    """
    if isinstance(obj, str):
        return _AMP_RE.sub("&amp;", obj)
    if isinstance(obj, dict):
        return {k: _escape_amp(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_escape_amp(x) for x in obj]
    return obj


def reference_date() -> date:
    """The committed date the whole derivation runs against.

    Hours accrue for every ongoing experience, so scores, levels and row order
    move with the reference date. Reading the clock would make the same
    revision regenerate differently tomorrow; `data/config.json` pins it, and
    the weekly refresh workflow bumps it deliberately.
    """
    config = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
    return date.fromisoformat(config["as_of"])


def load_data() -> dict[str, Any]:
    """Loads the data/*.json files and escapes `&` for XML/markdown use."""
    raw = {
        "profile": json.loads((DATA / "profile.json").read_text(encoding="utf-8")),
        "domains": json.loads((DATA / "domains.json").read_text(encoding="utf-8")),
        "techs": json.loads((DATA / "techs.json").read_text(encoding="utf-8")),
        "experiences": json.loads(
            (DATA / "experiences.json").read_text(encoding="utf-8")
        ),
        "timeline": json.loads((DATA / "timeline.json").read_text(encoding="utf-8")),
        "projects": json.loads((DATA / "projects.json").read_text(encoding="utf-8")),
        "services": json.loads((DATA / "services.json").read_text(encoding="utf-8")),
        "modes": json.loads((DATA / "modes.json").read_text(encoding="utf-8")),
        "methodology": json.loads(
            (DATA / "methodology.json").read_text(encoding="utf-8")
        ),
        "theme": json.loads((DATA / "theme.json").read_text(encoding="utf-8")),
        "content": json.loads((DATA / "content.json").read_text(encoding="utf-8")),
    }
    return _escape_amp(raw)


def enrich(data: dict[str, Any], today: date) -> dict[str, Any]:
    """Replaces raw `techs` with the enriched Skills (hours + max/current).

    The templates consume enriched techs: each tech carries `since`,
    `until`, `score_max`, `level_max`, `score_current`, `level_current`
    derived from the experiences (ADR-006). See scripts/view_builder.py.
    """
    data["techs"] = build_skills(
        data["techs"], data["experiences"], data["projects"], today
    )
    data["profile_as_code"] = build_profile_as_code(
        data["profile"], data["techs"], data["services"]
    )
    data["signature_arc"] = build_signature_arc(data["domains"])
    # The journey series: exposure hours per domain, per year. Derived from the
    # same hours that produce the scores, so the timeline and the numbers can
    # never disagree.
    data["domain_years"] = build_domain_year_hours(
        data["techs"], data["experiences"], data["projects"], today
    )
    return data


def make_env(data: dict[str, Any]) -> Environment:
    """Creates the Jinja2 environment with helpers exposed to the templates."""
    # autoescape=False is intentional: static SVG/Markdown generator,
    # not an HTML server. The data is self-authored (no external input),
    # `&` is escaped globally (_escape_amp), a raw `<`/`>` in the data
    # would produce malformed XML that validate.py rejects (well-formedness).
    # Autoescaping would break the intended SVG tags. False positive B701 in
    # a static-generation context.
    env = Environment(  # nosec B701
        loader=FileSystemLoader(TEMPLATES),
        autoescape=False,
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
        # look first by root id
        match = next((t for t in techs if t["id"] == tech_id), None)
        if match:
            return match
        # otherwise look by version id
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
        """Escapes &, <, > for use in SVG content (between tags)."""
        if s is None:
            return ""
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    env.filters["xml"] = xml_escape

    def outline(text: str, size: float) -> dict:
        """Outline display text (name, arc labels) to an SVG path — ADR-007."""
        return outline_text(text, FONT_DISPLAY, size)

    env.globals.update(data)
    env.globals["outline"] = outline
    env.globals["techs_by_domain"] = techs_by_domain
    env.globals["domain_by_id"] = domain_by_id
    env.globals["tech_by_id"] = tech_by_id
    env.globals["projects_by_category"] = projects_by_category
    env.globals["projects_highlighted"] = projects_highlighted
    env.globals["domains_in_id_card"] = domains_in_id_card
    env.globals["level_color"] = level_color
    env.globals["level_label"] = level_label

    # --- charts (ADR-009) -------------------------------------------------
    # Series colors and captions are injected here rather than living in
    # scripts/charts.py: the palette flips per render pass, and the captions
    # are display copy that must follow the language of the page.
    def _chart_ink() -> dict[str, str]:
        pal = data["theme"]["palette"]
        return {
            "text": pal["text"],
            "muted": pal["text_muted"],
            "dim": pal["text_dim"],
            "surface": pal["bg"],
            "track": pal["panel_alt"],
        }

    def _series_colors() -> dict[str, str]:
        theme = data["theme"]
        light = theme.get("series_light", theme["series"])
        is_light = data["theme"]["palette"] is theme.get("palette_light")
        return light if is_light else theme["series"]

    def _domain_labels() -> dict[str, str]:
        return {d["id"]: d["label"] for d in data["domains"]}

    def chart_journey_share(caption: str = "") -> str:
        return charts.stacked_area(
            data["domain_years"],
            _series_colors(),
            _chart_ink(),
            labels=_domain_labels(),
            caption=caption,
        )

    def chart_domain_split(caption: str = "", center_label: str = "") -> str:
        totals = {k: sum(v.values()) for k, v in data["domain_years"].items()}
        grand = sum(totals.values())
        if not grand:
            return charts.donut([], _series_colors(), _chart_ink(), caption=caption)
        shares = sorted(
            ((k, round(v / grand * 100, 1)) for k, v in totals.items()),
            key=lambda kv: -kv[1],
        )
        # Rounding each share independently rarely lands on 100; the donut
        # refuses a set that does not make a whole, so the remainder goes to
        # the smallest slice where it is least visible.
        drift = round(100.0 - sum(pct for _, pct in shares), 1)
        shares[-1] = (shares[-1][0], round(shares[-1][1] + drift, 1))
        return charts.donut(
            shares,
            _series_colors(),
            _chart_ink(),
            labels=_domain_labels(),
            caption=caption,
            center_value=str(len(shares)),
            center_label=center_label,
        )

    def chart_top_skills(count: int = 8, caption: str = "") -> str:
        ranked = sorted(
            (t for t in data["techs"] if t.get("score_current")),
            key=lambda t: -t["score_current"],
        )[:count]
        return charts.bar_rows(
            [(t["label"], t["score_current"]) for t in ranked],
            data["theme"]["palette"]["accent"],
            _chart_ink(),
            caption=caption,
        )

    env.globals["chart_journey_share"] = chart_journey_share
    env.globals["chart_domain_split"] = chart_domain_split
    env.globals["chart_top_skills"] = chart_top_skills

    def _chip_ink() -> dict[str, str]:
        pal = data["theme"]["palette"]
        return {
            "text": pal["text"],
            "muted": pal["text_muted"],
            "dim": pal["text_dim"],
            "surface": pal["panel"],
            "track": pal["panel_alt"],
            "border": pal["border"],
            # White reads on both accent steps; the chip fill is the accent,
            # never a pale tint, so a fixed value is safe here.
            "on_accent": "#ffffff",
        }

    def contact_chip(label: str, value: str = "", primary: bool = False) -> str:
        return charts.chip(
            label,
            _chip_ink(),
            accent=data["theme"]["palette"]["accent"],
            primary=primary,
            value=value,
        )

    env.globals["contact_chip"] = contact_chip
    env.globals["contact_chips"] = contact_targets(data)
    return env


# (template_filename, output_filename, extra_context)
SVG_TARGETS: list[tuple[str, str, dict]] = [
    ("header.svg.jinja", "header.svg", {}),
    ("stack_summary.svg.jinja", "stack-summary.svg", {}),
    ("core_expertise.svg.jinja", "core-expertise.svg", {}),
    ("services.svg.jinja", "services.svg", {}),
    ("methodology.svg.jinja", "methodology.svg", {}),
    ("activity_stats.svg.jinja", "activity-stats.svg", {}),
    ("timeline_mini.svg.jinja", "timeline-mini.svg", {}),
    ("featured_projects.svg.jinja", "featured-projects.svg", {}),
    ("modes.svg.jinja", "modes.svg", {}),
    # Charts (ADR-009): one standard form per question, each doubled by prose
    # in the page that embeds it.
    ("journey_share.svg.jinja", "journey-share.svg", {}),
    ("domain_split.svg.jinja", "domain-split.svg", {}),
    ("top_skills.svg.jinja", "top-skills.svg", {}),
]


def contact_targets(data: dict[str, Any]) -> list[dict[str, str]]:
    """Resolve each declared contact chip to its label, value and href.

    Labels are display copy and live in `content.json`; the addresses stay in
    `profile.json`, so neither is duplicated. A chip whose id resolves to
    nothing is dropped rather than rendered empty — an empty pill on the
    contact row reads as a broken link.
    """
    contacts = data["profile"]["contacts"]
    links = data["profile"]["links"]
    digits = contacts["phone"].replace("+", "").replace(" ", "")
    resolved = {
        "email": (contacts["email_pro"], f"mailto:{contacts['email_pro']}"),
        "phone": (contacts["phone"], f"tel:+{digits}"),
        "whatsapp": ("", f"https://wa.me/{digits}"),
        "linkedin": ("", links.get("linkedin", "")),
        "malt": ("", links.get("malt", "")),
        "pypi": ("", links.get("pypi", "")),
        "discord": ("", links.get("discord", "")),
        "twitter": ("", links.get("twitter", "")),
        "youtube": ("", links.get("youtube", "")),
        "github": ("", links.get("github", "")),
    }
    out: list[dict[str, str]] = []
    for spec in data["content"]["connect"]["chips"]:
        value, href = resolved.get(spec["id"], ("", ""))
        if not href:
            continue
        out.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "value": value,
                "href": href,
                "primary": spec.get("primary", False),
            }
        )
    return out


def _render_svgs(env: Environment, out_dir: pathlib.Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for tpl_name, out_name, ctx in SVG_TARGETS:
        result = env.get_template(tpl_name).render(**ctx)
        (out_dir / out_name).write_text(result, encoding="utf-8")
    # Contact chips: one SVG per chip, because an SVG served in an <img>
    # carries a single link and the row has to be clickable per item.
    for spec in env.globals["contact_chips"]:
        svg = env.globals["contact_chip"](spec["label"], spec["value"], spec["primary"])
        (out_dir / f"chip-{spec['id']}.svg").write_text(svg, encoding="utf-8")


def _render_both_palettes(env: Environment, theme: dict, svg_dir: pathlib.Path) -> None:
    """Render the SVG set twice — light-first: light default + dark/ override."""
    dark = theme["palette"]
    light = theme.get("palette_light", dark)
    theme["palette"] = light
    _render_svgs(env, svg_dir)  # light is primary → root dir
    theme["palette"] = dark
    _render_svgs(env, svg_dir / "dark")  # dark is the prefers-color-scheme override
    theme["palette"] = light  # restore: README badges use the light/default palette


def _render_pages(
    env: Environment, svg: str, root: str, out_dir: pathlib.Path, lang: str
) -> None:
    """Render the detail pages for one language (ADR-008)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for tpl in PAGE_TEMPLATES:
        result = env.get_template(tpl).render(svg=svg, root=root, lang=lang)
        (out_dir / tpl[: -len(".jinja")]).write_text(result, encoding="utf-8")


def main() -> int:
    raw = load_data()
    # EN data: localize the translatable fields from the committed cache, then
    # re-escape (`&` in English values) — _escape_amp is idempotent.
    as_of = reference_date()
    en_data = enrich(_escape_amp(localize_data(raw, CACHE)), as_of)
    fr_data = enrich(raw, as_of)

    env_fr = make_env(fr_data)
    env_en = make_env(en_data)

    print(f"[generate.py] data: {len(fr_data)} concepts loaded")
    print("[generate.py] target: assets/svg/{,dark,en,en/dark}, README(.en).md")
    print()

    # 4 SVG sets: fr×{dark,light} and en×{dark,light}.
    _render_both_palettes(env_fr, fr_data["theme"], SVG_OUT)
    _render_both_palettes(env_en, en_data["theme"], SVG_OUT / "en")
    print(f"  ✓ assets/svg/(dark|en|en/dark)/*.svg ({len(SVG_TARGETS)} × 4)")

    # FR README (light default, dark via <picture>) + reciprocal EN link.
    README_OUT.write_text(
        env_fr.get_template("README.md.jinja").render(svg="", lang="fr"),
        encoding="utf-8",
    )
    README_EN_OUT.write_text(
        env_en.get_template("README.md.jinja").render(svg="en/", lang="en"),
        encoding="utf-8",
    )
    print("  ✓ README.md + README.en.md")

    # Detail pages (ADR-008): README is the concise front, the deep content
    # lives in linked pages, generated for FR (pages/) and EN (pages/en/).
    _render_pages(env_fr, svg="", root="../", out_dir=PAGES_OUT, lang="fr")
    _render_pages(env_en, svg="en/", root="../../", out_dir=PAGES_OUT / "en", lang="en")
    print(f"  ✓ pages/(en/){{{', '.join(t[:-6] for t in PAGE_TEMPLATES)}}}")

    print()
    print("[generate.py] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
