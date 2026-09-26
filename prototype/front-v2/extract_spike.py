"""PROTOTYPE, throwaway. Reduce the activity spike to publishable aggregates.

Reads the spike scratch files (commit evidence per day, hours per tech) and
writes spike-data.json with aggregates only: a context and an intensity level
per commit day, real hours per year per context, hours per tech. No repository
name, path or identity leaves this script.

Run: .venv/bin/python prototype/front-v2/extract_spike.py <spike-scratch-dir>
"""

import html
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent / "spike-data.json"
DATA = Path(__file__).resolve().parents[2] / "data"
AS_OF = date(2026, 9, 26)
PRO_WEEKS, STUDY_WEEKS = 47 / 12, 30 / 12  # worked weeks per month
PERSONAL_H_PER_DAY = 3

# Calendar sources: (start, end inclusive, context, hours per week, weeks/month).
# Taken from the spike estimates; the two parallel employments of 2014-2020
# are one 50 h/week source, so the hours are never counted twice.
SOURCES = [
    ("2006-09", "2009-03", "study", 25, STUDY_WEEKS),
    ("2008-09", "2009-03", "study", 8, STUDY_WEEKS),
    ("2009-04", "2009-07", "study", 40, PRO_WEEKS),
    ("2009-10", "2014-02", "pro", 40, PRO_WEEKS),
    ("2014-04", "2020-03", "pro", 50, PRO_WEEKS),
    ("2026-06", "2026-09", "pro", 40, PRO_WEEKS),
]
PERSONAL = ("2020-04", "2026-05")


def context(day):
    month = day[:7]
    if month < "2020-04" or month >= "2026-06":
        return "pro"
    return "personal"


def months(start, end):
    y, m = map(int, start.split("-"))
    while f"{y:04d}-{m:02d}" <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def level(weight, cuts):
    return 1 + sum(weight > c for c in cuts)


def main(scratch):
    evidence = json.loads((scratch / "evidence-v2.json").read_text())
    day_tech = evidence["day_tech"]
    weights = sorted(sum(v.values()) for v in day_tech.values())
    cuts = [weights[len(weights) * q // 4] for q in (1, 2, 3)]
    days = {
        d: [context(d), level(sum(v.values()), cuts)]
        for d, v in sorted(day_tech.items())
        if d <= AS_OF.isoformat()
    }

    hours = defaultdict(lambda: defaultdict(float))
    for start, end, ctx, per_week, weeks in SOURCES:
        for y, m in months(start, end):
            share = 1.0
            if (y, m) == (AS_OF.year, AS_OF.month):
                share = AS_OF.day / 30
            hours[y][ctx] += per_week * weeks * share
    for d, (ctx, _) in days.items():
        if ctx == "personal" and PERSONAL[0] <= d[:7] <= PERSONAL[1]:
            hours[int(d[:4])]["personal"] += PERSONAL_H_PER_DAY

    label_to_tech = {
        t["label"]: t for t in json.loads((DATA / "techs.json").read_text())
    }
    techs = []
    lines = (scratch / "spike-hours-v3.txt").read_text().splitlines()[1:]
    for line in lines:
        cols = line.split()
        if len(cols) < 6:
            continue
        period = cols[-1]
        label = html.unescape(" ".join(cols[:-5]))
        total, pro, personal = (int(c.replace(",", "")) for c in cols[-5:-2])
        tech = label_to_tech[label]
        first, last = period.split("–")
        techs.append(
            {
                "id": tech["id"],
                "domain": tech["domain"],
                "hours": total,
                "pro": pro,
                "personal": personal,
                "first": int(first),
                "last": AS_OF.year if last == "now" else int(last),
            }
        )

    per_ctx = defaultdict(int)
    for ctx, _ in days.values():
        per_ctx[ctx] += 1
    data = {
        "as_of": AS_OF.isoformat(),
        "note": "Aggregates only, from the activity spike. Throwaway.",
        "model": {
            "pro_weeks_per_year": 47,
            "study_weeks_per_year": 30,
            "personal_hours_per_commit_day": PERSONAL_H_PER_DAY,
        },
        "commit_days": len(days),
        "commit_days_by_context": dict(sorted(per_ctx.items())),
        "days": days,
        "hours_by_year": {
            str(y): {k: round(v) for k, v in sorted(hours[y].items())}
            for y in sorted(hours)
        },
        "techs": techs,
    }
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print("wrote", OUT.name, len(days), "days", len(techs), "techs")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
