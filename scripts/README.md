# scripts/ — génération data-driven

Le README et les SVG sont **générés** depuis `data/*.json` via Jinja2.

## Installation

```bash
pip install -r scripts/requirements.txt
bash scripts/install-hook.sh         # installe le pre-commit hook
```

## Usage manuel

```bash
python3 scripts/generate.py          # régénère tous les SVG + README depuis data/
```

## Workflow

1. Édite un ou plusieurs fichiers dans `data/`
2. `git add data/...` (les changements de data)
3. `git commit` — le pre-commit hook détecte le changement dans `data/`, lance `generate.py`, ajoute les SVG et le README régénérés au commit
4. Tout ce qui est versionné reste cohérent : la data ET ses dérivés sont au même commit

## Structure

```
scripts/
├── generate.py              # entrée — charge data/*.json, rend les templates
├── install-hook.sh          # installe .git/hooks/pre-commit
├── requirements.txt         # jinja2
├── README.md                # ce fichier
└── templates/
    ├── _terminal_window.svg.jinja   # macro partagée (fenêtre macOS)
    ├── divider_ecg.svg.jinja
    ├── whoami.svg.jinja
    ├── id_card.svg.jinja
    ├── timeline.svg.jinja
    ├── parcours.svg.jinja
    ├── featured.svg.jinja
    ├── stack.svg.jinja              # template générique pour 7 stacks (paramétré par domain)
    ├── hero_desk.svg.jinja
    ├── map.svg.jinja
    └── README.md.jinja
```

## Helpers disponibles dans les templates

`generate.py` expose ces helpers dans tous les templates :

- `profile`, `domains`, `techs`, `timeline`, `projects`, `theme`, `content` — les 7 JSON chargés
- `techs_by_domain(domain_id)` → liste des techs d'un domain
- `domain_by_id(domain_id)` → dict du domain
- `tech_by_id(tech_id)` → dict du tech (id racine OU id de version)
- `projects_by_category(category)` → liste des projets d'une catégorie
- `projects_highlighted()` → liste des projets marqués `highlight: true`
- `domains_in_id_card()` → domains avec `show_in_id_card: true`, triés par order
- `level_color(level)` → nom de couleur Encre & Soleil pour un niveau de compétence
- `level_label(level)` → label humain pour un niveau

## Voir aussi

- [`/CONTEXT.md`](../CONTEXT.md) — glossaire des concepts
- [`/docs/adr/0001-data-driven-svg-generation.md`](../docs/adr/0001-data-driven-svg-generation.md) — décision architecture
