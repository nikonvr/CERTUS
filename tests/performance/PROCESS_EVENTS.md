
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # Cartographie `processEvents` / `time.sleep` (baseline ARCH-4)

Réentrance : tout appel à `QApplication.processEvents()` / `app.processEvents()` peut exécuter des slots Qt pendant une section critique (worker, optimisation, I/O).  
Risque : double entrée, état UI incohérent, et masquage d'un vrai goulet CPU.

## Périmètre et volume (snapshot 2026-04-25)

- **Code applicatif principal (prod)** : 30 occurrences `processEvents`, 1 occurrence `time.sleep`.
- **Outillage/tests/docs/archive** : occurrences séparées, non prioritaires pour ARCH-4 prod.
- **Objectif ARCH-4** : élimination progressive en commençant par les chemins à risque de réentrance élevée.

## Applications principales (prod)

| Fichier | Ligne | Appel | Contexte (résumé) | Risque |
|---------|-------|-------|-------------------|--------|
| `CERTUS_INDEX_SPLINE.py` | 5347 | `QApplication.processEvents()` | Pré-loop d'autofind + lancement thread manuel | Élevé |
| `CERTUS_INDEX_SPLINE.py` | 5397 | `QApplication.processEvents()` | Dans boucle de progression d'autofind | Élevé |
| `CERTUS_INDEX_SPLINE.py` | 5411 | `time.sleep(0.05)` | Temporisation dans boucle active (UI + timeout) | Élevé |
| `CERTUS_STRAT.py` | 19550 | `QApplication.processEvents()` | Callback live monitor pendant flux de calcul | Élevé |
| `certus_substrate_index.py` | 5273 | `lambda i,n: QApplication.processEvents()` | Callback de progression dans fit multi-modèles | Élevé |
| `CERTUS_DESIGN.py` | 9693 | `QApplication.processEvents()` | Callback d'update live en optimisation | Élevé |
| `CERTUS_INDEX.py` | 14181 | `QApplication.processEvents()` | Pré Phase-5 (fit global n/k), section coûteuse | Moyen/Élevé |
| `CERTUS_INDEX.py` | 14291 | `QApplication.processEvents()` | Avant auto-export post-calcul | Moyen |
| `CERTUS_INDEX.py` | 13935 | `QApplication.processEvents()` | Après rendu résultats/plots | Moyen |
| `CERTUS_INDEX.py` | 14321 | `QApplication.processEvents()` | Après mise à jour UI résultats TLU | Moyen |
| `CERTUS_INDEX.py` | 14475 | `QApplication.processEvents()` | Après table + rendu final | Moyen |
| `certus_substrate_index.py` | 4517 | `QApplication.processEvents()` | Pont de log UI | Moyen |
| `certus_substrate_index.py` | 4529 | `QApplication.processEvents()` | `_set_busy` (activation/désactivation widgets) | Moyen |
| `certus_substrate_index.py` | 5177 | `QApplication.processEvents()` | Progress update boucle colonnes | Moyen |
| `certus_substrate_index.py` | 5245 | `QApplication.processEvents()` | Progress update boucle fit modèle | Moyen |
| `certus_reset_framework.py` | 359 | `QApplication.processEvents()` | Refresh nettoyage mémoire/reset | Moyen |
| `certus_reset_framework.py` | 380 | `QApplication.processEvents()` | Refresh final reset | Moyen |
| `certus_curve_smoother.py` | 276 | `QApplication.processEvents()` | Avant auto-tune potentiellement long | Moyen |
| `CERTUS_RE.py` | 9926 | `app.processEvents()` | Splash démarrage | Faible |
| `CERTUS_RE.py` | 9942 | `app.processEvents()` | Splash chargement config par défaut | Faible |
| `CERTUS_INDEX.py` | 15498 | `app.processEvents()` | Splash démarrage | Faible |
| `CERTUS_INDEX.py` | 15518 | `app.processEvents()` | Splash démarrage UI | Faible |
| `CERTUS_DESIGN.py` | 14750 | `app.processEvents()` | Splash démarrage | Faible |
| `CERTUS_DESIGN.py` | 14766 | `app.processEvents()` | Splash chargement config | Faible |
| `CERTUS_STRAT.py` | 19661 | `app.processEvents()` | Splash démarrage | Faible |
| `CERTUS_STRAT.py` | 19681 | `app.processEvents()` | Splash chargement DB | Faible |
| `CERTUS_STRAT.py` | 19710 | `app.processEvents()` + `QThread.msleep(50)` | Boucle d'attente d'erreur splash | Faible/Moyen |
| `CERTUS_STRAT.py` | 19739 | `app.processEvents()` | Splash lancement UI | Faible |
| `CERTUS_METAL_SINGLE.py` | 3438 | `app.processEvents()` | Splash lancement | Faible |
| `CERTUS_METAL_BILAYER.py` | 3954 | `app.processEvents()` | Splash lancement | Faible |

## Hors prod (référentiel séparé)

- **Tests** : `tests/smoke_examples_subfolders.py`, `tests/smoke_re_reverse_samples.py`, `tests/test_examples_complete.py`, tests de perf spline.
- **Outillage** : `tools/release_checks.py` (`time.sleep(0.5)`).
- **Documentation/roadmap** : mentions textuelles dans `reports/...`.
- **Archive** : `archive/2404_cleanup/...` non bloquant pour la dette runtime actuelle.

## Priorisation d'exécution (prochaine étape)

1. **P0 immédiat** : `CERTUS_INDEX_SPLINE.py`, `CERTUS_STRAT.py` (live), `CERTUS_DESIGN.py`, `certus_substrate_index.py` callback de progression.
2. **P1** : `CERTUS_INDEX.py` (sections post-calcul/auto-export), `certus_curve_smoother.py`, `certus_reset_framework.py`.
3. **P2** : appels splash uniquement (`RE`, `INDEX`, `DESIGN`, `STRAT`, `METAL_*`) après migration des zones critiques.

## Règle d'implémentation ARCH-4

- Remplacer les boucles actives (`processEvents` + `sleep`) par `QThread`/`QRunnable` + signaux stricts.
- Conserver la progression UI via signaux `progress(int)` et timer UI léger si nécessaire.
- Interdire toute nouvelle introduction de `processEvents()` dans le code applicatif runtime.


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.