# CONTEXT — Glossary of the `Rinzler78/Rinzler78` repo

This repo is Boris Leclere's GitHub profile. The README and the decorative SVGs are **generated** from structured JSON data (data / presentation separation). This file defines the vocabulary used in the code and the data.

> This file is a **glossary**, not a specification. For implementation choices, see [docs/adr/](docs/adr/).

---

## Data concepts (sources of truth in `data/`)

### Profile

`data/profile.json` — Boris's identity: name, role, contacts (email, phone), links (LinkedIn, Malt, GitHub, PyPI, Discord, YouTube, X) and **location** (city, region, country, lat, lon, administrative zone, time zone). The location is inline in Profile, not a separate file, because it only changes when he moves.

### Domain

`data/domains.json` — Taxonomy of areas of expertise. Each domain has a stable snake_case `id`, a human `label` and an `order` (display rank). The current domains: `embedded`, `mobile`, `backend`, `devops`, `ai-llm`, `blockchain`. **Embedded comes first** by convention (signature track record).

### Signature arc

A first-class narrative concept: the **ordered progression of domains** `embedded → mobile → cloud → ai` that summarizes Boris's track record (2006 → now). Derived from `domains.order` bounded to the major active domains — never hand-entered. It is the **hero's hook** (see *Hero* under Views) and the central differentiator of the positioning (low-level versatility → AI). Each arc step carries a switch year (single source of truth derived from `timeline.json` / `experiences.json`, **not** replicated in `content.boot_log`) and a factual signature word (e.g. `NFC drivers`, `Xamarin`, `Docker/K8s`, `LLM/RAG`).

### Tech

`data/techs.json` — A "tech" is a technical skill with a root identifier that is **stable over time** (e.g. `csharp`, never `csharp-12`). Each tech carries: `id` (snake_case without version), `label`, `domain-id`, `since` (mandatory adoption year), `until` (year of last use if abandoned, optional), `notes`. It contains a `versions[]` array: each version has its own full snake_case `id` (e.g. `csharp_2_0`, `csharp_12`) + `version` (label) + `since` (year of that version).

**Level and score** are **derived values**, never entered directly (except via override). The generator computes `score` ∈ [0, 99] from the entered facts and infers `level` among 5 tiers (`expert` / `advanced` / `professional` / `working` / `explored`) via fixed thresholds. See [ADR-002](docs/adr/0002-tech-score-derivation.md) for the formula and the tiers.

`depth` field (0–3): depth of production usage, **factual self-assessment** (including private engagements invisible on GitHub). 0 = read-level, 3 = core expertise. Additive (+20/level). Corrects the bias "the formula only sees what is public". See [ADR-002](docs/adr/0002-tech-score-derivation.md).

Override fields (optional, to be used when the formula underrates, e.g. private usage not listed in `projects.json`):
- `level_override` — forces the qualitative level (applies to the **current** level)
- `score_override` — forces the current numeric score
- `featured` — **display-only** boolean (hero / core expertise selection). It **no longer** influences the score since [ADR-006](docs/adr/0006-hours-based-expertise-model.md).

**Score and levels derived from hours** (ADR-006): `since`, `until`, `score_max`/`level_max` (peak reached) and `score_current`/`level_current` (after decay) are **computed** by the `HoursCalculator → ScoreEngine → ViewBuilder` pipeline from **exposure hours**. The hours come from two sources: **Experience** (duration × 1880 h/year) and **Project** (`active_days` × 9 h), distributed across concurrent tiers `primary 0.70 / secondary 0.35 / incident 0.10` (cumulative, not normalized — on a C#+Xamarin+Bluetooth project all three count in full). `peak = 99·(1−e^(−h/3000))`; decay toward a `0.30·peak` floor based on time of inactivity.

**Temporal invariant**: a tech's `since`/`until` are **derived** from the Experience and Project that use it (`until = null` if a current source still employs it, otherwise the latest end). The principle "a skill stops at the end of its last period" is thus implemented structurally — no more manual entry of `until`.

### Experience

`data/experiences.json` — A **dated period** of the track record (employment, studies, mission, competition, internship): `id`, `org`, `role`, `type` (`cdi`/`freelance`/`mission`/`education`/`competition`/`internship`), `start` (`YYYY-MM`), `end` (`YYYY-MM` or `null` if current), `tech_weights` (map `tech_id → tier`). Hours source #1 (duration × 1880 h/year distributed across tiers). Dated bounds from the CV (LinkedIn). Good Angel / My Good Life (parallel, remote work) are modeled as **one** period in two phases so as not to double-count the hours.

### Timeline Event

`data/timeline.json` — The **narrative layer** of the track record: an editorial timeline of milestones for storytelling (rendered by the `timeline-mini` SVG). Each event: `year` (or `year-range`, e.g. `"2024-25"`, `"~1990s"`), `label`, `description`, `techs_added` (ids — ref to Tech or tech-version, **non-rendered metadata**), `techs_summary` (display prose), `highlight` (major milestones: 2006 first code, 2009 Master's, 2014 CTO, 2020 .NET Core, 2023 freelance, 2026 now), and optional flags `is_now` / `is_milestone` / `is_origin`.

**Timeline ≠ Experience.** Timeline is editorial (highlights, prose, non-professional milestones like "2006 first code" or "~1990s first computer"); **Experience** (`data/experiences.json`) is the structured and dated hours source (all periods). The two coexist and must not derive from one another — their roles differ (narrate vs compute). `techs_added` only serves to keep a record of the techs introduced per milestone; it references valid ids (verified by referential integrity) but does **not** feed the hours computation.

### Project

`data/projects.json` — A public repository. Dual role: **showcase** (`highlight`, `description`, `stack_label` — the ~8 shown) AND **hours source #2** (`active_days` × 9 h, distributed by `tech_weights` concurrent tiers). `active_days` = number of distinct days with commits (objective, from GitHub); `start`/`end` = creation/last push years (`end: null` = still active → contributes to the techs' `until = null`). Fields: `id`, `name`, `github_url`, `domain`, `tech_ids[]`, `active_days`, `start`, `end`, `tech_weights`, `state` (`active`/`legacy`/`archive`), `highlight`. All significant repositories (≥ 3 commit-days) are present for the hours; `highlight=true` selects the showcase.

### Service

`data/services.json` — A **sellable offering** that Boris proposes to a client: `id` (kebab-case), `title`, `short_description`, `keywords[]`, `priority` (display order), `visible` (boolean). Current services: Architecture & software overhaul, Technical audit, MVP design & delivery, CI/CD industrialization & delivery, AI-Driven Development, Developer tooling & automation.

Service answers the question "**what can I buy from Boris**". Not to be confused with **Mode**.

### Mode

`data/modes.json` — An **engagement mode**: `id` (kebab-case, English), `label`/`description` (FR content), `order`. Current modes: `part-time-cto`, `solutions-architect`, `emergency-support` (the firefighter — prod incident, critical debt, overwhelmed team), `technical-cofounder`.

Mode answers the question "**how can I engage Boris**". Extracted from the historical `content.modes_intervention[]` — promoted to a first-class entity.

### Methodology

`data/methodology.json` — Collection of **working principles**: `id` (kebab-case), `title`, `body`, `order`. Examples: "Simple before clever", "Tested before validated", "Business value before technical ego", "AI accelerates, it does not replace discipline".

> **i18n**: the narrative fields of Service / Mode / Methodology are in **raw FR** for now (like the rest of `content`). They will be wrapped `{fr, en}` uniformly when the i18n track (DeepL, [ADR-004](docs/adr/0004-i18n-bilingual-readme.md)) is implemented — no half-i18n for now.

### Config

`data/config.json` — Singleton-collection (1 entry `id: "main"`) that points to the **active theme** (`theme_id`) and the **active profile** (`profile_id`) if several are defined. Allows the design to evolve or an A/B test to be versioned without touching the other files.

### Theme

`data/theme.json` — The repo's "design system". Sub-blocks:
- **palette** (dark) and **palette_light** (the **primary**, light-first variant — paper/ink with a warm "Feu" accent). Same named keys (`bg`, `panel`, `accent`, `text`, …); the generator renders each view once per palette into `assets/svg/{,light/}`.
- **fonts**: `display` (**Fraunces**, outlined to paths for the hero — see [ADR-007](docs/adr/0007-display-type-outlined-to-paths.md)); `body` and `mono` are **system-safe** (`system-ui` / `monospace`) since GitHub loads no web font in `<img>` SVG.
- **patterns**: reusable components with their constants — `panel`, `bar`, `chip`, `stat_card`, `status_dot`, level-color maps.

The Theme is editable separately from the other data — change it and all the SVGs re-theme themselves.

### Content

`data/content.json` — Collection of residual narrative modules (those that have not become their own entities): `//` easter eggs per section, `boot_log[]` (lines of the `<details>`), the self-taught blockquote, `footer_eof`, `beyond_code` prose. Each module has `id`, `kind`, `payload` (i18n when prose).

**Promotions** from the historical content.json:
- `modes_intervention[]` → **Mode** entity (data/modes.json)
- working principles / the approach prose → **Methodology** entity (data/methodology.json)

---

## Generation concepts (in `scripts/`)

### Template

A `.jinja` file in `scripts/templates/` that describes the rendering of an SVG or of the README from the data. Uses Jinja2 syntax. A template can inherit from a partial (e.g. `_terminal_window.svg.jinja` reused by all the terminals).

### Generate

`scripts/generate.py` — Python script that loads `data/*.json`, loads `theme.json` (design constants), resolves the references by id, and produces `assets/svg/*.svg` + `README.md` via the Jinja2 templates.

### View (view)

A view is an SVG, a markdown **Page**, or a section that **aggregates** several data concepts. Examples:
- *hero* = identity banner: `Profile.name` (title) + **Signature arc** (hero visual) + "who-for" subtitle + scale line + contact cluster. **Light-first** (primary variant) with a dark mirror via `<picture>`. The arc ribbon's gradient **encodes the arc** (warm at the origin `embedded` → cool at the end `ai`). Display text (name + arc) is outlined to paths (see [ADR-007](docs/adr/0007-display-type-outlined-to-paths.md)).
- *id-card* = projection of Profile + filter of Techs (by domain)
- *timeline-life* = sorted Timeline Events
- *stack-{domain}* = Techs filtered by domain
- *featured* = Projects grouped by domain
- *career* = Timeline Events filtered (highlight=true)

Views are **derived**, never stored. This is the invariant that guarantees inter-view consistency.

### Page

A generated markdown file that is a view at document scale. `README.md` is the **front** Page (concise: hero + quick résumé + full contact cluster + links out); detail Pages live under `pages/` (e.g. `pages/stack.md`, `pages/journey.md`, `pages/projects.md`, `pages/toolbox.md`), each an aggregated view of the same `data/`. Pages are a first-class generation target alongside SVG views, rendered for FR + EN (`pages/en/*`) with the same dual-palette `<picture>` mechanism. See [ADR-008](docs/adr/0008-in-repo-multipage.md).

---

## Internationalization (i18n)

The **narrative fields** (titles, short descriptions, pitch, prose) are entered in FR in `data/*.json` and **translated automatically into EN by DeepL** at pre-commit. Each i18n field has the form `{ "fr": "..." }` at entry; the EN translation is stored in a **committed cache** under `data/i18n-cache/<entity>/<id>.<field>.en.json`.

The cache carries `{ fr_hash, en, manual: bool, reviewed: bool }`. If `manual: true`, the hook never touches `en`. If `reviewed: false`, the hook shows a warning but the generation of `README.en.md` proceeds.

The **factual fields** (id, name, dates, tech labels, URLs, score) are not i18n — plain string/number.

See [ADR-004](docs/adr/0004-i18n-bilingual-readme.md).

## Adaptive display

The SVGs are generated in **two variants**, **light-first**: the **light** variant is primary and lives in the **root** dir (`assets/svg/*`), served by the `<img>` fallback; the **dark** variant lives in `assets/svg/dark/*` and is the `prefers-color-scheme: dark` override. The README uses `<picture>` so the visitor's GitHub preference picks the right one, but **light is the default**.

```md
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/hero.svg" alt="...">
</picture>
```

See [ADR-003](docs/adr/0003-data-schema-collections-and-derived-views.md).

## Workflow

The quality gates run through the **pre-commit framework** (`.pre-commit-config.yaml`, see [ADR-005](docs/adr/0005-quality-gates-ci-branch-protection.md)) — replacing the old shell hook.

1. Edit one or more files in `data/`
2. `git add data/...`
3. `git commit` — the **pre-commit** stage validates the schemas + the referential integrity (`validate_data.py`), regenerates `assets/svg/*.svg` + `README.md` (`generate.py`), validates the artifacts (`validate.py`), and runs ruff / bandit / gitleaks / cspell / file hygiene. If the generation modifies files, the commit fails: re-stage then re-commit (standard pre-commit flow).
4. `git push` — the **pre-push** stage runs `pytest --cov` (≥ 90 % engine) + `pip-audit`.

This guarantees that **the versioned SVGs/README are always in sync with the data** at the same commit, and that everything passes the gates before being pushed.

---

## Invariants

- A **factual value** (e.g. "Python 3.11+ Expert since 2023") appears in **exactly one** data file — never replicated.
- The **tech and domain IDs** are stable over time: an ID is never reused for something else, and the version is not introduced into the root ID (otherwise the references break at the slightest upgrade).
- The generated files (`assets/svg/`, `README.md`) are **committable** but **never edited by hand** — any change goes through the data or the templates.
