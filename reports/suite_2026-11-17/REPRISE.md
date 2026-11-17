# Suite du 2026-11-17 — reprise

Décisions de 👤 (2026-11-17) : chantier 47 en **mm, champ dans le panneau DESIGN** (`substrate_thickness_mm`, vide = 1 mm) ;
périmètre **DESIGN seul** (METAL, RE, STRAT à part) ; recherche locale finale : **mesurer d'abord**. Ordre de 👤 : « commit push ».

| # | tâche | état |
|---|---|---|
| 1 | juge de paix à `e6fdac67`, deux règles de classement | fait : même gagnant, règle gardée, [bilan](classement_recherche_locale.md) |
| 2 | gradient DESIGN, face arrière nue : branche avant seule (14,6 % du coût à k = 0, signe faux à k = 1e-4) | corrigé `16b33d7d`, test rouge avant, [preuve](preuves/p_back_bare_gradient.txt) |
| 3 | C47 (1/3) : paramètre dans les entrées DESIGN | `2800a0a3`, `c1_diff` 9 172 au bit |
| 4 | C47 (2/3) : de la configuration aux noyaux (13 fichiers) | `23512693`, `c1_diff` 9 172 au bit, oracle 1 214 |
| 5 | C47 (3/3) : champ de l'interface DESIGN | `a7d4eba6`, test rouge avant |
| 6 | base de mutation de `certus_substrate_absorption.py` (42 → 56 fautes) | `d2207653` : un survivant nouveau tué par un test (0,5 mm) |
| 7 | validation complète, puis push sur ordre de 👤 | faite (ETAT §0) ; push |

Hors périmètre, laissés : `calculate_RT_vectorized_real_HL` (STRAT) ; préchauffage de `_certus_physics_impl.py` ; la branche RE de
l'évaluation spectrale (1 mm).

## Après-midi (ordre de 👤 : « continue en autonomie les 47, 34 et 44 », décisions déléguées)

| chantier | état |
|---|---|
| 43 | `ui` à 10 workers : 9:53 → 5:38–5:52 ([bilan](../chantier43_2026-11-17/bilan.md)) |
| 40 | TMM oblique contre `tmm` 0.2.0 : 4,3e-15 ([bilan](../tmm_tiers_2026-11-15/bilan.md)) |
| 39 | exécutable reconstruit, 11/11 modules, commit embarqué ([bilan](../chantier39_2026-11-17/bilan.md)) |
| 47 | spectre affiché de DESIGN corrigé ; RE en 3 commits ; METAL simple sans objet ; STRAT archivé sans objet (👤) |
| 34 | non reproduit sur cache vierge ; noyaux inchangés ([bilan](../chantier34_2026-11-17/bilan.md)) |
| 44 | R2 et R10 sans effet sur l'ordre ; rien n'est activé ([bilan](../chantier44_etape3_2026-11-17/bilan.md)) |

Erreurs de la journée, corrigées : le spec gelé poussé avec 7 tests rouges (`a3513987`), un plan figé ajouté au suivi qui faisait échouer `coherence_md` (`efd60e72`), deux fichiers longs allongés (`08e3bb2c`).

## Nuit du 17 au 18 (ordre de 👤 : « autonomie complète cette nuit »)

Décisions de 👤 : 05 pôle IR de catalogue (option inactive) ; 21 session dédiée ; 18 feu vert (18a puis 18b) ; pousser si
`VALIDATION=GO` et `PUBLICATION=GO`, puis clone `C:\dev\certus1111` (48).

| # | tâche | état |
|---|---|---|
| 1 | 19 : audits d'appels `tests/oracle`, `tests/unit`, quatre arêtes ajoutées | fait, [bilan](../chantier19_2026-11-17/bilan.md) |
| 2 | 05 : temps et convergence Sellmeier | mesuré, [bilan](../chantier05_2026-11-17/bilan.md) |
| 3 | 21 : profil SPLINE | mesuré, [bilan](../chantier21_2026-11-17/bilan.md) |
| 4 | validation complète sur `88e854dd` | GO (unit relancé, échec passager de `git ls-files`) |
| 5 | nettoyage des `.md` vivants (ordre de 👤) | fait |
| 6 | push, clone `C:\dev\certus1111`, `preflight` | à faire |
| 7 | session dédiée du 21 | à faire |
| 8 | 05 : option pôle IR, C1 au bit, mesures BK7 et données propres | à faire |
| 9 | 18a SMOOTHER, puis 18b SUBSTRATE | à faire |
