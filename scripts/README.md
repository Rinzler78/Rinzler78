# scripts/ — génération data-driven

Le README et les SVG sont **générés** depuis `data/*.json` via Jinja2. Le score
et les niveaux d'expertise sont **dérivés** des heures d'exposition (ADR-006).

## Installation

```bash
make setup        # uv pip install -e ".[dev]" + pre-commit install (pre-commit + pre-push)
```

## Usage manuel

```bash
python3 scripts/generate.py        # régénère tous les SVG + README depuis data/
python3 scripts/validate_data.py   # valide schemas + intégrité référentielle
python3 scripts/validate.py        # valide SVG well-formed + refs README
make check                         # validate-data + generate + lint + format + security + coverage
```

## Pipeline

```
data/*.json
   │  DataLoader  (load_collection + JSON Schema + intégrité référentielle)
   ▼
HoursCalculator  (heures d'exposition par tech : experiences ×1880 + projects ×9)
   ▼
ScoreEngine      (peak = 99·(1−e^(−h/3000)) ; current = decay(peak, oubli))
   ▼
ViewBuilder      (build_skills : techs enrichis hours/since/until/score/level)
   ▼
generate.py      (Jinja2)  →  assets/svg/*.svg + README.md
```

## Workflow

1. Édite un ou plusieurs fichiers dans `data/`
2. `git add data/...`
3. `git commit` — le hook **pre-commit** (framework) valide les schemas, régénère
   SVG + README, valide les artefacts. Si la génération modifie des fichiers, le
   commit échoue : re-stage puis re-commit (flux pre-commit standard).
4. `git push` — le stage **pre-push** lance `pytest --cov` (≥ 90 % moteur) + `pip-audit`.

## Modules

```
scripts/
├── data_loader.py       # load_collection + schema + check_referential_integrity
├── hours_calculator.py  # compute_tech_hours (tiers concurrents, since/until dérivés)
├── score_engine.py      # compute_skill (peak/decay, max vs current, overrides)
├── view_builder.py      # build_skills (enrichit techs pour les templates)
├── generate.py          # entrée — charge data, enrichit, rend les templates
├── validate_data.py     # CLI : schemas + intégrité référentielle
├── validate.py          # CLI : SVG well-formed + refs README
├── requirements.txt     # deps génération (jinja2, defusedxml, jsonschema)
└── templates/
    ├── _panel.svg.jinja         # macros partagées (panel, bar, chip, stat, status_dot)
    ├── header.svg.jinja
    ├── stack_summary.svg.jinja
    ├── activity_stats.svg.jinja
    ├── timeline_mini.svg.jinja
    ├── featured_projects.svg.jinja
    ├── modes.svg.jinja
    ├── map.svg.jinja
    └── README.md.jinja
```

## Helpers disponibles dans les templates

`generate.py` expose dans tous les templates : `profile`, `domains`, `techs`
(enrichis en Skills), `experiences`, `timeline`, `projects`, `theme`, `content`,
plus :

- `techs_by_domain(domain_id)` → Skills d'un domain
- `domain_by_id(domain_id)` / `tech_by_id(tech_id)` (id racine OU version)
- `projects_highlighted()` → projets `highlight: true` (vitrine)
- `domains_in_id_card()` → domains `show_in_id_card: true`, triés par order
- `level_color(level)` / `level_label(level)` → couleur / label pour les 5 niveaux

Chaque Skill porte : `since`, `until`, `score_max`, `level_max`, `score_current`,
`level_current` (ADR-006).

## Voir aussi

- [`/CONTEXT.md`](../CONTEXT.md) — glossaire des concepts
- [`/docs/adr/`](../docs/adr/) — décisions (001 génération, 006 modèle heures, 005 quality gates)
