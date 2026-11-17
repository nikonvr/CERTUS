# Chantier 19 — les arêtes que le sélecteur ne voit pas (2026-11-17)

`scripts/verify_changed.py --audit-calls` : chaque fonction du dépôt qu'un test **exécute** (`sys.monitoring`) est-elle dans
sa clôture statique ? Le parallélisme de l'audit se règle par `--audit-workers` (`--workers` ne le touche pas).

| suite | sortie | résultat | durée |
|---|---|---|---|
| `tests/oracle` | [avant](audit_calls_oracle.txt), [après](audit_calls_oracle_apres.txt) | 1 trou (`__path__`), corrigé ; puis OK, 22 fichiers | — |
| `tests/unit` | [audit](audit_calls_unit.txt) | 37 fichiers sur 492 avec un trou, pytest vert | 4 636 s, en série |
| `tests/unit`, les 37 | [après](audit_calls_unit_apres_37.txt) | **0 trou** ; un test rouge, voir plus bas | 190 s, 8 workers |

## Les 37 trous de `tests/unit`

- **35 faux trous** : du code **imbriqué** (le filtre d'événements de `hover_lift`, le patch de `ViewBox` de
  `_patch_pyqtgraph_viewbox_nan_transform_angle`), installé par un test précédent du même processus. Seuls, ces tests n'y
  passent pas (traçage d'un test DESIGN : aucun appel). L'audit ignore désormais le code `<locals>` : une fonction imbriquée
  ne tourne qu'après son parent, audité là où il tourne (`a9d3e3a4`).
- **2 vrais trous**, corrigés :
  - un test importe les aides d'un test voisin (`from test_design_memetic_lm_polisher import _build`) : l'arête s'arrêtait à
    l'aide, alors qu'un fichier de test n'a d'arêtes que pour lui entier (`60b65e21`) ;
  - `certus_hub.spec` (PyInstaller, donc du Python) charge `tools/frozen_licences.py` par son chemin : le sélecteur ne
    lisait pas le `.spec` (`1003c5f5`), et la ligne de commande ne mettait que les `*.py` dans le graphe (`dce46a3e`,
    trouvé au réaudit).

Chaque correctif a son test dans `tests/unit/test_verify_changed_plays_the_regression_suite.py`, rouge avant.

## Le test rouge du réaudit

`test_design_scheduled_tasks_run.py::test_a_scheduled_task_runs_after_its_delay[schedule_smart_pareto_decimation-…]`
attend un minuteur Qt 5 s au plus ; sous le profil de l'audit et 8 processus, il a manqué. Rejoué : 10 passés seul,
10 passés avec `-n 8`. Flaky de charge, non corrigé.

## Non fait

`tests/ui` n'est pas audité. Le réaudit complet de `tests/unit` après les correctifs non plus : seuls les 37 fichiers l'ont été.
