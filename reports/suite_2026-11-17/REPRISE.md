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
| 6 | base de mutation de `certus_substrate_absorption.py` (42 → 56 fautes) | pilote en cours |
| 7 | validation complète, puis push sur ordre de 👤 | à faire |

Hors périmètre, laissés : `calculate_RT_vectorized_real_HL` (STRAT) ; préchauffage de `_certus_physics_impl.py` ; la branche RE de
l'évaluation spectrale (1 mm).
