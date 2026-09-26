"""PROTOTYPE, throwaway. Front page v2 per ADR-015: grid, green palette, calendar.

Every tile shares one unit grid: a full tile is 1200 units wide, a half tile
590, and the 20-unit gap between two half tiles is drawn inside each tile
(10 transparent units on every side of the panel). Half tiles are embedded at
width 415 px, full tiles at 834 px (= 2 x 415 + the inline space), so every
tile renders at the same scale (~0.70) and half tiles stack on a phone.

Only the name, tile titles and large figures are outlined to paths (Inter
Display); every other SVG text uses a system-safe stack. Display copy lives in
copy.fr.json, activity aggregates in spike-data.json (see extract_spike.py).

Run: .venv/bin/python prototype/front-v2/build.py
Outputs prototype/front-v2/{svg/dark,svg/light}/*.svg and index.fr.md.
"""

import importlib.util
import json
import math
import textwrap
from collections import defaultdict
from datetime import date, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "font_outline", ROOT / "scripts/font_outline.py"
)
_FONT_OUTLINE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FONT_OUTLINE)
outline_text = _FONT_OUTLINE.outline_text

OUT = Path(__file__).resolve().parent
T = json.loads((OUT / "copy.fr.json").read_text(encoding="utf-8"))
S = json.loads((OUT / "spike-data.json").read_text(encoding="utf-8"))
TECHS = {t["id"]: t for t in json.loads((ROOT / "data/techs.json").read_text())}
SERVICES = json.loads((ROOT / "data/services.json").read_text(encoding="utf-8"))
FONT = str(ROOT / "assets/fonts/InterDisplay-ExtraBold.ttf")

FULL, HALF, INSET = 1200, 590, 10
EMBED_FULL, EMBED_HALF = 834, 415
PAD = 40  # content padding inside the panel
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
# Floor: 20 units * (360 / 590) = 12 px when a half tile stacks on a phone.
MIN_FS = 20
TITLE_FS = 34

AS_OF = date.fromisoformat(S["as_of"])
SINCE_CODING = 2006
LEVELS = [(5000, "expert"), (1600, "advanced"), (500, "professional"), (50, "working")]
# Measured on 2026-09-26 (PyPI download stats, Docker Hub); prototype constants.
PROOF = {"pypi_month": 320, "pypi_releases": 8, "docker_pulls": 1671, "since": 2020}
GROUPS = {
    "languages": ["csharp-dotnet", "c-cpp", "python", "objective-c", "bash"],
    "mobile_embedded": ["xamarin-forms", "bluetooth", "windows-ce", "nfc", "gps"],
    "backend_devops": ["asp-net-web-api-2", "git", "asp-net-core", "blazor", "docker"],
    "ai_chain": [
        "ai-driven-development",
        "claude-api",
        "litellm",
        "cosmos-sdk",
        "cometbft",
    ],
}
WEIGHT_DOMAINS = ["embedded", "mobile", "backend", "devops", "ai-llm", "blockchain"]

PALETTES = {
    "dark": {
        "panel": "#0c0f0a",
        "dot": "#1d2419",
        "border": "#262e21",
        "text": "#eef2e8",
        "muted": "#a3ab9a",
        "dim": "#7b8472",
        "accent": "#a3e635",
        "on_accent": "#0c0f0a",
        "track": "#1a2016",
        "personal": "#d9d4c1",
        "study": "#6e7864",
    },
    "light": {
        "panel": "#fbfcf8",
        "dot": "#e4e8dc",
        "border": "#d9dfcf",
        "text": "#141810",
        "muted": "#525a4a",
        "dim": "#6b7361",
        "accent": "#3f6212",
        "on_accent": "#fbfcf8",
        "track": "#eaede3",
        "personal": "#8c8570",
        "study": "#b3baa6",
    },
}


def fmt(n):
    return f"{n:,}".replace(",", " ")


def approx(h):
    # Floor, never round up: a displayed figure must not cross a level floor.
    step = 100 if h >= 1000 else 10
    return fmt(int(h // step) * step)


def level_of(h):
    return next((name for floor, name in LEVELS if h >= floor), "explored")


# ---- aggregates --------------------------------------------------------------

HOURS_BY_YEAR = {int(y): v for y, v in S["hours_by_year"].items()}
TOTAL_HOURS = sum(sum(v.values()) for v in HOURS_BY_YEAR.values())
PEAK = max(sum(v.values()) for v in HOURS_BY_YEAR.values())
DAYS = {date.fromisoformat(d): v for d, v in S["days"].items()}
CTX_DAYS = S["commit_days_by_context"]
TECH_H = {t["id"]: t for t in S["techs"]}
ADVANCED_PLUS = sum(1 for t in S["techs"] if t["hours"] >= 1600)
YEARS = AS_OF.year - SINCE_CODING
DOMAIN_H = defaultdict(int)
for t in S["techs"]:
    DOMAIN_H[t["domain"]] += t["hours"]
WEIGHT_TOTAL = sum(DOMAIN_H[d] for d in WEIGHT_DOMAINS)
WEIGHTS = sorted(
    ((d, DOMAIN_H[d] / WEIGHT_TOTAL * 100) for d in WEIGHT_DOMAINS),
    key=lambda kv: -kv[1],
)


def longest_streak():
    best = run = 0
    prev = None
    for d in sorted(DAYS):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best, prev = max(best, run), d
    return best


FILL = {
    "years": str(YEARS),
    "hours": approx(TOTAL_HOURS),
    "days": fmt(S["commit_days"]),
    "techs": str(ADVANCED_PLUS),
    "as_of": S["as_of"],
    "pro": fmt(CTX_DAYS.get("pro", 0)),
    "personal": fmt(CTX_DAYS.get("personal", 0)),
    "total": approx(TOTAL_HOURS),
    "peak": fmt(PEAK),
    "streak": str(longest_streak()),
    "pypi_month": str(PROOF["pypi_month"]),
    "pypi_releases": str(PROOF["pypi_releases"]),
    "docker_pulls": fmt(PROOF["docker_pulls"]),
    "top": T["activity"]["domains"][WEIGHTS[0][0]],
    "second": T["activity"]["domains"][WEIGHTS[1][0]].lower(),
}


def f(s, **extra):
    return s.format(**{**FILL, **extra})


# ---- primitives --------------------------------------------------------------


def text(x, y, s, size, fill, weight=400, family=SANS, anchor="start", ls=None):
    if size < MIN_FS:
        raise ValueError(f"font {size} under the {MIN_FS}-unit floor: {s}")
    extra = f' letter-spacing="{ls}"' if ls else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>'
        f"{escape(s)}</text>"
    )


def mono(x, y, s, fill, size=20, weight=500, anchor="start"):
    return text(x, y, s, size, fill, weight, MONO, anchor)


def outline(x, y, s, size, fill, anchor="start"):
    """Display text outlined to one path (ADR-007); returns (svg, width)."""
    o = outline_text(s, FONT, size)
    shift = {"start": 0, "middle": o["width"] / 2, "end": o["width"]}[anchor]
    return (
        f'<path transform="translate({x - shift:.1f},{y:.1f})" fill="{fill}" '
        f'd="{o["path"]}"/>',
        o["width"],
    )


def title(x, y, s, c):
    return outline(x, y, s, TITLE_FS, c["text"])[0]


def wrap(s, chars):
    return textwrap.wrap(s, chars)


def svg(w, h, body, c, aria):
    # Explicit width AND height: an intrinsic size GitHub scales by our width.
    pw, ph = w - 2 * INSET, h - 2 * INSET
    a = escape(aria)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{escape(aria)}">'
        f"<title>{a}</title>"
        '<defs><pattern id="dots" width="24" height="24" '
        'patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1.3" fill="{c["dot"]}"/></pattern></defs>'
        f'<rect x="{INSET + 0.5}" y="{INSET + 0.5}" width="{pw - 1}" '
        f'height="{ph - 1}" rx="22" fill="{c["panel"]}" stroke="{c["border"]}"/>'
        f'<rect x="{INSET + 1}" y="{INSET + 1}" width="{pw - 2}" height="{ph - 2}" '
        f'rx="21" fill="url(#dots)"/>{body}</svg>'
    )


def header(x, y, eyebrow, head, c, sub=None):
    """Mono eyebrow, outlined title, optional muted subtitle; returns (svg, y)."""
    b = mono(x, y, eyebrow, c["dim"])
    b += title(x, y + 50, head, c)
    y += 50
    if sub:
        b += text(x, y + 34, sub, 21, c["muted"])
        y += 34
    return b, y


# ---- tiles -------------------------------------------------------------------


def tile_identity(c):
    ti = T["identity"]
    x0, w = INSET + 56, FULL - 2 * INSET - 112
    b = mono(x0, 86, ti["prompt"], c["dim"], 22)
    b += outline(x0, 186, "Boris Leclere", 96, c["text"])[0]
    b += text(x0, 240, ti["role"], 32, c["text"], 600)
    b += mono(x0, 286, ti["arc"], c["muted"], 22)
    # availability pill, top right
    pw, px = 208, FULL - INSET - 56 - 208
    b += (
        f'<rect x="{px}" y="56" width="{pw}" height="46" rx="23" fill="none" '
        f'stroke="{c["accent"]}" stroke-width="2"/>'
        f'<circle cx="{px + 28}" cy="79" r="7" fill="{c["accent"]}"/>'
    )
    b += text(px + 46, 87, ti["available"], 23, c["accent"], 700)
    b += mono(FULL - INSET - 56, 136, T["stamp"], c["dim"], 20, anchor="end")
    b += (
        f'<line x1="{x0}" y1="330" x2="{x0 + w}" y2="330" '
        f'stroke="{c["border"]}" stroke-width="2"/>'
    )
    fig = ti["figures"]
    cells = [
        (FILL["years"], fig["years"], ""),
        (FILL["hours"], fig["hours"], ""),
        (FILL["days"], fig["days"], fig["days_extra"]),
        (FILL["techs"], fig["techs"], fig["techs_extra"]),
    ]
    cw = w / len(cells)
    for i, (v, lab, extra) in enumerate(cells):
        cx = x0 + i * cw
        if i:
            b += (
                f'<line x1="{cx - 30:.1f}" y1="362" x2="{cx - 30:.1f}" y2="490" '
                f'stroke="{c["border"]}"/>'
            )
        b += outline(cx, 428, v, 64, c["accent"])[0]
        b += text(cx, 470, lab, 22, c["muted"], 500)
        if extra:
            b += text(cx, 498, extra, 22, c["muted"], 500)
    return svg(FULL, 540, b, c, f(ti["aria"]))


def tile_proof(c, key, fig1, fig2, h):
    tp = T["proofs"][key]
    x0 = INSET + PAD
    b, y = header(x0, INSET + 60, tp["eyebrow"], tp["title"], c)
    y += 96
    p, w1 = outline(x0, y, fig1, 64, c["accent"])
    b += p
    x2 = x0 + max(w1, 150) + 56
    b += outline(x2, y, fig2, 64, c["accent"])[0]
    b += text(x0, y + 36, tp["fig1"], 21, c["muted"], 600)
    b += text(x0, y + 62, tp["fig1_extra"], 21, c["muted"])
    b += text(x2, y + 36, tp["fig2"], 21, c["muted"], 600)
    b += text(x2, y + 62, tp["fig2_extra"], 21, c["muted"])
    y += 116
    for i, line in enumerate(wrap(tp["desc"], 44)):
        b += text(x0, y + i * 30, line, 21, c["text"])
    b += mono(x0, h - INSET - 34, f(tp["source"]), c["dim"])
    return svg(HALF, h, b, c, f(tp["aria"]))


def log_pos(h):
    return (math.log10(max(h, 10)) - 1) / (math.log10(20000) - 1)


def skill_row(x, y, w, tid, c):
    t = TECH_H[tid]
    lvl = level_of(t["hours"])
    ts = T["skills"]
    b = text(x, y, TECHS[tid]["label"], 22, c["text"], 600)
    b += text(x + w, y, ts["levels"][lvl], 21, c["accent"], 700, anchor="end")
    meta = f"≈ {approx(t['hours'])} h · {t['first']}–{t['last']}"
    b += mono(x, y + 30, meta, c["muted"])
    if t["last"] >= AS_OF.year:
        b += mono(x + w, y + 30, ts["active"], c["accent"], anchor="end")
    else:
        last = ts["last_use"].format(year=t["last"])
        b += mono(x + w, y + 30, last, c["dim"], anchor="end")
    # log-scale hours bar with the four level thresholds as ticks
    yb = y + 46
    b += f'<rect x="{x}" y="{yb}" width="{w}" height="6" rx="3" fill="{c["track"]}"/>'
    b += (
        f'<rect x="{x}" y="{yb}" width="{w * log_pos(t["hours"]):.1f}" height="6" '
        f'rx="3" fill="{c["accent"]}"/>'
    )
    for floor, _ in LEVELS:
        tx = x + w * log_pos(floor)
        b += (
            f'<line x1="{tx:.1f}" y1="{yb - 3}" x2="{tx:.1f}" y2="{yb + 9}" '
            f'stroke="{c["panel"]}" stroke-width="2"/>'
        )
    return b


def tile_skills(c, group, h):
    x0, w = INSET + PAD, HALF - 2 * INSET - 2 * PAD
    name = T["skills"]["groups"][group]
    b, y = header(x0, INSET + 60, "skills." + group.replace("_", "+"), name, c)
    y += 60
    for i, tid in enumerate(GROUPS[group]):
        b += skill_row(x0, y + i * 92, w, tid, c)
    return svg(HALF, h, b, c, skills_aria(group))


def skills_aria(group):
    rows = []
    for tid in GROUPS[group]:
        t = TECH_H[tid]
        lvl = T["skills"]["levels"][level_of(t["hours"])]
        rows.append(f"{TECHS[tid]['label']} {approx(t['hours'])} h {lvl}")
    name = T["skills"]["groups"][group]
    return T["skills"]["aria"].format(group=name, rows=", ".join(rows))


def tile_timeline_a(c, h):
    tt = T["timeline"]
    x0 = INSET + PAD
    b, y = header(x0, INSET + 60, "git log --reverse", tt["title_a"], c, tt["sub_a"])
    y += 64
    rail = x0 + 6
    n = len(tt["entries_a"])
    step = (h - INSET - 50 - y) / (n - 1)
    b += (
        f'<line x1="{rail}" y1="{y - 8}" x2="{rail}" y2="{y + (n - 1) * step}" '
        f'stroke="{c["border"]}" stroke-width="2"/>'
    )
    for i, (period, org, brief, ctx) in enumerate(tt["entries_a"]):
        yy = y + i * step
        col = c["accent"] if ctx == "pro" else c["study"]
        b += f'<circle cx="{rail}" cy="{yy - 7}" r="6" fill="{col}"/>'
        b += mono(x0 + 28, yy, period, col, weight=600)
        b += text(x0 + 160, yy, org, 22, c["text"], 700)
        b += text(x0 + 160, yy + 28, brief, 20, c["muted"])
    return svg(HALF, h, b, c, tt["aria_a"])


def tile_timeline_b(c, h):
    tt = T["timeline"]
    x0, tx = INSET + PAD, INSET + PAD + 64
    b, y = header(x0, INSET + 60, "git log", tt["title_b"], c, tt["sub_b"])
    rail, rail2 = x0 + 8, x0 + 30

    def bar(x, y1, y2, col, width=12, opacity=1.0):
        return (
            f'<rect x="{x - width / 2}" y="{y1:.1f}" width="{width}" '
            f'height="{y2 - y1:.1f}" rx="{width / 2}" fill="{col}" '
            f'opacity="{opacity}"/>'
        )

    def block(y0, period, lines, col):
        out = mono(tx, y0 + 16, period, col, weight=600)
        for i, (s, strong) in enumerate(lines):
            size, ink, wt = (22, c["text"], 700) if strong else (20, c["muted"], 400)
            out += text(tx, y0 + 50 + i * 28, s, size, ink, wt)
        return out

    # 2014-2020: two parallel employments, two rails on the same span
    y1 = y + 44
    b += mono(tx, y1 + 16, tt["dual_period"], c["accent"], weight=600)
    yy = y1 + 54
    for org, role, brief in tt["dual"]:
        b += text(tx, yy, org, 22, c["text"], 700)
        b += text(tx, yy + 28, role, 20, c["muted"])
        b += text(tx, yy + 54, brief, 20, c["muted"])
        yy += 94
    b += mono(tx, yy - 4, tt["dual_note"], c["dim"])
    y2 = yy + 8
    b += bar(rail, y1, y2, c["accent"]) + bar(rail2, y1, y2, c["accent"], 6, 0.6)
    # 2020-2026: personal R&D
    r1 = y2 + 36
    period, org, brief, extra = tt["rnd"]
    b += block(
        r1, period, [(org, True), (brief, False), (f(extra), False)], c["personal"]
    )
    r2 = r1 + 140
    b += bar(rail, r1, r2, c["personal"])
    # 2026-: client mission
    m1 = r2 + 36
    period, org, brief, extra = tt["mission"]
    b += block(m1, period, [(org, True), (brief, False), (extra, False)], c["accent"])
    b += bar(rail, m1, m1 + 106, c["accent"])
    if m1 + 106 > h - INSET - 20:
        raise ValueError("timeline-b content overflows its tile")
    return svg(HALF, h, b, c, tt["aria_b"])


CAL_X = INSET + PAD
CAL_W = HALF - 2 * INSET - 2 * PAD
PITCH = CAL_W / 54
CELL = PITCH - 2
OPACITY = {1: 0.32, 2: 0.55, 3: 0.78, 4: 1.0}


def year_grid(x, y, year, c):
    first = date(year, 1, 1)
    offset = first.weekday()
    last = min(date(year, 12, 31), AS_OF)
    out = []
    d = first
    while d <= last:
        idx = (d - first).days + offset
        cx, cy = x + (idx // 7) * PITCH, y + (idx % 7) * PITCH
        hit = DAYS.get(d)
        if hit:
            ctx, lvl = hit
            fill = c["accent"] if ctx == "pro" else c["personal"]
            out.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{CELL:.1f}" '
                f'height="{CELL:.1f}" rx="1.5" fill="{fill}" '
                f'fill-opacity="{OPACITY[lvl]}"/>'
            )
        else:
            out.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{CELL:.1f}" '
                f'height="{CELL:.1f}" rx="1.5" fill="{c["track"]}"/>'
            )
        d += timedelta(days=1)
    return "".join(out)


def legend(x, y, c):
    ta = T["activity"]
    b = ""
    for i, (key, col) in enumerate((("pro", c["accent"]), ("personal", c["personal"]))):
        xx = x + i * 120
        b += f'<rect x="{xx}" y="{y - 15}" width="16" height="16" rx="3" fill="{col}"/>'
        b += text(xx + 26, y, ta[key], 20, c["muted"])
    xs = x + CAL_W - 5 * (PITCH + 4) - 70
    b += text(xs - 10, y, ta["less"], 20, c["muted"], anchor="end")
    for i, lvl in enumerate((0, 1, 2, 3, 4)):
        xx = xs + i * (PITCH + 4)
        fill = c["track"] if not lvl else c["accent"]
        op = OPACITY.get(lvl, 1)
        b += (
            f'<rect x="{xx:.1f}" y="{y - 13}" width="{PITCH:.1f}" '
            f'height="{PITCH:.1f}" rx="1.5" fill="{fill}" fill-opacity="{op}"/>'
        )
    b += text(xs + 5 * (PITCH + 4) + 8, y, ta["more"], 20, c["muted"])
    return b


def tile_calendar(c, years, slot_count, h, side):
    ta = T["activity"]
    x0 = INSET + PAD
    b, y = header(
        x0,
        INSET + 60,
        ta["cal_prompt"],
        ta[f"cal_title_{side}"],
        c,
        ta[f"cal_sub_{side}"],
    )
    y += 40
    block = 118
    n_days = 0
    for i, year in enumerate(years):
        yy = y + i * block
        count = sum(1 for d in DAYS if d.year == year)
        n_days += count
        b += mono(CAL_X, yy + 20, str(year), c["text"], 22, 700)
        b += mono(
            CAL_X + CAL_W,
            yy + 20,
            f"{count} {ta['days_unit']}",
            c["muted"],
            anchor="end",
        )
        b += year_grid(CAL_X, yy + 34, year, c)
    if len(years) < slot_count:
        yy = y + len(years) * block
        lines = [f(s, years=AS_OF.year - 2014 + 1) for s in ta["summary"]]
        b += mono(CAL_X, yy + 24, "$ wc -l", c["dim"])
        for j, line in enumerate(lines):
            col = (c["accent"], c["personal"], c["muted"])[j]
            b += mono(CAL_X, yy + 54 + j * 28, line, col, 20, 600)
    b += legend(CAL_X, h - INSET - 36, c)
    aria = ta[f"aria_{side}"].format(n=fmt(n_days))
    return svg(HALF, h, b, c, aria)


def tile_history(c, h):
    ta = T["activity"]
    x0 = INSET + PAD
    b, y = header(x0, INSET + 60, "hours --by=year", ta["history_title"], c)
    b += text(x0, y + 34, ta["history_sub"], 21, c["muted"])
    b += mono(x0, y + 70, f(ta["history_total"]), c["accent"], 21, 700)
    top, base = y + 150, h - INSET - 110
    axis_x = x0 + 64
    plot_w = HALF - INSET - PAD - axis_x
    years = list(range(SINCE_CODING, AS_OF.year + 1))
    pitch = plot_w / len(years)
    bar = pitch - 6
    y_max = 2500
    for tick in (0, 1000, 2000):
        ty = base - tick / y_max * (base - top)
        b += (
            f'<line x1="{axis_x}" y1="{ty:.1f}" x2="{axis_x + plot_w:.1f}" '
            f'y2="{ty:.1f}" stroke="{c["border"]}"/>'
        )
        b += mono(axis_x - 10, ty + 7, fmt(tick), c["dim"], anchor="end")
    colors = {"study": c["study"], "pro": c["accent"], "personal": c["personal"]}
    for i, year in enumerate(years):
        stack = HOURS_BY_YEAR.get(year, {})
        yy = base
        bx = axis_x + i * pitch + 3
        for ctx in ("study", "pro", "personal"):
            v = stack.get(ctx, 0)
            if not v:
                continue
            hh = v / y_max * (base - top)
            b += (
                f'<rect x="{bx:.1f}" y="{yy - hh:.1f}" width="{bar:.1f}" '
                f'height="{hh:.1f}" fill="{colors[ctx]}"/>'
            )
            yy -= hh
        if year % 5 == 0 or year == SINCE_CODING:
            b += mono(bx + bar / 2, base + 30, str(year), c["dim"], anchor="middle")
    # bracket over the dual-employment years
    bx1 = axis_x + (2015 - SINCE_CODING) * pitch + 3
    bx2 = axis_x + (2019 - SINCE_CODING) * pitch + 3 + bar
    by = base - PEAK / y_max * (base - top) - 14
    b += (
        f'<path d="M{bx1:.1f},{by + 6:.1f} V{by:.1f} H{bx2:.1f} V{by + 6:.1f}" '
        f'fill="none" stroke="{c["muted"]}" stroke-width="1.5"/>'
    )
    b += mono((bx1 + bx2) / 2, by - 10, ta["history_dual"], c["muted"], anchor="middle")
    ly = h - INSET - 40
    for i, key in enumerate(("pro", "personal", "study")):
        xx = x0 + i * 130
        b += (
            f'<rect x="{xx}" y="{ly - 15}" width="16" height="16" rx="3" '
            f'fill="{colors[key]}"/>'
        )
        b += text(xx + 26, ly, ta[key], 20, c["muted"])
    return svg(HALF, h, b, c, f(ta["history_aria"]))


def tile_weight(c, h):
    ta = T["activity"]
    x0, w = INSET + PAD, HALF - 2 * INSET - 2 * PAD
    b, y = header(x0, INSET + 60, "hours --by=domain", ta["weight_title"], c)
    b += text(x0, y + 34, ta["weight_sub"], 21, c["muted"])
    y += 100
    top = WEIGHTS[0][1]
    for i, (d, pct) in enumerate(WEIGHTS):
        yy = y + i * 62
        label = ta["domains"][d]
        b += text(x0, yy, label, 22, c["text"], 600)
        b += mono(x0 + w, yy, f"{pct:.0f} %", c["accent"], 21, 700, anchor="end")
        b += (
            f'<rect x="{x0}" y="{yy + 12}" width="{w}" height="10" rx="5" '
            f'fill="{c["track"]}"/><rect x="{x0}" y="{yy + 12}" '
            f'width="{w * pct / top:.1f}" height="10" rx="5" fill="{c["accent"]}"/>'
        )
    b += mono(x0, h - INSET - 40, "// " + ta["weight_note"], c["dim"])
    return svg(HALF, h, b, c, weight_aria())


def weight_aria():
    domains = T["activity"]["domains"]
    rows = ", ".join(f"{domains[d]} {pct:.0f} %" for d, pct in WEIGHTS)
    return T["activity"]["weight_aria"].format(rows=rows)


# ---- render ------------------------------------------------------------------

CAL_H = 1150
TILES = {
    "identity": tile_identity,
    "proof-pypi": lambda c: tile_proof(
        c, "pypi", str(PROOF["pypi_month"]), str(PROOF["pypi_releases"]), 470
    ),
    "proof-docker": lambda c: tile_proof(
        c, "docker", fmt(PROOF["docker_pulls"]), str(PROOF["since"]), 470
    ),
    **{f"skills-{g}": (lambda c, g=g: tile_skills(c, g, 640)) for g in GROUPS},
    "timeline-a": lambda c: tile_timeline_a(c, 820),
    "timeline-b": lambda c: tile_timeline_b(c, 820),
    "calendar-a": lambda c: tile_calendar(c, range(2014, 2020), 7, CAL_H, "a"),
    "calendar-b": lambda c: tile_calendar(c, range(2020, 2027), 7, CAL_H, "b"),
    "history-hours": lambda c: tile_history(c, 660),
    "history-weight": lambda c: tile_weight(c, 660),
}

for theme, pal in PALETTES.items():
    d = OUT / "svg" / theme
    d.mkdir(parents=True, exist_ok=True)
    for key, fn in TILES.items():
        (d / f"{key}.svg").write_text(fn(pal) + "\n", encoding="utf-8")


def img(key, alt, width):
    return (
        '<picture><source media="(prefers-color-scheme: light)" '
        f'srcset="svg/light/{key}.svg" /><img src="svg/dark/{key}.svg" '
        f'width="{width}" alt="{escape(alt)}" /></picture>'
    )


def days_in(first, last):
    return fmt(sum(1 for d in DAYS if first <= d.year <= last))


def pair(a, b):
    return f"{img(*a, EMBED_HALF)} {img(*b, EMBED_HALF)}"


tp, ts, tt, ta = T["proofs"], T["skills"], T["timeline"], T["activity"]
groups = list(GROUPS)
services = "\n".join(
    f"- **{s['title']}** — {s['short_description']}"
    for s in sorted(SERVICES, key=lambda s: s["priority"])
    if s.get("visible", True)
)
method = "\n\n".join(f(p) for p in T["method"]["body"])
page = f"""<!-- PROTOTYPE: throwaway, see prototype/front-v2/build.py -->

> {T["prototype_banner"]}

{img("identity", f(T["identity"]["aria"]), EMBED_FULL)}

{T["contact_line"]}

{f(T["identity"]["sentence"])}

## {T["help"]["title"]}

{T["help"]["intro"]}

{services}

## {tp["title"]}

{f(tp["intro"])}

{pair(("proof-pypi", f(tp["pypi"]["aria"])), ("proof-docker", f(tp["docker"]["aria"])))}

{f(tp["sentence"])}

## {ts["title"]}

{ts["intro"]}

{pair(*[(f"skills-{g}", skills_aria(g)) for g in groups[:2]])}

{pair(*[(f"skills-{g}", skills_aria(g)) for g in groups[2:]])}

{ts["sentence"]}

<sub>{ts["footnote"]}</sub>

## {tt["title"]}

{tt["intro"]}

{pair(("timeline-a", tt["aria_a"]), ("timeline-b", tt["aria_b"]))}

{tt["sentence"]} [{tt["detail"]} →](../../pages/journey.md)

## {T["method"]["title"]}

{method}

## {ta["title"]}

{ta["intro"]}

{
    pair(
        ("calendar-a", ta["aria_a"].format(n=days_in(2014, 2019))),
        ("calendar-b", ta["aria_b"].format(n=days_in(2020, 2026))),
    )
}

{f(ta["sentence"])}

{pair(("history-hours", f(ta["history_aria"])), ("history-weight", weight_aria()))}

{f(ta["history_sentence"])} {f(ta["weight_sentence"])}

---

<sub>{f(T["footer"]["signature"])}</sub><br>
<sub><code>{f(T["footer"]["egg"])}</code></sub>
"""
(OUT / "index.fr.md").write_text(page, encoding="utf-8")
print("built", len(TILES), "tiles x", len(PALETTES), "themes + index.fr.md")
