# ADR-013 — Hours from an activity timeline and commit evidence

- **Status**: Accepted
- **Date**: 2026-09-26
- **Supersedes**: [ADR-006](0006-hours-based-expertise-model.md) (tier fractions, 0–99 score, forgetting curve)
- **Amends**: [ADR-011](0011-committed-reference-date.md) (what the committed data holds)
- **Related to**: [ADR-014](0014-claims-evidence-registry.md), [ADR-015](0015-front-page-v2-grid-palette-type.md)

## Context

ADR-006 derived each tech's expertise from exposure hours: every source (experience or
personal project) declared a tier per tech — `primary` 0.70, `secondary` 0.35,
`incident` 0.10 of its hours, cumulative and not normalized — then a 0–99 score came out
of `99·(1 − e^(−h/3000))` and decayed after last use toward 30 % of the peak.

An audit on 2026-09-26 ran that model against the data and checked its outputs against
primary sources. It published statements that were false or misleading:

1. **A tech shown as current and expert after it stopped.** A source with no end date
   keeps a tech "active", so a side project of a dozen commit days, last touched years
   earlier, held a framework at 95 with no decay — a framework whose vendor had itself
   ended support.
2. **A start date before the tech existed.** A project spanning 2014–2021 dated GitHub
   Actions from 2014; GitHub Actions reached general availability in November 2019, and
   the repository holds no workflow file.
3. **A tool ranked second.** Git, declared `primary` on the freelance source, scored 96.
4. **Inflation by declaration count.** Cumulative fractions made one calendar year of the
   freelance source worth 4.85 years of exposure (18 techs declared); the total grows
   with how many techs a source lists, not with time.
5. **A one-month mission counted as zero** (`start == end` month).
6. **False precision.** A two-digit score implies ±1-point accuracy from hand-picked
   constants (3000 h, 1880 h/year, 0.70/0.35/0.10, a 2–18-year half-life, a 30 % floor).

Normalizing each source to 100 % was measured too: it collapses daily-use skills of the
last years to the `working` level, which is equally untrue. The fault is not only the
formula: tiers are declarations, and declarations drift.

Public research gives no measurement to replace them. The "10,000 hours" figure is a
popularization its originator disputed; a meta-analysis (Macnamara, Hambrick & Oswald,
*Psychological Science*, 2014) found deliberate practice explains under 1 % of the
variance in performance in professions. **Any mapping from hours to a level is a
convention**, and is honest only when presented as one.

## Decision

Hours are measured from **what happened**, allocated from **what was written**, and
turned into a level by a **stated convention**.

### 1. A continuous activity timeline

The history is a sequence of periods, month by month since 2005-09, with no gap. Each
period has a context — study, employment, client mission, full-time independent R&D —
and a daily budget within a fixed grid: **08:00–22:00 minus 12:00–13:00 and
18:00–20:00, i.e. 11 hours available**.

| Context | Professional hours / day | Personal hours / day |
|---|---|---|
| Employment, client mission | 8 | 3 |
| Parallel dual employment, 2014-04 → 2020-03 (50 h/week, 80 % coding, split 70/30 between the two employers) | 10 | 1 |
| Full-time independent R&D | — | 11 |
| Study, 2006-09 → 2009 | ≈ 12 h of coding per week, 30 weeks per year | — |

- **Professional time counts by the calendar.** The employment record is authoritative
  for dates and job titles. Where the timeline must differ from it, the exception is an
  explicit entry of the private registry (ADR-014), never an unrecorded edit.
- **Personal time counts only on days with at least one own commit**, at the period's
  personal budget; a weekend commit day counts the same as a weekday. A commit proves a
  day was worked, not how long — this is the defensible lower bound.
- Code starts in 2006 (first code at university); 2005-09 → 2006-08 counts zero.

### 2. Evidence: own commits, every source

Own commits are collected from every place they live — public and private GitHub
repositories, organization repositories, local working copies, archived repositories of
past employers — filtered by the author's identities, and **deduplicated by commit hash**
so a repository present in several copies counts once. The audit found 11,245 unique
own commits over 1,478 distinct days across 151 repositories; 16 % of those days touch a
public repository.

### 3. Allocation: static analysis of added lines

On a counted day, the hours are split across techs by **static analysis of the lines
each own commit added**:

- the language from the file;
- frameworks and domains (BLE, NFC, blockchain, LLM APIs, …) from a **versioned
  vocabulary** of imports, APIs and packages, which includes the author's own wrapper
  libraries — measured case: BLE reached through an in-house `Bluetooth` wrapper is
  invisible to a vocabulary that only knows platform APIs;
- **generated code excluded** (`*.designer.cs`, `Resource.designer.cs`, `bin/`, `obj/`,
  lock files, vendored trees) — measured case: one generated Android resource file
  produced over 2,000 spurious matches.

Declared tiers survive only for periods **without any trace** (before 2014), as
estimates, and the page says so.

### 4. Overlap rule

One hour may count for several techs — writing Python with an AI assistant inside Docker
exercises all three — but **no tech may exceed its period's budget**. Hours per tech are
therefore not additive; hours per context are, and are the only stacked totals shown.

### 5. Levels by convention, no score, no decay

| Level | Hours |
|---|---|
| working | ≥ 50 |
| professional | ≥ 500 |
| advanced | ≥ 1,600 |
| expert | ≥ 5,000 |

Steps of ×10, with one intermediate step between 500 and 5,000. The page labels them as
a convention. A skill line shows **rounded hours · level · period · last use**. There is
**no 0–99 score and no forgetting curve**: "last used: 2013" says what a decay would
say, without three invented constants. A tech appears on the page only from 50 hours;
below that it stays in the data.

### 6. Where it runs

Private and local sources are not reachable from CI. The collection and allocation run
**on the author's workstation**; only **aggregates** are committed — hours per month per
tech, per domain and per context — together with the coverage figure. The repository
classification (context, organization, visibility, whether a project may be named) is
private and lives outside this repository (see ADR-014). Generation in CI stays
deterministic from the committed aggregates and `as_of` (ADR-011).

## Considered options

- **Keep ADR-006 and fix the data** — the tiers are the source of the drift; fixing
  today's values leaves the mechanism that produced them.
- **Normalize each source to 100 %** — measured: daily tools of recent years fall to
  `working`. Rejected.
- **Cap cumulative exposure per source** — one more invented constant compensating for
  declarations. Rejected.
- **Declared hours per week per tech** — replaces a tier by a number that is still a
  declaration. Rejected in favour of measuring from commits wherever commits exist.
- **Count every weekday of an R&D period** — measured: commits cover about 30–40 % of
  those weekdays; crediting the rest asserts work with no trace. Rejected.
- **Public repositories only** — fully checkable by anyone, but it would erase six years
  of employment and most independent work, an understatement as untrue as inflation.
  Rejected; coverage is published instead.

## Consequences

**Positive**
- Every hour on the page traces back to a dated period or a dated commit, and every
  level to a published convention.
- The false statements listed in *Context* disappear by construction: a tech stops when
  its commits stop, a start date is the first commit or the first period that used it.
- The allocation vocabulary is one reviewable file instead of a judgement per source.

**Negative**
- A collection step that only the author can run; a stale aggregate under-reports, and
  is visible as such through `as_of`.
- Periods without traces (before 2014) remain estimates.
- The vocabulary needs upkeep as new libraries appear; an unknown library falls back to
  its language.

## Success criteria

- No tech shows a first-use year earlier than its first own commit or first period that
  used it.
- No tech's hours in a period exceed that period's budget.
- A regenerated profile from the same committed aggregates and `as_of` is
  byte-identical.
- The page publishes the coverage (share of commit days in public repositories) and the
  level convention.
