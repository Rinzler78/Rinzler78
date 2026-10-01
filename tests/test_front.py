# cspell:ignore gagné actif Méthode méthode peux
"""Front page v2 view model (ADR-015, ADR-016, ADR-018): figures computed from
the data, achievements gated by the claims lock, live badges, skill tiles."""

from __future__ import annotations

import pytest

from scripts import front

WORDS_FR = {"thousands": " ", "decimal": ",", "and": " et "}


# --- Number formatting --------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "words", "text"),
    [
        (30744, WORDS_FR, "30 744"),
        (950, WORDS_FR, "950"),
        (1474, {"thousands": ","}, "1,474"),
    ],
)
def test_thousands(value, words, text):
    assert front.thousands(value, words) == text


def test_join_uses_the_language_conjunction():
    assert front.join(["a", "b", "c"], WORDS_FR) == "a, b et c"
    assert front.join(["a"], WORDS_FR) == "a"
    assert front.join([], WORDS_FR) == ""


# --- Key figures --------------------------------------------------------------


def _aggregates() -> dict:
    return {
        "activity_as_of": "2026-10-01",
        "context_totals": {"pro": 23218.0, "personal": 6518.0, "study": 1008.0},
        "coverage": {"commit_days": 3, "public_share": 0.1649},
        "levels": {
            "working": 50,
            "professional": 500,
            "advanced": 1600,
            "expert": 5000,
        },
        "calendar": {
            "2014-04-24": {"context": "pro", "intensity": 1},
            "2026-09-30": {"context": "personal", "intensity": 4},
            "2026-10-01": {"context": "personal", "intensity": 2},
        },
    }


def test_key_figures_are_computed_never_typed():
    skills = [
        {"level": "expert"},
        {"level": "advanced"},
        {"level": "professional"},
        {"level": "working"},
    ]
    figures = front.key_figures(_aggregates(), {"since_coding": 2006}, skills)
    assert figures == {
        "years": 20,
        # The sum of the additive context totals, rounded down like every
        # displayed figure (to 1,000 above 10,000 h): never above the data.
        "hours": 30000,
        "days": 3,
        "first_year": 2014,
        "skills": 2,
        "since": 2006,
    }


# --- Contacts -----------------------------------------------------------------


def test_contact_links_are_native_markdown_targets():
    profile = {
        "contacts": {"email_pro": "me@example.org"},
        "links": {
            "linkedin": "https://l.example",
            "malt": "https://m.example",
            "github": "https://g.example",
            "pypi": "https://p.example",
        },
    }
    assert front.contact_links(profile) == [
        ("me@example.org", "mailto:me@example.org"),
        ("LinkedIn", "https://l.example"),
        ("Malt", "https://m.example"),
        ("GitHub", "https://g.example"),
        ("PyPI", "https://p.example"),
    ]


def test_a_contact_without_a_link_is_dropped():
    profile = {"contacts": {"email_pro": "me@example.org"}, "links": {}}
    assert front.contact_links(profile) == [("me@example.org", "mailto:me@example.org")]


# --- Achievements (ADR-014) ---------------------------------------------------


def _achievement(**over) -> dict:
    return {
        "id": "award",
        "claim": "award-2017",
        "context": "product",
        "date": "2017-06",
        "fr": "Le produit a gagné un prix.",
        "en": "The product won an award.",
        **over,
    }


def test_no_achievement_is_shown_while_the_lock_is_empty():
    assert front.achievements([_achievement()], lock={"claims": {}}, lang="fr") == []


def test_only_attested_achievements_are_shown_with_their_marker():
    items = [
        _achievement(),
        _achievement(id="other", claim="not-attested", date="2020"),
    ]
    lock = {"claims": {"award-2017": {"wording_sha256": {}}}}
    shown = front.achievements(items, lock=lock, lang="en")
    assert [a["id"] for a in shown] == ["award"]
    assert shown[0]["wording"] == (
        "<!-- claim:award-2017 -->The product won an award.<!-- /claim -->"
    )
    assert shown[0]["context"] == "product"
    assert shown[0]["year"] == "2017"


def test_achievements_are_newest_first():
    items = [
        _achievement(id="a", claim="c-a", date="2015"),
        _achievement(id="b", claim="c-b", date="2021-03"),
        _achievement(id="c", claim="c-c", date="2021-11"),
    ]
    lock = {"claims": {"c-a": {}, "c-b": {}, "c-c": {}}}
    shown = front.achievements(items, lock=lock, lang="fr")
    assert [a["id"] for a in shown] == ["c", "b", "a"]


# --- Open source and live badges (ADR-016 amendment) ---------------------------


def _project(**over) -> dict:
    return {
        "id": "pkg",
        "name": "Pkg",
        "github_url": "https://github.com/Owner/Pkg",
        "tech_ids": ["python", "git"],
        "start": "2024-01",
        "highlight": True,
        "description": "A client. Adopted by everyone.",
        "metrics": {"pypi": "pkg-name"},
        **over,
    }


def test_open_source_keeps_projects_with_a_live_source_and_a_description():
    projects = [
        _project(),
        _project(id="no-metrics", metrics=None),
        _project(id="no-desc", description=None),
        _project(id="docker", metrics={"dockerhub": "me/img"}, highlight=False),
    ]
    assert [p["id"] for p in front.open_source(projects)] == ["pkg", "docker"]


def test_open_source_description_is_the_first_sentence_only():
    # One line per tile; later sentences are not attested and stay off the tile.
    (project,) = front.open_source([_project()])
    assert project["summary"] == "A client."


def test_first_sentence_keeps_a_period_inside_a_name():
    assert front.first_sentence(".NET client library. More.") == ".NET client library."
    assert front.first_sentence("No period at all") == "No period at all"


def test_live_badges_for_a_pypi_project():
    alts = {"pypi": "Downloads", "dockerhub": "Pulls", "stars": "Stars"}
    badges = front.live_badges(_project(), alts)
    assert badges == [
        {
            "alt": "Downloads",
            "src": "https://img.shields.io/pypi/dm/pkg-name?style=flat-square&color=3f6212",
            "href": "https://pypi.org/project/pkg-name/",
        },
        {
            "alt": "Stars",
            "src": "https://img.shields.io/github/stars/Owner/Pkg?style=flat-square&color=3f6212",
            "href": "https://github.com/Owner/Pkg",
        },
    ]


def test_live_badges_for_a_docker_project():
    alts = {"pypi": "Downloads", "dockerhub": "Pulls", "stars": "Stars"}
    badges = front.live_badges(_project(metrics={"dockerhub": "me/img"}), alts)
    assert badges[0] == {
        "alt": "Pulls",
        "src": "https://img.shields.io/docker/pulls/me/img?style=flat-square&color=3f6212",
        "href": "https://hub.docker.com/r/me/img",
    }


def test_pairs_group_tiles_two_by_two():
    assert front.pairs([1, 2, 3]) == [[1, 2], [3]]


# --- Skills (ADR-016 section 4, ADR-018) ----------------------------------------


def _skill(tech_id, domain, hours, last="2026-09", **over) -> dict:
    return {
        "id": tech_id,
        "label": tech_id.title(),
        "domain": domain,
        "hours": hours,
        "display_hours": hours,
        "level": "working",
        "level_source": "hours",
        "first": "2010-01",
        "last": last,
        "since": 2010,
        "until": None if last.startswith("2026") else int(last[:4]),
        **over,
    }


DOMAINS = [
    {"id": "mobile", "order": 2, "label": "Mobile"},
    {"id": "embedded", "order": 1, "label": "Embedded"},
    {"id": "empty", "order": 3, "label": "Empty"},
]


def test_skill_tiles_follow_domain_order_and_skip_empty_domains():
    skills = [_skill("a", "mobile", 100), _skill("b", "embedded", 60)]
    tiles = front.skill_tiles(skills, DOMAINS, bars=5)
    assert [t["domain"] for t in tiles] == ["embedded", "mobile"]


def test_first_five_are_bars_the_rest_one_line_in_skill_order():
    skills = [_skill(f"t{i}", "mobile", 100 + i) for i in range(7)]
    (tile,) = front.skill_tiles(skills, DOMAINS, bars=5)
    assert [s["id"] for s in tile["bars"]] == ["t0", "t1", "t2", "t3", "t4"]
    assert [s["id"] for s in tile["also"]] == ["t5", "t6"]


def test_period_is_first_to_last_or_active():
    assert front.period(_skill("a", "m", 1), active="actif") == "2010–actif"
    old = _skill("a", "m", 1, last="2013-03")
    assert front.period(old, active="actif") == "2010–2013"
    same = _skill("a", "m", 1, last="2010-05", first="2010-01")
    assert front.period(same, active="actif") == "2010"


def test_evidence_marker_only_for_an_attested_evidence_level():
    assert front.evidence_marked([_skill("a", "m", 1)]) == []
    lifted = _skill("b", "m", 1, level="expert", level_source="evidence")
    assert front.evidence_marked([lifted]) == ["b"]


def test_bar_fraction_is_logarithmic_and_bounded():
    assert front.bar_fraction(10, 10000) == 0.0
    assert front.bar_fraction(10000, 10000) == 1.0
    assert front.bar_fraction(100, 10000) == pytest.approx(1 / 3)
    assert front.bar_fraction(5, 10000) == 0.0


# --- Chronology ---------------------------------------------------------------


def test_chronology_is_newest_first_with_stable_anchors():
    experiences = [
        {"id": "old", "org": "A", "type": "cdi", "start": "2009-10", "end": "2010-12"},
        {"id": "now", "org": "B", "type": "freelance", "start": "2023-04", "end": None},
        {
            "id": "short",
            "org": "C",
            "type": "mission",
            "start": "2013-04",
            "end": "2013-04",
        },
    ]
    entries = front.chronology(experiences, now="today")
    assert [e["anchor"] for e in entries] == ["exp-now", "exp-short", "exp-old"]
    assert [e["when"] for e in entries] == ["2023 → today", "2013", "2009 – 2010"]
    assert [e["type"] for e in entries] == ["freelance", "mission", "cdi"]


def test_chronology_merges_consecutive_positions_at_one_organization():
    # Where and when only (ADR-016): two phases at one employer are one line,
    # linked to the newest phase's anchor.
    experiences = [
        {"id": "p1", "org": "A", "type": "cdi", "start": "2014-04", "end": "2020-01"},
        {"id": "p2", "org": "A", "type": "cdi", "start": "2020-01", "end": "2023-04"},
        {"id": "x", "org": "B", "type": "freelance", "start": "2023-04", "end": None},
    ]
    entries = front.chronology(experiences, now="today")
    assert [(e["org"], e["when"], e["anchor"]) for e in entries] == [
        ("B", "2023 → today", "exp-x"),
        ("A", "2014 – 2023", "exp-p2"),
    ]


# --- Activity calendar --------------------------------------------------------


def test_calendar_years_split_in_two_halves_oldest_first():
    assert front.calendar_halves(2014, 2026) == (
        list(range(2014, 2021)),
        list(range(2021, 2027)),
    )


def test_calendar_counts_per_context():
    counts = front.calendar_counts(_aggregates()["calendar"])
    assert counts == {"pro": 1, "personal": 2, "study": 0}


def test_longest_streak_of_consecutive_commit_days():
    days = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
    assert front.longest_streak(days) == 3
    assert front.longest_streak([]) == 0


def test_busiest_year_breaks_ties_on_the_latest_year():
    days = ["2020-01-01", "2020-01-02", "2021-01-01", "2021-03-01"]
    assert front.busiest_year(days) == (2021, 2)


# --- Anchors ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("Méthode", "méthode"),
        ("Comment je peux aider", "comment-je-peux-aider"),
        ("What GitHub sees", "what-github-sees"),
        ("IA & LLM", "ia--llm"),
    ],
)
def test_github_anchor(heading, anchor):
    assert front.github_anchor(heading) == anchor


# --- Third-party widgets labelled as what GitHub sees ----------------------------


def test_streak_url_uses_the_tile_palette_and_the_page_language():
    pal = {
        "panel": "#0c0f0a",
        "border": "#262e21",
        "text": "#eef2e8",
        "muted": "#a3ab9a",
        "dim": "#7b8472",
        "accent": "#a3e635",
    }
    url = front.streak_url("Someone", pal, "fr")
    assert url.startswith("https://streak-stats.demolab.com/?user=Someone&locale=fr&")
    assert "ring=a3e635" in url and "fire=a3e635" in url
    assert "background=0c0f0a" in url
    assert "#" not in url


def test_band_width_keeps_the_skillicons_scale():
    # A full line of 16 icons spans the 834 px column; shorter lines keep the
    # same scale, so an in-house icon is the size of a skillicons one.
    assert front.band_width(16) == 834
    assert front.band_width(1) == round(256 * 834 / (16 * 300 - 44))
