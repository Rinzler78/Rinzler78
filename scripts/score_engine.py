"""Expertise scoring: peak (max) and current, from exposure hours (ADR-006).

Public surface:
- ``Level`` enum (5 paliers).
- ``Skill`` dataclass (tech_id, score_max, level_max, score_current,
  level_current, override_applied).
- ``compute_skill(tech, tech_hours, today)`` pure function.

The additive formula of ADR-002 was superseded by ADR-006: expertise now
derives from exposure hours with a peak (diminishing returns) and a current
value (Ebbinghaus-style forgetting toward a residual floor).
"""

import math
from dataclasses import dataclass
from datetime import date
from enum import Enum

from scripts.hours_calculator import TechHours

# ADR-006 constants
H0 = 3000  # hours scale for diminishing returns
ALPHA = 0.30  # residual floor fraction of peak
HALFLIFE_MIN = 2  # years (low peak forgets fast)
HALFLIFE_MAX = 18  # years (deep mastery forgets slowly)
MIN_SCORE = 0
MAX_SCORE = 99


class Level(str, Enum):
    EXPERT = "expert"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"
    WORKING = "working"
    EXPLORED = "explored"


@dataclass(frozen=True)
class Skill:
    tech_id: str
    score_max: int
    level_max: Level
    score_current: int
    level_current: Level
    override_applied: bool


_LEVEL_THRESHOLDS: tuple[tuple[int, Level], ...] = (
    (85, Level.EXPERT),
    (70, Level.ADVANCED),
    (55, Level.PROFESSIONAL),
    (35, Level.WORKING),
)


def _level_from_score(score: int) -> Level:
    for threshold, level in _LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return Level.EXPLORED


def _peak(hours: float) -> float:
    return MAX_SCORE * (1 - math.exp(-hours / H0))


def _decay(peak: float, years_inactive: int) -> float:
    if years_inactive <= 0 or peak <= 0:
        return peak
    floor = ALPHA * peak
    halflife = HALFLIFE_MIN + (HALFLIFE_MAX - HALFLIFE_MIN) * (peak / 100)
    lam = math.log(2) / halflife
    return floor + (peak - floor) * math.exp(-lam * years_inactive)


def _extract_overrides(tech: dict) -> tuple[int | None, "Level | None"]:
    score_override = tech.get("score_override")
    level_override_raw = tech.get("level_override")
    level_override = (
        Level(level_override_raw) if level_override_raw is not None else None
    )
    if score_override is not None and level_override is not None:
        derived = _level_from_score(score_override)
        if derived != level_override:
            raise ValueError(
                f"Incoherent overrides for {tech['id']!r}: "
                f"score_override={score_override} maps to {derived.value!r} "
                f"but level_override={level_override.value!r}"
            )
    return score_override, level_override


def compute_skill(tech: dict, tech_hours: TechHours, today: date) -> Skill:
    score_override, level_override = _extract_overrides(tech)

    peak = _peak(tech_hours.hours)
    years_inactive = 0 if tech_hours.until is None else today.year - tech_hours.until
    current = _decay(peak, years_inactive)

    score_max = max(MIN_SCORE, min(MAX_SCORE, round(peak)))
    computed_current = max(MIN_SCORE, min(MAX_SCORE, round(current)))

    score_current = score_override if score_override is not None else computed_current
    level_current = (
        level_override
        if level_override is not None
        else _level_from_score(score_current)
    )
    override_applied = score_override is not None or level_override is not None

    return Skill(
        tech_id=tech["id"],
        score_max=score_max,
        level_max=_level_from_score(score_max),
        score_current=score_current,
        level_current=level_current,
        override_applied=override_applied,
    )
