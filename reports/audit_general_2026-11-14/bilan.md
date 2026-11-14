# Audit général du projet — 2026-11-14, 20 h

Demandé par 👤. Objet : chercher des améliorations absentes de [la liste des chantiers](../../docs/CHANTIERS_RESTANTS.md),
après l'audit contradictoire de la reprise du chantier 19 et de cette liste.

Méthode : lecture et recherches (`git grep`, `git log`) sur `ac191592`, plus la relecture des résultats déjà produits
par le chantier 19 (`reports/selecteur_tests_2026-11-14/runs/`, non suivis à cette date). **Aucun test ni aucune mesure
de calcul n'a été lancé.** Un compte ci-dessous est le résultat d'une recherche ; « non vérifié » veut dire que je n'ai
pas regardé.

## 1. Ce qui est sain

| Point | Constat |
|---|---|
| Frontières de CLAUDE.md §8 | 0 import de PyQt6 et 0 import de `certus.ui` dans `certus/core`, `certus/physics`, `certus/domain` |
| Exceptions | 0 `except:` nu ; 226 `except Exception` dans `certus/` (138 dans `ui`, 4 dans `physics`), gardés par `tests/unit/test_no_broad_exception_is_swallowed_in_silence.py` |
| Dette visible | 0 `TODO`/`FIXME` dans `certus/` ; 16 `# noqa` ; 28 `type: ignore` |
| Tests | 668 fichiers de test, 115 738 lignes pour 177 000 lignes de `certus/` environ ; témoin du 19 : 9 327 tests passés |
| Chantier 07 | une seule définition de `_warmup_numba_thread_runner` ; démarrage à froid identique sur les cinq fenêtres |

## 2. Constats qui appellent un chantier

1. **Un test C1 échoue par intermittence (→ 34).** `test_the_slit_profile_is_inert_when_absent_or_zero` compare au
   bit (`np.array_equal`) deux appels de `update_run_states_kernel`, profil de fente absent et nul. Il échoue au
   premier passage sous charge et passe au rejeu isolé, à la validation de `de52e01c` comme au témoin du 19 sur
   `ac191592` ; il n'a pas échoué dans la suite complète du cas `infrared_center`. Le validateur le classe
   `ARTEFACT`. Cause non mesurée. Tant qu'elle est inconnue, « identique au bit » n'est pas établi sous charge, et les
   reprises 27 à 29 reposent sur cette identité.
2. **ALG-03 est ouvert et sans chantier (→ 35).** `docs/ETAT.md` §1 : « le mode oblique calcule sur 2 points au lieu
   de 135 ». Le bilan Q du 13 novembre le dit encore ouvert : la grille densifiée par
   `maybe_upgrade_grid_tikhonravov` ne reconstruit pas le précalcul câblé dans
   `_initialize_runtime_state_for_optimization`. Les deux fonctions existent ; je n'ai pas vérifié que le défaut se
   produit encore. C'est la classe d'erreur que CLAUDE.md redoute : un résultat faux qui a l'air juste.
3. **Le registre des défauts a disparu (→ 36).** D84, D111, D112, D113 et D116 sont cités « ouverts » par les audits
   du 14 novembre et par la liste (gel du 26). Aucun n'a de définition dans `docs/`, `certus/`, `tests/` ni
   `scripts/` ; ils ne vivent que dans d'anciens rapports. Il en va de même de C20, « gradient faux sur couches
   absorbantes, à corriger avant d'étendre quoi que ce soit » (A §4). Personne ne peut dire lesquels sont corrigés.
4. **Rien ne contrôle une publication avant qu'elle parte (→ 37).** `gitleaks` et `pip-audit` ne tournent qu'en CI.
   `master` a 93 commits d'avance sur `origin/master` : aucun n'est passé par la CI, ni sous Linux. Aucun script
   local ne vérifie secrets, métadonnées des classeurs et œuvres de tiers.
5. **Il reste des algorithmes dans `certus.ui` (→ 38).** Deux `scipy.optimize.minimize` avec leur fonction de coût
   et de gradient dans `certus/ui/certus_design_ui_optimization.py`. Même violation de CLAUDE.md §8 que celle levée par 21 (a).
6. **L'exécutable gelé a 657 commits de retard (→ 39).** Construit à `dbec2fc1` (2026-10-06). `pyproject.toml` porte
   la version `26.05.0`. Non vérifié : que les exports portent une version qui distingue l'état du code.
7. **Aucun recoupement par un code tiers (→ 40).** `tests/oracle/tmm_reference.py` est indépendant de
   `certus.physics`, mais écrit dans ce projet. Aucun test ne compare à un code externe, et `docs/ETAT.md` §1 note
   « validation externe : aucune ».
8. **Douze branches Dependabot en attente (→ 41)**, la plus ancienne du 2026-09-30, dont `pillow-13.0.0` et
   `setuptools-84.1.0`.
9. **30 scripts sur 106 ne sont cités nulle part hors `reports/` (→ 42).** Parmi eux, des outils qui appliquent une
   règle de CLAUDE.md : `check_inert_params.py` (C1), `check_param_effect.py` (§4, paramètre qui n'atteint pas le
   calcul), `probe_kernel_threads.py`, `narrow_broad_except.py`. Un outil que personne ne trouve ne sert pas.

## 3. Constats sans chantier nouveau

- **`docs/ETAT.md` §6** disait encore que les P1 concernent la co-conception ; corrigé avec la liste.
- **CI** : mypy et `bench_kernels` non bloquants, contrôles documentaires absents de `lint.yml` : déjà chez 👤
  (`docs/ETAT.md` §5, D110).
- **Couverture** : jamais mesurée (`--no-cov` partout, CI comprise). `scripts/mutation_pilot.py` existe et mesurerait
  mieux la force des tests ; coût machine élevé, non proposé tant que 34 à 36 sont ouverts.
- **107 marqueurs `skip`** dans `tests/` : non triés ; à regarder si un jour la suite doit prouver davantage.
- **Poids de l'interface** : 78 737 lignes sur 177 000, soit 44 % du code ; les chantiers 16 et 18 le traitent.

## 4. Ordre proposé

1. **34, 35, 36** : fiabilité du calcul ; une IA peut les mener seule, un à la fois (34 occupe la machine).
2. **37** avant la prochaine poussée, quelle qu'en soit la date.
3. **38**, puis le reste de la liste selon les décisions de 👤.
4. **39 à 42** : décisions de 👤 d'abord.

## 5. Validation

`VALIDATION=GO` le 2026-11-14 sur `376baef1`, branche `claude/claude-code-suije-bf4f1f`, 16 workers, ui 6 :
20 min 41 s au total. Paliers : ruff et documentation 0:09, oracle 0:22 (1 205), unit 4:18 (6 176 ; 4 échecs verts au
rejeu), ui 10:29 (1 594), rest 3:54 (322), performance 0:21 (30). Les quatre échecs du premier passage, verts seuls
sur cache Numba vierge : POEM (§6), `test_the_automatic_export_is_off_under_test` et les deux tests de
`test_the_default_pytest_run_is_quiet.py`.

## 6. Bits selon l'historique de compilation (chantier 34)

- `test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit` échouait **seul** (150,0000000000008 contre
  150,0000000000001) sur le cache partagé, et passait sur cache vierge (deux fois). Reproduit : cache vierge, palier
  `unit` complet, puis le test seul sur ce cache → échec.
- Coupable isolé par dichotomie parmi 42 objets : une spécialisation de `simulate_growth_kernel`, même signature qu'un
  objet compilé à neuf, mais 444 Ko de code machine contre 333 Ko. Elle lie deux versions de plus des routines
  internes `complex_mul` et `complex_div` de Numba, compilées plus tôt dans le même processus. Les derniers bits d'un
  noyau dépendent donc de ce que le processus a compilé avant lui, et le cache transmet cet historique.
- Conséquence : « identique au bit » ne vaut qu'entre processus de même historique, ou froid contre froid (règle déjà
  suivie par `c1_diff.py`). Les reprises 27 à 29 doivent en tenir compte.
- `f350044d` : `validate_parallel.py` rejoue ses échecs sur un cache Numba vierge (la section 0 d’`ETAT.md` le demandait à la main).
- Non fait : rendre les noyaux indépendants de l'historique ; tout changement de noyau change les bits (C1).

## 7. Durée des tests (chantier 43)

- `b6d392bb` : `test_le_pilotage_par_QProcess_remplit_reellement_le_tableau` attendait au démontage le préchauffage
  STRAT de sa fenêtre (fichier seul à froid : 100 s, 3,8 s sans préchauffage). Sous 16 workers, l'attente dépassait les
  180 s de `qt_lifecycle`, qui appelle `pytest.exit` ; xdist le rapporte comme un worker mort. Deux passages `unit` sur
  cinq ont ainsi perdu environ 1 500 tests.
- `376baef1` : une étape xdist reçoit `NUMBA_NUM_THREADS` = cœurs ÷ workers, sauf valeur déjà posée.

| `tests/unit/`, `-n 16 --dist loadfile`, même arbre | durée |
|---|---:|
| 16 fils Numba par worker, cache chaud | 512 s |
| 1 fil par worker, cache chaud | 299 s |
| 1 fil par worker, cache vierge | 408 s |

| `tests/ui/`, 6 workers, cache chaud, `D:` | durée |
|---|---:|
| 16 fils Numba | 10:11 |
| 2 fils (règle de `376baef1`) | 10:31 |
| 2 fils, `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=1` | 10:44 |

La règle est neutre sur `ui` et divise `unit` par 1,7.

## 8. Deux défauts de calcul corrigés (chantiers 35 et 36)

🔴 **Les deux correctifs changent des résultats de DESIGN.** Ils ont été décidés sous le mandat de nuit de 👤 du
2026-11-14 ; chacun tient dans un commit qui s'annule par `git revert`.

- **C20 (D113), `78515573`.** Couches absorbantes données en n − ik, substrat sans perte, sans face arrière :
  `compute_gradient_all_layers_analytic` passait les indices à `_compute_gradient_analytic_kernel`, juste seulement
  en n + ik. Sur le cas de `tests/oracle/test_absorbing_front_cost_matches_the_reference.py`, son coût dépassait la
  référence indépendante de 343 % : L-BFGS-B minimisait un autre objectif, et le RMSE final, calculé par la TMM de
  production (identique pour les deux signes), avait l'air juste. Correction : conjugaison à cette seule frontière.
  `c1_diff HEAD` : 136 tableaux sur 9 092 changent, tous dans `normal.gradall0/1` ; les autres gardent leurs bits.
  Non vérifié : un design réel de l'utilisateur dans ce mode.
- **ALG-03, `4d634756`.** En incidence oblique, la grille densifiée avant l'affinage final n'atteignait pas les
  configurations obliques du worker. Sonde [`probe_alg03.py`](../alg03_grille_oblique_2026-11-14/probe_alg03.py) :
  avant, coût et gradient sur 2 points au lieu de 135, RMSE rapporté 0,026 pour 0,175 sur la grille dense
  ([avant](../alg03_grille_oblique_2026-11-14/alg03.json)) ; après, 135 points et RMSE rapporté = RMSE dense = 0,17197
  ([après](../alg03_grille_oblique_2026-11-14/alg03_apres.json)). `c1_diff HEAD` : identique au bit (son corpus
  n'exerce pas le worker).
