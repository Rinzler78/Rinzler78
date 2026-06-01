from pathlib import Path

from scripts.font_outline import outline_text

ROOT = Path(__file__).resolve().parent.parent
FONT = str(ROOT / "assets" / "fonts" / "Fraunces-Display.ttf")


def test_outline_text_produces_a_path_and_metrics():
    r = outline_text("Boris", FONT, 64)
    assert r["path"].startswith("M")  # SVG path data
    assert r["width"] > 0
    assert r["ascent"] > 0


def test_outline_text_is_deterministic():
    assert outline_text("Leclere", FONT, 48) == outline_text("Leclere", FONT, 48)


def test_outline_text_width_scales_linearly_with_size():
    small = outline_text("ai", FONT, 20)["width"]
    big = outline_text("ai", FONT, 40)["width"]
    assert abs(big - 2 * small) < 0.5


def test_outline_text_counts_spaces_in_width():
    assert (
        outline_text("a b", FONT, 30)["width"] > outline_text("ab", FONT, 30)["width"]
    )


def test_outline_text_skips_glyphs_absent_from_the_subset():
    # A char outside the subset (here U+4E2D) advances without crashing.
    r = outline_text("a" + chr(0x4E2D) + "b", FONT, 30)
    assert r["width"] > 0
