# 0001 — Architecture data-driven : JSON sources + Jinja2 + pre-commit hook

**Statut :** Accepted · 2026-05-26

## Contexte

Le README et les ~14 SVG du profil contenaient les mêmes faits dupliqués à plusieurs endroits (versions de techs, années d'adoption, descriptions de projets…). À chaque itération de design — changer la palette, le format d'un terminal, la disposition d'une section — toutes les copies devaient être maintenues en cohérence à la main. Le design est destiné à évoluer plusieurs fois ; les faits, rarement.

Le coût d'une refonte design était donc disproportionné au regard de la valeur ajoutée, et les divergences entre vues étaient probables à terme (`Python 3.11+` vs `Python 3.11` à deux endroits, par exemple).

## Décision

Séparer **data** (faits, change peu) et **présentation** (rendu, itère souvent) :

- Stocker les **faits** dans `data/*.json` — 7 fichiers correspondant à 7 concepts atomiques : `profile`, `domains`, `techs`, `timeline`, `projects`, `theme`, `content`. Aucune duplication entre fichiers ; les liens sont des références par `id`.
- Générer les **SVG et le README** via des templates Jinja2 (`scripts/templates/*.jinja`) qui consomment les JSON.
- Déclencher la régénération automatiquement via un **pre-commit hook git**. Les fichiers générés (`assets/svg/`, `README.md`) sont versionnés (pour que GitHub les serve sans étape CI) mais le hook garantit qu'ils restent en phase avec les data au moment du commit.

Convention IDs : **snake_case sans version pour la tech racine** (`csharp`), **versions imbriquées avec id complet** (`csharp_2_0`, `csharp_12`). Le référencement entre concepts est **hybride** : IDs pour les liens forts (timeline → techs, projects → techs), texte libre pour la narration uniquement.

## Alternatives écartées

- **README dynamique en client JS** : impossible, GitHub markdown n'exécute pas de JavaScript.
- **10 fichiers JSON par vue** (un fichier par SVG) : créait à nouveau de la redondance entre fichiers (les mêmes techs apparaîssent dans timeline, id-card, et stacks). Réfuté par l'utilisateur : « autant de JSON ne me semble pas correct ».
- **Un fichier monolithique `data.json`** : édition pénible, conflits git fréquents. Compromis avec 7 fichiers concepts.
- **f-strings ou DOM builder Python au lieu de Jinja2** : pas assez expressif pour les boucles imbriquées (techs × versions, timeline events × techs-added). Jinja2 est un dépendance triviale (`pip install jinja2`) qui simplifie nettement les templates.
- **GitHub Actions au lieu de pre-commit hook** : ajoute du délai entre push et rendu, et nécessite que la branche d'output soit poussée par un bot. Le pre-commit hook local garantit la synchronisation au moment du commit, sans aller-retour CI.
- **README pas généré, juste les SVG** : laisse les textes narratifs (modes d'intervention, easter eggs, prose) couplés à la structure markdown. Tout générer rend le `content.json` la source unique des textes éditables.

## Conséquences

**Positives**
- Une valeur factuelle apparaît dans un et un seul fichier.
- Refonte design = modif des templates Jinja2 + theme.json, sans toucher aux faits.
- Cohérence inter-vues garantie (un `update` de `dotnet.version` met à jour id-card, timeline, stack-backend, projects en un seul build).
- Réutilisable pour d'autres formats (CV PDF, page perso, JSON-resume) à partir des mêmes data.

**Négatives**
- Setup initial coûteux : ~1-2 h pour extraire les data, écrire `generate.py` et les templates.
- Dépendance Python + Jinja2 sur la machine de Boris (et sur tout autre contributeur).
- Le pre-commit hook ralentit chaque commit qui touche `data/` (de quelques secondes).
- Les fichiers générés doublent le nombre de fichiers versionnés. Mitigé par leur taille modeste (< 100 Ko total).

## Critères de réussite

- Régénération entièrement reproductible : `python scripts/generate.py` produit toujours la même sortie depuis les mêmes data.
- Pas de divergence entre data et SVG/README versionnés (le hook empêche ce cas).
- Une refonte de palette = un seul commit éditant `theme.json` (+ les SVG/README régénérés).
