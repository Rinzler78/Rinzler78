"""Front page v2 view model (ADR-015, ADR-016, ADR-018).

Everything the front page states is computed here from the committed data —
key figures from the aggregates, achievements gated by the claims lock, live
counters as shields.io badge URLs (never stored), skill tiles by domain and
recency, the chronology newest first — and handed to the README template and
to the tile renderer (``scripts/tiles.py``). Display copy comes from
``content.front``; its placeholders are filled here, so a figure is never typed.

Public surface: the small pure helpers below, and ``build_front(data, lang)``
which assembles the page view for one language.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, timedelta

from scripts.activity.hours import display_hours
from scripts.claims import mark
from scripts.icons import band_entries, band_rows, band_units, tile_icon

# A badge reads on both GitHub themes in the deep green step of the palette:
# the bright dark-theme accent would carry white badge text below AA.
BADGE_COLOR = "3f6212"
BADGE_STYLE = f"style=flat-square&color={BADGE_COLOR}"
SHIELDS = "https://img.shields.io"
CONTEXTS = ("pro", "personal", "study")
LEVEL_ORDER = ("working", "professional", "advanced", "expert")
STREAK = "https://streak-stats.demolab.com"
# Icons per band line, and the column width a full line spans.
BAND_PER_LINE = 16
COLUMN_PX = 834
# Detail pages per language (ADR-008), relative to the README.
PAGES = {"fr": "pages/", "en": "pages/en/"}
# Skills drawn as bars in a domain tile; the others share one compact line.
BARS_PER_TILE = 5
_CONTACTS = (("linkedin", "LinkedIn"), ("malt", "Malt"), ("github", "GitHub"))
_CONTACTS_TAIL = (("pypi", "PyPI"),)
_SENTENCE_END = re.compile(r"(?<=[^\s.])\.(?=\s|$)")


# --- Formatting -----------------------------------------------------------------


def thousands(value: int, words: dict) -> str:
    return f"{value:,}".replace(",", words["thousands"])


def join(items: list[str], words: dict) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + words["and"] + items[-1]


def github_anchor(heading: str) -> str:
    """The id GitHub gives a markdown heading: lowercase, punctuation dropped,
    each space a hyphen (an ``&`` between spaces leaves two hyphens)."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def first_sentence(text: str) -> str:
    """Up to the first full stop that ends a sentence (``.NET`` survives)."""
    match = _SENTENCE_END.search(text)
    return text[: match.end()] if match else text


def pairs(items: list) -> list[list]:
    return [items[i : i + 2] for i in range(0, len(items), 2)]


def streak_url(user: str, pal: dict, lang: str) -> str:
    """The streak widget in the tile palette (ADR-016: labelled as GitHub's)."""
    params = {
        "border": pal["border"],
        "background": pal["panel"],
        "stroke": pal["border"],
        "ring": pal["accent"],
        "fire": pal["accent"],
        "currStreakNum": pal["text"],
        "sideNums": pal["text"],
        "currStreakLabel": pal["accent"],
        "sideLabels": pal["muted"],
        "dates": pal["dim"],
    }
    query = "&".join(f"{k}={v.lstrip('#')}" for k, v in params.items())
    return f"{STREAK}/?user={user}&locale={lang}&{query}"


def band_width(count: int) -> int:
    """Pixel width of a band line of ``count`` icons, at the full-line scale."""
    return round(band_units(count) * COLUMN_PX / band_units(BAND_PER_LINE))


# --- Identity -------------------------------------------------------------------


def key_figures(aggregates: dict, profile: dict, skills: list[dict]) -> dict:
    """The identity figures: every one derived, none typed (ADR-016)."""
    as_of_year = int(aggregates["activity_as_of"][:4])
    total = math.fsum(aggregates["context_totals"].values())
    calendar = aggregates.get("calendar") or {}
    return {
        "years": as_of_year - profile["since_coding"],
        "hours": display_hours(total),
        "days": aggregates["coverage"]["commit_days"],
        "first_year": int(min(calendar)[:4]) if calendar else as_of_year,
        "skills": sum(1 for s in skills if s["level"] in ("advanced", "expert")),
        "since": profile["since_coding"],
    }


def contact_links(profile: dict) -> list[tuple[str, str]]:
    """Native markdown contacts: e-mail first, then the professional links."""
    out = []
    email = profile.get("contacts", {}).get("email_pro")
    if email:
        out.append((email, f"mailto:{email}"))
    links = profile.get("links", {})
    for key, label in _CONTACTS + _CONTACTS_TAIL:
        if links.get(key):
            out.append((label, links[key]))
    return out


# --- Achievements (ADR-014) -----------------------------------------------------


def achievements(items: list[dict], lock: dict, lang: str) -> list[dict]:
    """Attested achievements only, newest first, each wording claim-marked.

    An achievement whose claim is absent from the lock is not published: the
    lock is the public trace of an attestation (ADR-014), and ``claims check``
    then verifies the wording on the page against the locked hash.
    """
    attested = set(lock.get("claims", {}))
    shown = [a for a in items if a["claim"] in attested]
    shown.sort(key=lambda a: (a["date"], a["id"]), reverse=True)
    return [
        {
            "id": a["id"],
            "context": a["context"],
            "year": a["date"][:4],
            "wording": mark(a["claim"], a[lang]),
        }
        for a in shown
    ]


# --- Open source (ADR-016 amendment: counters live only) -------------------------


def open_source(projects: list[dict]) -> list[dict]:
    """Public projects with a live counter source and a description."""
    shown = [p for p in projects if p.get("metrics") and p.get("description")]
    # Highlighted first, then newest first (two stable sorts).
    shown.sort(key=lambda p: (p["start"], p["id"]), reverse=True)
    shown.sort(key=lambda p: not p.get("highlight"))
    return [{**p, "summary": first_sentence(p["description"])} for p in shown]


def _repo_path(github_url: str) -> str:
    return github_url.rstrip("/").split("github.com/", 1)[1]


def live_badges(project: dict, alts: dict) -> list[dict]:
    """shields.io badges read live by the visitor's browser; nothing stored."""
    metrics = project.get("metrics") or {}
    badges = []
    if metrics.get("pypi"):
        pkg = metrics["pypi"]
        badges.append(
            {
                "alt": alts["pypi"],
                "src": f"{SHIELDS}/pypi/dm/{pkg}?{BADGE_STYLE}",
                "href": f"https://pypi.org/project/{pkg}/",
            }
        )
    if metrics.get("dockerhub"):
        image = metrics["dockerhub"]
        badges.append(
            {
                "alt": alts["dockerhub"],
                "src": f"{SHIELDS}/docker/pulls/{image}?{BADGE_STYLE}",
                "href": f"https://hub.docker.com/r/{image}",
            }
        )
    badges.append(
        {
            "alt": alts["stars"],
            "src": f"{SHIELDS}/github/stars/{_repo_path(project['github_url'])}"
            f"?{BADGE_STYLE}",
            "href": project["github_url"],
        }
    )
    return badges


def oss_entry(project: dict, labels: dict, copy: dict) -> dict:
    """One open-source tile: every registry the project publishes to."""
    metrics = project["metrics"]
    registries, commands = [], []
    if metrics.get("pypi"):
        registries.append(copy["registries"]["pypi"])
        commands.append(f"$ pip install {metrics['pypi']}")
    if metrics.get("dockerhub"):
        registries.append(copy["registries"]["dockerhub"])
        commands.append(f"$ docker pull {metrics['dockerhub']}")
    techs = [labels[t] for t in project["tech_ids"] if t != "git" and t in labels]
    return {
        "id": project["id"],
        "name": project["name"],
        "summary": project["summary"],
        "registries": registries,
        "commands": commands,
        "legacy": copy["legacy"] if project.get("state") == "legacy" else "",
        "techs": techs,
        "badges": live_badges(project, copy["badges"]),
        "aria": _fill(
            copy["aria"],
            name=project["name"],
            summary=project["summary"],
            techs=", ".join(techs),
        ),
    }


# --- Skills ---------------------------------------------------------------------


def skill_tiles(skills: list[dict], domains: list[dict], bars: int) -> list[dict]:
    """One tile per domain in domain order; skills keep their recency order."""
    tiles = []
    for domain in sorted(domains, key=lambda d: d["order"]):
        rows = [s for s in skills if s["domain"] == domain["id"]]
        if rows:
            tiles.append(
                {"domain": domain["id"], "bars": rows[:bars], "also": rows[bars:]}
            )
    return tiles


def band_segments(entries: list, per_line: int) -> list[dict]:
    """The icon band in its order: runs of one source, split at ``per_line``.

    Each run becomes one image (a skillicons.dev URL or a local SVG), so the
    band keeps the order of ``band_entries`` instead of grouping by source.
    """
    runs: list[dict] = []
    for entry in entries:
        if runs and runs[-1]["source"] == entry.source:
            runs[-1]["keys"].append(entry.key)
        else:
            runs.append({"source": entry.source, "keys": [entry.key]})
    return [
        {"source": run["source"], "keys": chunk}
        for run in runs
        for chunk in band_rows(run["keys"], per_line)
    ]


def period(skill: dict, active: str) -> str:
    first = str(skill["since"])
    last = str(skill["until"])
    if skill["until"] is None:
        return f"{first}–{active}"
    return first if first == last else f"{first}–{last}"


def evidence_marked(skills: list[dict]) -> list[str]:
    """Skills whose shown level comes from an attested achievement (ADR-018)."""
    return [s["id"] for s in skills if s["level_source"] == "evidence"]


def bar_fraction(hours: float, top: float, floor: float = 10.0) -> float:
    """Log-scale share of the bar: hours span four orders of magnitude."""
    if hours <= floor:
        return 0.0
    return min(1.0, math.log10(hours / floor) / math.log10(top / floor))


# --- Chronology -----------------------------------------------------------------


def experience_anchor(experience_id: str) -> str:
    """Stable anchor of a position on the journey page."""
    return f"exp-{experience_id}"


def _when(start: str, end: str | None, now: str) -> str:
    if end is None:
        return f"{start} → {now}"
    return start if start == end else f"{start} – {end}"


def chronology(experiences: list[dict], now: str) -> list[dict]:
    """One line per position, newest first: where, when and its kind.

    Consecutive positions at one organization (two phases of one employment)
    make one line, linked to the newest phase.
    """
    ordered = sorted(experiences, key=lambda e: (e["start"], e["id"]), reverse=True)
    out: list[dict] = []
    for x in ordered:
        start = x["start"][:4]
        end = x["end"][:4] if x.get("end") else None
        if out and out[-1]["org"] == x["org"]:
            merged = out[-1]
            merged["start"] = start
            merged["when"] = _when(start, merged["end"], now)
            continue
        out.append(
            {
                "anchor": experience_anchor(x["id"]),
                "org": x["org"],
                "type": x.get("type", ""),
                "start": start,
                "end": end,
                "when": _when(start, end, now),
            }
        )
    return out


# --- Activity -------------------------------------------------------------------


def calendar_halves(first: int, last: int) -> tuple[list[int], list[int]]:
    """The calendar years in two tiles, oldest first; the first takes the odd
    year."""
    years = list(range(first, last + 1))
    cut = (len(years) + 1) // 2
    return years[:cut], years[cut:]


def calendar_counts(calendar: dict) -> dict[str, int]:
    counts = Counter(entry["context"] for entry in calendar.values())
    return {ctx: counts.get(ctx, 0) for ctx in CONTEXTS}


def longest_streak(days: list[str]) -> int:
    best = run = 0
    previous: date | None = None
    for day in sorted(date.fromisoformat(d) for d in days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best, previous = max(best, run), day
    return best


def busiest_year(days: list[str]) -> tuple[int, int]:
    counts = Counter(int(d[:4]) for d in days)
    year, count = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    return year, count


# --- Page view ------------------------------------------------------------------


def _fill(template: str, **values) -> str:
    """Fill a copy template; an unknown placeholder fails the build."""
    return template.format_map(values)


def _hours_text(hours: int, words: dict) -> str:
    return f"≈ {thousands(hours, words)} h"


def _levels_sentence(levels: dict, names: dict, words: dict) -> str:
    ordered = [lvl for lvl in LEVEL_ORDER if lvl in levels]
    return join(
        [
            words["level"].format(level=names[lvl], hours=thousands(levels[lvl], words))
            for lvl in ordered
        ],
        words,
    )


def _skill_row(skill: dict, copy: dict, words: dict, top: float, icons_doc: dict):
    return {
        "id": skill["id"],
        "label": skill["label"],
        "icon": tile_icon(skill["id"], icons_doc),
        "hours": skill["display_hours"],
        "hours_text": _hours_text(skill["display_hours"], words),
        "level": copy["levels"][skill["level"]],
        "evidence": skill["level_source"] == "evidence",
        "period": period(skill, copy["active"]),
        "active": skill["until"] is None,
        "fraction": bar_fraction(skill["hours"], top),
    }


def build_front(data: dict, lang: str) -> dict:
    """The whole front page view for one language, from the enriched bag."""
    copy = data["content"]["front"]
    pages = PAGES[lang]
    words = data["content"]["caption_words"][lang]
    aggregates = data["aggregates"]
    profile = data["profile"]
    skills = data["skills"]
    as_of = aggregates["activity_as_of"]
    as_of_year = int(as_of[:4])
    figures = key_figures(aggregates, profile, skills)
    fig_text = {
        "years": str(figures["years"]),
        "hours": thousands(figures["hours"], words),
        "days": thousands(figures["days"], words),
        "first_year": str(figures["first_year"]),
        "skills": str(figures["skills"]),
        "since": str(figures["since"]),
    }
    method_anchor = github_anchor(copy["method"]["title"])
    status = copy["identity"]["status"].get(profile["status"], profile["status"])
    arc = " → ".join(n["label"] for n in data["signature_arc"])
    location = f"{profile['location']['city']}, {profile['location']['region']}"

    # Identity --------------------------------------------------------------
    identity = {
        "prompt": copy["identity"]["prompt"],
        "name": profile["name"],
        "role_lines": [part.strip() for part in re.split(r"\s[·-]\s", profile["role"])],
        "status": status,
        "arc": arc,
        "since": _fill(copy["identity"]["since"], since=fig_text["since"]),
        "location": location,
        "aria": _fill(
            copy["identity"]["aria_name"],
            name=profile["name"],
            role=profile["role"],
            status=status,
            arc=arc,
            location=location,
        ),
    }
    ci = copy["identity"]
    figure_tile = {
        "prompt": _fill(ci["figures_prompt"], since=fig_text["since"]),
        "cells": [
            (fig_text["years"], ci["years"], ""),
            (fig_text["hours"], ci["hours"], ci["hours_extra"]),
            (
                fig_text["days"],
                ci["days"],
                _fill(ci["days_extra"], first_year=fig_text["first_year"]),
            ),
            (fig_text["skills"], ci["skills"], ci["skills_extra"]),
        ],
        "aria": _fill(ci["aria_figures"], **fig_text),
    }

    # Offer -------------------------------------------------------------------
    services = sorted(
        (s for s in data["services"] if s.get("visible")),
        key=lambda s: s["priority"],
    )
    modes = [m["label"] for m in sorted(data["modes"], key=lambda m: m["order"])]

    # Open source -------------------------------------------------------------
    labels = {t["id"]: t["label"] for t in data["techs"]}
    oss_copy = copy["oss"]
    oss = [oss_entry(p, labels, oss_copy) for p in open_source(data["projects"])]
    registries: list[str] = []
    for entry in oss:
        registries += [r for r in entry["registries"] if r not in registries]

    # Skills ------------------------------------------------------------------
    sk = copy["skills"]
    top = max((s["hours"] for s in skills), default=10.0)
    tiles = []
    for tile in skill_tiles(skills, data["domains"], BARS_PER_TILE):
        title = sk["domains"].get(tile["domain"], tile["domain"])
        bars = [_skill_row(s, sk, words, top, data["icons"]) for s in tile["bars"]]
        also = [_skill_row(s, sk, words, top, data["icons"]) for s in tile["also"]]
        rows = ", ".join(
            f"{r['label']} {r['hours_text']} {r['level']} {r['period']}"
            for r in bars + also
        )
        tiles.append(
            {
                "domain": tile["domain"],
                "title": title,
                "eyebrow": f"skills --domain={tile['domain']}",
                "also_label": sk["also"],
                "bars": bars,
                "also": also,
                "aria": _fill(sk["aria"], domain=title, rows=rows),
            }
        )
    ordered_ids = [r["id"] for t in tiles for r in t["bars"] + t["also"]]
    band = band_entries(ordered_ids, data["icons"])
    segments = band_segments(band, BAND_PER_LINE)
    local_count = 0
    for segment in segments:
        segment["alt"] = (
            ", ".join(labels[t] for t in segment["keys"])
            if segment["source"] == "local"
            else ""
        )
        if segment["source"] == "local":
            local_count += 1
            segment["file"] = f"skills-band-{local_count}.svg"
    active = [s for s in skills if s["until"] is None]
    top_active = sorted(active, key=lambda s: (-s["hours"], s["id"]))[:3]
    skills_sentence = _fill(
        sk["sentence"],
        count=str(len(skills)),
        threshold=str(aggregates["levels"]["working"]),
        domains=str(len(tiles)),
        active=str(len(active)),
        year=str(as_of_year),
        top=join(
            [
                f"{s['label']} ({_hours_text(s['display_hours'], words)})"
                for s in top_active
            ],
            words,
        ),
    )

    # Chronology ---------------------------------------------------------------
    tl = copy["timeline"]
    entries = chronology(data["experiences"], tl["now"])
    for e in entries:
        e["type_label"] = tl["types"].get(e["type"], e["type"])
    first_position = min(x["start"][:4] for x in data["experiences"])

    # Activity -----------------------------------------------------------------
    act = copy["activity"]
    calendar = aggregates["calendar"]
    days = sorted(calendar)
    counts = calendar_counts(calendar)
    halves = []
    for years in calendar_halves(int(days[0][:4]), as_of_year):
        if not years:
            continue
        in_half = {d: v for d, v in calendar.items() if int(d[:4]) in years}
        half_counts = calendar_counts(in_half)
        halves.append(
            {
                "years": years,
                "title": f"{years[0]} → {years[-1]}",
                "sub": _fill(act["cal_sub"], days=thousands(len(in_half), words)),
                "aria": _fill(
                    act["aria"],
                    first=str(years[0]),
                    last=str(years[-1]),
                    days=thousands(len(in_half), words),
                    pro=thousands(half_counts["pro"], words),
                    personal=thousands(half_counts["personal"], words),
                ),
            }
        )
    busiest, busiest_days = busiest_year(days)

    return {
        "identity": identity,
        "figures": figure_tile,
        "identity_sentence": _fill(ci["sentence"], role=profile["role"], **fig_text),
        "contacts": contact_links(profile),
        "help": {
            "title": copy["help"]["title"],
            "intro": _fill(copy["help"]["intro"], count=str(len(services))),
            "services": services,
            "modes": _fill(copy["help"]["modes"], modes=" · ".join(modes)),
        },
        "achievements": {
            "title": copy["achievements"]["title"],
            "items": [
                {**a, "context_label": copy["achievements"]["contexts"][a["context"]]}
                for a in achievements(data["achievements"], data["claims_lock"], lang)
            ],
        },
        "oss": {
            "title": oss_copy["title"],
            "items": oss,
            "pairs": pairs(oss),
            "sentence": _fill(
                oss_copy["sentence"],
                count=str(len(oss)),
                registries=join(registries, words),
            ),
        },
        "skills": {
            "title": sk["title"],
            "band_alt": sk["band_alt"],
            "band": segments,
            "labels": labels,
            "tiles": tiles,
            "pairs": pairs(tiles),
            "sentence": skills_sentence,
            "evidence_note": (
                _fill(sk["evidence_note"], method=method_anchor)
                if evidence_marked(skills)
                else ""
            ),
        },
        "timeline": {
            "title": tl["title"],
            "entries": entries,
            "sentence": _fill(
                tl["sentence"],
                count=str(len(entries)),
                first=first_position,
                journey=f"{pages}journey.md",
            ),
        },
        "method": {
            "title": copy["method"]["title"],
            "hours": _fill(
                copy["method"]["hours"],
                days=fig_text["days"],
                first_year=fig_text["first_year"],
                public=thousands(aggregates["coverage"]["public_days"], words),
            ),
            "levels": _fill(
                copy["method"]["levels"],
                levels=_levels_sentence(aggregates["levels"], sk["levels"], words),
            ),
            "statements": copy["method"]["statements"],
        },
        "activity": {
            "title": act["title"],
            "prompt": act["cal_prompt"],
            "halves": halves,
            "contexts": act["contexts"],
            "days_unit": act["days_unit"],
            "less": act["less"],
            "more": act["more"],
            "sentence": _fill(
                act["sentence"],
                days=fig_text["days"],
                first_year=fig_text["first_year"],
                pro=thousands(counts["pro"], words),
                personal=thousands(counts["personal"], words),
            ),
            "github_title": act["github_title"],
            "github_sentence": act["github_sentence"],
            "snake_alt": act["snake_alt"],
            "streak_alt": act["streak_alt"],
        },
        "more": copy["more"],
        "pages": pages,
        "footer": {
            "signature": _fill(
                copy["footer"]["signature"],
                name=profile["name"],
                as_of=as_of,
                method=method_anchor,
            ),
            "egg": _fill(
                copy["footer"]["egg"],
                since=fig_text["since"],
                years=fig_text["years"],
                days=fig_text["days"],
                streak=str(longest_streak(days)),
                busiest=str(busiest_days),
                busiest_year=str(busiest),
                tagline=profile["tagline"],
            ),
        },
    }
