# scripts/ — data-driven generation

The README and the SVGs are **generated** from `data/*.json` via Jinja2. The score
and the expertise levels are **derived** from the exposure hours (ADR-006).

## Installation

```bash
make setup        # uv pip install -e ".[dev]" + pre-commit install (pre-commit + pre-push)
```

## Manual usage

```bash
python3 scripts/generate.py        # regenerate all SVGs + README from data/
python3 scripts/validate_data.py   # validate schemas + referential integrity
python3 scripts/validate.py        # validate SVG well-formedness + README refs
make check                         # validate-data + generate + lint + format + security + coverage
```

## Pipeline

```
data/*.json
   │  DataLoader  (load_collection + JSON Schema + referential integrity)
   ▼
HoursCalculator  (exposure hours per tech: experiences ×1880 + projects ×9)
   ▼
ScoreEngine      (peak = 99·(1−e^(−h/3000)) ; current = decay(peak, gap))
   ▼
ViewBuilder      (build_skills: techs enriched with hours/since/until/score/level)
   ▼
generate.py      (Jinja2)  →  assets/svg/*.svg + README.md
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
├── data_loader.py       # load_collection + schema + check_referential_integrity
├── hours_calculator.py  # compute_tech_hours (concurrent tiers, derived since/until)
├── score_engine.py      # compute_skill (peak/decay, max vs current, overrides)
├── view_builder.py      # build_skills (enriches techs for the templates)
├── generate.py          # entry point — loads data, enriches, renders templates
├── validate_data.py     # CLI: schemas + referential integrity
├── validate.py          # CLI: SVG well-formedness + README refs
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

## Helpers available in the templates

`generate.py` exposes in all templates: `profile`, `domains`, `techs`
(enriched into Skills), `experiences`, `timeline`, `projects`, `theme`, `content`,
plus:

- `techs_by_domain(domain_id)` → Skills of a domain
- `domain_by_id(domain_id)` / `tech_by_id(tech_id)` (root id OR version)
- `projects_highlighted()` → `highlight: true` projects (showcase)
- `domains_in_id_card()` → `show_in_id_card: true` domains, sorted by order
- `level_color(level)` / `level_label(level)` → color / label for the 5 levels

Each Skill carries: `since`, `until`, `score_max`, `level_max`, `score_current`,
`level_current` (ADR-006).

## See also

- [`/CONTEXT.md`](../CONTEXT.md) — glossary of concepts
- [`/docs/adr/`](../docs/adr/) — decisions (001 generation, 006 hours model, 005 quality gates)
