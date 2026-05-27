from datetime import date

import pytest

from scripts.score_engine import Level, compute_skill


def test_compute_skill_empty_tech_yields_zero_explored():
    tech = {"id": "foo", "since": 2026, "versions": []}
    projects = []
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.tech_id == "foo"
    assert result.score == 0
    assert result.level == Level.EXPLORED
    assert result.override_applied is False


def test_compute_skill_years_only_scores_proportional():
    # 17 active years × 3 pts = 51, no other contributions
    # 51 falls in 35–54 → working
    tech = {"id": "csharp", "since": 2009, "versions": []}
    projects = []
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == 51
    assert result.level == Level.WORKING


@pytest.mark.parametrize(
    "nb_versions, expected",
    [
        (0, 0),
        (3, 9),
        (5, 15),
        (10, 15),  # capped at 15
    ],
)
def test_compute_skill_versions_contribute_three_each_capped_at_fifteen(
    nb_versions, expected
):
    tech = {
        "id": "py",
        "since": 2026,
        "versions": [{"id": f"v{i}"} for i in range(nb_versions)],
    }
    projects = []
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == expected


@pytest.mark.parametrize(
    "nb_projects_using, expected",
    [
        (0, 0),
        (3, 9),
        (5, 15),
        (8, 15),  # capped at 15
    ],
)
def test_compute_skill_projects_using_tech_contribute_three_each_capped(
    nb_projects_using, expected
):
    tech = {"id": "py", "since": 2026, "versions": []}
    projects = [
        {"id": f"p{i}", "domain": "backend", "tech_ids": ["py"]}
        for i in range(nb_projects_using)
    ]
    # add a noise project that doesn't reference py
    projects.append({"id": "noise", "domain": "embedded", "tech_ids": ["c"]})
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == expected


@pytest.mark.parametrize(
    "domains, expected",
    [
        # 1 project, 1 domain: projets_pts=3, centralité=0 → 3
        (["backend"], 3),
        # 2 projects, 2 distinct domains: 6 + 5 = 11
        (["backend", "mobile"], 11),
        # 3 projects, 3 distinct domains: 9 + min(10, 2*5)=10 → 19
        (["backend", "mobile", "embedded"], 19),
        # 4 projects, 4 distinct domains: 12 + cap 10 → 22
        (["backend", "mobile", "embedded", "devops"], 22),
        # 4 projects, 1 domain (no centrality): 12 + 0 → 12
        (["backend", "backend", "backend", "backend"], 12),
    ],
)
def test_compute_skill_centrality_adds_five_per_extra_domain_capped_at_ten(
    domains, expected
):
    tech = {"id": "py", "since": 2026, "versions": []}
    projects = [
        {"id": f"p{i}", "domain": d, "tech_ids": ["py"]}
        for i, d in enumerate(domains)
    ]
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == expected


@pytest.mark.parametrize(
    "since, until, expected_score, expected_level",
    [
        # Abandoned long ago: 4 active years (12 pts) − 13×6 oubli (78) → −66 → floor 0
        (2009, 2013, 0, Level.EXPLORED),
        # Recently stopped: 16 active years (48 pts) − 1×6 oubli (6) → 42 → working
        (2009, 2025, 42, Level.WORKING),
        # Stopped exactly this year: 17 active years (51) − 0 oubli → 51 → working
        (2009, 2026, 51, Level.WORKING),
    ],
)
def test_compute_skill_until_triggers_recency_penalty_floored_at_zero(
    since, until, expected_score, expected_level
):
    tech = {"id": "wince", "since": since, "until": until, "versions": []}
    projects = []
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == expected_score
    assert result.level == expected_level


@pytest.mark.parametrize(
    "featured, expected_score, expected_level",
    [
        (False, 51, Level.WORKING),
        (True, 66, Level.PROFESSIONAL),
    ],
)
def test_compute_skill_featured_adds_fifteen_bonus(
    featured, expected_score, expected_level
):
    tech = {"id": "csharp", "since": 2009, "versions": [], "featured": featured}
    projects = []
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == expected_score
    assert result.level == expected_level


def test_compute_skill_score_override_replaces_computed_score():
    tech = {"id": "py", "since": 2026, "versions": [], "score_override": 95}

    result = compute_skill(tech, [], date(2026, 1, 1))

    assert result.score == 95
    assert result.level == Level.EXPERT
    assert result.override_applied is True


def test_compute_skill_level_override_replaces_derived_level():
    # Empty tech would score 0 → explored. Override to advanced.
    tech = {"id": "py", "since": 2026, "versions": [], "level_override": "advanced"}

    result = compute_skill(tech, [], date(2026, 1, 1))

    assert result.level == Level.ADVANCED
    assert result.override_applied is True


def test_compute_skill_both_overrides_coherent_applied_together():
    tech = {
        "id": "py",
        "since": 2026,
        "versions": [],
        "score_override": 80,
        "level_override": "advanced",
    }

    result = compute_skill(tech, [], date(2026, 1, 1))

    assert result.score == 80
    assert result.level == Level.ADVANCED
    assert result.override_applied is True


def test_compute_skill_incoherent_overrides_raises_value_error():
    # score_override=95 maps to expert but level_override claims working
    tech = {
        "id": "py",
        "since": 2026,
        "versions": [],
        "score_override": 95,
        "level_override": "working",
    }

    with pytest.raises(ValueError, match="incoherent|coherent"):
        compute_skill(tech, [], date(2026, 1, 1))


def test_compute_skill_score_clamped_at_ninety_nine_when_all_max():
    # 26y → base capped 60, 10 versions → 15, 5 projets/5 domains → 15 + 10, featured 15
    # Total raw = 60 + 15 + 15 + 10 + 15 = 115 → clamp 99
    tech = {
        "id": "csharp",
        "since": 2000,
        "versions": [{"id": f"v{i}"} for i in range(10)],
        "featured": True,
    }
    projects = [
        {"id": "p1", "domain": "backend", "tech_ids": ["csharp"]},
        {"id": "p2", "domain": "mobile", "tech_ids": ["csharp"]},
        {"id": "p3", "domain": "embedded", "tech_ids": ["csharp"]},
        {"id": "p4", "domain": "devops", "tech_ids": ["csharp"]},
        {"id": "p5", "domain": "ai-llm", "tech_ids": ["csharp"]},
    ]
    today = date(2026, 1, 1)

    result = compute_skill(tech, projects, today)

    assert result.score == 99
    assert result.level == Level.EXPERT
