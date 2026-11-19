# CERTUS — référence (à la demande)

Complément de [`CLAUDE.md`](../CLAUDE.md) (même numérotation `CLAUDE.md §N`). Un fait, un seul endroit.

## 1. Démarrage et publication

- `preflight.py` vérifie l'import `certus` et ses dépendances sans chemin en dur.
- Committer est local : le hook `.githooks/post-commit` ne s'active que via `git config core.hooksPath .githooks`. Vérifier `git config --get core.hooksPath` et `git status -sb`. Les données de 👤 sont son choix.
- **Consigne absolue (👤 2026-11-19)** : rester exclusivement dans le dépôt Drive `certus1111` (`D:\drivfl`), ne jamais cloner/déplacer ailleurs (ex. `C:\dev`). Lire avec `git --no-optional-locks` ; purger un `.git\index.lock` vide ancien avant un commit.

## 2. Valider — pièges

- Un échec isolé au premier run sur arbre neuf peut venir du cache Numba : relancer une fois avant de conclure.
- Test Qt mort sans traceback = worker encore actif : relancer avec `QT_FORCE_STDERR_LOGGING=1` et `-s`. Vert seul / rouge en suite = état partagé.
- Tout module typé dans `domain`/`physics`/`core` suit `tests/architecture_debt.json`.
- Itérer : `python scripts\verify_changed.py` (`--list` explique ; `VERIF_CIBLEE=GO` suffit pour un commit local ; suite entière pour une fusion) ; suite rapide : `python scripts\validate_parallel.py` (`VALIDATION=GO`).
- Après modif du gel ou d'un point d'entrée de STRAT : `powershell tools\build_frozen.ps1` puis `python tools\release_checks.py --check-frozen --check-frozen-run`. Nettoyer `dist/` et `build/`, jamais `reports/`.

## 5. C1 au bit — mode d'emploi de `c1_diff`

Une recompilation décale les derniers bits (`fastmath`). `python scripts\c1_diff.py HEAD` compare l'arbre de travail à un commit dans des interpréteurs neufs à caches Numba vierges (prouve uniquement les appels de son corpus). Toujours comparer froid à froid ; ne pas découper un noyau `fastmath` sauf `inline="always"` en gardant les boucles fusionnées. Auto-contrôle du corpus : `python scripts\c1_diff.py X --tete X --sans-cache` = `0`.

## 6. Pièges d'exécution

- `params` (DTO Pydantic) : `get` et `[]` marchent, pas `setdefault`. Dans `certus/physics`, éviter `certus_physics.X` (cycle via `__init__.py`).
- **Cache Numba** (`numba_cache_key` dans `certus/core/certus_core.py`) : inclure `numba` dans le texte de tout module exposant une constante/façade aux noyaux (`tests/unit/test_the_cache_key_covers_what_the_kernels_read.py`). Chauffer Numba avant tout chronométrage.
- **Qt / tests** : restaurer les caches de classe par fixture ; utiliser la fixture `qapp` (jamais de `QApplication` locale). `tests/headless/test_design.py` et `test_strat.py` simulent ; mesurer avec `scripts/bench_examples.py`.
- Phase A : `reports/STRAT_observability_*.json`. Dans INDEX SPLINE, `d_lo`/`d_hi` = nominale/tolérance au widget mais bornes dans `SplineOptConfig`.
- **I/O & erreurs** : écrire tout export via `atomic_open` (`certus/utils/certus_atomic_io.py`) ; tout `except` large journalise ou se restreint (`test_exports_are_written_atomically.py`, `test_no_broad_exception_is_swallowed_in_silence.py`).
- **Qt / thème** : `apply_certus_theme()` + jetons `CertusTheme` (jamais d'hexadécimal) ; encre bouton plein `CertusTheme.label_on`, transparence `CertusTheme.tint(couleur, 0.18)` ; `refresh_widget_sheets()` au changement de thème ; vérifier le rendu (`widget.grab()`, `scripts/audit_ux_certus.py`).
- **Outils `scripts/`** : paramètre inerte -> `check_inert_params.py`, `check_param_effect.py` ; imports -> `lint_ns_snapshot.py` ; UX -> `tests/ui/ux_skeleton.json` + `regenerer_squelette.py --ecrire`, modales -> `sonde_retenants_fenetre.py`. Ne pas écrire le motif littéral d'un garde-fou dans le code.

## 7. QWOT et point tournant

QWOT = épaisseur optique d'une couche (`m = 4nd/λ`) ; point tournant = admittance système réelle (`tan 2δ = R/Q`). Même période d'un quart d'onde à `λ_mon`, mais déphasage initial `½·arctan(R/Q)` fixé par l'empilement dessous (coïncidence uniquement sur couche 1 sur substrat nu ou empilement tout QWOT).

## 8. Architecture — gel et points d'entrée (CLAUDE.md §8)

- Gel (`certus_hub.spec`) : un exécutable unique (`CERTUS_HUB.exe`, `--run-module NOM [fichier]`). Point d'entrée `tools/frozen_entry.py`, jamais un fichier de `certus/core/` (masquerait `certus_substrate_index.py`). Tout script `scripts/` importé au boot doit être dans `datas` (`test_the_frozen_spec_bundles_the_suite`).
- Points d'entrée racine : `certus_curve_smoother.py` et `certus_substrate_index.py` (ré-exporte les globales de `certus.core.certus_substrate_index`).

## 9. Vocabulaire

| terme | sens |
|---|---|
| juge de paix | dichroïque 48 couches `example/example_strat/JSON-strat-example.json` |
| λ de contrôle, bloc | longueur d'onde surveillée ; couches consécutives sur la même λ |
| POEM | arrêt à un pourcentage de l'amplitude entre les deux derniers points tournants |
| plantage, rendement | dépôt non terminé ; part terminée (objectif 95 %) |
| Phase A, Phase B | choix d'une λ par couche ; regroupement en blocs + Monte-Carlo |
| SEEL | erreur d'épaisseur équivalente par couche (nm) — grandeur rapportée |

## 10. Tenir la documentation

- Un fait, un endroit (`docs/ETAT.md` = état, ici = règle) ; citer des fonctions, jamais des numéros de ligne ; pas de récit (« disait… »).
- Les 3 scripts doc de `CLAUDE.md §2` vérifient la mécanique, pas la vérité des phrases.
- `pages/*.html` : rapports scientifiques **en anglais**, strictement fidèles au code ; `pages/CERTUS_STRAT.html` sourçable et contrôlée par `python scripts\verifier_html.py pages\CERTUS_STRAT.html`.

## 12. Vérifier le travail d'un autre agent

Un rapport est une déclaration, pas une preuve : vérifier (1) diff vs déclaration, (2) reproductibilité de la mesure, (3) validité de la conclusion. Contrôler : paramètre nouveau inerte au bit, test rouge avant correctif, sensibilité au bruit, comptes réels de rejets, absence d'extrapolation. Ne pas déplacer `depart-gemini`.
