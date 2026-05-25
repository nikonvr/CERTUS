# Plan Global de Mise à Niveau (> 18/20) - CERTUS Suite

Ce document décrit le plan d'implémentation complet pour lever les limitations identifiées lors des audits et faire passer tous les modules de la suite CERTUS à une note strictement supérieure à 18/20.

---

## User Review Required

> [!IMPORTANT]
> Ce plan implique des changements architecturaux significatifs (découpage modulaire, introduction de modèles d'oscillateurs physiques pour la causalité, et parallélisation multiprocessus). Chaque étape sera réalisée de manière incrémentale et validée par les tests unitaires.

---

## 1. Concurrence & Robustesse Système

### A. Assainissement Concurrence STRAT
- **Fichier** : [certus_strat_workers.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_strat_workers.py)
- **Objectif** : Éliminer l'émission de signaux Qt depuis un thread système brut Python (`threading.Thread`).
- **Plan** : 
  - Supprimer la création de `threading.Thread` dans `_run_step_23_full`.
  - Mettre en place un `QTimer` asynchrone sur le thread principal qui interroge régulièrement la file d'attente de statistiques (`stats_queue.get_nowait()`) sans bloquer l'interface.

### B. Validation de Schémas au Runtime
- **Fichier** : [certus_result_schema.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_result_schema.py)
- **Objectif** : Intercepter les corruptions ou incohérences de fichiers projets JSON au chargement pour éviter des `KeyError` au milieu du rendu GUI.
- **Plan** : 
  - Définir un validateur de schéma léger à l'aide de `jsonschema` ou convertir les dictionnaires typés statiquement en modèles structurels avec vérification dynamique.
  - Lever une exception claire `CorruptedProjectError` interceptée par le framework d'erreurs UI.

### C. Persistance Asynchrone des États
- **Fichier** : [certus_reset_framework.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_reset_framework.py)
- **Objectif** : Décharger le thread GUI des I/O d'écriture de fichiers d'historiques lourds.
- **Plan** : 
  - Implémenter un worker d'écriture asynchrone (`QRunnable` + `QThreadPool`) dédié à la sérialisation des états de session.

---

## 2. Performances Algorithmiques & Calculs

### A. JIT-compilation des Corridors Spline
- **Fichiers** : [certus_index_spline_corridors.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_index_spline_corridors.py) & [spline_profile_corridors.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/spline_profile_corridors.py)
- **Objectif** : Éliminer la latence lors de l'évaluation interactive des enveloppes de profil d'indice.
- **Plan** : 
  - Extraire et vectoriser les calculs de boucles d'évaluation de spectres de corridors en fonctions pures NumPy.
  - Décorer ces fonctions avec `@njit(cache=True, fastmath=True, parallel=True)` pour compiler le code machine et paralléliser sur tous les cœurs.

### B. Bypasser le GIL lors de l'Optimisation RE
- **Fichier** : [certus_re_workers.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_re_workers.py)
- **Objectif** : Permettre aux calculs de jacobiennes de s'exécuter à 100% en parallèle.
- **Plan** : 
  - Remplacer `ThreadPoolExecutor` par un `ProcessPoolExecutor` dans `_execute_phase1` et `_evaluate_p2_fd_derivative` pour distribuer les évaluations de dérivées dans des processus système indépendants.
  - Alterner avec une approche JIT Numba compile `@njit(nogil=True)` sur les noyaux mathématiques sous-jacents.

---

## 3. Rigueur Physique & Modélisation

### A. Intégration de la Causalité de Kramers-Kronig (METAL)
- **Fichiers** : [CERTUS_METAL_SINGLE.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/CERTUS_METAL_SINGLE.py) & [certus_metal_common.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_metal_common.py)
- **Objectif** : Empêcher le solveur de produire des profils métalliques $n(\lambda)$ et $k(\lambda)$ physiquement impossibles.
- **Plan** : 
  - Restreindre l'espace de recherche de l'optimiseur de constantes de métaux à l'ajustement des paramètres d'un modèle d'oscillateurs (ex: Drude + Lorentz).
  - Calculer analytiquement $n(\lambda)$ et $k(\lambda)$ à partir des constantes diélectriques complexes $\varepsilon_1(E)$ et $\varepsilon_2(E)$ générées par le modèle physique, garantissant la cohérence KK interne.

### B. Barrières de Contraintes Régulières
- **Objectif** : Stabiliser la convergence locale L-BFGS-B près des bornes physiques ($k \ge 0$, $d \ge 0$).
- **Plan** : 
  - Substituer les pénalités simples de barrière dure par une barrière logarithmique continue et dérivable ($-\mu \log(x - x_{min})$).
  - Réduire progressivement le coefficient de température $\mu$ à chaque itération du solveur global (méthode de barrière adaptative).

---

## 4. Architecture logicielle

### A. Découpage du Monolithe Spline UI
- **Fichier** : [certus_index_spline_ui.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_index_spline_ui.py)
- **Objectif** : Rendre le code maintenable et lisible en éliminant le fichier monolithique de 15 000 lignes.
- **Plan** : 
  - Extraire la logique d'onglets et de contrôles Qt dans des modules distincts : `spline_tab_visualizer.py`, `spline_tab_corridors.py`, `spline_tab_presets.py`.
  - Maintenir un orchestrateur central minimal `CertusIndexSplineApp` gérant uniquement la coordination des signaux et l'état global de session.

### B. Séparation des Gabarits de Rapports
- **Fichiers** : [certus_spline_report.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_spline_report.py) & [certus_reports.py](file:///c:/driveFL/couches%20minces%202026/CERTUS/2505/certus_reports.py)
- **Objectif** : Rendre les rapports éditables et lisibles en sortant le HTML/JS du code Python.
- **Plan** : 
  - Créer un répertoire `resources/templates/`.
  - Extraire les gabarits HTML bruts dans des fichiers de ressources statiques séparés.
  - Charger et interpoler ces gabarits dynamiquement à l'aide de marqueurs ou via un moteur de templating léger lors de la génération du rapport final.
