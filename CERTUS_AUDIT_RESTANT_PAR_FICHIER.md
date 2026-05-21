# Audit des fichiers restants CERTUS

## Périmètre
Ce document couvre les fichiers qui ne sont pas dans le noyau prioritaire mais qui restent importants pour l’exploitation, les tests, l’outillage et la maintenance.

---

## Fichiers d’outillage et de validation

### `tools/release_checks.py`
- **Rôle :** validation de release.
- **Forces :** bon garde-fou.
- **Risques :** checks obsolètes, trop permissifs ou trop liés à un état local.
- **Améliorations :** rendre les critères explicites, ajouter des sorties lisibles, couvrir les artefacts livrés.
- **Priorité :** P1.

### `scripts/smoke/run_examples_headless.py`
- **Rôle :** smoke tests headless.
- **Forces :** bon filet de sécurité.
- **Risques :** trop fragile si les exemples changent sans contrat.
- **Améliorations :** assertions minimales claires, rapport d’échec utile, couverture de plusieurs familles de workflows.
- **Priorité :** P1.

### `clean_nodeids.py`
- **Rôle :** nettoyage de node IDs de test.
- **Forces :** bon outil de maintenance.
- **Risques :** faible si le script reste petit; plus haut s’il commence à muter la structure des tests.
- **Améliorations :** documenter précisément l’entrée/sortie, ajouter une validation sur le format.
- **Priorité :** P2.

### `_run_test_batches.py`
- **Rôle :** orchestrer des batchs de tests.
- **Forces :** utile pour la CI locale.
- **Risques :** peut masquer des dépendances d’ordre ou des états partagés.
- **Améliorations :** standardiser les batchs et la remontée d’échec.
- **Priorité :** P2.

---

## Fichiers de documentation

### `README.md`
- **Rôle :** porte d’entrée du projet.
- **Forces :** indispensable.
- **Risques :** rapidement obsolète si le projet évolue vite.
- **Améliorations :** clarifier l’installation, l’exécution, les exemples, les prérequis et les liens vers les docs de référence.
- **Priorité :** P1.

### `docs/index.md`
- **Rôle :** index documentaire.
- **Forces :** bon point d’accès.
- **Risques :** désynchronisation avec les fichiers réels.
- **Améliorations :** maintenir la cartographie des docs et l’état des pages.
- **Priorité :** P2.

### `docs/API_DOCUMENTATION.md`
- **Rôle :** référence API.
- **Forces :** utile pour la maintenance.
- **Risques :** si l’API bouge, la doc peut mentir.
- **Améliorations :** lier les entrées publiques aux modules réels, maintenir un changelog.
- **Priorité :** P1.

### `docs/DETERMINISM_GUARANTEE.md`
- **Rôle :** engagement déterministe.
- **Forces :** excellent signal de maturité.
- **Risques :** doit être respecté par le code et les tests.
- **Améliorations :** relier chaque promesse à un test concret.
- **Priorité :** P1.

### `docs/NUMERICAL_TOLERANCES.md`
- **Rôle :** politique de tolérances numériques.
- **Forces :** très important pour le socle scientifique.
- **Risques :** dérive des seuils avec le temps.
- **Améliorations :** relier les tolérances aux tests de non-régression et aux wrappers numériques.
- **Priorité :** P1.

### `docs/REFRACTORING_EXECUTION_PROTOCOL.md`
- **Rôle :** protocole de refactor.
- **Forces :** bon cadre d’exécution.
- **Risques :** peut devenir théorique si non appliqué.
- **Améliorations :** le lier à un backlog exécutif réel.
- **Priorité :** P2.

### `docs/SYM_NUMBA_V2_SPEC.md`
- **Rôle :** spécification algorithmique.
- **Forces :** très bon support de rigueur.
- **Risques :** si le code dérive, la spec perd sa valeur.
- **Améliorations :** maintenir la spec avec les tests et le code concerné.
- **Priorité :** P2.

### `docs/adr/000_template.md`
- **Rôle :** modèle ADR.
- **Forces :** utile pour capitaliser les décisions.
- **Risques :** faible si peu utilisé.
- **Améliorations :** encourager son usage pour les refactors majeurs.
- **Priorité :** P2.

### `docs/project_meta/GEMINI.md`
- **Rôle :** méta-information projet.
- **Forces :** utile pour contextualiser l’assistant et les conventions.
- **Risques :** désalignement avec l’état réel.
- **Améliorations :** garder les faits à jour, éviter les affirmations trop générales.
- **Priorité :** P2.

### `OPTICAL_FUNCTIONS_EXPORT.md`
### `OPTICAL_FUNCTIONS_QUICK_REFERENCE.md`
- **Rôle :** référentiels d’aide optique.
- **Forces :** utiles pour les utilisateurs.
- **Risques :** duplications ou obsolescence.
- **Améliorations :** aligner les définitions, éviter les divergences.
- **Priorité :** P2.

### `samples/README.md`
- **Rôle :** documentation des exemples.
- **Forces :** utile pour le onboarding.
- **Risques :** si les exemples changent, la doc devient fausse.
- **Améliorations :** relier chaque exemple à un cas d’usage connu.
- **Priorité :** P2.

### `example/README.md`
- **Rôle :** documentation du dossier d’exemples.
- **Forces :** utile comme porte d’entrée.
- **Risques :** obsolescence rapide.
- **Améliorations :** décrire le format des fichiers attendus et les limites.
- **Priorité :** P2.

---

## Fichiers de configuration et packaging

### `pyproject.toml`
- **Rôle :** configuration build, format, lint, dépendances.
- **Forces :** pièce centrale de la reproductibilité.
- **Risques :** surconfiguration, divergence entre outils, pinning trop rigide.
- **Améliorations :** garder une configuration cohérente et documentée.
- **Priorité :** P1.

### `requirements.txt`
### `requirements.lock`
- **Rôle :** dépendances et verrouillage.
- **Forces :** améliore la reproductibilité.
- **Risques :** divergence entre les deux fichiers, pins incohérents.
- **Améliorations :** vérifier qu’ils racontent la même histoire, surveiller les versions.
- **Priorité :** P1.

### `.github/workflows/lint.yml`
### `.github/workflows/release-windows.yml`
### `.github/workflows/security.yml`
- **Rôle :** CI, release, sécurité.
- **Forces :** très bon niveau d’outillage.
- **Risques :** maintenance des chemins, compatibilité des versions, charge de CI.
- **Améliorations :** garder les workflows alignés avec le packaging et les tests réels.
- **Priorité :** P1.

---

## Fichiers de rapport et production de sorties

### `reports/CERTUS_CHANGELOG_ROADMAP.md`
### `reports/CERTUS_MASTER_TODO_OPTIMIZATION.md`
### `reports/dead_code_audit_report.md`
- **Rôle :** rapports techniques et roadmap.
- **Forces :** bon historique projet.
- **Risques :** accumulation d’artefacts et désynchronisation.
- **Améliorations :** distinguer ce qui est archive de ce qui est source de vérité.
- **Priorité :** P2.

### `audit_complet_certus.md`
### `CERTUS_AUDIT_ACTION_PLAN.md`
### `CERTUS_MASTER_TASKS.md`
### `CERTUS_P0_P1_PLAN.md`
### `CERTUS_HANDOFF.md`
### `implementation_plan.md`
### `task.md`
- **Rôle :** documents de pilotage.
- **Forces :** utiles pour le suivi.
- **Risques :** multiplication de sources de vérité.
- **Améliorations :** consolider ou archiver ce qui est redondant.
- **Priorité :** P2.

---

## Fichiers de tests complémentaires

### `tests/unit/test_certus_errors.py`
### `tests/unit/test_certus_services.py`
### `tests/unit/test_certus_hub.py`
### `tests/unit/test_certus_re.py`
### `tests/unit/test_certus_design.py`
### `tests/unit/test_certus_reset_framework.py`
### `tests/unit/test_spline_objective.py`
### `tests/unit/test_spline_objective_extended.py`
### `tests/unit/test_spline_presets.py`
### `tests/unit/test_seed_contract_global.py`
- **Rôle :** garde-fous unitaires variés.
- **Forces :** couvrent des domaines critiques.
- **Risques :** certains peuvent être trop proches de l’implémentation.
- **Améliorations :** recentrer sur les invariants métier et les cas de régression connus.
- **Priorité :** P1.

### `tests/ui/test_certus_shortcuts_overlay.py`
### `tests/ui/test_certus_skeleton.py`
### `tests/ui/test_certus_toast_stack.py`
### `tests/ui/test_certus_ux_system.py`
### `tests/ui/conftest.py`
- **Rôle :** tests UI.
- **Forces :** très utiles pour le comportement visuel et l’UX.
- **Risques :** fragilité liée à l’environnement GUI/headless.
- **Améliorations :** stabiliser les fixtures et réduire la dépendance aux détails visuels.
- **Priorité :** P2.

### `tests/integration/test_tsio2_1700_spline.py`
### `tests/integration/test_example_pipelines.py`
- **Rôle :** tests intégration.
- **Forces :** capturent les vrais workflows.
- **Risques :** lenteur et fragilité des dépendances externes.
- **Améliorations :** mieux isoler les fixtures et réduire la variance.
- **Priorité :** P1.

### `tests/performance/PROCESS_EVENTS.md`
- **Rôle :** doc/process autour des tests perf.
- **Forces :** utile pour les baselines.
- **Risques :** si la procédure n’est pas suivie, elle perd son intérêt.
- **Améliorations :** relier la doc aux seuils réels et au protocole d’exécution.
- **Priorité :** P2.

---

## Fichiers de données et artefacts d’exemple

### `example/sapphire fresnel.xlsx`
### `reference strat.png`
### `Capture d’écran 2026-05-12 145634.png`
### `Capture d’écran 2026-05-12 145734.png`
### `Report_METAL_20260519_174037_RMSE_0.01230.xlsx`
### `reports/*.html`, `reports/*.xlsx`, `reports/*.json`
- **Rôle :** exemples, traces, artefacts de calcul.
- **Forces :** utiles pour comparer et valider.
- **Risques :** bruit dans le dépôt, difficile de savoir ce qui est source versus sortie.
- **Améliorations :** séparer clairement les artefacts reproductibles des sources maintenues.
- **Priorité :** P2.

---

## Recommandation finale

Les fichiers restants sont globalement moins critiques que le noyau, mais ils participent à la qualité d’ensemble.

Le bon ordre d’action est :
1. **outillage et CI**,
2. **tests critiques**,
3. **documentation de référence**,
4. **artefacts et rapports**,
5. **fichiers secondaires d’UX et de support**.
