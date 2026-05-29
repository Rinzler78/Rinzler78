# ADR-006 — Modèle d'expertise basé sur les heures (max vs actuelle)

- **Statut** : Accepted
- **Date** : 2026-05-29
- **Supersede** : la **formule** d'[ADR-002](0002-tech-score-derivation.md) (base années + versions + projets + centralité + depth). Les paliers (5 niveaux) et le mécanisme d'override d'ADR-002 sont **conservés**.

## Contexte

La formule additive d'ADR-002, même amendée du facteur `depth`, restait un assemblage de proxies (« combien j'ai bossé »). Trois passes de validation sur les 41 techs réelles ont montré qu'elle ne capturait ni l'**expertise privée** (missions client invisibles sur GitHub), ni les **outils ambiants** (git/docker/AI-tooling jamais « le sujet » mais omniprésents), ni la **distinction entre le pic atteint et ce qu'il en reste aujourd'hui**.

Boris a formulé le bon modèle : estimer un **nombre d'heures** par sujet, en tirer une **expertise max** (le pic, absolu, ne baisse jamais), puis une **expertise actuelle** = max après une **courbe d'oubli** dont la vitesse dépend du niveau atteint et qui ne retombe jamais à zéro (il reste toujours des traces).

## Décision

### 1. Les heures sont la seule donnée d'entrée du score

Deux sources, agrégées par `HoursCalculator` :

- **Experience** (emploi, études, mission, compétition) — `data/experiences.json` :
  `hours = span_années × HEURES_PAR_AN`, `HEURES_PAR_AN = 1880` (40 h × 47 sem). Les études comptent **temps plein** (1880).
- **Project** perso — `data/projects.json` :
  `hours = jours_actifs × HEURES_PAR_JOUR_PERSO`, `HEURES_PAR_JOUR_PERSO = 9` (journée perso type 8h–18h −1h pause). `jours_actifs` = nombre de jours avec commits (dérivé de GitHub, stocké et rafraîchissable).

### 2. Allocation par tiers concurrents (heures d'exposition, cumulables)

Chaque source porte **une** map `tech_weights : {tech_id: tier}`. Un tier est une **affirmation factuelle** (« sur ce travail, cette tech était primaire / secondaire / incidente »), pas une décimale devinée.

Chaque tech reçoit `fraction(tier) × source_hours`, **cumulable et non normalisée** :

| tier | fraction | sens |
|---|---|---|
| `primary` | 0.70 | en jeu sur l'essentiel de la période |
| `secondary` | 0.35 | en jeu sur une part significative |
| `incident` | 0.10 | touché ponctuellement |

**Pas de normalisation, pas de partage.** Sur un projet mêlant C#/.NET + Xamarin + Bluetooth, les trois sont utilisés **en même temps** : chacun reçoit `0.70 × source_hours`, pas un tiers. La somme des allocations d'une période peut donc dépasser ses heures — c'est correct : ce sont des **heures d'exposition** (la courbe d'oubli d'Ebbinghaus mesure la pratique, pas le temps exclusif). Utiliser Xamarin, c'est aussi pratiquer C#.

Les outils transverses (git, docker, Claude Code, github-actions) sont simplement des techs `secondary`/`primary` selon leur présence — pas une catégorie à part.

### 3. `since` / `until` sont dérivés des sources

- `since(tech)` = plus ancienne date de début parmi les sources qui l'utilisent.
- `until(tech)` = `null` si une source **courante** (end = null) l'utilise, sinon la plus récente date de fin.

Conséquence : une tech s'arrête automatiquement quand sa dernière période s'arrête — l'invariant temporel de Boris est implémenté structurellement, plus aucune saisie manuelle de `until`.

### 4. Expertise max et actuelle

```
total_hours(tech)  = Σ sources [ fraction(tier) × source_hours ]   # cumulable

peak    = 99 · (1 − exp(−total_hours / H0))          # H0 = 3000
t       = today.year − until.year                     # 0 si until est null (actif)
F       = α · peak                                    # plancher résiduel, α = 0.30
halflife(peak) = HL_MIN + (HL_MAX − HL_MIN)·(peak/100)   # 2 → 18 ans
λ       = ln(2) / halflife(peak)
current = F + (peak − F) · exp(−λ · t)
```

- **peak** (= expertise max) : absolu, monotone, ne baisse jamais. Rendements décroissants (la 1ʳᵉ heure apprend plus que la 10 000ᵉ ; ~6000 h ⇒ expert).
- **current** (= expertise actuelle) : ≤ peak, ≥ plancher `α·peak`. Décroît d'autant plus vite que le pic est bas (exploré = oubli rapide ; maîtrise profonde = oubli lent). Ne retombe jamais à 0.

### 5. Paliers (conservés d'ADR-002)

| Score | level |
|---|---|
| ≥ 85 | expert |
| 70–84 | advanced |
| 55–69 | professional |
| 35–54 | working |
| < 35 | explored |

Appliqués **deux fois** : `level_max` (sur peak) et `level_current` (sur current). Le view model `Skill` expose les deux paires (score + level).

### 6. Overrides (conservés)

`score_override` / `level_override` sur une tech remplacent la valeur **actuelle** calculée, avec le même contrôle de cohérence qu'ADR-002. `featured` redevient un simple flag d'affichage (sélection hero), **plus un input de score**.

### 7. Constantes

`HEURES_PAR_AN = 1880` · `HEURES_PAR_JOUR_PERSO = 9` · `H0 = 3000` · `α = 0.30` · `HL_MIN = 2 ans` · `HL_MAX = 18 ans` · tiers `primary 0.70 / secondary 0.35 / incident 0.10`. Tout changement de ces constantes nécessite une nouvelle ADR.

## Conséquences

### Positives

- Tout (heures, since, until, max, actuelle) **dérive** de sources factuelles — zéro chiffre saisi arbitrairement. Aligné avec la règle anti-gonflage.
- La couche **ambient** capture enfin l'AI-driven development et les outils transverses.
- **max vs actuelle** raconte la trajectoire embarqué→cloud→IA (un C++ pic advanced redescend professional ; un Windows CE working redescend explored).
- Corriger un score = éditer un **tier** dans un fichier data + relancer le moteur (déterministe). Plus de devinette.

### Négatives

- Modèle plus riche : plusieurs constantes, des heures d'exposition cumulables (non intuitives : la somme par période dépasse les heures réelles). Seul le *résultat* (les levels affichés) est public, donc la défendabilité tient au réalisme, pas à la simplicité.
- Dépend de la qualité des tiers et de l'estimation des heures de période. Les tiers sont des affirmations honnêtes mais subjectives ; le code (linguist/cloc) sert de cross-check là où il existe.
- `jours_actifs` perso dépend d'un refresh GitHub (workflow update-profile).
- Refonte de `ScoreEngine` (le modèle a changé) + nouveau module `HoursCalculator`. Les tests de la formule additive sont retirés.
