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
READMES = [ROOT / "README.md", ROOT / "README.en.md"]


def _read_all() -> dict[str, str]:
    # Recursive: covers all SVG variants (fr/en × dark/light) plus both READMEs.
    out = {r.name: r.read_text(encoding="utf-8") for r in READMES}
    for svg in sorted(SVG_DIR.rglob("*.svg")):
        out[str(svg.relative_to(SVG_DIR))] = svg.read_text(encoding="utf-8")
    return out


def test_generation_leaves_no_unrendered_jinja():
    gen.main()
    for name, content in _read_all().items():
        assert "{{" not in content, f"unrendered expression in {name}"
        assert "{%" not in content, f"unrendered statement in {name}"


def test_generated_svgs_are_well_formed_xml():
    gen.main()
    svgs = sorted(SVG_DIR.rglob("*.svg"))
    assert any(s.parent.name == "light" for s in svgs)  # both variants present
    for svg in svgs:
        ET.fromstring(svg.read_text(encoding="utf-8"))  # raises on malformed XML


def test_generation_is_deterministic():
    gen.main()
    first = _read_all()
    gen.main()
    second = _read_all()
    assert first == second


def test_readmes_embed_the_live_github_widgets():
    # PRD-001 animations: typing banner, stats card (rank hidden), activity
    # graph and the contribution snake must appear in both language READMEs.
    gen.main()
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert "readme-typing-svg.demolab.com" in text
        assert "github-readme-stats.vercel.app" in text
        assert "hide_rank=true" in text  # anti-inflation: no grade circle
        assert "github-readme-activity-graph.vercel.app" in text
        assert "github-contribution-grid-snake" in text
