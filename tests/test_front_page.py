# cspell:ignore Réalisations Compétences Chronologie Méthode Activité méthode peux voit
# cspell:ignore preuve preuves téléchargements étoiles jours aujourd
"""The generated front page v2, as it ships (ADR-015, ADR-016, ADR-018)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "svg"
AGGREGATES = json.loads(
    (ROOT / "data" / "activity" / "aggregates.json").read_text(encoding="utf-8")
)
LOCK = json.loads((ROOT / "data" / "claims.lock.json").read_text(encoding="utf-8"))
PROJECTS = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))
TECHS = json.loads((ROOT / "data" / "techs.json").read_text(encoding="utf-8"))


def _headings(text: str) -> list[str]:
    return re.findall(r"^#{2,3} (.+)$", text, flags=re.MULTILINE)


def _fresh_text() -> tuple[str, str]:
    # The session fixture regenerated the READMEs after import time.
    return (
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "README.en.md").read_text(encoding="utf-8"),
    )


def test_sections_follow_the_pyramid_order():
    fr, en = _fresh_text()
    expected_fr = ["Comment je peux aider", "Open source", "Compétences"]
    expected_fr += ["Chronologie", "Méthode", "Activité", "Ce que GitHub voit"]
    expected_fr += ["Pour aller plus loin"]
    expected_en = ["How I can help", "Open source", "Skills", "Timeline", "Method"]
    expected_en += ["Activity", "What GitHub sees", "Going further"]
    if LOCK["claims"]:
        expected_fr.insert(1, "Réalisations")
        expected_en.insert(1, "Achievements")
    assert _headings(fr) == expected_fr
    assert _headings(en) == expected_en


def test_identity_comes_first_as_two_half_tiles():
    fr, _ = _fresh_text()
    first_images = re.findall(r'<img src="assets/svg/([^"]+)" width="(\d+)"', fr)[:2]
    assert first_images == [("identity.svg", "415"), ("figures.svg", "415")]


def test_no_achievement_heading_while_nothing_is_attested():
    if LOCK["claims"]:
        return
    fr, en = _fresh_text()
    assert "Réalisations" not in fr and "Achievements" not in en
    assert "<!-- claim:" not in fr + en


def test_nothing_is_presented_as_proof():
    fr, en = _fresh_text()
    assert not re.search(r"\bpreuves?\b", fr, flags=re.IGNORECASE)
    assert not re.search(r"\bproofs?\b", en, flags=re.IGNORECASE)


def test_contacts_are_native_links_not_images():
    fr, en = _fresh_text()
    for text in (fr, en):
        assert "](mailto:borisleclere.pro@gmail.com)" in text
        assert "](https://www.linkedin.com/in/borisleclere)" in text
        assert "](https://www.malt.fr/profile/borisleclere)" in text
        assert "](https://github.com/Rinzler78)" in text
        assert "chip-" not in text


def test_every_half_tile_is_415_px_and_carries_alt_text():
    fr, en = _fresh_text()
    for text in (fr, en):
        for tag in re.findall(r'<img src="assets/svg/[^"]+"[^>]*>', text):
            name = re.search(r'src="assets/svg/(?:en/)?([^"]+)"', tag).group(1)
            assert re.search(r'alt="[^"]+"', tag), tag
            if not name.startswith("skills-band"):
                assert 'width="415"' in tag, tag


def test_tiles_are_fixed_size_on_the_shared_grid():
    for name in ("identity.svg", "figures.svg"):
        root = ET.fromstring((SVG / name).read_text(encoding="utf-8"))
        assert root.get("width") == "590"
        assert root.get("height")
        assert root.get("viewBox") == f"0 0 590 {root.get('height')}"


def test_the_name_is_outlined_and_still_read_by_screen_readers():
    svg = (SVG / "identity.svg").read_text(encoding="utf-8")
    assert "Boris Leclere" not in re.sub(
        r'aria-label="[^"]*"|<title>.*?</title>', "", svg
    )
    assert 'aria-label="Boris Leclere, ' in svg


def test_tiles_use_the_green_palette_per_theme():
    assert "#a3e635" in (SVG / "figures.svg").read_text(encoding="utf-8")
    light = (SVG / "light" / "figures.svg").read_text(encoding="utf-8")
    assert "#3f6212" in light and "#a3e635" not in light


def test_key_figures_are_the_computed_ones():
    figures = ET.fromstring((SVG / "figures.svg").read_text(encoding="utf-8"))
    aria = figures.get("aria-label")
    days = f"{AGGREGATES['coverage']['commit_days']:,}".replace(",", " ")
    assert days in aria
    years = int(AGGREGATES["activity_as_of"][:4]) - 2006
    assert aria.startswith(f"{years} ans de code")


def test_every_skill_line_is_on_the_page():
    # ADR-016: every tech shown as a skill appears on the front page.
    fr, _ = _fresh_text()
    labels = {t["id"]: t["label"] for t in TECHS}
    alts = " ".join(re.findall(r'alt="([^"]+)"', fr))
    for tech_id, entry in AGGREGATES["techs"].items():
        if entry["display_level"]:
            label = labels[tech_id].replace("&", "&amp;")
            assert label in alts, f"{tech_id} is not on the front page"


def test_git_is_in_the_icon_band_only():
    fr, _ = _fresh_text()
    assert re.search(r"skillicons\.dev/icons\?i=[a-z,]*\bgit\b", fr)
    alts = " ".join(re.findall(r'alt="([^"]+)"', fr))
    assert not re.search(r"\bGit\b ≈", alts)


def test_counters_are_live_badges_never_typed():
    fr, _ = _fresh_text()
    for project in PROJECTS:
        metrics = project.get("metrics") or {}
        if not project.get("description"):
            continue
        if metrics.get("pypi"):
            assert f"img.shields.io/pypi/dm/{metrics['pypi']}?" in fr
        if metrics.get("dockerhub"):
            assert f"img.shields.io/docker/pulls/{metrics['dockerhub']}?" in fr
    en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    typed = r"\d[\d ,.]*\s*(pulls|téléchargements|downloads|étoiles|stars)"
    assert not re.search(typed, fr + en, flags=re.IGNORECASE)


def test_github_widgets_are_labelled_as_what_github_sees():
    fr, en = _fresh_text()
    for text, title in ((fr, "### Ce que GitHub voit"), (en, "### What GitHub sees")):
        widgets = text.split(title, 1)[1]
        assert "github-contribution-grid-snake-dark.svg" in widgets
        assert "streak-stats.demolab.com" in widgets
        assert "streak-stats.demolab.com" not in text.split(title, 1)[0]


def test_remote_images_come_only_from_live_sources():
    allowed = (
        "https://skillicons.dev/icons?",
        "https://img.shields.io/",
        "https://streak-stats.demolab.com/",
        "https://raw.githubusercontent.com/Rinzler78/Rinzler78/output/",
    )
    fr, en = _fresh_text()
    for text in (fr, en):
        remote = re.findall(r'(?:src|srcset)="(https?://[^"]+)"', text)
        remote += re.findall(r"!\[[^\]]*\]\((https?://[^)]+)\)", text)
        for url in remote:
            assert url.startswith(allowed), url


def test_calendar_draws_every_commit_day():
    drawn = 0
    for svg in sorted(SVG.glob("calendar-*.svg")):
        drawn += svg.read_text(encoding="utf-8").count("fill-opacity=") - 5  # legend
    assert drawn == AGGREGATES["coverage"]["commit_days"]


def test_timeline_lines_link_to_anchors_that_exist():
    fr, en = _fresh_text()
    for text, page in ((fr, "pages/journey.md"), (en, "pages/en/journey.md")):
        journey = (ROOT / page).read_text(encoding="utf-8")
        anchors = re.findall(rf"\({re.escape(page)}#(exp-[a-z0-9-]+)\)", text)
        assert anchors
        for anchor in anchors:
            assert f'id="{anchor}"' in journey, anchor


def test_timeline_is_newest_first():
    fr, _ = _fresh_text()
    years = [int(y) for y in re.findall(r"^- \*\*(\d{4})", fr, flags=re.MULTILINE)]
    assert years == sorted(years, reverse=True)


def test_footer_signs_with_the_activity_date_and_the_method():
    fr, en = _fresh_text()
    for text, anchor in ((fr, "#méthode"), (en, "#method")):
        footer = text.rsplit("---", 1)[1]
        assert AGGREGATES["activity_as_of"] in footer
        assert f"]({anchor})" in footer
        assert "mailto:" not in footer
        assert "$ uptime" in footer


def test_english_page_carries_english_copy():
    _, en = _fresh_text()
    for french in ("Comment je peux aider", "jours de commit", "aujourd'hui"):
        assert french not in en
    assert "commit days" in en


def test_icon_band_is_one_line_in_band_order():
    fr, _ = _fresh_text()
    section = fr.split("## Compétences", 1)[1].split("skills-embedded.svg", 1)[0]
    band_lines = [
        line
        for line in section.splitlines()
        if "skillicons.dev" in line or "skills-band-" in line
    ]
    assert len(band_lines) == 1  # one flowing paragraph, runs in order
    assert band_lines[0].index("skills-band-1.svg") < band_lines[0].index(
        "skillicons.dev"
    )
