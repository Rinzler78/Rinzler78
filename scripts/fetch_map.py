"""Fetch a static OSM map for the profile location — run manually, like
``fetch_metrics.py``.

The README cannot embed an interactive map (no JS/iframe in GitHub markdown)
and the generator must stay deterministic and offline, so this script is run
by hand on relocation: it stitches OpenStreetMap raster tiles (light) and
CartoDB dark tiles (dark) around the location, drops a marker, and writes the
committed assets ``assets/map.png`` / ``assets/map-dark.png``. The README then
serves those committed rasters (reliable, no runtime external dependency) and
links to the live OpenStreetMap page.

Usage: ``python scripts/fetch_map.py``
"""

from __future__ import annotations

import json
import math
import pathlib
import urllib.request

from PIL import Image, ImageDraw

REPO = pathlib.Path(__file__).resolve().parent.parent
PROFILE = REPO / "data" / "profile.json"
THEME = REPO / "data" / "theme.json"
ASSETS = REPO / "assets"

TILE = 256
ZOOM = 9
SIZE = (640, 280)
UA = "RinzlerProfileBot/1.0 (+https://github.com/Rinzler78)"
LIGHT_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DARK_TILES = "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"


def deg2px(lat: float, lon: float, zoom: float) -> tuple[float, float]:
    """World pixel coordinates of a lat/lon at ``zoom`` (Web Mercator)."""
    n = 2.0**zoom
    x = (lon + 180.0) / 360.0 * n * TILE
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n * TILE
    return x, y


def _hex_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def build_map(
    tmpl: str, lat: float, lon: float, marker: str, out: pathlib.Path
) -> None:
    w, h = SIZE
    px, py = deg2px(lat, lon, ZOOM)
    x0, x1 = int((px - w / 2) // TILE), int((px + w / 2) // TILE)
    y0, y1 = int((py - h / 2) // TILE), int((py + h / 2) // TILE)

    canvas = Image.new("RGB", ((x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE))
    for xt in range(x0, x1 + 1):
        for yt in range(y0, y1 + 1):
            req = urllib.request.Request(
                tmpl.format(z=ZOOM, x=xt, y=yt), headers={"User-Agent": UA}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
                tile = Image.open(resp).convert("RGB")
            canvas.paste(tile, ((xt - x0) * TILE, (yt - y0) * TILE))

    left, top = px - x0 * TILE - w / 2, py - y0 * TILE - h / 2
    crop = canvas.crop((int(left), int(top), int(left) + w, int(top) + h))

    draw = ImageDraw.Draw(crop, "RGBA")
    mx, my = w // 2, h // 2
    draw.ellipse(
        [mx - 10, my - 10, mx + 10, my + 10],
        fill=_hex_rgba(marker),
        outline=(255, 255, 255, 255),
        width=3,
    )
    draw.ellipse([mx - 3, my - 3, mx + 3, my + 3], fill=(255, 255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    # Quantize to a 256-colour palette: a detailed map raster drops from
    # ~330 KB to ~120 KB with no perceptible loss, keeping the repo light.
    crop.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(out, optimize=True)
    print(f"  ✓ {out.relative_to(REPO)} ({out.stat().st_size // 1024} KB)")


def main() -> int:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    theme = json.loads(THEME.read_text(encoding="utf-8"))
    lat, lon = profile["location"]["lat"], profile["location"]["lon"]
    print(f"[fetch_map.py] location: {lat}, {lon} (zoom {ZOOM})")
    build_map(
        LIGHT_TILES, lat, lon, theme["palette_light"]["accent"], ASSETS / "map.png"
    )
    build_map(DARK_TILES, lat, lon, theme["palette"]["accent"], ASSETS / "map-dark.png")
    print("[fetch_map.py] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
