"""Tech icons: vendored brand paths, contrast fallback, the hybrid icon band."""

from __future__ import annotations

import json
from pathlib import Path

import defusedxml.ElementTree as ET
import pytest

from scripts import icons

ROOT = Path(__file__).resolve().parent.parent
ICONS = json.loads((ROOT / "data" / "icons.json").read_text(encoding="utf-8"))

DOC = {
    "version": 1,
    "techs": {
        "python": {"band": "py", "tile": "simple-icons/python", "color": "#3776AB"},
        "nfc": {"tile": "simple-icons/nfc", "color": "#002E5F"},
        "gps": {"initials": "GPS"},
        "docker": {"band": "docker", "tile": "simple-icons/docker", "color": "#2496ED"},
        "dotnet-5": {
            "band": "dotnet",
            "tile": "simple-icons/dotnet",
            "color": "#512BD4",
        },
        "asp-net-core": {
            "band": "dotnet",
            "tile": "simple-icons/dotnet",
            "color": "#512BD4",
        },
        "git": {
            "band": "git",
            "tile": "simple-icons/git",
            "color": "#F03C2E",
            "band_only": True,
        },
    },
}


# --- Contrast (WCAG 2 relative luminance) -------------------------------------


def test_contrast_of_black_on_white_is_21():
    assert icons.contrast("#000000", "#ffffff") == pytest.approx(21.0)


def test_contrast_is_symmetric_and_one_for_equal_colors():
    assert icons.contrast("#3776ab", "#0c0f0a") == icons.contrast("#0c0f0a", "#3776ab")
    assert icons.contrast("#a3e635", "#a3e635") == pytest.approx(1.0)


def test_brand_color_is_kept_when_it_reads_on_the_background():
    assert icons.ink_for("#3776AB", "#fbfcf8", "#141810") == "#3776AB"


def test_brand_color_falls_back_to_the_monochrome_variant():
    # NFC's navy on a near-black tile is below 3:1, the non-text minimum.
    assert icons.ink_for("#002E5F", "#0c0f0a", "#eef2e8") == "#eef2e8"
    # Linux yellow on a near-white tile is too.
    assert icons.ink_for("#FCC624", "#fbfcf8", "#141810") == "#141810"


# --- Tile icons ---------------------------------------------------------------


def test_a_vendored_icon_reads_its_paths_and_view_box():
    spec = icons.tile_icon("python", DOC)
    assert spec.kind == "vendored"
    assert spec.view_box == (0.0, 0.0, 24.0, 24.0)
    assert spec.paths and all(p.startswith("M") for p in spec.paths)
    assert spec.color == "#3776AB"


def test_multi_path_devicon_keeps_every_path():
    spec = icons.tile_icon(
        "objective-c",
        {
            "techs": {
                "objective-c": {
                    "tile": "devicon/objectivec-plain",
                    "color": "#0B5A9D",
                }
            }
        },
    )
    assert len(spec.paths) > 1
    assert spec.view_box == (0.0, 0.0, 128.0, 128.0)


def test_a_tech_without_logo_gets_its_initials():
    spec = icons.tile_icon("gps", DOC)
    assert spec.kind == "initials"
    assert spec.initials == "GPS"


def test_a_tech_missing_from_the_map_fails_the_build():
    with pytest.raises(ValueError, match="ghost"):
        icons.tile_icon("ghost", DOC)


def test_render_vendored_icon_scales_into_its_box():
    spec = icons.tile_icon("python", DOC)
    out = icons.render(spec, 10, 20, 36, fill="#3776AB", ink={})
    assert 'transform="translate(10,20) scale(1.5)"' in out
    assert 'fill="#3776AB"' in out
    ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{out}</svg>')


def test_render_initials_draws_a_badge_with_the_letters():
    spec = icons.tile_icon("gps", DOC)
    ink = {"stroke": "#a3e635", "text": "#a3e635", "fill": "#0c0f0a"}
    out = icons.render(spec, 0, 0, 36, fill="", ink=ink)
    assert ">GPS</text>" in out
    assert "<rect" in out


def test_initials_shrink_to_fit_but_never_under_the_floor():
    long = icons.initials_font_size("MVVM", 36)
    short = icons.initials_font_size("AR", 36)
    assert long < short
    assert long >= icons.MIN_FONT


# --- Icon band ----------------------------------------------------------------


def test_band_keeps_order_deduplicates_and_skips_initials():
    entries = icons.band_entries(
        ["python", "gps", "dotnet-5", "nfc", "asp-net-core"], DOC
    )
    assert [(e.source, e.key) for e in entries] == [
        ("skillicons", "py"),
        ("skillicons", "dotnet"),
        ("local", "nfc"),
        ("skillicons", "git"),  # band-only tools come last
    ]


def test_skillicons_url_lists_ids_per_theme():
    url = icons.skillicons_url(["py", "docker"], theme="light", per_line=16)
    assert url == "https://skillicons.dev/icons?i=py,docker&theme=light&perline=16"


def test_band_rows_split_skillicons_and_local_by_line_length():
    rows = icons.band_rows(["a", "b", "c"], per_line=2)
    assert rows == [["a", "b"], ["c"]]


def test_band_width_matches_the_skillicons_geometry():
    # skillicons.dev draws 256-unit icons on a 300-unit pitch.
    assert icons.band_units(1) == 256
    assert icons.band_units(16) == 16 * 300 - 44


def test_local_band_svg_uses_the_skillicons_template():
    out = icons.band_svg(["nfc"], DOC, theme="dark")
    root = ET.fromstring(out)
    assert root.get("width") == "256" and root.get("height") == "256"
    assert icons.BAND_BG["dark"] in out
    assert 'rx="60"' in out


def test_local_band_svg_light_background():
    assert icons.BAND_BG["light"] in icons.band_svg(["nfc"], DOC, theme="light")


# --- Real data ----------------------------------------------------------------


def test_every_mapped_icon_file_exists_and_parses():
    for tech_id, entry in ICONS["techs"].items():
        if "tile" in entry:
            spec = icons.tile_icon(tech_id, ICONS)
            assert spec.paths, tech_id


def test_vendored_sources_ship_their_license():
    assert (ROOT / "assets" / "icons" / "devicon" / "LICENSE").is_file()
    assert (ROOT / "assets" / "icons" / "simple-icons" / "LICENSE.md").is_file()


def test_only_used_icons_are_vendored():
    used = {e["tile"] for e in ICONS["techs"].values() if "tile" in e}
    on_disk = {
        f"{p.parent.name}/{p.stem}" for p in (ROOT / "assets" / "icons").rglob("*.svg")
    }
    assert on_disk == used


def test_initials_too_wide_for_the_badge_are_tightened_not_shrunk():
    spec = icons.IconSpec("mvvm", "initials", initials="MVVM")
    ink = {"stroke": "#a3e635", "text": "#a3e635", "fill": "#0c0f0a"}
    out = icons.render(spec, 0, 0, 48, fill="", ink=ink)
    # 4 glyphs x 0.62 em x 20 = 49.6 units for 42 of room: -1.9 per glyph.
    assert 'letter-spacing="-1.9"' in out
    assert 'font-size="20"' in out
