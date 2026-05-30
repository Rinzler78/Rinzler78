"""Exposure-hours aggregation per tech (ADR-006).

Public surface:
- ``TechHours`` dataclass (hours, since, until).
- ``compute_tech_hours(experiences, projects, today)`` aggregates exposure
  hours per tech from dated experiences and personal projects, via concurrent
  (non-normalized) tier fractions, and derives since/until per tech.
"""

from dataclasses import dataclass
from datetime import date

HOURS_PER_YEAR = 1880
HOURS_PER_PERSO_DAY = 9

TIER_FRACTION = {"primary": 0.70, "secondary": 0.35, "incident": 0.10}


@dataclass(frozen=True)
class TechHours:
    hours: int
    since: int | None
    until: int | None


def _span_years(start: str, end: str | None, today: date) -> float:
    sy, sm = (int(x) for x in start.split("-"))
    if end is None:
        ey, em = today.year, today.month
    else:
        ey, em = (int(x) for x in end.split("-"))
    return max(0.0, (ey - sy) + (em - sm) / 12)


def _year(ym: str) -> int:
    return int(ym.split("-")[0])


def compute_tech_hours(
    experiences: list[dict],
    projects: list[dict],
    today: date,
) -> dict[str, TechHours]:
    hours: dict[str, float] = {}
    since: dict[str, int] = {}
    until: dict[str, int | None] = {}

    def _absorb(tech_id: str, h: float, start_year: int, end_year: int | None) -> None:
        hours[tech_id] = hours.get(tech_id, 0.0) + h
        if tech_id not in since or start_year < since[tech_id]:
            since[tech_id] = start_year
        # until = None (active) wins; otherwise keep the latest end year
        if tech_id not in until:
            until[tech_id] = end_year
        elif end_year is None:
            until[tech_id] = None
        else:
            current = until[tech_id]
            if current is not None and end_year > current:
                until[tech_id] = end_year

    for exp in experiences:
        end = exp.get("end")
        exp_hours = _span_years(exp["start"], end, today) * HOURS_PER_YEAR
        sy = _year(exp["start"])
        ey = _year(end) if end is not None else None
        for tech_id, tier in exp["tech_weights"].items():
            _absorb(tech_id, exp_hours * TIER_FRACTION[tier], sy, ey)

    for proj in projects:
        proj_hours = proj.get("active_days", 0) * HOURS_PER_PERSO_DAY
        sy = _year(proj["start"]) if "start" in proj else today.year
        end = proj.get("end")
        ey = _year(end) if end is not None else None
        for tech_id, tier in proj.get("tech_weights", {}).items():
            _absorb(tech_id, proj_hours * TIER_FRACTION[tier], sy, ey)

    return {
        tech_id: TechHours(round(h), since[tech_id], until[tech_id])
        for tech_id, h in hours.items()
    }
