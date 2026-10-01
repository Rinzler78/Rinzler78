"""Front page v2 tiles: SVG panels on one unit grid (ADR-015).

Every tile shares one grid: a half tile is 590 units wide and is embedded at
415 px, a full tile 1,200 units at 834 px, so every tile renders at one scale
(about 0.70) and two half tiles side by side on desktop stack on a phone. The
20-unit gap between two half tiles is drawn inside each tile: 10 transparent
units on every side of the panel. Every root declares its width and height;
no text is set under 20 units (12 px once a half tile stacks at 360 px).

Only the name, tile titles and large figures are outlined to paths in Inter
Display (ADR-007 mechanism); every other text uses a system-safe stack.

Input is the page view of ``scripts.front.build_front``; output is markup.
"""

from __future__ import annotations

import pathlib
from datetime import date, timedelta
from html import unescape

from scripts import icons
from scripts.charts import escape
from scripts.font_outline import outline_text
from scripts.front import bar_fraction

REPO = pathlib.Path(__file__).resolve().parent.parent
FONT = str(REPO / "assets" / "fonts" / "InterDisplay-ExtraBold.ttf")

FULL, HALF, INSET = 1200, 590, 10
EMBED_FULL, EMBED_HALF = 834, 415
PAD = 40
X0 = INSET + PAD
WIDTH = HALF - 2 * INSET - 2 * PAD
RIGHT = X0 + WIDTH
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
MIN_FS = 20
TITLE_FS = 34
# Advance-width estimates, in em, for text measured without font metrics
# (GitHub serves the SVG without any web font). Generous: too wide only pads.
SANS_ADVANCE = 0.56
MONO_ADVANCE = 0.62

IDENTITY_H = 480
OSS_H = 440
ICON = 48
ROW = 100
ALSO_ICON = 24
ALSO_LINE = 38
CAL_YEAR = 118
OPACITY = {1: 0.35, 2: 0.55, 3: 0.78, 4: 1.0}


class LayoutError(ValueError):
    """Content does not fit its tile: fail the build, never ship a clip."""


# --- Primitives -------------------------------------------------------------------


def _t(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def text(x, y, s, size, fill, weight=400, family=SANS, anchor="start", extra=""):
    if size < MIN_FS:
        raise LayoutError(f"font {size} under the {MIN_FS}-unit floor: {s}")
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (
        f'<text x="{_t(x)}" y="{_t(y)}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}"{a}{extra}>{escape(s)}</text>'
    )


def mono(x, y, s, fill, size=20, weight=500, anchor="start"):
    return text(x, y, s, size, fill, weight, MONO, anchor)


def width_of(s: str, size: float, advance: float = SANS_ADVANCE) -> float:
    return len(unescape(s)) * size * advance


def outline(x, y, s, size, fill, anchor="start", max_width=None):
    """Display text outlined to one path; shrinks to ``max_width`` (floor 20).

    The data bag reaches here with ``&`` escaped once; glyphs are drawn from
    the plain text.
    """
    s = unescape(s)
    o = outline_text(s, FONT, size)
    if max_width and o["width"] > max_width:
        size = max(MIN_FS, size * max_width / o["width"])
        o = outline_text(s, FONT, size)
    shift = {"start": 0, "middle": o["width"] / 2, "end": o["width"]}[anchor]
    return (
        f'<path transform="translate({_t(x - shift)},{_t(y)})" fill="{fill}" '
        f'd="{o["path"]}"/>',
        o["width"],
    )


def wrap(s: str, max_width: float, size: float, advance=SANS_ADVANCE) -> list[str]:
    """Greedy word wrap by estimated width."""
    lines: list[str] = []
    for word in s.split():
        if lines and width_of(f"{lines[-1]} {word}", size, advance) <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def wrap_items(items: list[str], max_width: float, size: float) -> list[str]:
    """Join items with a middle dot, breaking lines between items only."""
    lines: list[str] = []
    for item in items:
        candidate = f"{lines[-1]} · {item}" if lines else item
        if lines and width_of(candidate, size, MONO_ADVANCE) <= max_width:
            lines[-1] = candidate
        else:
            lines.append(item)
    return lines


def wrap_command(s: str, max_width: float, size: float = 20) -> list[str]:
    """Break a shell command after a space or a slash, monospace widths."""
    per_line = int(max_width // (size * MONO_ADVANCE))
    lines, rest = [], s
    while len(rest) > per_line:
        cut = max(rest.rfind(" ", 0, per_line), rest.rfind("/", 0, per_line))
        cut = cut + 1 if cut > 0 else per_line
        lines.append(rest[:cut].rstrip())
        rest = rest[cut:]
    return [*lines, rest]


def frame(w: int, h: int, body: str, pal: dict, aria: str) -> str:
    """A rounded panel inset by ``INSET``; the root carries width and height."""
    pw, ph = w - 2 * INSET, h - 2 * INSET
    a = escape(aria)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{a}">'
        f"<title>{a}</title>"
        '<defs><pattern id="dots" width="24" height="24" '
        'patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1.3" fill="{pal["dot"]}"/></pattern></defs>'
        f'<rect x="{INSET + 0.5}" y="{INSET + 0.5}" width="{pw - 1}" '
        f'height="{ph - 1}" rx="22" fill="{pal["panel"]}" stroke="{pal["border"]}"/>'
        f'<rect x="{INSET + 1}" y="{INSET + 1}" width="{pw - 2}" height="{ph - 2}" '
        f'rx="21" fill="url(#dots)"/>{body}</svg>\n'
    )


def header(eyebrow: str, title: str, pal: dict) -> tuple[str, float]:
    """Mono eyebrow and outlined title; returns the markup and the title y."""
    body = mono(X0, 70, eyebrow, pal["dim"])
    body += outline(X0, 120, title, TITLE_FS, pal["text"], max_width=WIDTH)[0]
    return body, 120


def _line(x1, y1, x2, y2, color, width=2) -> str:
    return (
        f'<line x1="{_t(x1)}" y1="{_t(y1)}" x2="{_t(x2)}" y2="{_t(y2)}" '
        f'stroke="{color}" stroke-width="{width}"/>'
    )


# --- Identity -------------------------------------------------------------------


def identity_tile(view: dict, pal: dict) -> str:
    v = view["identity"]
    b = mono(X0, 86, v["prompt"], pal["dim"], 22)
    label_w = width_of(v["status"], 23)
    pill_w = 46 + label_w + 22
    px = RIGHT - pill_w
    if px < X0 + width_of(v["prompt"], 22, MONO_ADVANCE) + 16:
        raise LayoutError("identity: the status pill overlaps the prompt")
    b += (
        f'<rect x="{_t(px)}" y="56" width="{_t(pill_w)}" height="44" rx="22" '
        f'fill="none" stroke="{pal["accent"]}" stroke-width="2"/>'
        f'<circle cx="{_t(px + 26)}" cy="78" r="7" fill="{pal["accent"]}"/>'
    )
    b += text(px + 44, 86, v["status"], 23, pal["accent"], 700)
    b += outline(X0, 180, v["name"], 64, pal["text"], max_width=WIDTH)[0]
    y = 232
    for line in v["role_lines"]:
        if width_of(line, 28) > WIDTH:
            raise LayoutError(f"identity: role line too wide: {line}")
        b += text(X0, y, line, 28, pal["text"], 600)
        y += 38
    b += mono(X0, y + 12, v["arc"], pal["muted"], 21)
    b += _line(X0, y + 46, RIGHT, y + 46, pal["border"])
    b += mono(X0, y + 90, f"// {v['since']}", pal["dim"])
    b += mono(X0, y + 122, f"// {v['location']}", pal["dim"])
    if y + 122 > IDENTITY_H - INSET - 20:
        raise LayoutError("identity: content overflows the tile")
    return frame(HALF, IDENTITY_H, b, pal, v["aria"])


def figures_tile(view: dict, pal: dict) -> str:
    v = view["figures"]
    b = mono(X0, 86, v["prompt"], pal["dim"], 22)
    col = WIDTH / 2
    for i, (value, label, extra) in enumerate(v["cells"]):
        cx = X0 + (i % 2) * col + (24 if i % 2 else 0)
        fy = 196 + (i // 2) * 164
        b += outline(cx, fy, value, 64, pal["accent"], max_width=col - 40)[0]
        b += text(cx, fy + 40, label, 21, pal["muted"], 500)
        if extra:
            b += text(cx, fy + 68, extra, 21, pal["muted"], 500)
        for line in (label, extra):
            if width_of(line, 21) > col - 30:
                raise LayoutError(f"figures: label too wide: {line}")
    b += _line(X0 + col, 130, X0 + col, IDENTITY_H - 60, pal["border"], 1)
    b += _line(X0, 290, RIGHT, 290, pal["border"], 1)
    return frame(HALF, IDENTITY_H, b, pal, v["aria"])


# --- Open source ----------------------------------------------------------------


def oss_tile(project: dict, pal: dict) -> str:
    eyebrow = project["registry"].lower()
    if project["legacy"]:
        eyebrow += f" · {project['legacy']}"
    b = mono(X0, 70, eyebrow, pal["dim"])
    b += outline(X0, 120, project["name"], TITLE_FS, pal["text"], max_width=WIDTH)[0]
    y = 168
    summary = wrap(project["summary"], WIDTH, 21)
    if len(summary) > 3:
        raise LayoutError(f"oss {project['id']}: summary longer than three lines")
    for line in summary:
        b += text(X0, y, line, 21, pal["text"])
        y += 30
    y += 12
    techs = wrap_items(project["techs"], WIDTH, 20)
    for line in techs[:2]:
        b += mono(X0, y, line, pal["accent"], weight=600)
        y += 28
    command = wrap_command(project["command"], WIDTH)
    cy = OSS_H - INSET - 34 - 28 * (len(command) - 1)
    if cy < y + 10:
        raise LayoutError(f"oss {project['id']}: content overflows the tile")
    for i, line in enumerate(command):
        b += mono(X0, cy + 28 * i, line, pal["muted"])
    return frame(HALF, OSS_H, b, pal, project["aria"])


# --- Skills ---------------------------------------------------------------------


def _icon(spec, x, y, size, pal) -> str:
    fill = icons.ink_for(spec.color, pal["panel"], pal["text"]) if spec.color else ""
    ink = {"stroke": pal["accent"], "text": pal["accent"], "fill": pal["panel"]}
    return icons.render(spec, x, y, size, fill, ink)


def _bar_row(row: dict, y: float, pal: dict, ticks: list[float]) -> str:
    b = _icon(row["icon"], X0, y - 38, ICON, pal)
    if width_of(row["label"], 22) > WIDTH - ICON - 12:
        raise LayoutError(f"skills: label too wide: {row['label']}")
    b += text(X0 + ICON + 12, y, row["label"], 22, pal["text"], 600)
    level = row["level"] + (" ◆" if row["evidence"] else "")
    meta = f"{row['hours_text']} · "
    # The meta line starts under the icon: the label line is the one that
    # needs the icon beside it, and the meta line needs the width.
    tx = X0
    b += (
        f'<text x="{_t(tx)}" y="{_t(y + 30)}" font-family="{MONO}" font-size="20" '
        f'font-weight="500" fill="{pal["muted"]}">{escape(meta)}'
        f'<tspan fill="{pal["accent"]}" font-weight="700">{escape(level)}</tspan>'
        "</text>"
    )
    period_fill = pal["accent"] if row["active"] else pal["dim"]
    b += mono(RIGHT, y + 30, row["period"], period_fill, anchor="end")
    used = width_of(meta + level, 20, MONO_ADVANCE) + width_of(
        row["period"], 20, MONO_ADVANCE
    )
    if used > RIGHT - tx - 12:
        raise LayoutError(f"skills: meta line too wide for {row['label']}")
    yb = y + 46
    b += (
        f'<rect x="{X0}" y="{_t(yb)}" width="{WIDTH}" height="8" rx="4" '
        f'fill="{pal["track"]}"/>'
        f'<rect x="{X0}" y="{_t(yb)}" width="{_t(WIDTH * row["fraction"])}" '
        f'height="8" rx="4" fill="{pal["accent"]}"/>'
    )
    for tick in ticks:
        b += _line(X0 + WIDTH * tick, yb - 3, X0 + WIDTH * tick, yb + 11, pal["panel"])
    return b


def _also_layout(rows: list[dict]) -> list[list[tuple[dict, float]]]:
    """Flow the compact chips into lines: (row, x) per chip."""
    lines: list[list[tuple[dict, float]]] = [[]]
    x = X0
    for row in rows:
        w = _chip_icon_w(row) + width_of(_chip_text(row), 20, MONO_ADVANCE)
        if lines[-1] and x + w > RIGHT:
            lines.append([])
            x = X0
        lines[-1].append((row, x))
        x += w + 22
    return lines if rows else []


def _chip_icon_w(row: dict) -> float:
    """A logo leads its chip; initials would only repeat the label's letters."""
    return ALSO_ICON + 8 if row["icon"].kind == "vendored" else 0


def _chip_text(row: dict) -> str:
    return f"{row['label']} {row['hours_text'].replace('≈ ', '')}"


def skills_height(tile: dict) -> int:
    also = _also_layout(tile["also"])
    height = 176 + len(tile["bars"]) * ROW
    if also:
        height += 36 + len(also) * ALSO_LINE
    return height + 20


def skills_tile(tile: dict, pal: dict, height: int, ticks: list[float]) -> str:
    b, _ = header(tile["eyebrow"], tile["title"], pal)
    y = 186
    for row in tile["bars"]:
        b += _bar_row(row, y, pal, ticks)
        y += ROW
    lines = _also_layout(tile["also"])
    if lines:
        y += 4
        b += mono(X0, y, tile["also_label"], pal["dim"])
        y += ALSO_LINE
        for line in lines:
            for row, x in line:
                if row["icon"].kind == "vendored":
                    b += _icon(row["icon"], x, y - 19, ALSO_ICON, pal)
                b += mono(x + _chip_icon_w(row), y, _chip_text(row), pal["muted"])
            y += ALSO_LINE
    if y - ALSO_LINE + 30 > height:
        raise LayoutError(f"skills {tile['domain']}: content overflows the tile")
    return frame(HALF, height, b, pal, tile["aria"])


# --- Activity calendar ------------------------------------------------------------


def calendar_height(years: int) -> int:
    return 196 + years * CAL_YEAR + 70


def _year_grid(year: int, calendar: dict, as_of: date, y: float, pal: dict) -> str:
    pitch = WIDTH / 54
    cell = pitch - 2
    colors = {"pro": pal["accent"], "personal": pal["personal"], "study": pal["study"]}
    first = date(year, 1, 1)
    offset = first.weekday()
    last = min(date(year, 12, 31), as_of)
    out = []
    day = first
    while day <= last:
        index = (day - first).days + offset
        cx, cy = X0 + (index // 7) * pitch, y + (index % 7) * pitch
        hit = calendar.get(day.isoformat())
        if hit:
            out.append(
                f'<rect x="{_t(cx)}" y="{_t(cy)}" width="{_t(cell)}" '
                f'height="{_t(cell)}" rx="1.5" fill="{colors[hit["context"]]}" '
                f'fill-opacity="{OPACITY[hit["intensity"]]}"/>'
            )
        else:
            out.append(
                f'<rect x="{_t(cx)}" y="{_t(cy)}" width="{_t(cell)}" '
                f'height="{_t(cell)}" rx="1.5" fill="{pal["track"]}"/>'
            )
        day += timedelta(days=1)
    return "".join(out)


def _legend(y: float, view: dict, counts: dict, pal: dict) -> str:
    colors = {"pro": pal["accent"], "personal": pal["personal"], "study": pal["study"]}
    b = ""
    x = X0
    for ctx in ("pro", "personal", "study"):
        if not counts.get(ctx):
            continue
        b += (
            f'<rect x="{_t(x)}" y="{_t(y - 15)}" width="16" height="16" rx="3" '
            f'fill="{colors[ctx]}"/>'
        )
        label = view["contexts"][ctx]
        b += text(x + 26, y, label, 20, pal["muted"])
        x += 26 + width_of(label, 20) + 28
    pitch = WIDTH / 54 + 4
    more_w = width_of(view["more"], 20)
    xs = RIGHT - more_w - 10 - 5 * pitch
    if xs - width_of(view["less"], 20) - 10 < x:
        raise LayoutError("calendar: the legend overlaps")
    b += text(xs - 10, y, view["less"], 20, pal["muted"], anchor="end")
    for i, level in enumerate((0, 1, 2, 3, 4)):
        fill = pal["track"] if not level else pal["accent"]
        b += (
            f'<rect x="{_t(xs + i * pitch)}" y="{_t(y - 13)}" '
            f'width="{_t(pitch - 4)}" height="{_t(pitch - 4)}" rx="1.5" '
            f'fill="{fill}" fill-opacity="{OPACITY.get(level, 1)}"/>'
        )
    b += text(xs + 5 * pitch + 6, y, view["more"], 20, pal["muted"])
    return b


def calendar_tile(
    half: dict, view: dict, calendar: dict, as_of: str, pal: dict, height: int
) -> str:
    end = date.fromisoformat(as_of)
    b, _ = header(view["prompt"], half["title"], pal)
    b += text(X0, 156, half["sub"], 21, pal["muted"])
    y = 196
    counts: dict[str, int] = {}
    for year in half["years"]:
        days = {d: v for d, v in calendar.items() if d.startswith(f"{year}-")}
        for entry in days.values():
            counts[entry["context"]] = counts.get(entry["context"], 0) + 1
        b += mono(X0, y + 20, str(year), pal["text"], 22, 700)
        b += mono(
            RIGHT,
            y + 20,
            f"{len(days)} {view['days_unit']}",
            pal["muted"],
            anchor="end",
        )
        b += _year_grid(year, days, end, y + 34, pal)
        y += CAL_YEAR
    b += _legend(height - INSET - 36, view, counts, pal)
    return frame(HALF, height, b, pal, half["aria"])


# --- All tiles ------------------------------------------------------------------


def level_ticks(levels: dict, top: float) -> list[float]:
    return [bar_fraction(h, top) for h in sorted(levels.values())]


def render_all(view: dict, data: dict, mode: str) -> dict[str, str]:
    """Every front tile for one theme: ``{file name: svg}``."""
    pal = data["theme"]["tiles"][mode]
    out = {
        "identity.svg": identity_tile(view, pal),
        "figures.svg": figures_tile(view, pal),
    }
    for project in view["oss"]["items"]:
        out[f"oss-{project['id']}.svg"] = oss_tile(project, pal)
    top = max((s["hours"] for s in data["skills"]), default=10.0)
    ticks = level_ticks(data["aggregates"]["levels"], top)
    for pair in view["skills"]["pairs"]:
        height = max(skills_height(t) for t in pair)
        for tile in pair:
            out[f"skills-{tile['domain']}.svg"] = skills_tile(tile, pal, height, ticks)
    if view["skills"]["local"]:
        out["skills-band.svg"] = icons.band_svg(
            view["skills"]["local"], data["icons"], mode, view["skills"]["labels"]
        )
    activity = view["activity"]
    height = calendar_height(max(len(h["years"]) for h in activity["halves"]))
    for half in activity["halves"]:
        name = f"calendar-{half['years'][0]}-{half['years'][-1]}.svg"
        out[name] = calendar_tile(
            half,
            activity,
            data["aggregates"]["calendar"],
            data["aggregates"]["activity_as_of"],
            pal,
            height,
        )
    return out
