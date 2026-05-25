# Audit Technique des Modules Spécifiques - CERTUS Suite (2026)

Cet audit détaille la qualité de l'implémentation, les limitations mathématiques et système, et les opportunités d'optimisation pour les modules Reverse Engineering (RE), Stratification (STRAT), Couches Métalliques (METAL) et Spline Index Profiler (SPLINE).

---

## 1. Synthèse des Évaluations des Modules Spécifiques

| Module / Composant | Note | Risque Majeur | Axe Majeur d'Amélioration |
2. | :--- | :---: | :---: | :--- |
3. | **Reverse Engineering (RE)** | **16/20** | Performance (GIL) | Paralléliser les dérivées par différences finies via multiprocessing ou JIT Numba. |
4. | **Spline Index & Corridors (SPLINE)** | **15/20** | Maintenance & CPU | Compiler les noyaux de corridor en JIT (Numba) et découper le fichier UI géant. |
5. | **Couches Métalliques (METAL)** | **16.5/20** | Cohérence Physique | Coupler l'ajustement de $n(\lambda)$ et $k(\lambda)$ par les relations de Kramers-Kronig. |
6. | **Stratification & Suivi (STRAT)** | **17/20** | Concurrence Qt | Remplacer le thread de logs brut Python par un `QThread` ou `QTimer` asynchrone. |

---

## 2. Analyses Détaillées par Module

### A. Reverse Engineering (Note : 16/20)
#### Problème majeur
- **Goulot d'étranglement du GIL (Global Interpreter Lock)** : La phase 2b de l'ajustement RE (`certus_re_workers.py`) exécute le calcul des jacobiennes par différences finies via un `ThreadPoolExecutor` (`_ex_p2`). Cependant, la fonction appelée en parallèle (`_evaluate_p2_fd_derivative`) est une méthode Python pure non compilée. En conséquence, les threads Python restent bloqués par le GIL, rendant la parallélisation inefficace et limitant les performances sur les architectures multi-cœurs.

#### Recommandation (Top 1%)
- Extraire la fonction d'évaluation des différences finies dans une fonction pure JIT-compilée par Numba avec l'option `nogil=True`, ou bien migrer de `ThreadPoolExecutor` vers `ProcessPoolExecutor` (multiprocessing) pour exécuter ces calculs dans des processus système indépendants exempts de contraintes de GIL.

---

### B. Spline Index Profiler & Corridors (Note : 15/20)
#### Problème majeur
- **Absence de compilation JIT et Monolithe de code** : 
  - Les calculs d'enveloppes et de corridors de B-splines (`certus_index_spline_corridors.py`, `spline_profile_corridors.py`) évaluent des milliers de profils d'indices candidats. Cependant, ces modules n'exploitent aucune fonction `@njit` de Numba, ce qui ralentit considérablement la réactivité de l'interface lors de l'exploration interactive des enveloppes d'incertitude.
  - De plus, le fichier d'interface `certus_index_spline_ui.py` fait plus de **15 000 lignes**, ce qui rend toute maintenance ou évolution extrêmement complexe.

#### Recommandation (Top 1%)
- Vectoriser et JIT-compiler les calculs de recherche de corridors de splines sous Numba. Découper `certus_index_spline_ui.py` en sous-modules gérant spécifiquement les différents onglets de l'interface de profilage (visualisation, simulation de bruit, ajustements).

---

### C. Couches Métalliques (Note : 16.5/20)
#### Problème majeur
- **Absence de couplage physique (Kramers-Kronig)** : Les applications `CERTUS_METAL_SINGLE` et `CERTUS_METAL_BILAYER` optimisent de manière indépendante les splines représentant $n(\lambda)$ et $k(\lambda)$ pour le film métallique. Cette indépendance mathématique permet au solveur stochastique d'ajuster des profils d'indices hautement irréalistes (violation du principe de causalité et des relations fondamentales de Kramers-Kronig).

#### Recommandation (Top 1%)
- Au lieu d'ajuster $n$ et $k$ indépendamment, optimiser les paramètres d'un modèle d'oscillateurs physiques (ex: modèle combiné de Drude et de Lorentz adapté aux métaux) et en déduire $n$ et $k$ par construction analytique cohérente, garantissant le respect de la causalité.

---

### D. Stratification & Suivi (Note : 17/20)
#### Problème majeur
- **Emissions de signaux hors-concurrence Qt** : Le worker `WorkerThread` de stratification (`certus_strat_workers.py`) initialise un thread brut Python (`threading.Thread`) pour consommer les statistiques de calcul (`_stats_consumer_loop`). Ce thread brut appelle directement `.emit()` sur les signaux Qt de l'application. Cette pratique est déconseillée dans Qt, car elle contourne la boucle d'événements interne et peut provoquer des comportements indéterminés ou des plantages silencieux sous certaines conditions système.

#### Recommandation (Top 1%)
- Remplacer le thread brut par une boucle de consommation animée par un `QTimer` asynchrone sur le thread principal (GUI), ou utiliser une instance de `QThread` dédiée configurée avec les affinités de signaux appropriées.
