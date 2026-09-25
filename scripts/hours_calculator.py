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
HOURS_PER_PERSONAL_DAY = 9

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


def _months(start: str, end: str | None, today: date) -> tuple[int, int]:
    """Absolute month index of the half-open span [start, end)."""
    sy, sm = (int(x) for x in start.split("-"))
    if end is None:
        ey, em = today.year, today.month
    else:
        ey, em = (int(x) for x in end.split("-"))
    return sy * 12 + sm, ey * 12 + em


def compute_tech_hours_by_year(
    experiences: list[dict],
    projects: list[dict],
    today: date,
) -> dict[str, dict[int, int]]:
    """Split each tech's exposure hours across the calendar years it spans.

    A partition of what :func:`compute_tech_hours` totals — the same sources,
    the same tier fractions, sliced by year. A per-domain timeline needs the
    slices; the scores need only the totals.

    Experiences carry months, so their span is pro-rated exactly. Projects
    carry `active_days` and a year range with no months, so their hours are
    **spread uniformly** over that range: an explicit approximation, not a
    measurement. It is the honest default — `active_days` records how many
    distinct days saw commits, never which ones.
    """
    per_year: dict[str, dict[int, float]] = {}

    def _add(tech_id: str, year: int, h: float) -> None:
        if h <= 0:
            return
        per_year.setdefault(tech_id, {})[year] = (
            per_year.setdefault(tech_id, {}).get(year, 0.0) + h
        )

    for exp in experiences:
        a, b = _months(exp["start"], exp.get("end"), today)
        if b <= a:
            continue
        for year in range(a // 12, b // 12 + 1):
            # Month indices run 1..12, so a year ends at the next January.
            lo, hi = max(a, year * 12 + 1), min(b, (year + 1) * 12 + 1)
            if hi <= lo:
                continue
            year_hours = (hi - lo) / 12 * HOURS_PER_YEAR
            for tech_id, tier in exp["tech_weights"].items():
                _add(tech_id, year, year_hours * TIER_FRACTION[tier])

    for proj in projects:
        sy = _year(proj["start"]) if "start" in proj else today.year
        end = proj.get("end")
        ey = _year(end) if end is not None else today.year
        span = max(1, ey - sy + 1)
        share = proj.get("active_days", 0) * HOURS_PER_PERSONAL_DAY / span
        for year in range(sy, ey + 1):
            for tech_id, tier in proj.get("tech_weights", {}).items():
                _add(tech_id, year, share * TIER_FRACTION[tier])

    return {
        tech_id: {y: round(h) for y, h in sorted(years.items()) if round(h) > 0}
        for tech_id, years in per_year.items()
    }


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
        proj_hours = proj.get("active_days", 0) * HOURS_PER_PERSONAL_DAY
        sy = _year(proj["start"]) if "start" in proj else today.year
        end = proj.get("end")
        ey = _year(end) if end is not None else None
        for tech_id, tier in proj.get("tech_weights", {}).items():
            _absorb(tech_id, proj_hours * TIER_FRACTION[tier], sy, ey)

    return {
        tech_id: TechHours(round(h), since[tech_id], until[tech_id])
        for tech_id, h in hours.items()
    }
