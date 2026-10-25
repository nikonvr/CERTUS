# Audit des travaux du 2026-10-21 au 2026-10-25

Périmètre : les 128 commits de toutes les branches depuis le 2026-10-21. Méthode de [REGLES §12](../../docs/REGLES_reference.md) :
le diff correspond-il à la déclaration, la mesure se reproduit-elle, la conclusion suit-elle de la mesure. Une mesure n'a été
refaite que là où le tableau le dit ; ailleurs, le contrôle porte sur le rapport et ses fichiers bruts.

## 1. Deux lignes divergentes, réunies dans `claude/integration-2026-10-25`

Depuis `e774a120` (2026-10-21, 23 h 25), deux lignes ne s'étaient jamais rejointes :

| ligne | commits | contenu |
|---|---:|---|
| `gemini/2026-10-21` (arbre principal) | 62 | DESIGN (mémétique, relances, plafonds, problème de Tikhonravov 1996), design et stratégie Bonne Mère 90 couches sur silice, règles Rate de l'opérateur |
| `claude/2026-10-22` (contient `master` et `chatgpt/2026-10-22`) | 47 | A3, A4, A5, A8b, A11, A12, A13, garde de la recherche locale armée par défaut, ETAT condensé (67 → 24 Ko) |
| branches du 2026-10-25 | 4 | étape libre avant la conversion, registre ARGON (A15), E402 (A8a), protocole A5 |

Fusion : trois conflits (`certus_strat_local_search.py`, `certus_strat_workers_local_search.py`, `docs/ETAT.md`). L'étage garde
les deux lignes : garde, présélection et passe guidée de l'une, règles Rate et conversion de l'autre, et l'étape libre avant la
conversion, qui tourne sous la garde. Le protocole A5 du 2026-10-25 n'est pas fusionné : A5 était fait le 2026-10-24.
Validation complète de `3260c766` : GO (oracle 1 159, unit 5 710, ui 1 342, rest 321, performance 40) ; C1 non remesuré.

Conséquences :
- **Les mesures Bonne Mère 90 couches ont tourné sans la garde**, armée par défaut sur l'autre ligne depuis le 2026-10-23 : le
  STRAT intégré n'est pas celui qui les a produites (A16).
- `master` pointe `0c759aa2`, quatre commits derrière `claude/2026-10-22`, sans la ligne gemini ; `origin` n'a ni l'une ni l'autre.
- **A9 ne partirait pas** : `chain_A9.sh` refuse un code différent de son commit figé du 2026-10-17 (`code_frozen`, `sources_sha256.txt`).

## 2. Vérifications

| chantier | déclaré | contrôle | verdict |
|---|---|---|---|
| Bonne Mère 90 c., plan libre et règle du saphir | 0,2046 et 0,2608 nm au holdout | `index_share_log.txt`, `native_final_holdout.json` | confirmé |
| `rate_rules_final_only` natif | 0,3355 nm, 1 arrêt | `native_final_holdout.json` ; artefact `git_dirty: true` sur `ea5c284a` | confirmé, sur arbre modifié |
| cause de l'écart natif / main | « écart probable » | la conversion partait du gagnant ELITE (73 Rate, 56 conversions) ; la main partait du plan libre après recherche locale (0,313 → 0,210 nm) | établie |
| étape libre avant la conversion (`5bba4396`) | — | mesurée le 2026-10-25 : 0,2655 nm au holdout, 1 arrêt, 16 Rate, graine 77, arbre modifié (A/B) | écart à la main : +29 % → +1,8 % ; une graine |
| A5, tours et budgets ELITE (2026-10-24) | référence 0,3967 nm, gains de 2 à 4 % | référence refaite le 2026-10-25 sur une autre ligne de code (`3f2564b4`, arbre propre) : 0,3967 nm | reproduit |
| A3, 99 couches C2 | médianes 0,549 puis 0,597 nm (+9 %) | bilans : écart entre graines ±17 % autour de la médiane | +9 % de médiane sur trois graines ne se distingue pas de la dispersion |
| A8b | plus aucune arête montante | `tests/architecture_debt.json` : 0 arête montante, 1 cycle | confirmé |
| A12, A13 (présélection) | refusés par leur règle écrite d'avance | `regle.md` présents, verdicts conformes aux tableaux | conforme, non remesuré |
| garde de la recherche locale | dix cas, armée par décision de 👤 le 2026-10-23 | `reports/STRAT_garde_2026-10-22/bilan.md` ; la décision n'est attestée que par le message de `25d76df9` | conforme |
| DESIGN, séparatrice 400–1200 nm | 0,000135 depuis l'exemple ; 8,6e-5 contre 1,77e-4 pour Tikhonravov | `bilan.md`, `tikhonravov/curve/curve.csv` | conforme ; le `README` disait « dès 30 couches » sous leur design, ses chiffres disent 28 (corrigé) |
| DESIGN sous erreurs de fabrication | limité par la tolérance | `curve.csv`, 0,1 % + 0,2 nm à 2σ : RMSE moyen au plus bas entre 22 et 28 couches (0,00219), 0,0031 à 34 | constat ajouté ; un run par nombre de couches |
| DESIGN, nouveaux défauts | mémétique, champion conforme, relances (décision de 👤) | ETAT §3 | tout résultat DESIGN d'avant le 2026-10-23 est PGLOBAL |
| A15, observations ARGON | — | `pass02.json` : en oblique, coût et gradient sur 2 points sur 135, RMSE rapporté 0,026 contre 0,175 sur la grille dense | reporté (ALG-03, ALG-13, UX-20) |
| A8a | — | E402 : deux modules faits ; 554 sur la branche de travail | en cours |
| validation | — | un sous-processus d'interface figé sous charge au premier passage, passé au rejeu | C32, à reproduire |

## 3. À trancher par 👤

1. Faire de `claude/integration-2026-10-25` la branche de travail, puis y amener `master`.
2. Le design publié de Tikhonravov et al. est versionné dans un dépôt public « avec l'autorisation des auteurs » : la conserver
   par écrit, ou retirer le fichier (CLAUDE.md §1).
3. A9 : refiger le protocole sur la branche de travail, puis donner ou non le GO.
4. Dossier : 2,5 Go le 2026-10-25, dont `reports/` 1,05 Go pour une limite de 1 Go et un worktree de session de 593 Mo.

## 4. Suite

A16 : remesurer `bm90final` avec l'étape libre sur la branche de travail (garde armée), graines 77 et 202, jugées sur le holdout
20261022201–203 contre 0,2608 nm.
