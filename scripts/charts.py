"""Static SVG chart primitives for the generated profile.

GitHub serves README SVGs through an `<img>` tag: no JavaScript, no hover, no
tooltip, no second render. Everything a reader needs has to be in the markup —
so each chart bakes in its own direct labels, and every function returns a
complete, self-describing `<svg>` with an `aria-label`.

Series colors are supplied by the caller and come from a palette validated for
color-vision deficiency. They are deliberately *not* the brand accent: an
indigo/coral-led categorical set measured ΔE 1.5 between coral and aqua under
protanopia, i.e. two series a colorblind reader cannot separate. Indigo and
coral stay as interface accents, never as series identity.
"""

from __future__ import annotations

import math

MONO = "'JetBrains Mono', ui-monospace, monospace"
SANS = "'Inter', system-ui, sans-serif"


def escape(text: str) -> str:
    """Escape text for XML character data and attribute values.

    Deliberately not `xml.sax.saxutils.escape`: importing from `xml.sax` pulls
    a parser module into a file that only ever *writes* markup, which is both
    unnecessary and the thing bandit's B406 blacklist is there to catch. `&`
    must go first, or the ampersands introduced by the later rules get escaped
    a second time.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _t(x: float) -> str:
    """Trim a coordinate: shorter paths, and byte-identical across runs."""
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _text(x, y, content, *, size, fill, weight=600, family=SANS, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    return (
        f'<text x="{_t(x)}" y="{_t(y)}"{a} font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f"{escape(content)}</text>"
    )


def _caption(caption: str, values: str) -> str:
    """Join a caller-supplied caption to the value list.

    The caption is display copy, so it arrives already localized: this module
    writes markup and must not carry prose in any one language, or the English
    README would inherit French accessibility labels.
    """
    return f"{caption}. {values}" if caption else values


def _svg(width, height, aria, body) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_t(width)} {_t(height)}" '
        f'width="100%" role="img" aria-label="{escape(aria)}">'
        f"<title>{escape(aria)}</title>{body}</svg>"
    )


def stacked_area(
    series: dict[str, dict[int, float]],
    colors: dict[str, str],
    ink: dict[str, str],
    *,
    labels: dict[str, str] | None = None,
    caption: str = "",
    width: float = 820,
    height: float = 250,
    label_gutter: float = 128,
) -> str:
    """Share of effort per year, each year normalized to a full column.

    Normalizing is the point: the underlying tier fractions are cumulative, so
    a raw column height would encode double-counted hours and read as growth
    the data never claims. The shape answers "what was he doing then", which
    is a question about proportion.
    """
    labels = labels or {}
    order = list(series)
    years = sorted({y for row in series.values() for y in row})
    if not years:
        return _svg(width, height, caption, "")

    pad_t, pad_b, pad_l = 8.0, 22.0, 4.0
    plot_w = width - pad_l - label_gutter
    plot_h = height - pad_t - pad_b

    shares: list[list[float]] = []
    for year in years:
        column = [max(0.0, series[k].get(year, 0.0)) for k in order]
        total = sum(column)
        shares.append([v / total for v in column] if total else [0.0] * len(order))

    def x_at(i: int) -> float:
        return pad_l if len(years) == 1 else pad_l + plot_w * i / (len(years) - 1)

    def y_at(frac: float) -> float:
        return pad_t + plot_h * (1 - frac)

    parts: list[str] = []
    cursor = [0.0] * len(years)
    for si, key in enumerate(order):
        lower = list(cursor)
        for i in range(len(years)):
            cursor[i] += shares[i][si]
        top = " ".join(
            f"{'M' if i == 0 else 'L'}{_t(x_at(i))},{_t(y_at(cursor[i]))}"
            for i in range(len(years))
        )
        bottom = " ".join(
            f"L{_t(x_at(i))},{_t(y_at(lower[i]))}" for i in reversed(range(len(years)))
        )
        parts.append(
            f'<path d="{top} {bottom} Z" fill="{colors[key]}" '
            f'stroke="{ink["surface"]}" stroke-width="1.5"/>'
        )
        # Direct label on the last column — the only reading aid available
        # without a hover layer. Skipped when the band is too thin to host it.
        last = shares[-1][si]
        if last >= 0.06:
            mid = y_at((cursor[-1] + lower[-1]) / 2) + 4
            parts.append(
                _text(
                    pad_l + plot_w + 10,
                    mid,
                    labels.get(key, key),
                    size=11,
                    fill=ink["text"],
                    weight=700,
                )
            )
            parts.append(
                _text(
                    pad_l + plot_w + 10,
                    mid + 13,
                    f"{round(last * 100)} %",
                    size=10,
                    fill=ink["muted"],
                    weight=400,
                    family=MONO,
                )
            )

    for i, year in enumerate(years):
        if year % 5 == 0 or i in (0, len(years) - 1):
            parts.append(
                _text(
                    x_at(i),
                    height - 6,
                    str(year),
                    size=9.5,
                    fill=ink["dim"],
                    weight=400,
                    family=MONO,
                    anchor="middle",
                )
            )

    aria = _caption(
        caption,
        ", ".join(
            f"{labels.get(k, k)} {round(shares[-1][i] * 100)}% ({years[-1]})"
            for i, k in enumerate(order)
        ),
    )
    return _svg(width, height, aria, "".join(parts))


def donut(
    shares: list[tuple[str, float]],
    colors: dict[str, str],
    ink: dict[str, str],
    *,
    labels: dict[str, str] | None = None,
    caption: str = "",
    size: float = 190,
    thickness: float = 30,
    center_value: str = "",
    center_label: str = "",
) -> str:
    """Lifetime split, as percentages that must make a whole.

    A wedge chart whose parts do not sum to 100 misstates its own denominator,
    and nothing in the drawing reveals it — so that case raises instead.
    """
    total = sum(pct for _, pct in shares)
    if abs(total - 100.0) > 0.5:
        raise ValueError(f"donut shares must sum to 100, got {total:.2f}")

    labels = labels or {}
    outer = size / 2 - 4
    inner = outer - thickness
    c = size / 2
    parts: list[str] = []
    angle = -math.pi / 2

    for key, pct in shares:
        sweep = 2 * math.pi * pct / 100
        end = angle + sweep
        large = 1 if sweep > math.pi else 0
        if pct >= 99.99:  # a single full ring has no arc endpoints to join
            parts.append(
                f'<circle cx="{_t(c)}" cy="{_t(c)}" r="{_t((outer + inner) / 2)}" '
                f'fill="none" stroke="{colors[key]}" stroke-width="{_t(thickness)}"/>'
            )
            angle = end
            continue
        p = [
            (c + outer * math.cos(angle), c + outer * math.sin(angle)),
            (c + outer * math.cos(end), c + outer * math.sin(end)),
            (c + inner * math.cos(end), c + inner * math.sin(end)),
            (c + inner * math.cos(angle), c + inner * math.sin(angle)),
        ]
        parts.append(
            f'<path d="M{_t(p[0][0])},{_t(p[0][1])} '
            f"A{_t(outer)},{_t(outer)} 0 {large} 1 {_t(p[1][0])},{_t(p[1][1])} "
            f"L{_t(p[2][0])},{_t(p[2][1])} "
            f'A{_t(inner)},{_t(inner)} 0 {large} 0 {_t(p[3][0])},{_t(p[3][1])} Z" '
            f'fill="{colors[key]}" stroke="{ink["surface"]}" stroke-width="2"/>'
        )
        angle = end

    if center_value:
        parts.append(
            _text(
                c,
                c - 2,
                center_value,
                size=20,
                fill=ink["text"],
                weight=800,
                anchor="middle",
            )
        )
    if center_label:
        parts.append(
            _text(
                c,
                c + 14,
                center_label,
                size=9,
                fill=ink["dim"],
                weight=400,
                family=MONO,
                anchor="middle",
            )
        )

    aria = _caption(
        caption, ", ".join(f"{labels.get(k, k)} {pct}%" for k, pct in shares)
    )
    return _svg(size, size, aria, "".join(parts))


def bar_rows(
    items: list[tuple[str, float]],
    accent: str,
    ink: dict[str, str],
    *,
    width: float = 820,
    label_width: float = 150,
    row_height: float = 26,
    gap: float = 8,
    maximum: float = 99,
    unit: str = "",
    caption: str = "",
) -> str:
    """Ranked horizontal bars, every value printed beside its bar.

    Values above ``maximum`` are clamped to the track: a bar that overflows its
    own scale reads as a rendering bug rather than as data.
    """
    height = len(items) * (row_height + gap) - gap if items else 0
    track_w = width - label_width - 54
    parts: list[str] = []

    for i, (name, value) in enumerate(items):
        top = i * (row_height + gap)
        filled = track_w * min(max(value, 0.0), maximum) / maximum
        parts.append(
            _text(
                0, top + row_height / 2 + 4, name, size=12, fill=ink["text"], weight=700
            )
        )
        parts.append(
            f'<rect x="{_t(label_width)}" y="{_t(top + 5)}" width="{_t(track_w)}" '
            f'height="{_t(row_height - 10)}" rx="4" fill="{ink["track"]}"/>'
        )
        parts.append(
            f'<rect x="{_t(label_width)}" y="{_t(top + 5)}" width="{_t(filled)}" '
            f'height="{_t(row_height - 10)}" rx="4" fill="{accent}"/>'
        )
        parts.append(
            _text(
                width - 46,
                top + row_height / 2 + 4,
                f"{round(value)}{unit}",
                size=11,
                fill=ink["text"],
                weight=700,
                family=MONO,
            )
        )

    aria = _caption(caption, ", ".join(f"{n} {round(v)}{unit}" for n, v in items))
    return _svg(width, max(height, 1), aria, "".join(parts))


# Rough advance width per character at 1px font-size, for the sans stack. SVGs
# are served without the web font (GitHub strips @font-face inside an <img>),
# so no font metric is available at render time and the box has to be sized
# from an estimate. Erring wide leaves padding; erring narrow clips the text,
# so this is deliberately generous.
_AVG_CHAR_WIDTH = 0.58


def _text_width(text: str, size: float) -> float:
    return len(text) * size * _AVG_CHAR_WIDTH


def chip(
    label: str,
    ink: dict[str, str],
    *,
    accent: str,
    primary: bool = False,
    value: str = "",
    height: float = 34,
    font_size: float = 13,
) -> str:
    """A small pill: the contact row, generated instead of fetched.

    One SVG per chip rather than one image for the row, because an SVG served
    in an `<img>` carries a single link — a combined strip could not be
    clickable per item.
    """
    pad_x, dot, gap = 14.0, 5.0, 8.0
    label_w = _text_width(label, font_size)
    value_w = _text_width(value, font_size - 1.5) + gap if value else 0.0
    width = pad_x * 2 + dot * 2 + gap + label_w + value_w

    fill = accent if primary else ink["surface"]
    stroke = accent if primary else ink["border"]
    text_fill = ink["on_accent"] if primary else ink["text"]
    value_fill = ink["on_accent"] if primary else ink["muted"]
    dot_fill = ink["on_accent"] if primary else accent

    x = pad_x
    parts = [
        f'<rect x="0.5" y="0.5" width="{_t(width - 1)}" height="{_t(height - 1)}" '
        f'rx="{_t(height / 2)}" fill="{fill}" stroke="{stroke}"/>',
        f'<circle cx="{_t(x + dot)}" cy="{_t(height / 2)}" r="{_t(dot)}" '
        f'fill="{dot_fill}"/>',
    ]
    x += dot * 2 + gap
    parts.append(
        _text(
            x,
            height / 2 + font_size * 0.36,
            label,
            size=font_size,
            fill=text_fill,
            weight=700,
        )
    )
    if value:
        x += label_w + gap
        parts.append(
            _text(
                x,
                height / 2 + font_size * 0.36,
                value,
                size=font_size - 1.5,
                fill=value_fill,
                weight=400,
                family=MONO,
            )
        )

    aria = f"{label} {value}".strip()
    return _svg(width, height, aria, "".join(parts))
