"""Tech score and level derivation (ADR-002).

Public surface:
- ``Level`` enum (5 paliers).
- ``Skill`` dataclass (tech_id, score, level, override_applied).
- ``compute_skill(tech, projects, today)`` pure function.

Formula coefficients live as module-level constants so the ADR is readable
in code. Any coefficient change must update ADR-002.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Level(str, Enum):
    EXPERT = "expert"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"
    WORKING = "working"
    EXPLORED = "explored"


@dataclass(frozen=True)
class Skill:
    tech_id: str
    score: int
    level: Level
    override_applied: bool


# Formula coefficients — ADR-002.
POINTS_PER_ACTIVE_YEAR = 3
MAX_BASE_POINTS = 60

POINTS_PER_VERSION = 3
MAX_VERSIONS_POINTS = 15

POINTS_PER_PROJECT = 3
MAX_PROJECTS_POINTS = 15

POINTS_PER_EXTRA_DOMAIN = 5
MAX_CENTRALITY_POINTS = 10

POINTS_PER_DEPTH_LEVEL = 20  # depth 0..3 -> 0/20/40/60

OUBLI_PENALTY_PER_YEAR = 6
FEATURED_BONUS = 15

MIN_SCORE = 0
MAX_SCORE = 99

# Level thresholds — ADR-002.
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


def _extract_overrides(tech: dict) -> tuple[int | None, Level | None]:
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


def _compute_raw_score(tech: dict, projects: list[dict], today: date) -> int:
    tech_id = tech["id"]
    since = tech.get("since")
    if since is None:
        # No measurable adoption year (read-level / never really used).
        years_active = 0
        recency_oubli = 0
    else:
        until = tech.get("until")
        last_active_year = until if until is not None else today.year
        years_active = last_active_year - since
        recency_oubli = max(0, today.year - last_active_year)

    base = min(MAX_BASE_POINTS, years_active * POINTS_PER_ACTIVE_YEAR)
    versions_pts = min(
        MAX_VERSIONS_POINTS, len(tech.get("versions", [])) * POINTS_PER_VERSION
    )

    projects_using = [p for p in projects if tech_id in p.get("tech_ids", [])]
    projets_pts = min(MAX_PROJECTS_POINTS, len(projects_using) * POINTS_PER_PROJECT)
    nb_domains = len({p["domain"] for p in projects_using})
    centralite_pts = min(
        MAX_CENTRALITY_POINTS, max(0, nb_domains - 1) * POINTS_PER_EXTRA_DOMAIN
    )

    depth_pts = tech.get("depth", 0) * POINTS_PER_DEPTH_LEVEL
    bonus_featured = FEATURED_BONUS if tech.get("featured") else 0

    raw = base + versions_pts + projets_pts + centralite_pts + depth_pts
    oubli = recency_oubli * OUBLI_PENALTY_PER_YEAR
    return max(MIN_SCORE, min(MAX_SCORE, raw - oubli + bonus_featured))


def compute_skill(tech: dict, projects: list[dict], today: date) -> Skill:
    score_override, level_override = _extract_overrides(tech)
    computed_score = _compute_raw_score(tech, projects, today)

    final_score = score_override if score_override is not None else computed_score
    final_level = (
        level_override if level_override is not None else _level_from_score(final_score)
    )
    override_applied = score_override is not None or level_override is not None

    return Skill(
        tech_id=tech["id"],
        score=final_score,
        level=final_level,
        override_applied=override_applied,
    )
