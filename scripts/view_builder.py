"""Derived view models from the data bag (ADR-003, ADR-006).

Public surface (V1, incremental):
- ``build_skills(techs, experiences, projects, today)`` enriches each tech
  with its derived exposure hours and expertise (max + current), producing
  template-ready dicts.

Skills are *derived*, never stored: the enrichment composes HoursCalculator
(hours + since/until per tech) and ScoreEngine (peak/decay) over the raw
tech collection.
"""

from datetime import date

from scripts.hours_calculator import TechHours, compute_tech_hours
from scripts.score_engine import compute_skill


def build_skills(
    techs: list[dict],
    experiences: list[dict],
    projects: list[dict],
    today: date,
) -> list[dict]:
    tech_hours = compute_tech_hours(experiences, projects, today)

    skills: list[dict] = []
    for tech in techs:
        th = tech_hours.get(tech["id"], TechHours(0, None, None))
        skill = compute_skill(tech, th, today)
        skills.append(
            {
                **tech,
                "hours": th.hours,
                "since": th.since,
                "until": th.until,
                "score_max": skill.score_max,
                "level_max": skill.level_max.value,
                "score_current": skill.score_current,
                "level_current": skill.level_current.value,
                "override_applied": skill.override_applied,
            }
        )
    return skills
