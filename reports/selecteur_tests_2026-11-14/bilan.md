# Chantier 19 — le sélecteur de tests face à la suite complète (2026-11-14/15)

`scripts/probe_test_selector.py` sur un worktree détaché de `df36593f` (`%LOCALAPPDATA%\Temp\certus_c19_df36593f`),
16 ouvriers. Pour chaque cas : faute injectée, sélection de `scripts/verify_changed.py` jouée (`-x`), puis suite
complète en cinq paliers pytest (sans ruff ni contrôles documentaires). Sorties : `runs_df36593f/`.

## 1. Témoin

`control.json` : vert, 1 844 s. Palier `unit` : `ARTEFACT` (un échec au premier passage, vert au rejeu isolé :
`test_the_slit_profile_is_inert_when_absent_or_zero`, chantier 34).

## 2. Cas

| cas | type | statut | élus / 672 | sélection | complète | échec de la sélection |
|---|---|---|---|---|---|---|
| infrared_center | historique `3865ac09` | OK | 205 | 626 s | 1 681 s | test du correctif |
| empty_phase_a | historique `68f40d27` | OK | 179 | 735 s | 1 398 s | test du correctif |
| qwot_signal_state | historique `5a456ec7` | OK | 672 (tout) | 248 s | 1 465 s | garde d'architecture des mixins ¹ |
| angle_boundary | mutation `>` → `>=` | OK | 343 | 874 s | 1 453 s | test visant la ligne |
| spectral_width | mutation `-` → `+` | **ESCAPED** | 325 | invalide ² | 1 488 s | test visant la ligne |
| thickness_units | mutation `*` → `/` | OK | 64 | 295 s | 1 420 s | test visant la ligne |
| field_chain | mutation `*` → `/` | ESCAPED, **artefact** ³ | 202 | 614 s | 1 667 s | test visant la ligne |
| overflow_boundary | mutation `>` → `>=` | ESCAPED, **survivant** ⁴ | 307 | 1 296 s | 1 524 s | aucun (4 instables UX) |

**Bilan : 5 OK, 3 ESCAPED, dont un seul trou réel du sélecteur (`spectral_width`).**

Dans la suite complète, `test_a_reduced_offender_lowers_its_ceiling[fichiers_longs]` échoue aussi pour les deux
premiers cas historiques : il est déclenché par le patch inversé lui-même (le fichier raccourcit), pas par la faute.

¹ Sélection = suite entière (`672 fichiers de test sur 672 : autant tout jouer`) ; `-x` s'arrête au premier échec. Le
test du correctif (`test_physical_thickness_updates_the_re_qwot_column`) échoue dans la suite complète, et son fichier
figure parmi les élus.

² La sélection a duré 22 082 s : le worker de `tests/ui/test_ux_no_horizontal_scroll.py` a ouvert la boîte modale
« Unsaved configuration » à `win.close()`, et `run_ux_worker` n'avait aucun délai. Un surveillant l'a tué à 08:22.
La liste des élus est calculée avant l'exécution : elle n'est pas faussée.

³ Palier `unit` à 45 échecs, au-delà de `MAX_REPLAY` = 40 (`validate_parallel.py`) : aucun rejeu. Les deux « échappés »
sont des instables connus : `test_the_slit_profile_is_inert_when_absent_or_zero` (l'artefact du témoin, chantier 34) et
`test_a_scheduled_task_runs_after_its_delay[schedule_export_pareto_report-…]`. Contre-épreuve du 2026-11-15 vers 11:06, sur
l'arbre mesuré muté à la main : les 43 tests de `test_field_peak_gradients.py` échouent, les deux « échappés » passent
seuls. Défaut de la sonde, pas du sélecteur : `classify` compte un instable non rejoué comme un échappé.

⁴ Aucun test de comportement ne voit la mutation : la sélection n'échoue que sur quatre tests UX de DESIGN, verts au
rejeu isolé, et la suite complète sur `test_the_mutation_baseline_describes_the_code_as_it_is.py` seul, qui vérifie que
les survivants jugés de la base de mutation existent encore dans le code : la ligne mutée en est un. Ce garde lit ses
chemins dans un fichier de données, pas dans son source : l'étape 4 du sélecteur ne peut pas le relier au fichier modifié.

## 3. L'échappé de `spectral_width` (lu dans le code et dans le JSON)

`tests/regression/test_convergence_guard.py::test_convergence_has_not_regressed[SPLINE]` échoue dans la suite
complète, aussi au rejeu en série ; SPLINE n'est pas dans `STOCHASTIQUES`. Le garde importe
`tests/regression/test_convergence.py`, qui lance `tests/headless/test_spline.py` par `subprocess`, nommé par son seul
nom de fichier. Le graphe statique de `verify_changed.py` (étape 2) ne suit pas cette arête, et `--audit-calls`, qui
profile le processus du test, ne la verrait pas non plus. Trou structurel : tout test qui lance un script du dépôt en
sous-processus.

## 4. Suites proposées (non faites)

- Relier au graphe les scripts lancés en sous-processus et nommés par leur seul nom de fichier
  (`tests/regression/test_convergence.py` → `tests/headless/*.py`), ou toujours jouer `tests/regression/` quand un module
  du dépôt change.
- `probe_test_selector.py::classify` : rejouer seuls les échecs de la suite complète absents de la sélection avant de les
  déclarer échappés, même au-delà de `MAX_REPLAY`.

## 5. Limites

- 8 cas choisis à la main, tous dans des `.py` à tests directs : un trou réel sur 8 laisse un taux d'échappement
  compatible avec 0,3 % à 53 % (intervalle exact de Clopper-Pearson à 95 %, `scipy.stats.beta`).
- Aucun cas sur un fichier non Python, un `conftest` ou `_certus_physics_impl.py`.
- `OK` (`probe_test_selector.py::classify`) : suite complète rouge, sélection rouge, et chaque fichier en échec de la
  suite complète parmi les élus. Il ne vérifie pas que la sélection a échoué sur le test de la faute ; `escaped` est une
  appartenance de fichier, pas un test joué.
- Lu dans le code (`verify_changed.py::select`) : un `conftest.py`, `pyproject.toml`, les verrous, un `.py` qui ne
  s'analyse pas, un fichier supprimé ou plus de 60 % des tests demandent la suite complète ; un module du dépôt modifié
  ajoute `pytest --collect-only tests` (`selection.collect`) ; un `.md` ou `.html` lance les trois contrôles
  documentaires ; un fichier de `certus/physics/` ou citant numba ajoute tout l'oracle.

## 6. Incidents

- Premier essai sur `20b979d9` (`runs_20b979d9/`) : témoin tué, worker mort au join de 180 s (corrigé `ddd29cc4`).
- 2026-11-15 09:04-09:07, cas `thickness_units` : palier `ui` à 223 échecs et 61 erreurs (`native abort, exit status
  0xc0000142`, DLL_INIT_FAILED), puis palier `rest` sans sortie et arrêt de la sonde. Contemporain d'un changement de
  session sur la machine : artefact d'environnement. Dossier gardé : `runs_df36593f/thickness_units_invalide_0xc0000142_0907/`.
  Cas relancé.
