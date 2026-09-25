# cspell:ignore Conçu produit jalons carrière carriere parcours
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
    # Recursive: covers all SVG variants (fr/en × dark/light), both READMEs,
    # and every generated detail page (fr + en).
    out = {r.name: r.read_text(encoding="utf-8") for r in READMES}
    for svg in sorted(SVG_DIR.rglob("*.svg")):
        out[str(svg.relative_to(SVG_DIR))] = svg.read_text(encoding="utf-8")
    for page in sorted((ROOT / "pages").rglob("*.md")):
        out[str(page.relative_to(ROOT))] = page.read_text(encoding="utf-8")
    return out


def test_front_links_to_the_four_detail_pages():
    fr = (ROOT / "README.md").read_text(encoding="utf-8")
    for page in ("stack", "journey", "projects", "working-with-me"):
        assert f"(pages/{page}.md)" in fr
        assert (ROOT / "pages" / f"{page}.md").exists()
    en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    for page in ("stack", "journey", "projects", "working-with-me"):
        assert f"(pages/en/{page}.md)" in en
        assert (ROOT / "pages" / "en" / f"{page}.md").exists()


def test_front_is_lean_with_dashboards_moved_to_pages():
    fr = (ROOT / "README.md").read_text(encoding="utf-8")
    for moved in ("services.svg", "core-expertise.svg", "featured-projects.svg"):
        assert moved not in fr
    assert "core-expertise.svg" in (ROOT / "pages" / "stack.md").read_text(
        encoding="utf-8"
    )
    assert "featured-projects.svg" in (
        (ROOT / "pages" / "projects.md").read_text(encoding="utf-8")
    )
    assert "services.svg" in (
        (ROOT / "pages" / "working-with-me.md").read_text(encoding="utf-8")
    )


def test_pages_back_link_resolves_per_language():
    assert "../README.md" in (ROOT / "pages" / "stack.md").read_text(encoding="utf-8")
    assert "../../README.en.md" in (
        (ROOT / "pages" / "en" / "stack.md").read_text(encoding="utf-8")
    )


def test_generation_leaves_no_unrendered_jinja():
    for name, content in _read_all().items():
        assert "{{" not in content, f"unrendered expression in {name}"
        assert "{%" not in content, f"unrendered statement in {name}"


def test_generated_svgs_are_well_formed_xml():
    svgs = sorted(SVG_DIR.rglob("*.svg"))
    assert any(s.parent.name == "dark" for s in svgs)  # both variants present
    for svg in svgs:
        ET.fromstring(svg.read_text(encoding="utf-8"))  # raises on malformed XML


def test_every_picture_defaults_to_light_with_a_dark_override():
    # One dual-render mechanism for every figure: the <img> fallback carries
    # the default variant and prefers-color-scheme:dark is the override.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert "(prefers-color-scheme: light)" not in text
        assert "(prefers-color-scheme: dark)" in text


def test_readme_is_light_first():
    # Light-first: the <img> default is the light (root-dir) SVG; dark is the
    # prefers-color-scheme override. The old light/ subdir must be gone.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert 'media="(prefers-color-scheme: dark)"' in text
        assert "dark/header.svg" in text
        assert "light/header.svg" not in text  # light is now the default, not a source
    assert not (SVG_DIR / "light").exists()
    assert (SVG_DIR / "dark").is_dir()


def test_generation_is_deterministic():
    # The session fixture already rendered once; this compares that output
    # against a second, independent run.
    first = _read_all()
    gen.main()
    second = _read_all()
    assert first == second


def test_quality_manifesto_is_localized_per_readme():
    # Bilingual rule: prose is French in README.md, English in README.en.md.
    fr = (ROOT / "README.md").read_text(encoding="utf-8")
    en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    assert "Conçu comme un produit" in fr
    assert "Built like a product" not in fr
    assert "Built like a product" in en


def test_timeline_alt_says_parcours_not_carriere():
    # 1990s milestones are personal (basketball), not career — use "parcours".
    # The timeline now lives on the journey page.
    fr = (ROOT / "pages" / "journey.md").read_text(encoding="utf-8")
    assert "jalons de parcours" in fr.lower()
    assert "jalons de carrière" not in fr


def test_footer_exposes_no_fake_email():
    # `boris@github` reads as a non-viable email in the footer; use a real ref.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert "boris@github" not in text, f"fake email-like token in {readme.name}"
        assert "github.com/Rinzler78" in text


def test_front_contact_cluster_has_phone_and_whatsapp():
    # All communication channels live on the front, phone actionable via tel:
    # and WhatsApp (wa.me, digits derived from profile.contacts.phone).
    for readme in READMES:
        t = readme.read_text(encoding="utf-8")
        assert "mailto:borisleclere.pro@gmail.com" in t
        assert "linkedin.com/in/borisleclere" in t
        assert "malt.fr/profile/borisleclere" in t
        assert "pypi.org/user/Rinzler78" in t
        assert "discordapp.com/users/rinzler84" in t
        assert "twitter.com/BorisLeclere" in t
        assert "tel:+33626263461" in t
        assert "https://wa.me/33626263461" in t


def test_location_uses_committed_osm_map_linked_to_live():
    # Real OSM raster (light + dark), committed for reliability, linked to the
    # live OpenStreetMap page. The hand-drawn map.svg is retired.
    for readme in READMES:
        t = readme.read_text(encoding="utf-8")
        assert "assets/map.png" in t
        assert "assets/map-dark.png" in t
        assert "openstreetmap.org/?mlat=43.74&mlon=5.06" in t
        assert "map.svg" not in t
    assert (ROOT / "assets" / "map.png").exists()
    assert (ROOT / "assets" / "map-dark.png").exists()


def test_no_third_party_service_renders_any_figure():
    # ADR-009: every figure is generated from this repo's own data. The
    # replaced widgets were also a liability — two of the three were returning
    # 503 and 402 while this was written, so the profile showed broken images.
    RENDERERS = (
        "readme-typing-svg.demolab.com",
        "github-readme-stats.vercel.app",
        "github-readme-activity-graph.vercel.app",
        "github-contribution-grid-snake",
        "github-profile-trophy.vercel.app",
        "capsule-render.vercel.app",
        "streak-stats.demolab.com",
    )
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        for renderer in RENDERERS:
            assert renderer not in text, f"{readme.name} still renders via {renderer}"


def test_the_front_page_carries_the_charts_it_replaced_them_with():
    # A widget is removed only when something stronger stands in its place
    # (ADR-009): the three in-house charts are that replacement.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        for chart in ("journey-share.svg", "top-skills.svg", "domain-split.svg"):
            assert chart in text, f"{readme.name} is missing {chart}"


def test_each_chart_is_doubled_by_a_text_conclusion():
    # The charts are images: a reader who only reads prose, or who reads with a
    # screen reader, must still get the point. The expected prose is read from
    # the data rather than repeated here — a copy in the test would pass while
    # the page said something else.
    import json

    charts = json.loads((ROOT / "data" / "content.json").read_text(encoding="utf-8"))[
        "charts"
    ]
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for key, block in charts.items():
        conclusion = block.get("conclusion")
        assert conclusion, f"{key} has no conclusion to double its chart"
        assert conclusion in text, f"{key}: the conclusion never reaches the page"
