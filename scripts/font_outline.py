"""Outline display text to a single SVG path (ADR-007).

GitHub serves README SVGs through an ``<img>`` tag that loads no web font, so
the hero's display text (name + arc labels) is converted to vector paths at
generation time — it then renders identically for every visitor, independent
of their OS fonts.

Glyphs are laid out left-to-right by their advance widths (no kerning — fine
for short display strings), flipped from the font's y-up space into SVG's
y-down space with the baseline at ``y = 0``, and scaled so ``size`` is the em
size in pixels. Pure and deterministic: same (text, font, size) -> same path.
"""

from __future__ import annotations

from functools import lru_cache

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


@lru_cache(maxsize=4)
def _font(font_path: str) -> TTFont:
    return TTFont(font_path)


def outline_text(text: str, font_path: str, size: float) -> dict:
    """Return ``{path, width, ascent, descent}`` for ``text`` at ``size`` px.

    ``path`` is a single SVG path ``d`` string with the baseline at ``y = 0``
    (ascenders negative). ``width`` is the advance width in px.
    """
    font = _font(font_path)
    upem = font["head"].unitsPerEm
    scale = size / upem
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]

    svg_pen = SVGPathPen(glyph_set)
    x = 0.0
    for ch in text:
        gname = cmap.get(ord(ch))
        if gname is None:
            x += upem * 0.3  # unknown char -> blank advance
            continue
        # Bake scale + y-flip + horizontal offset into the path coordinates so
        # the result is one flat <path d=...> with no wrapping transform.
        tpen = TransformPen(svg_pen, (scale, 0, 0, -scale, x * scale, 0))
        glyph_set[gname].draw(tpen)
        x += hmtx[gname][0]

    return {
        "path": svg_pen.getCommands(),
        "width": round(x * scale, 2),
        "ascent": round(font["hhea"].ascent * scale, 2),
        "descent": round(font["hhea"].descent * scale, 2),
    }
