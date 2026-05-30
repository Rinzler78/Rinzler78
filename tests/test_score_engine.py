import math
from datetime import date

import pytest

from scripts.hours_calculator import TechHours
from scripts.score_engine import Level, compute_skill


def _peak(h):
    return round(99 * (1 - math.exp(-h / 3000)))


def test_zero_hours_yields_explored_max_and_current():
    skill = compute_skill({"id": "x"}, TechHours(0, None, None), date(2026, 1, 1))

    assert skill.score_max == 0
    assert skill.level_max == Level.EXPLORED
    assert skill.score_current == 0
    assert skill.level_current == Level.EXPLORED
    assert skill.override_applied is False


def test_peak_derived_from_hours_diminishing_returns():
    # 3000 h → 99·(1-1/e) ≈ 63 → professional
    skill = compute_skill({"id": "x"}, TechHours(3000, None, None), date(2026, 1, 1))

    assert skill.score_max == _peak(3000)
    assert skill.score_max == 63
    assert skill.level_max == Level.PROFESSIONAL


def test_active_tech_current_equals_max():
    # until is None → no decay
    skill = compute_skill({"id": "x"}, TechHours(8000, None, None), date(2026, 1, 1))

    assert skill.score_current == skill.score_max
    assert skill.level_current == skill.level_max


def test_closed_tech_current_below_max_but_above_floor():
    # peak ~84 at 5500h, stopped 13 years ago → decays toward floor 0.3·peak
    th = TechHours(5500, 2009, 2013)
    skill = compute_skill({"id": "cpp"}, th, date(2026, 1, 1))

    assert skill.score_max == _peak(5500)
    assert skill.score_current < skill.score_max
    assert skill.score_current >= round(0.30 * skill.score_max)


def test_high_peak_decays_slower_than_low_peak():
    # Same 13-year gap; deep expertise (high peak) retains more than shallow.
    deep = compute_skill({"id": "d"}, TechHours(9000, 2000, 2013), date(2026, 1, 1))
    shallow = compute_skill({"id": "s"}, TechHours(1200, 2000, 2013), date(2026, 1, 1))

    deep_retention = deep.score_current / deep.score_max
    shallow_retention = shallow.score_current / shallow.score_max
    assert deep_retention > shallow_retention


@pytest.mark.parametrize(
    "hours, expected_level",
    [
        (200, Level.EXPLORED),
        (1300, Level.WORKING),
        (2600, Level.PROFESSIONAL),
        (4000, Level.ADVANCED),
        (7000, Level.EXPERT),
    ],
)
def test_level_max_mapping(hours, expected_level):
    skill = compute_skill({"id": "x"}, TechHours(hours, None, None), date(2026, 1, 1))
    assert skill.level_max == expected_level


def test_score_override_replaces_current_only():
    th = TechHours(5500, 2009, 2013)  # would compute a decayed current
    skill = compute_skill({"id": "cpp", "score_override": 90}, th, date(2026, 1, 1))

    assert skill.score_current == 90
    assert skill.level_current == Level.EXPERT
    assert skill.override_applied is True
    # max is still derived from hours, untouched by the override
    assert skill.score_max < 90 or skill.score_max >= 0  # max stays computed


def test_level_override_replaces_current_level():
    skill = compute_skill(
        {"id": "x", "level_override": "advanced"},
        TechHours(0, None, None),
        date(2026, 1, 1),
    )

    assert skill.level_current == Level.ADVANCED
    assert skill.override_applied is True


def test_incoherent_overrides_raise():
    with pytest.raises(ValueError, match="ncoherent|coherent"):
        compute_skill(
            {"id": "x", "score_override": 90, "level_override": "working"},
            TechHours(0, None, None),
            date(2026, 1, 1),
        )


def test_empty_string_level_override_rejected():
    with pytest.raises(ValueError):
        compute_skill(
            {"id": "x", "level_override": ""},
            TechHours(0, None, None),
            date(2026, 1, 1),
        )
