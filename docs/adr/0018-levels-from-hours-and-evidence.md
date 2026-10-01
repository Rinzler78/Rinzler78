# ADR-018 — Levels from hours and evidence; declared shares of tools

- **Status**: Accepted
- **Date**: 2026-09-30
- **Amends**: [ADR-013](0013-activity-timeline-evidence-hours.md) (§5 levels; declared shares), [ADR-016](0016-front-page-v2-content-icons-dates.md) (skills order)
- **Related to**: [ADR-014](0014-claims-evidence-registry.md), [ADR-017](0017-author-statement-evidence-kind.md)

## Context

ADR-013 turned hours into a level by a stated convention (working ≥ 50 h,
professional ≥ 500 h, advanced ≥ 1,600 h, expert ≥ 5,000 h). Applied to the full
aggregates, with project-level frameworks and author-declared periods, the ranking was
reviewed tech by tech with its per-year chronology. Three biases appeared:

1. **The past outweighs the present.** Technologies practiced full-time fifteen years
   ago rank above current strengths; nothing but a "last used" date tells them apart.
2. **Depth is under-counted.** Designing an architecture others build on takes few
   hours in few files. The author's white-label mobile SDK — its view-model base classes
   inherited by five apps, its platform abstractions — measured 858 h of MVVM and 448 h
   of platform abstraction: professional and working levels for work that is expert by
   any reading.
3. **Uniform declared shares inflate tools.** A tier applied to every hour of a long
   period turns "used it daily" into "spent a third of the time on it": 3,006 h of
   Docker where the repositories whose product is a container account for 48 commit
   days in seven years; 3,317 h of "mobile build and release", 35 % of six years of
   coding. The daily build, moreover, is the ordinary action that precedes any
   execution, not a skill.

## Decision

### 1. Displayed level = the higher of two levels

- The **hours level** keeps the ADR-013 convention.
- An **evidence level** may be granted to a tech by an achievement recorded in the
  claims registry (ADR-014, ADR-017), e.g. "designed the SDK five apps inherit from".
- The page shows the higher of the two and its origin: "858 h · expert (SDK design)".
- Evidence levels live in a committed data file mapping each tech to its level and
  claim identifier; the claim's wording and proof stay under the registry's rules.

### 2. Order by domain and recency

Skills are grouped by domain and ordered by recency within the page, not by hours.
Historical technologies are presented as history, with their period.

### 3. Declared shares measure time, for identified work only

A declared tier states the share of coding time spent **on** the tool or practice, not
whether it was used. It applies only to a mission or activity identified as such (a
virtualization mission, a build environment to freeze), never as a uniform share over a
long period.

### 4. What counts as a skill

- **Build** — the everyday compile, test, run, package loop — is not a skill.
- **Mobile release** is: signing, provisioning, store submission (TestFlight, Play
  Console), measured from signing properties, release scripts and pipeline steps, plus
  an occasional declared share where releases were the author's job.
- **Cross-compilation toolchains** is: defining the compilation chain per platform and
  architecture (toolchain files, CMake/Make, NDK settings, per-OS/arch build scripts),
  measured from those files, plus declared missions.
- **Docker** is measured at project level: every hour in a repository whose product is
  a container image counts, plus Dockerfile/compose files elsewhere; identified
  container missions are declared.

## Considered options

- **Reintroduce a forgetting curve** — rejected by ADR-013 for its invented constants;
  recency is shown by period and order instead.
- **Drop levels** — loses the one-glance reading the page needs.
- **Hours only** — keeps the three biases above.

## Consequences

**Positive**
- A level can reflect design depth when an attested achievement proves it.
- Declared hours can no longer grow a tool beyond what the work was.

**Negative**
- Evidence levels depend on the registry being kept; an unattested achievement grants
  nothing.
- Two sources for one label; the page must say which one applies.

## Success criteria

- Every displayed level above its hours level cites a claim present in the lock.
- No declared overlay period spans more than an identified mission or activity.
- The front page never orders skills by hours alone.
