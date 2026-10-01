"""Tech icons for the front page (ADR-016 section 4).

Two places show icons, with different constraints:

- **The icon band** heads the skills section. It is markdown, so it may load
  images: skillicons.dev serves the icons it has, and the others are drawn
  here on the same template (a 256-unit rounded square on ``BAND_BG``).
- **The skills tiles** are SVGs served through ``<img>``, which cannot load
  another image: every logo there is vendored path data (Devicon, MIT; Simple
  Icons, CC0) drawn in its brand color. A brand color below the 3:1 non-text
  contrast minimum on the tile falls back to the theme's ink — the monochrome
  variant both projects publish. A tech without a published logo gets an
  initials badge.

The map from tech to icon is ``data/icons.json``; only the files it names are
vendored under ``assets/icons/``.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from html import escape, unescape

import defusedxml.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parent.parent
ICON_DIR = REPO / "assets" / "icons"

SKILLICONS = "https://skillicons.dev/icons"
# skillicons.dev geometry: 256-unit icons on a 300-unit pitch.
BAND_ICON = 256
BAND_PITCH = 300
BAND_RADIUS = 60
BAND_LOGO = 160  # logo box inside a band icon, centered
BAND_BG = {"dark": "#242938", "light": "#F4F2ED"}
BAND_INK = {"dark": "#F4F2ED", "light": "#242938"}
# WCAG 2.1 SC 1.4.11: graphical objects need 3:1 against their background.
MIN_CONTRAST = 3.0
# The tiles' smallest text size (ADR-015): initials obey it too.
MIN_FONT = 20
# Advance width of a monospace glyph, in em: sizes the initials badge text.
_MONO_ADVANCE = 0.62
_MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"


@dataclass(frozen=True)
class IconSpec:
    tech_id: str
    kind: str  # "vendored" | "initials"
    color: str = ""
    view_box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    paths: tuple[str, ...] = field(default_factory=tuple)
    initials: str = ""


@dataclass(frozen=True)
class BandEntry:
    source: str  # "skillicons" | "local"
    key: str  # skillicons id, or the tech id drawn in-house


# --- Contrast -------------------------------------------------------------------


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio (1 to 21) between two six-digit hex colors."""
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ink_for(color: str, background: str, fallback: str) -> str:
    """The brand ``color`` when it reads on ``background``, else ``fallback``."""
    return color if contrast(color, background) >= MIN_CONTRAST else fallback


# --- Vendored files -------------------------------------------------------------


def _read_icon(rel: str) -> tuple[tuple[float, float, float, float], tuple[str, ...]]:
    root = ET.parse(ICON_DIR / f"{rel}.svg").getroot()
    box = [float(v) for v in root.get("viewBox", "").split()]
    if len(box) != 4:
        raise ValueError(f"icon {rel}: no viewBox")
    paths = tuple(
        str(el.get("d"))
        for el in root.iter()
        if el.tag.endswith("path") and el.get("d")
    )
    if not paths:
        raise ValueError(f"icon {rel}: no path")
    return (box[0], box[1], box[2], box[3]), paths


def tile_icon(tech_id: str, doc: dict) -> IconSpec:
    """The icon a skills tile draws for ``tech_id``; unknown ids fail."""
    entry = doc["techs"].get(tech_id)
    if entry is None:
        raise ValueError(f"no icon for tech {tech_id!r}: add it to data/icons.json")
    if "tile" not in entry:
        return IconSpec(tech_id, "initials", initials=entry["initials"])
    view_box, paths = _read_icon(entry["tile"])
    return IconSpec(tech_id, "vendored", entry["color"], view_box, paths)


def _t(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def initials_font_size(initials: str, size: float) -> float:
    """Largest mono size that fits ``initials`` in a ``size`` badge, floored."""
    fitting = size * 0.92 / (max(len(initials), 1) * _MONO_ADVANCE)
    return max(MIN_FONT, min(round(fitting, 1), round(size * 0.6, 1)))


def render(
    spec: IconSpec, x: float, y: float, size: float, fill: str, ink: dict
) -> str:
    """SVG fragment drawing ``spec`` in the ``size`` square at ``(x, y)``.

    ``fill`` colors a vendored logo; ``ink`` (``stroke``, ``text``, ``fill``)
    colors an initials badge.
    """
    if spec.kind == "initials":
        font = initials_font_size(spec.initials, size)
        room = size - 6
        natural = len(spec.initials) * _MONO_ADVANCE * font
        # At the 20-unit floor four letters overflow a small badge: tighten
        # the letter spacing instead of shrinking the text below 20.
        fit = (
            f' letter-spacing="{_t((room - natural) / len(spec.initials))}"'
            if natural > room
            else ""
        )
        return (
            f'<rect x="{_t(x + 1)}" y="{_t(y + 1)}" width="{_t(size - 2)}" '
            f'height="{_t(size - 2)}" rx="{_t(size * 0.24)}" fill="{ink["fill"]}" '
            f'stroke="{ink["stroke"]}" stroke-width="2"/>'
            f'<text x="{_t(x + size / 2)}" y="{_t(y + size / 2 + font * 0.36)}" '
            f'text-anchor="middle" font-family="{_MONO}" font-size="{_t(font)}" '
            f'font-weight="700" fill="{ink["text"]}"{fit}>'
            f"{escape(spec.initials)}</text>"
        )
    vx, vy, vw, vh = spec.view_box
    scale = size / max(vw, vh)
    dx = x + (size - vw * scale) / 2 - vx * scale
    dy = y + (size - vh * scale) / 2 - vy * scale
    body = "".join(f'<path d="{d}"/>' for d in spec.paths)
    return (
        f'<g transform="translate({_t(dx)},{_t(dy)}) scale({_t(scale)})" '
        f'fill="{fill}">{body}</g>'
    )


# --- Icon band ------------------------------------------------------------------


def band_entries(tech_ids: list[str], doc: dict) -> list[BandEntry]:
    """Band icons in tile order, one per logo, then the band-only tools.

    A skillicons.dev id wins over the vendored logo; techs with initials only
    stay out of the band (a row of letter badges says nothing at a glance).
    """
    ordered = list(tech_ids) + sorted(
        t for t, e in doc["techs"].items() if e.get("band_only") and t not in tech_ids
    )
    seen: set[str] = set()
    out: list[BandEntry] = []
    for tech_id in ordered:
        entry = doc["techs"].get(tech_id, {})
        if "band" in entry:
            item = BandEntry("skillicons", entry["band"])
            identity = f"skillicons:{entry['band']}"
        elif "tile" in entry:
            item = BandEntry("local", tech_id)
            identity = f"tile:{entry['tile']}"
        else:
            continue
        if identity not in seen:
            seen.add(identity)
            out.append(item)
    return out


def skillicons_url(ids: list[str], theme: str, per_line: int) -> str:
    return f"{SKILLICONS}?i={','.join(ids)}&theme={theme}&perline={per_line}"


def band_rows(items: list, per_line: int) -> list[list]:
    return [items[i : i + per_line] for i in range(0, len(items), per_line)]


def band_units(count: int) -> int:
    """Width, in skillicons units, of a band line of ``count`` icons."""
    return count * BAND_PITCH - (BAND_PITCH - BAND_ICON) if count else 0


def band_svg(
    tech_ids: list[str], doc: dict, theme: str, labels: dict | None = None
) -> str:
    """One line of in-house band icons on the skillicons.dev template."""
    bg, fallback = BAND_BG[theme], BAND_INK[theme]
    width = band_units(len(tech_ids))
    parts = []
    names = []
    for i, tech_id in enumerate(tech_ids):
        spec = tile_icon(tech_id, doc)
        x = i * BAND_PITCH
        parts.append(
            f'<rect x="{x}" y="0" width="{BAND_ICON}" height="{BAND_ICON}" '
            f'rx="{BAND_RADIUS}" fill="{bg}"/>'
        )
        offset = (BAND_ICON - BAND_LOGO) / 2
        fill = ink_for(spec.color, bg, fallback) if spec.color else fallback
        parts.append(render(spec, x + offset, offset, BAND_LOGO, fill, {}))
        names.append((labels or {}).get(tech_id, tech_id))
    aria = escape(unescape(", ".join(names)))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {BAND_ICON}" '
        f'width="{width}" height="{BAND_ICON}" role="img" aria-label="{aria}">'
        f"<title>{aria}</title>{''.join(parts)}</svg>"
    )
