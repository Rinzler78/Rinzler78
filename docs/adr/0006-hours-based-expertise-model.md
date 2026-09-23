# ADR-006 — Hours-based expertise model (max vs current)

- **Status**: Accepted (extended by [ADR-009](0009-visual-redesign-devtool-direction.md))
- **Date**: 2026-05-29
- **Supersedes**: the **formula** from [ADR-002](0002-tech-score-derivation.md) (base years + versions + projects + centrality + depth). The tiers (5 levels) and the override mechanism from ADR-002 are **kept**.

> **Extended 2026-09-23:** the same exposure hours are now also split **per calendar
> year** (`compute_tech_hours_by_year`) and aggregated per domain
> (`build_domain_year_hours`) to feed the journey charts. The split is a *partition* of
> the totals below — a test pins the two together, so a chart and a score drawn from
> this model can never disagree. Experiences carry months and are pro-rated exactly;
> projects carry `active_days` and a year range with no months, so their hours are
> spread **uniformly** over that range — an explicit approximation, since `active_days`
> records how many distinct days saw commits, never which ones. The `languages` domain
> is excluded from the per-domain timeline: it is used inside every other domain, so it
> would be lit every year while flattening the scale of the rows that carry
> information. Tier fractions remain cumulative, so summing across domains
> double-counts: these values are rendered as **shares**, never as hours worked.

## Context

The additive formula from ADR-002, even amended with the `depth` factor, remained an assembly of proxies ("how much I worked"). Three validation passes over the 41 real techs showed that it captured neither **private expertise** (client missions invisible on GitHub), nor **ambient tooling** (git/docker/AI-tooling never "the topic" but omnipresent), nor the **distinction between the peak reached and what remains of it today**.

Boris formulated the right model: estimate a **number of hours** per topic, derive from it a **max expertise** (the peak, absolute, never decreases), then a **current expertise** = max after a **forgetting curve** whose speed depends on the level reached and which never drops back to zero (some traces always remain).

## Decision

### 1. Hours are the only input to the score

Two sources, aggregated by `HoursCalculator`:

- **Experience** (employment, studies, mission, competition) — `data/experiences.json`:
  `hours = span_years × HOURS_PER_YEAR`, `HOURS_PER_YEAR = 1880` (40 h × 47 weeks). Studies count as **full time** (1880).
- **Project** personal — `data/projects.json`:
  `hours = active_days × HOURS_PER_PERSONAL_DAY`, `HOURS_PER_PERSONAL_DAY = 9` (typical personal day 8am–6pm −1h break). `active_days` = number of days with commits (derived from GitHub, stored and refreshable).

### 2. Allocation by concurrent tiers (exposure hours, cumulative)

Each source carries **one** map `tech_weights : {tech_id: tier}`. A tier is a **factual assertion** ("on this work, this tech was primary / secondary / incidental"), not a guessed decimal.

Each tech receives `fraction(tier) × source_hours`, **cumulative and not normalized**:

| tier | fraction | meaning |
|---|---|---|
| `primary` | 0.70 | in play across most of the period |
| `secondary` | 0.35 | in play over a significant portion |
| `incident` | 0.10 | touched occasionally |

**No normalization, no sharing.** On a project combining C#/.NET + Xamarin + Bluetooth, all three are used **at the same time**: each receives `0.70 × source_hours`, not one third. The sum of a period's allocations can therefore exceed its hours — that is correct: these are **exposure hours** (the Ebbinghaus forgetting curve measures practice, not exclusive time). Using Xamarin also means practicing C#.

Cross-cutting tools (git, docker, Claude Code, github-actions) are simply `secondary`/`primary` techs depending on their presence — not a separate category.

### 3. `since` / `until` are derived from the sources

- `since(tech)` = earliest start date among the sources that use it.
- `until(tech)` = `null` if a **current** source (end = null) uses it, otherwise the most recent end date.

Consequence: a tech automatically stops when its last period stops — Boris's temporal invariant is implemented structurally, no more manual entry of `until`.

### 4. Max and current expertise

```
total_hours(tech)  = Σ sources [ fraction(tier) × source_hours ]   # cumulative

peak    = 99 · (1 − exp(−total_hours / H0))          # H0 = 3000
t       = today.year − until.year                     # 0 if until is null (active)
F       = α · peak                                    # residual floor, α = 0.30
halflife(peak) = HL_MIN + (HL_MAX − HL_MIN)·(peak/100)   # 2 → 18 years
λ       = ln(2) / halflife(peak)
current = F + (peak − F) · exp(−λ · t)
```

- **peak** (= max expertise): absolute, monotonic, never decreases. Diminishing returns (the 1st hour teaches more than the 10,000th; ~6000 h ⇒ expert).
- **current** (= current expertise): ≤ peak, ≥ floor `α·peak`. Decreases all the faster as the peak is low (explored = fast forgetting; deep mastery = slow forgetting). Never drops back to 0.

### 5. Tiers (kept from ADR-002)

| Score | level |
|---|---|
| ≥ 85 | expert |
| 70–84 | advanced |
| 55–69 | professional |
| 35–54 | working |
| < 35 | explored |

Applied **twice**: `level_max` (on peak) and `level_current` (on current). The `Skill` view model exposes both pairs (score + level).

### 6. Overrides (kept)

`score_override` / `level_override` on a tech replace the computed **current** value, with the same consistency check as ADR-002. `featured` becomes once again a simple display flag (hero selection), **no longer a score input**.

### 7. Constants

`HOURS_PER_YEAR = 1880` · `HOURS_PER_PERSONAL_DAY = 9` · `H0 = 3000` · `α = 0.30` · `HL_MIN = 2 years` · `HL_MAX = 18 years` · tiers `primary 0.70 / secondary 0.35 / incident 0.10`. Any change to these constants requires a new ADR.

## Consequences

### Positive

- Everything (hours, since, until, max, current) **derives** from factual sources — zero arbitrarily entered number. Aligned with the anti-inflation rule.
- The **ambient** layer finally captures AI-driven development and cross-cutting tools.
- **max vs current** tells the embedded→cloud→AI trajectory (a C++ advanced peak drops back to professional; a Windows CE working drops back to explored).
- Correcting a score = editing a **tier** in a data file + re-running the engine (deterministic). No more guessing.

### Negative

- Richer model: several constants, cumulative exposure hours (not intuitive: the per-period sum exceeds the real hours). Only the *result* (the displayed levels) is public, so defensibility rests on realism, not simplicity.
- Depends on the quality of the tiers and the estimation of period hours. The tiers are honest but subjective assertions; the code (linguist/cloc) serves as a cross-check where it exists.
- Personal `active_days` depends on a GitHub refresh (update-profile workflow).
- Overhaul of `ScoreEngine` (the model changed) + new `HoursCalculator` module. The additive-formula tests are removed.
