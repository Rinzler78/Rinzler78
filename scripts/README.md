# scripts/ — data-driven generation

The README and the SVGs are **generated** from `data/*.json` via Jinja2. Hours,
levels and periods are **read** from the committed activity aggregates
(`data/activity/aggregates.json`, ADR-013, ADR-018); the generator derives none
of them, and its only reference date is the aggregates' `activity_as_of`.

## Installation

```bash
make setup        # uv pip install -e ".[dev]" + pre-commit install (pre-commit + pre-push)
```

## Manual usage

```bash
python3 scripts/generate.py        # regenerate all SVGs + README from data/
python3 scripts/validate_data.py   # validate schemas + referential integrity
python3 scripts/validate.py        # validate SVG well-formedness + README refs
python -m scripts.claims check     # claim markers match the attested lock (ADR-014)
make check                         # validate-data + generate + lint + format + security + coverage
```

## Pipeline

```
private timeline + commit evidence        (author's machine only)
   │  scripts/activity/hours.py
   ▼
data/activity/aggregates.json + data/*.json   (committed)
   │  DataLoader  (load_collection + JSON Schema + referential integrity,
   │               every aggregate tech catalogued under the same domain)
   ▼
ViewBuilder      (build_skills: catalogue + hours/level/period, recency order;
   │              build_domain_year_hours: by_month domains → per-year series)
   ▼
generate.py      (Jinja2)  →  assets/svg/*.svg + README.md + pages/
```

## Workflow

1. Edit one or more files in `data/`
2. `git add data/...`
3. `git commit` — the **pre-commit** hook (framework) validates the schemas, regenerates
   SVG + README, validates the artifacts. If the generation modifies files, the
   commit fails: re-stage then re-commit (standard pre-commit flow).
4. `git push` — the **pre-push** stage runs `pytest --cov` (≥ 90 % engine) + `pip-audit`.

## Modules

```
scripts/
├── data_loader.py       # load_collection + schema + referential/aggregates integrity
├── view_builder.py      # build_skills, build_domain_year_hours (from the aggregates)
├── captions.py          # chart conclusions: figures computed per language, never typed
├── generate.py          # entry point — loads data, enriches, renders templates
├── validate_data.py     # CLI: schemas + referential integrity
├── validate.py          # CLI: SVG well-formedness + README refs
├── claims.py            # CLI: claim markers vs data/claims.lock.json (ADR-014)
├── requirements.txt     # generation deps (jinja2, defusedxml, jsonschema)
└── templates/
    ├── _panel.svg.jinja         # shared macros (panel, bar, chip, stat, status_dot)
    ├── header.svg.jinja
    ├── stack_summary.svg.jinja
    ├── activity_stats.svg.jinja
    ├── timeline_mini.svg.jinja
    ├── featured_projects.svg.jinja
    ├── modes.svg.jinja
    ├── map.svg.jinja
    └── README.md.jinja
```

## Claims registry (ADR-014)

A statement that needs evidence (an award, a client, a figure of impact) is
published only if the author holds the proof. The proof lives in a **private**
registry outside this repository; the repository only carries claim identifiers
and a lock file of hashes.

**Marker.** In the generated markdown (`README.md`, `README.en.md`, `pages/**/*.md`)
a claim is wrapped in two HTML comments, invisible on GitHub:

```markdown
<!-- claim:award-2017 -->The product whose apps I built won an award in 2017.<!-- /claim -->
```

`scripts.claims.mark(claim_id, wording)` produces this form. Identifiers are
lowercase letters, digits and hyphens. Markers cannot nest; an unclosed, stray
or malformed marker is an error, never silently ignored.

**Wording and hash.** The text between the markers is the public wording. It is
hashed (SHA-256) after decoding HTML entities, Unicode NFC and collapsing
whitespace, so re-wrapping a template is not a rewording; markdown emphasis is
kept. Each language is locked separately: `README.en.md` and `pages/en/` are
English, every other page is French. Rewording either language needs a new
attestation.

**Lock file** `data/claims.lock.json`, committed:

```json
{"version": 1, "claims": {"award-2017": {"attested": "2026-09-26",
  "wording_sha256": {"en": "<sha256>", "fr": "<sha256>"}}}}
```

Nothing else crosses into the repository: no evidence kind, no pointer, no
wording text. Registry entries that no page uses are not written either.

**Private registry** `$PROFILE_PRIVATE_DIR/claims.json` (never committed, no
default path):

```json
{"version": 1, "claims": {"award-2017": {
  "wording": {"fr": "…", "en": "…"},
  "evidence_kind": "public_source | measured | private_attestation | author_statement",
  "scope": "career | impact  (author_statement only; impact wordings carry \"(selon l'auteur)\" / \"(per the author)\")",
  "pointer": "where the evidence is",
  "attested": "YYYY-MM-DD"}}}
```

**Modes.**

| Command | Where | Fails when |
|---|---|---|
| `make claims` (`python -m scripts.claims check`) | pre-commit, CI, anywhere | a marker is not in the lock, a language is not locked, or the wording hash differs. A lock entry no page uses is a **warning** only (it attests an unpublished wording; the next lock run prunes it). |
| `make claims-lock` (`python -m scripts.claims lock`) | the author's machine | `PROFILE_PRIVATE_DIR` unset, registry missing or malformed, a marker without a registry entry, evidence incomplete (kind, pointer, ISO date, both wordings), or the page wording differs from the registry wording. |

Publishing a new claim: add the registry entry, add the marker through the
data/templates, `make generate`, `make claims-lock`, commit the pages and the lock.

## Hours aggregates (ADR-013)

`python -m scripts.activity.hours --out data/activity/aggregates.json` turns the
private timeline and commit evidence into the committed aggregates. It runs on
the author's machine only: it reads `$PROFILE_PRIVATE_DIR/timeline.json`
(the last period may be open, `end: null`, and `as_of` may be omitted: the
timeline then runs to the month of the latest evidence day),
`evidence.json` (collector output) and `repo-classes.json` (every repository key
mapped to `{"context": "pro" | "personal", "source": <timeline source id>}`;
unclassified repositories count as personal).

The collector (`python -m scripts.activity.evidence`, vocabulary v2) gives
each file the techs of its language, path rules and line signatures, plus
those of its nearest enclosing project file (`.csproj`, `packages.config`,
`build.gradle`, `package.json`, `pyproject.toml`): a file of a Xamarin.iOS
project counts for xamarin and ios as well as C#. Project rules can be scoped
to some files (MVVM frameworks: views and view models). A project holding the Model / View / ViewModel triad counts those
layers for mvvm. Vocabulary v3 adds behavior rules: a file both exposing
commands and raising PropertyChanged, a class generic over a Page type, or a
model raising PropertyChanged is a ViewModel whatever its name, and so is any
class deriving from one (resolved across the tree). Vocabulary v4 counts mvvm
at project level: a project defining a ViewModel, referencing an MVVM
framework, or referencing (`ProjectReference`, shared-project `Import`) such a
project counts its whole presentation layer (`presentation`: pages, views,
controls, page controllers, view models, bindable models, converters,
renderers) for mvvm, not its services or platform glue. References into
submodules resolve through a registry built from every repository's HEAD
before the walk;
cross-platform-architecture counts only files defining the platform
abstraction (an interface implemented in both an iOS and an Android project,
`DependencyService.Register`, `[assembly: Dependency/ExportRenderer]`,
platform `#if` lines, multi-target or
shared project files); in repositories holding a mobile project, scripts and
pipeline steps that publish (upload, store, TestFlight, App Center) count for
mobile-release. Vocabulary v5 (ADR-018): building alone is not a skill;
signing and provisioning properties, fastlane and store metadata count for
mobile-release; toolchain files (CMake, Make, NDK sections, `.vcxproj`
platform lines, per-OS/arch scripts, `GOOS`/`--target`/`-march`) count for
cross-compilation-toolchains. A repository whose product is a container image
(a root Dockerfile or compose file, and a path naming docker/node/devcontainer
or a tree made mostly of image support files) counts every file for docker;
elsewhere only Dockerfile, compose and `.devcontainer` files do. A `.h` header is
Objective-C when its directory or build root holds `.m`/`.mm` files. Days
also record `test_only_commits`.

The collector keeps only repositories
owned by the author or by a company he worked for: `$PROFILE_PRIVATE_DIR/owners.json`
lists allowed key prefixes (`{"allow": ["github.com/<owner>/", "local:"]}`);
other repositories are dropped before deduplication and listed in
`summary.excluded_repos` with their number of own commits.

**Allocation (file share).**

- A tech receives the hours times the share of analyzed files touching it
  (`files` and `file_counts` per evidence day). A C# file calling a BLE API
  counts for both; each file has one language, so languages sum to about 1 and
  no tech exceeds its period's budget. Context totals are additive; tech and
  domain totals are not. A domain sums its techs' shares, capped at 1.
- Professional hours (calendar weekdays) are split by timeline source. A
  source's month uses the file counts summed over that source's commit days of
  the month; a month without a commit uses the counts over the whole period,
  restricted to techs already seen in an own commit by then (hours with
  nothing left count for the context, not for a tech).
- Declared periods (no trace: before 2014, a client whose commits are not
  collected) come from the private `$PROFILE_PRIVATE_DIR/declared.json`,
  written by the author: per source and month range (`end: null` runs to
  `as_of`), explicit `languages` shares summing to 1 and `tiers` for other
  techs (primary 0.70, secondary 0.35, incident 0.10). Periods covering the
  same month share its hours equally (a mission overlap; a
  `within_study_budget` project takes half of the study months it covers).
  `pro_hours_per_weekday` overrides the context budget for those months, in
  `hours.py` (the timeline keeps its budgets). Hours are flagged `declared`.
- `overlays` declare a tech (AI-assisted development, Docker, TDD...) as a
  tier share (full 1.00, primary 0.70, secondary 0.35, incident 0.10) of the
  hours in scope during listed months: `personal` (commit days), `pro`
  (professional and study hours) or `all`, per overlay or per period; a period
  with a `source` applies to that source's professional hours only. The
  measured share wins when higher; `measured_from` ends a declaration.
- Last fallback, for a month with neither evidence nor a declared period:
  the tiers of `data/experiences.json` (`SOURCE_EXPERIENCES` maps timeline ids
  to experience ids; declared languages share 100 % pro rata). The CLI lists
  every such month.
- Personal hours: the period's personal budget on each commit day with at least
  one personal repository, with that day's file shares. A professional
  repository outside its source's period counts as personal.
- `tech_map.json` maps collector ids to catalogue ids, gives each catalogue id
  a kind (language, platform, domain) and a domain, and excludes Git. An
  unknown collector id is an error: extend the map, never skip it.

**Levels (ADR-018).** `data/activity/evidence_levels.json` (committed) maps a
tech to a level granted by an attested achievement and its claim id
(`{"version": 1, "levels": {tech: {"level", "claim"}}}`), never the evidence
itself. Each tech gets `hours_level` (the ADR-013 convention),
`evidence_level`, `display_level`, `level_source` (`hours` | `evidence`),
`claim` and `pending_claim`. An evidence level lifts `display_level` above
`hours_level` only when its claim is in `data/claims.lock.json`; until then it
grants nothing, `level_source` stays `hours` and the claim appears as
`pending_claim`. The CLI fails when the committed levels differ from the
author's `evidence_levels` in `declared.json`, and lists pending claims (not a
failure).

**Output** `data/activity/aggregates.json` (`version` 3: ADR-018 level fields,
then the commit calendar): `version`, `activity_as_of` (last evidence day),
`coverage` (commit days, public days, public share), `context_totals`, `levels`,
`by_month` (`context`, `techs`, `domains`), `calendar` (every commit day:
`context` — `pro` when a repository of the period's source was touched, `study`
in a study period, else `personal` — and `intensity`, the 1–4 quartile of the
day's analyzed files among all days), `techs` (`hours`, `display_hours` rounded
down, `first`, `last`, `declared_share`, `kind`, `domain`, and the level fields
above) and `notes`. No repository, identity, private source id or per-day count
is written.

**Sanity checks** (the file is not written when one fails): no tech starts
before its first commit or declared period, nor before its release month
(`RELEASE_MONTHS`); no tech exceeds a period's budget.

## Helpers available in the templates

`generate.py` exposes in all templates: `profile`, `domains`, `techs` (the
whole catalogue, enriched), `skills` (the techs with a displayed level),
`experiences`, `timeline`, `projects`, `theme`, `content`, `aggregates`,
`as_of` / `as_of_year` (from `activity_as_of`), plus:

- `techs_by_domain(domain_id)` → skill lines of a domain, by recency then hours
- `domain_by_id(domain_id)` / `tech_by_id(tech_id)` (root id OR version)
- `projects_highlighted()` → `highlight: true` projects (showcase)
- `domains_in_id_card()` → `show_in_id_card: true` domains, sorted by order
- `level_color(level)` / `level_label(level)` → color / label for the 4 levels

Each tech carries: `hours`, `display_hours`, `level` (the aggregates'
`display_level`, `None` below the working threshold or for a tool such as
Git), `level_source`, `claim`, `first`, `last`, `since` and `until` (`None`
while used in the year of `activity_as_of`).

## See also

- [`/CONTEXT.md`](../CONTEXT.md) — glossary of concepts
- [`/docs/adr/`](../docs/adr/) — decisions (001 generation, 005 quality gates, 013 hours, 016 page content and dates, 018 levels)
