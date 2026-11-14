# Tri du registre supprimé — 2026-11-14, nuit (chantier 36)

Source : `git show b6fb1939^:docs/AUDITS.md`, état au 2026-10-26, 69 entrées « ouvert » ou « à reproduire ».
Méthode : recherche dans le code de `20b979d9` du symptôme ou du symbole nommé. **Présent** = la trace citée existe
encore (le défaut n'est pas mesuré) ; **corrigé** = preuve citée ; **non vérifié** = pas regardé cette nuit.

## Calcul

| id | verdict | preuve |
|---|---|---|
| C20 (D113) | corrigé `78515573` | oracle `test_absorbing_front_cost_matches_the_reference.py` |
| ALG-03 | corrigé `4d634756` | `test_design_oblique_refinement_sees_the_dense_grid.py` |
| C13 (D112) | corrigé le 14 novembre | `certus_index_objectives.py` : `dk5 = 0.0` au centre |
| C18 (D111) | parade en place, cause ouverte | `cache=False` sur `calc_spectrum_front`, `calc_spectrum_full`, `compute_batch_rmse` |
| ALG-13 | présent | `run_coord_descent_5cycles` ne lit aucun drapeau d'arrêt |
| ALG-20 | présent | `optim_bounds_thickness_global` : `max(1.2·λ0/(4·n4), 1.2·ep0)` |
| C06/C07 (D108, D109) | présent ; décision de 👤 (`ETAT.md` §5) | `get_nk_from_spline` ne teste aucun NaN ; aucun refus d'épaisseur négative |
| C21/C22 (D114) | non vérifié ; décision de 👤 (`ETAT.md` §5) | — |
| C23–C28 (D116) | non vérifié ; le dernier bit selon l'historique est éclairci au [bilan §6](bilan.md) | — |
| C29 (D115) | non vérifié | `xyz_to_lab` est testé par trois fichiers ; la survie des mutants n'a pas été remesurée |
| ALG-01, ALG-21, ALG-22 | non vérifié | — |
| IDX-01, STR-01 | décision de 👤 | — |

## Interface

| id | verdict | preuve |
|---|---|---|
| UX-24 | présent | la palette annonce `Ctrl+R` pour `run.optimize` |
| UX-26 | présent | `_on_recent_config_selected` journalise et n'ouvre rien |
| UX-27 | présent | `calculationation` : 13 occurrences |
| UX-06 | présent | `color="black"` : 5 occurrences |
| UX-07 | présent, assumé pour RE | `Ctrl+E` = Évaluer (commentaire de `certus_re_layout_mixin.py`) |
| UX-22 | probablement présent | `DualStageProgressWidget` n'a pas `apply_progress_snapshot` ; l'appel de RE est sous `except NUMERICAL_FAULT_EXCEPTIONS` |
| UX-16, UX-34, UX-40, UX-44, UX-47, UX-49, UX-53 | présent | la trace citée par le registre existe encore |
| autres UX (40 environ) | non vérifié | relevant du périmètre UI des chantiers 16 et 18 |

## Divers

| id | verdict | preuve |
|---|---|---|
| C14 | en partie | trois `.tmp` suivis sous `reports/STRAT_Rate_joint_refinement_2026-10-13*` |
| C31 | présent | `hashlib.sha1` dans `scripts/lint_ns_snapshot.py` (empreinte, pas de sécurité) |
| C10/C30 (D110) | décision de 👤 (`ETAT.md` §5) | — |
