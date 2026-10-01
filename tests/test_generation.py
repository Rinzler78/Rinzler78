# cspell:ignore jalons carrière carriere parcours
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


def test_detail_pages_still_carry_their_own_view():
    # ADR-009 reversed ADR-008's lean front: the figures below are now on the
    # front page as well. What the detail pages must keep is their own copy —
    # they go deeper, they are not emptied by the front page carrying the
    # headline.
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
    assert any(s.parent.name == "light" for s in svgs)  # both variants present
    for svg in svgs:
        ET.fromstring(svg.read_text(encoding="utf-8"))  # raises on malformed XML


def test_every_picture_defaults_to_dark_with_a_light_override():
    # One dual-render mechanism for every figure: the <img> fallback carries
    # the default variant and prefers-color-scheme:light is the override.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert "(prefers-color-scheme: dark)" not in text
        assert "(prefers-color-scheme: light)" in text


def test_readme_is_dark_first():
    # ADR-009 reverses the posture: the <img> fallback is the dark (root-dir)
    # SVG and light is the prefers-color-scheme override. The old dark/ subdir
    # must be gone, or stale files from the previous posture keep shipping.
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert 'media="(prefers-color-scheme: light)"' in text
        assert "light/identity.svg" in text
        assert "dark/identity.svg" not in text  # dark is the default, not a source
    assert not (SVG_DIR / "dark").exists()
    assert (SVG_DIR / "light").is_dir()


def test_generation_is_deterministic():
    # The session fixture already rendered once; this compares that output
    # against a second, independent run.
    first = _read_all()
    gen.main()
    second = _read_all()
    assert first == second


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


def test_each_chart_is_doubled_by_a_text_conclusion():
    # The charts are images: a reader who only reads prose, or who reads with a
    # screen reader, must still get the point. The expected prose is computed
    # from the data rather than repeated here — a copy in the test would pass
    # while the page said something else.
    import copy

    from scripts.translate import CACHE, localize_data

    raw = gen.load_data()
    pages = {
        "fr": (copy.deepcopy(raw), ROOT / "README.md"),
        "en": (gen._escape_amp(localize_data(raw, CACHE)), ROOT / "README.en.md"),
    }
    for lang, (bag, _readme) in pages.items():
        # The history charts moved to the stack page with the v2 front page.
        stack = ROOT / "pages" / ("en/" if lang == "en" else "") / "stack.md"
        text = stack.read_text(encoding="utf-8")
        for key, block in gen.enrich(bag, lang)["content"]["charts"].items():
            conclusion = block.get("conclusion")
            assert conclusion, f"{key} has no conclusion to double its chart"
            assert conclusion in text, (
                f"{lang} {key}: the conclusion is not on the page"
            )


def test_activity_stats_count_claims_no_hours_threshold():
    # The count is of displayed levels, and an attested evidence level can
    # lift a tech below 50 h (ADR-018): the label must not promise "50 h".
    import defusedxml.ElementTree as ET

    fr = ET.fromstring((SVG_DIR / "activity-stats.svg").read_text(encoding="utf-8"))
    en = ET.fromstring(
        (SVG_DIR / "en" / "activity-stats.svg").read_text(encoding="utf-8")
    )
    for root in (fr, en):
        assert "50 h" not in root.get("aria-label")
    assert "displayed level" in en.get("aria-label")
    assert fr.get("aria-label") != en.get("aria-label")


def test_every_generated_svg_is_shown_somewhere():
    # A view nobody links is a view nobody sees; generation clears the tree
    # first, so a retired view cannot linger either.
    shown = "".join(_read_all()[k] for k in _read_all() if k.endswith(".md"))
    for svg in sorted(SVG_DIR.glob("*.svg")):
        assert svg.name in shown, f"{svg.name} is generated but shown nowhere"


def test_history_charts_live_on_the_stack_page():
    for page in (ROOT / "pages" / "stack.md", ROOT / "pages" / "en" / "stack.md"):
        text = page.read_text(encoding="utf-8")
        for chart in ("journey-share.svg", "top-skills.svg", "domain-split.svg"):
            assert chart in text, f"{page.name} is missing {chart}"
