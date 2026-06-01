"""Derived view models from the data bag (ADR-003, ADR-006).

Public surface (V1, incremental):
- ``build_skills(techs, experiences, projects, today)`` enriches each tech
  with its derived exposure hours and expertise (max + current), producing
  template-ready dicts.

Skills are *derived*, never stored: the enrichment composes HoursCalculator
(hours + since/until per tech) and ScoreEngine (peak/decay) over the raw
tech collection.

- ``build_profile_as_code(profile, skills, services)`` renders the profile as
  a small C# class (the "Profile as Code" section).
"""

import re
from datetime import date

from scripts.hours_calculator import TechHours, compute_tech_hours
from scripts.score_engine import compute_skill


def build_profile_as_code(
    profile: dict, skills: list[dict], services: list[dict]
) -> str:
    class_name = re.sub(r"[^A-Za-z0-9]", "", profile["name"])
    featured = sorted(
        (s for s in skills if s.get("featured")),
        key=lambda s: s.get("score_current", 0),
        reverse=True,
    )
    core = ", ".join(f'"{s["label"]}"' for s in featured)

    shown = sorted(
        (s for s in services if s.get("visible")),
        key=lambda s: s.get("priority", 0),
    )
    svc = ", ".join(f'"{s["title"]}"' for s in shown)

    status = profile.get("status", "")
    return (
        f"public sealed class {class_name} : FreelanceCto\n"
        f"{{\n"
        f"    public string[] CoreSkills => [{core}];\n"
        f"    public string[] Services   => [{svc}];\n"
        f'    public string   Status     => "{status}";\n'
        f"}}"
    )


def build_signature_arc(domains: list[dict]) -> list[dict]:
    """The curated `embedded → mobile → cloud → ai` narrative arc.

    Selects the domains carrying ``arc_order`` (a curated subset — the years
    and signature words are editorial, user-validated), ordered by it, and
    projects each to ``{label, year, signature, domain_id}``. Single source
    of truth for the hero hook and for ``content.boot_log`` consistency.
    """
    nodes = sorted(
        (d for d in domains if d.get("arc_order") is not None),
        key=lambda d: d["arc_order"],
    )
    return [
        {
            "label": d["arc_label"],
            "year": d["arc_year"],
            "signature": d["arc_signature"],
            "domain_id": d["id"],
        }
        for d in nodes
    ]


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
