"""View models from the data bag and the committed aggregates (ADR-003).

Public surface:
- ``build_skills(techs, aggregates)`` enriches each catalogue tech with its
  figures from ``data/activity/aggregates.json`` — hours, displayed hours and
  level, level source and claim, first and last month, since/until years —
  and orders them by recency, then hours (ADR-018).
- ``build_domain_year_hours(aggregates)`` sums the per-month domain hours of
  the aggregates per calendar year: the journey series.
- ``build_profile_as_code(profile, skills, services)`` renders the profile as
  a small C# class (the "Profile as Code" section).
- ``build_signature_arc(domains)`` projects the curated narrative arc.

Nothing about a skill is derived here: hours, levels and periods are computed
on the author's workstation from the activity timeline and commit evidence
(ADR-013, ADR-018), and the generator only reads them.
"""

import re

# Cross-cutting domains, excluded from the per-domain timeline. Languages and
# engineering practices are used inside every other domain, so their rows are
# lit every year and only flatten the scale of the rows that carry information.
TIMELINE_EXCLUDED_DOMAINS = frozenset({"languages", "practices"})


def build_profile_as_code(
    profile: dict, skills: list[dict], services: list[dict]
) -> str:
    class_name = re.sub(r"[^A-Za-z0-9]", "", profile["name"])
    featured = [s for s in skills if s.get("featured")]
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


def build_domain_year_hours(aggregates: dict) -> dict[str, dict[int, float]]:
    """Hours per domain, per calendar year — the journey series.

    Sums the per-month domain hours of the aggregates, skipping
    :data:`TIMELINE_EXCLUDED_DOMAINS` and years without hours. Hours per
    domain are not additive across domains (one file may touch several), so
    these values are drawn as *shares*, never as a total of hours worked.
    """
    series: dict[str, dict[int, float]] = {}
    for month, row in sorted(aggregates["by_month"].items()):
        year = int(month[:4])
        for domain, hours in row["domains"].items():
            if domain in TIMELINE_EXCLUDED_DOMAINS or hours <= 0:
                continue
            years = series.setdefault(domain, {})
            years[year] = years.get(year, 0.0) + hours
    return {
        domain: {year: round(hours, 1) for year, hours in sorted(years.items())}
        for domain, years in series.items()
    }


def _month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7])


def build_skills(techs: list[dict], aggregates: dict) -> list[dict]:
    """Catalogue techs enriched with their aggregate figures, newest first.

    Every catalogue tech is returned, so a project or a timeline event can
    still resolve its label; ``level`` is ``None`` for a tech that is not a
    skill line — below the working threshold, or a tool every commit implies
    such as Git, which the aggregates never measure (ADR-016).

    ``until`` is ``None`` while the tech was used in the year of
    ``activity_as_of``, else the year of its last use. Order: most recent last
    use first, then hours (ADR-018: never by hours alone).
    """
    as_of_year = int(aggregates["activity_as_of"][:4])
    skills: list[dict] = []
    for tech in techs:
        entry = aggregates["techs"].get(tech["id"])
        if entry is None:
            skills.append(
                {
                    **tech,
                    "hours": 0,
                    "display_hours": 0,
                    "level": None,
                    "level_source": None,
                    "claim": None,
                    "first": None,
                    "last": None,
                    "since": None,
                    "until": None,
                }
            )
            continue
        last_year = int(entry["last"][:4])
        skills.append(
            {
                **tech,
                "hours": entry["hours"],
                "display_hours": entry["display_hours"],
                "level": entry["display_level"],
                "level_source": entry["level_source"],
                "claim": entry["claim"],
                "first": entry["first"],
                "last": entry["last"],
                "since": int(entry["first"][:4]),
                "until": None if last_year >= as_of_year else last_year,
            }
        )
    return sorted(
        skills,
        key=lambda s: (
            -_month_index(s["last"]) if s["last"] else 0,
            -s["hours"],
            s["id"],
        ),
    )
