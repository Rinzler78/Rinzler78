# ADR-002 — Deriving the score and level of a Tech

- **Status**: Accepted
- **Date**: 2026-05-27
- **Supersedes**: —
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md)

## Context

The profile displays a radar chart and skill bars. To stay credible and publicly defensible, the displayed levels cannot be arbitrary hand-entered ratings ("C# 87/100"): that is exactly the "made-up numbers" red flag we reject.

Two models were ruled out:

1. **Free-entry rating** (Spec V1, `skill.score: 95`) — unverifiable, inflatable, unmaintainable.
2. **3 purely qualitative tiers** (the repo's original model: `expert` / `intermediate` / `notions`) — robust but too coarse: it does not distinguish "shipped to production" (Professional) from "tinkered with in a prototype" (Working/Explored).

## Decision

The `score` and `level` of a Tech are **derived** by the generator from the facts entered in `data/techs.json` and `data/projects.json`. They are not stored.

### Entered facts (techs.json)

- `since` — year of first use (**nullable**; `null` = never actually adopted, e.g. read-level)
- `until` — year of last use if abandoned (optional; absent = still active)
- `versions[]` — list of versions worked through (required, may be empty)
- `depth` — depth of production usage, **0 to 3** (optional, defaults to 0) — see amendment below
- `featured` — boolean, commercial override (optional)
- `level_override` — forces the qualitative tier (optional)
- `score_override` — forces the numeric score (optional)

### Formula

```
active_years    = (until or today) − since   # 0 if since is null
recency_gap     = max(0, today − (until or today))   # 0 if since is null
n_versions      = len(tech.versions)
n_projects      = count(p ∈ projects.json where tech.id ∈ p.tech_ids)
n_domains       = count(distinct p.domain for those projects)

base            = min(60, active_years × 3)
versions_pts    = min(15, n_versions × 3)
projects_pts    = min(15, n_projects × 3)
centrality_pts  = min(10, max(0, n_domains − 1) × 5)
depth_pts       = depth × 20                       # 0 / 20 / 40 / 60

raw             = base + versions_pts + projects_pts + centrality_pts + depth_pts
forgetting      = recency_gap × 6
featured_bonus  = 15 if featured else 0

score = clamp(0, 99, raw − forgetting + featured_bonus)
```

### The `depth` factor (post-migration amendment, 2026-05-28)

The original formula only rewarded **public evidence** (GitHub projects, logged versions, years). Yet real expertise largely comes from **private client engagements** that are invisible on GitHub. Of the 41 real techs, only 2 (`csharp`, `dotnet`) reached their real level; `python`, `docker`, `asp-net-core`, etc. dropped to `explored` despite production expertise.

`depth` corrects this bias. It is a **factual self-assessment** of the depth of production usage, not an arbitrary number:

| depth | Meaning |
|---|---|
| 0 | Read-level, experimental, never shipped (default) |
| 1 | Shipped occasionally, secondary on some engagements |
| 2 | Used regularly in production across several engagements |
| 3 | Core expertise, deep mastery, primary tool in production for years |

`depth` is **additive** (`+20` per level) and feeds into `raw`, so the forgetting penalty degrades it too (a `depth=3` abandoned long ago drops back down correctly). `since: null` is now tolerated (years_active = 0).

### Tiers

| Score | `level` |
|---|---|
| ≥ 85 | `expert` |
| 70–84 | `advanced` |
| 55–69 | `professional` |
| 35–54 | `working` |
| < 35 | `explored` |

### Override rules

- If `score_override` is set, it replaces the computed score.
- If `level_override` is set, it replaces the level derived from the score.
- If both are set, they must be consistent (the `score_override` must fall within the range of the `level_override`). A test enforces this consistency.
- An override never hides the raw score in the code: both are visible in the view model for audit.

## Consequences

### Positive

- The score is **defensible**: every number can be justified by the formula + the facts.
- Evolution over time is **automatic**: one more year → score recomputed with no data entry.
- Overrides force you to ask "why doesn't the formula capture this case" → implicit documentation via `notes`.
- 5 tiers make it possible to distinguish production / prototype / watching.

### Negative

- The formula depends on `projects.json` being honest: missing projects → underrated score → need for an override. It requires discipline.
- The coefficients (3 pts/year, caps 60/15/15/10, forgetting penalty 6/year, featured bonus 15) are editorial choices: a future adjustment will shift all the boundaries. Any change to the coefficients requires a new ADR.
- The formula does not capture **intensity** (full-time engagement vs side-project): only the override compensates for that.
