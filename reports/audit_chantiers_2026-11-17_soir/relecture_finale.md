# Relecture finale : chaque premier pas est-il faisable ? (17 novembre 2026 au soir)

Demande de 👤 : vérifier que tout est faisable. Ce qu'une relecture peut prouver : que l'entrée, l'outil et le chemin de
chaque premier pas existent, et qu'il tourne là où un essai court le permet. Elle ne peut pas promettre l'issue d'un
chantier (un gain, une corrélation). Base `6015cf8b` ; un autre processus python tournait (`serveur.py`) : les durées
ci-dessous sont indicatives.

## Essais exécutés

| Chantier | Essai | Résultat | Effet |
|---|---|---|---|
| 50 | [`p50_inc_tmm_smoke.py`](preuves/p50_inc_tmm_smoke.py) : `tmm.inc_tmm` contre `calculate_RT_with_backside_fused`, deux couches sur substrat de 1 mm | Couches dans l'ordre inverse (convention du 40) : k = 0, écart 8,9e-16 ; substrat absorbant, écart qui monte à 3,2e-8 (k = 2e-5) puis retombe quand T → 0 ([sortie](preuves/p50_inc_tmm_smoke.txt)). Dans l'ordre direct, 0,25 : piège de convention. | Faisable. Premier objet : expliquer les 3e-8 (CERTUS prend les interfaces du substrat à Re(n), `tmm` à n complexe ; hypothèse). Le critère « 1e-12 » était mal posé. |
| 19 | `verify_changed.py --audit-calls` sur `tests/oracle/test_normal_cost_and_gradient_agree.py` | `AUDIT_APPELS=OK`, 57 s pour 19 tests, graphe et compilation compris. | Faisable ; la durée sur `tests/oracle` entier reste à mesurer (premier pas). |
| 05 | [`p05_sellmeier_time.py`](preuves/p05_sellmeier_time.py) : un ajustement Sellmeier 3 pôles de SUBSTRATE, réglages par défaut, données BK7 synthétiques bruitées à 2e-5 | 2,65 s à chaud, dont 2,38 s dans `least_squares` (Jacobiens par différences finies) ([sortie](preuves/p05_sellmeier_time.txt)). | Le gain n'est pas négligeable : 05 ne s'archive pas sur la durée. Anomalie à instruire : écart quadratique 2,95e-4, quinze fois le bruit, source `analytic-sellmeier-3term-standard` (une mesure, données synthétiques). |

## Vérifications de lecture

| Chantier | Constaté | Effet |
|---|---|---|
| 49 | `JSON-strat-example.json` n'a pas de cibles (`targets` absent) : c'est un réglage STRAT (48 multiplicateurs, matériaux en fichiers dispersifs). `bench_codesign.py` exige des cibles DESIGN, des indices constants et 34 couches H/L. | L'exemple ne peut pas servir de composant. Premier pas : 👤 fournit un problème DESIGN représentatif (cibles, matériaux, nombre de couches) ; bloqué d'ici là. 24, 31 et 32 en héritent. |
| 31 | `native_evaluator` fige `p_thick_nominal` ; un pas d'épaisseur reconstruit l'évaluateur, et le gain se juge contre des cibles DESIGN. | Même prérequis que 49 ; complexité très forte. |
| 18 | La fenêtre SUBSTRATE est `certus_substrate_ui.py::SubstrateIndexGUI` (l'audit citait un dialogue). Ni elle ni `CurveSmootherGUI` n'ont `_collect_config` / `_apply_config`, sur lesquels repose la session (`certus_base_app_config_mixin`). | Faisable : chaque pas commence par définir ce que la fenêtre sauvegarde. |
| 21 | Cas à profiler présents : `example/example_index_spline`, `tests/headless/test_spline.py`. | Faisable. |
| 48 | Déplacer le clone casse les quatre arbres de travail Git (chemins absolus ; `git worktree repair`) et sépare `scripts/restore_rate_evidence.py` de l'archive qu'il cherche à côté du clone. | Faisable, à faire avec ces deux points. |
| 41 | Cinq PR ouvertes, fusionnabilité non encore calculée par GitHub (`UNKNOWN`). | Faisable par 👤. |
| 24, 32, 47, 33 | Dépendent de 49, d'une décision de 👤 ou d'une date. | Faisables sous leur condition, pas avant. |
