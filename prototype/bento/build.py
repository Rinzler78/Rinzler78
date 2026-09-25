"""PROTOTYPE, throwaway. Bento-grid front page, three structural variants.

Question: which layout gives the GitHub front page consistent proportions and a
modern-CV reading order? Every tile shares one unit grid (FULL=1200 units wide,
two HALF tiles plus a 20-unit gap = FULL), so displayed at width 100% / 49% every
tile gets the same scale and a given font size renders identically everywhere.

Display copy lives in copy.fr.json (repo convention: English code, *.fr.* copy).

Run: .venv/bin/python prototype/bento/build.py
Outputs prototype/bento/{svg/, *.fr.md}. Not tested, not for main.
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.generate import enrich, load_data, reference_date  # noqa: E402

OUT = Path(__file__).resolve().parent
T = json.loads((OUT / "copy.fr.json").read_text(encoding="utf-8"))
FULL, GAP = 1200, 20
HALF = (FULL - GAP) // 2
QUARTER = (FULL - 3 * GAP) // 4
SIDE = 398
MAIN = FULL - GAP - SIDE
SANS = "-apple-system, 'Segoe UI', Inter, system-ui, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
# Floor: 17 units * (846 / 1200) = 12 px in GitHub's column.
MIN_FS = 17

DATA = enrich(load_data(), reference_date())
AS_OF = reference_date()
P = DATA["profile"]
TOP = sorted(
    (t for t in DATA["techs"] if t.get("score_current")),
    key=lambda t: -t["score_current"],
)
DOMAIN_LABEL = {d["id"]: d["label"] for d in DATA["domains"]}
TOTALS = {k: sum(v.values()) for k, v in DATA["domain_years"].items()}
GRAND = sum(TOTALS.values())
SHARES = sorted(
    ((k, v / GRAND * 100) for k, v in TOTALS.items()), key=lambda kv: -kv[1]
)
KPIS = [
    (str(AS_OF.year - P["since_coding"]), T["kpi_years"]),
    (str(len(DATA["techs"])), T["kpi_techs"]),
    (str(len(SHARES)), T["kpi_domains"]),
    (str(len(DATA["projects"])), T["kpi_projects"]),
]


def text(x, y, s, size, fill, weight=500, family=SANS, anchor="start", ls=None):
    if size < MIN_FS:
        raise ValueError(f"font {size} under the {MIN_FS}-unit floor: {s}")
    extra = f' letter-spacing="{ls}"' if ls else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{s}</text>'
    )


def label(x, y, s, c):
    return text(x, y, s.upper(), 17, c["muted"], 700, ls="2")


def svg(w, h, body, c, aria):
    # Explicit width AND height: the image has an intrinsic size, so GitHub
    # scales it by the width we ask for and never inflates it on its own.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{aria}"><title>{aria}</title>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="18" '
        f'fill="{c["panel"]}" stroke="{c["border"]}"/>{body}</svg>'
    )


def status_pill(x, y, c, anchor_right=True):
    w = 190
    x0 = x - w if anchor_right else x
    return (
        f'<rect x="{x0}" y="{y}" width="{w}" height="40" rx="20" fill="none" '
        f'stroke="{c["success"]}"/>'
        f'<circle cx="{x0 + 24}" cy="{y + 20}" r="6" fill="{c["success"]}"/>'
        + text(x0 + 40, y + 27, T["available"], 19, c["success"], 600)
    )


def kpi_row(x, y, w, c, value_fs=48):
    cell = w / len(KPIS)
    out = []
    for i, (v, lab) in enumerate(KPIS):
        cx = x + i * cell
        if i:
            out.append(
                f'<line x1="{cx:.1f}" y1="{y - 44}" x2="{cx:.1f}" y2="{y + 30}" '
                f'stroke="{c["border"]}"/>'
            )
        pad = 0 if i == 0 else 28
        out.append(text(cx + pad, y, v, value_fs, c["accent"], 800))
        out.append(text(cx + pad, y + 30, lab, 17, c["muted"], 700, ls="1.5"))
    return "".join(out)


def bars(x, y, w, c, n, row=52):
    out = []
    for i, t in enumerate(TOP[:n]):
        yy = y + i * row
        score = t["score_current"]
        out.append(text(x, yy, t["label"], 21, c["text"], 600))
        out.append(text(x + w, yy, str(score), 21, c["accent"], 700, MONO, "end"))
        out.append(
            f'<rect x="{x}" y="{yy + 12}" width="{w}" height="8" rx="4" '
            f'fill="{c["track"]}"/>'
        )
        out.append(
            f'<rect x="{x}" y="{yy + 12}" width="{w * score / 99:.1f}" height="8" '
            f'rx="4" fill="{c["accent"]}"/>'
        )
    return "".join(out)


def donut(cx, cy, r, c, series):
    out, a0 = [], -math.pi / 2
    for k, pct in SHARES:
        a1 = a0 + pct / 100 * 2 * math.pi
        large = 1 if a1 - a0 > math.pi else 0
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1 - 0.02), cy + r * math.sin(a1 - 0.02)
        out.append(
            f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f}" '
            f'fill="none" stroke="{series[k]}" stroke-width="30"/>'
        )
        a0 = a1
    out.append(text(cx, cy + 12, str(len(SHARES)), 44, c["text"], 800, anchor="middle"))
    out.append(
        text(cx, cy + 40, T["domains_center"], 17, c["muted"], 600, anchor="middle")
    )
    return "".join(out)


def legend(x, y, c, series, row=38):
    out = []
    for i, (k, pct) in enumerate(SHARES):
        yy = y + i * row
        out.append(
            f'<rect x="{x}" y="{yy - 13}" width="14" height="14" rx="3" '
            f'fill="{series[k]}"/>'
        )
        out.append(text(x + 26, yy, DOMAIN_LABEL[k], 19, c["text"], 500))
        out.append(text(x + 250, yy, f"{pct:.0f} %", 19, c["muted"], 600, MONO, "end"))
    return "".join(out)


# ---- tiles ------------------------------------------------------------------


def tile_hero(c, s):
    b = text(56, 96, P["name"], 64, c["text"], 800)
    b += text(56, 140, T["role_full"], 24, c["accent"], 600)
    for i, line in enumerate(T["pitch"]):
        b += text(56, 184 + i * 30, line, 21, c["muted"], 400)
    b += status_pill(FULL - 48, 58, c)
    b += f'<line x1="56" y1="236" x2="{FULL - 56}" y2="236" stroke="{c["border"]}"/>'
    b += kpi_row(56, 290, FULL - 112, c)
    return svg(FULL, 330, b, c, T["hero_aria"])


def tile_skills(c, s, n=6):
    b = label(40, 58, T["skills"], c) + bars(40, 112, HALF - 80, c, n)
    return svg(HALF, 112 + n * 52 + 10, b, c, T["skills_aria"])


def tile_domains(c, s):
    b = label(40, 58, T["domains"], c)
    b += donut(150, 250, 100, c, s) + legend(290, 140, c, s)
    return svg(HALF, 112 + 6 * 52 + 10, b, c, T["domains_aria"])


def tile_banner(c, s):
    b = text(48, 78, P["name"], 48, c["text"], 800)
    b += text(48, 118, T["role_full"], 22, c["accent"], 600)
    b += status_pill(FULL - 48, 50, c)
    return svg(FULL, 160, b, c, T["banner_aria"])


def tile_kpi(c, s, i):
    v, lab = KPIS[i]
    b = text(36, 118, v, 84, c["accent"], 800)
    b += text(36, 158, lab, 17, c["muted"], 700, ls="1.5")
    return svg(QUARTER, 200, b, c, f"{v} {lab.lower()}")


def tile_milestones(c, s):
    items = DATA["timeline"][:6]
    x = 60
    b = label(40, 58, T["milestones"], c)
    b += (
        f'<line x1="{x}" y1="100" x2="{x}" y2="{100 + (len(items) - 1) * 58}" '
        f'stroke="{c["border"]}" stroke-width="2"/>'
    )
    for i, it in enumerate(items):
        y = 100 + i * 58
        dot = c["accent"] if it.get("highlight") else c["panel"]
        b += (
            f'<circle cx="{x}" cy="{y}" r="7" fill="{dot}" stroke="{c["accent"]}" '
            f'stroke-width="2"/>'
        )
        b += text(x + 24, y + 7, it["year"], 19, c["accent"], 700, MONO)
        b += text(x + 124, y + 7, it["label"][:34], 19, c["text"], 500)
    return svg(HALF, 110 + len(items) * 58, b, c, T["milestones_aria"])


def tile_services(c, s):
    items = [x for x in DATA["services"] if x.get("visible", True)][:6]
    b = label(40, 58, T["services"], c)
    for i, it in enumerate(items):
        y = 110 + i * 58
        b += (
            f'<rect x="40" y="{y - 22}" width="6" height="30" rx="3" '
            f'fill="{c["accent"]}"/>'
        )
        b += text(62, y, it["title"], 21, c["text"], 600)
    return svg(HALF, 110 + len(items) * 58, b, c, T["services"])


def tile_sidebar(c, s):
    b = f'<circle cx="92" cy="104" r="52" fill="{c["accent"]}"/>'
    b += text(92, 120, "BL", 44, "#ffffff", 800, anchor="middle")
    b += status_pill(40, 180, c, anchor_right=False)
    city = f"{P['location']['city']}, Provence"
    rows = [
        (T["contact"], [P["contacts"]["email_pro"], P["contacts"]["phone"]]),
        (T["location"], [city, T["location_extra"]]),
        (T["languages"], T["languages_list"]),
    ]
    y = 280
    for head, lines in rows:
        b += label(40, y, head, c)
        for j, ln in enumerate(lines):
            b += text(40, y + 36 + j * 30, ln, 19, c["text"], 500)
        y += 36 + len(lines) * 30 + 34
    return svg(SIDE, 600, b, c, T["sidebar_aria"])


def tile_main(c, s):
    b = text(48, 96, P["name"], 58, c["text"], 800)
    b += text(48, 138, T["role_short"], 24, c["accent"], 600)
    for i, line in enumerate(T["pitch"]):
        b += text(48, 184 + i * 30, line[:64], 20, c["muted"], 400)
    b += kpi_row(48, 300, MAIN - 96, c, value_fs=42)
    b += label(48, 390, T["skills"], c) + bars(48, 438, MAIN - 96, c, 3)
    return svg(MAIN, 600, b, c, T["main_aria"])


def chip(c, lab, primary=False):
    w = int(len(lab) * 11.5 + 64)
    fill = c["accent"] if primary else c["panel"]
    ink = "#ffffff" if primary else c["text"]
    dot = ink if primary else c["accent"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 36" width="{w}" '
        f'height="36" role="img" aria-label="{lab}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="35" rx="18" fill="{fill}" '
        f'stroke="{c["border"]}"/><circle cx="22" cy="18" r="5" fill="{dot}"/>'
        + text(36, 24, lab, 17, ink, 600)
        + "</svg>"
    )


# ---- render -----------------------------------------------------------------

TILES = {
    "hero": tile_hero,
    "skills": tile_skills,
    "domains": tile_domains,
    "banner": tile_banner,
    "milestones": tile_milestones,
    "services": tile_services,
    "sidebar": tile_sidebar,
    "main": tile_main,
    **{f"kpi{i}": (lambda c, s, i=i: tile_kpi(c, s, i)) for i in range(4)},
}
CHIPS = [
    ("chip-email", "Email", "mailto:" + P["contacts"]["email_pro"], True),
    ("chip-linkedin", "LinkedIn", P["links"]["linkedin"], False),
    ("chip-malt", "Malt", P["links"]["malt"], False),
    ("chip-whatsapp", "WhatsApp", "https://wa.me/33626263461", False),
    ("chip-github", "GitHub", P["links"]["github"], False),
    ("chip-pypi", "PyPI", P["links"]["pypi"], False),
]

theme = DATA["theme"]
for name, pal, series in (
    ("dark", theme["palette"], theme["series"]),
    ("light", theme["palette_light"], theme.get("series_light", theme["series"])),
):
    c = dict(pal, muted=pal["text_muted"], track=pal["panel_alt"])
    d = OUT / "svg" / name
    d.mkdir(parents=True, exist_ok=True)
    for key, fn in TILES.items():
        (d / f"{key}.svg").write_text(fn(c, series) + "\n", encoding="utf-8")
    for key, lab, _, prim in CHIPS:
        (d / f"{key}.svg").write_text(chip(c, lab, prim) + "\n", encoding="utf-8")


def img(key, alt, width=None):
    w = f' width="{width}"' if width else ""
    return (
        '<picture><source media="(prefers-color-scheme: light)" '
        f'srcset="svg/light/{key}.svg" /><img src="svg/dark/{key}.svg"{w} '
        f'alt="{alt}" /></picture>'
    )


def chips_row():
    return " ".join(f'<a href="{url}">{img(k, lab)}</a>' for k, lab, url, _ in CHIPS)


BELOW = (
    f"\n### {T['below_title']}\n\n{T['below_text']}\n\n"
    '<picture><source media="(prefers-color-scheme: light)" '
    'srcset="../../assets/svg/light/journey-share.svg" />'
    '<img src="../../assets/svg/journey-share.svg" width="100%" '
    f'alt="{T["below_alt"]}" /></picture>\n\n<sub>{T["below_note"]}</sub>\n'
)
CHIPS_P = f'<p align="center">{chips_row()}</p>\n'
BODIES = {
    "a": f"{img('hero', T['banner_aria'], '100%')}\n\n"
    f"{img('skills', T['skills'], '49%')} {img('domains', T['domains'], '49%')}\n\n"
    + CHIPS_P,
    "b": f"{img('sidebar', T['sidebar_aria'], '33%')} "
    f"{img('main', T['main_aria'], '65%')}\n\n" + CHIPS_P,
    "c": f"{img('banner', T['banner_aria'], '100%')}\n\n"
    + " ".join(img(f"kpi{i}", KPIS[i][1], "24%") for i in range(4))
    + "\n\n"
    f"{img('milestones', T['milestones'], '49%')} "
    f"{img('services', T['services'], '49%')}\n\n" + CHIPS_P,
}

for key, body in BODIES.items():
    title, desc = T["variants"][key]
    (OUT / f"variant-{key}.fr.md").write_text(
        f"<!-- PROTOTYPE: throwaway, see prototype/bento/build.py -->\n\n"
        f"{T['nav']}\n\n## {T['variant_heading']} {title}\n\n{desc}\n\n{body}{BELOW}",
        encoding="utf-8",
    )

rows = "".join(
    f"| [{t}](variant-{k}.fr.md) | {d} |\n" for k, (t, d) in T["variants"].items()
)
(OUT / "README.fr.md").write_text(
    f"<!-- PROTOTYPE: throwaway -->\n\n# {T['index_title']}\n\n{T['index_question']}"
    f"\n\n{T['index_grid']}\n\n{T['index_table_head']}\n|---|---|\n{rows}",
    encoding="utf-8",
)
print("built", sorted(p.name for p in OUT.glob("*.md")))
