# ADR-002 — Dérivation du score et du level d'une Tech

- **Statut** : Accepted
- **Date** : 2026-05-27
- **Supersede** : —
- **Lié à** : [ADR-001](0001-data-driven-svg-generation.md)

## Contexte

Le profil affiche un radar et des barres de compétences. Pour rester crédible et défendable publiquement, les niveaux affichés ne peuvent pas être des notes arbitraires (« C# 87/100 ») saisies à la main : c'est exactement le red flag « chiffres inventés » qu'on refuse.

Deux modèles ont été écartés :

1. **Note libre saisie** (Spec V1, `skill.score: 95`) — invérifiable, gonflable, non maintenable.
2. **3 paliers qualitatifs purs** (modèle d'origine du repo : `expert` / `intermediate` / `notions`) — robuste mais trop grossier : ne distingue pas « livré en prod » (Professional) de « bidouillé en proto » (Working/Explored).

## Décision

Le `score` et le `level` d'une Tech sont **dérivés** par le generator depuis les faits saisis dans `data/techs.json` et `data/projects.json`. Ils ne sont pas stockés.

### Faits saisis (techs.json)

- `since` — année de premier usage (**nullable** ; `null` = jamais réellement adoptée, ex. read-level)
- `until` — année de dernier usage si abandonnée (optionnel ; absent = encore actif)
- `versions[]` — liste des versions traversées (obligatoire, peut être vide)
- `depth` — profondeur d'usage en production, **0 à 3** (optionnel, défaut 0) — voir amendement ci-dessous
- `featured` — booléen, override commercial (optionnel)
- `level_override` — force le palier qualitatif (optionnel)
- `score_override` — force le score numérique (optionnel)

### Formule

```
années_actives  = (until ou aujourd'hui) − since   # 0 si since est null
récence_oubli   = max(0, aujourd'hui − (until ou aujourd'hui))   # 0 si since est null
nb_versions     = len(tech.versions)
nb_projets      = count(p ∈ projects.json où tech.id ∈ p.tech_ids)
nb_domains      = count(distinct p.domain pour ces projets)

base            = min(60, années_actives × 3)
versions_pts    = min(15, nb_versions × 3)
projets_pts     = min(15, nb_projets × 3)
centralité_pts  = min(10, max(0, nb_domains − 1) × 5)
depth_pts       = depth × 20                       # 0 / 20 / 40 / 60

raw             = base + versions_pts + projets_pts + centralité_pts + depth_pts
oubli           = récence_oubli × 6
bonus_featured  = 15 si featured else 0

score = clamp(0, 99, raw − oubli + bonus_featured)
```

### Le facteur `depth` (amendement post-migration, 2026-05-28)

La formule d'origine ne récompensait que les **preuves publiques** (projets GitHub, versions loggées, années). Or l'expertise réelle vient largement de **missions client privées** invisibles sur GitHub. Sur les 41 techs réelles, seules 2 (`csharp`, `dotnet`) atteignaient leur niveau réel ; `python`, `docker`, `asp-net-core` etc. tombaient en `explored` malgré une expertise prod.

`depth` corrige ce biais. C'est une **auto-évaluation factuelle** de la profondeur d'usage en production, pas un chiffre arbitraire :

| depth | Sens |
|---|---|
| 0 | Read-level, expérimental, jamais shippé (défaut) |
| 1 | Shippé ponctuellement, secondaire sur certaines missions |
| 2 | Utilisé régulièrement en production sur plusieurs missions |
| 3 | Expertise cœur, maîtrise profonde, outil primaire en prod depuis des années |

`depth` est **additif** (`+20` par niveau) et passe dans `raw`, donc la pénalité d'oubli le dégrade aussi (un `depth=3` abandonné depuis longtemps redescend correctement). `since: null` est désormais toléré (years_active = 0).

### Paliers

| Score | `level` |
|---|---|
| ≥ 85 | `expert` |
| 70–84 | `advanced` |
| 55–69 | `professional` |
| 35–54 | `working` |
| < 35 | `explored` |

### Règles d'override

- Si `score_override` est posé, il remplace le score calculé.
- Si `level_override` est posé, il remplace le level dérivé du score.
- Si les deux sont posés, ils doivent être cohérents (le `score_override` doit tomber dans la fourchette du `level_override`). Un test garantit cette cohérence.
- Un override ne masque jamais le score brut dans le code : les deux sont visibles dans le view model pour audit.

## Conséquences

### Positives

- Le score est **défendable** : on peut justifier chaque chiffre par la formule + les faits.
- L'évolution dans le temps est **automatique** : un an de plus → score recalculé sans saisie.
- Les overrides forcent à se demander « pourquoi la formule ne capture pas ce cas » → documentation implicite via `notes`.
- 5 paliers permettent de distinguer prod / proto / veille.

### Négatives

- La formule dépend de `projects.json` étant honnête : projets manquants → score sous-évalué → besoin d'override. Demande de la discipline.
- Les coefficients (3 pts/an, plafonds 60/15/15/10, pénalité 6/an oubli, bonus featured 15) sont des choix éditoriaux : un futur ajustement déplacera toutes les frontières. Tout changement de coefficients nécessite une nouvelle ADR.
- La formule ne capture pas l'**intensité** (mission temps plein vs side-project) : seul l'override le compense.
