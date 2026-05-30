"""Generation pipeline guards (PRD: test_generation / test_determinism).

These run the real generator into the repo's output files. Generation is
idempotent, so re-running it is safe; the determinism test asserts a second
run produces byte-identical output.
"""

from pathlib import Path

import defusedxml.ElementTree as ET  # secure XML parsing (bandit B314/B405)

import scripts.generate as gen

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets" / "svg"
README = ROOT / "README.md"


def _read_all() -> dict[str, str]:
    out = {"README.md": README.read_text(encoding="utf-8")}
    for svg in sorted(SVG_DIR.glob("*.svg")):
        out[svg.name] = svg.read_text(encoding="utf-8")
    return out


def test_generation_leaves_no_unrendered_jinja():
    gen.main()
    for name, content in _read_all().items():
        assert "{{" not in content, f"unrendered expression in {name}"
        assert "{%" not in content, f"unrendered statement in {name}"


def test_generated_svgs_are_well_formed_xml():
    gen.main()
    for svg in sorted(SVG_DIR.glob("*.svg")):
        ET.fromstring(svg.read_text(encoding="utf-8"))  # raises on malformed XML


def test_generation_is_deterministic():
    gen.main()
    first = _read_all()
    gen.main()
    second = _read_all()
    assert first == second
