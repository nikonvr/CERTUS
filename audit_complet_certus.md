# Plan de Bataille (CERTUS 2026) : Ce qu'il reste à faire

*Dernière mise à jour : 10 Mai 2026, 21:11:53+02:00*

## Vision Globale
Nous avons atteint le **Score Global de Maintenabilité : A (95/100)** 🟢. 
Le nettoyage des monolithes UI (`_show_smart_init_preview_dialog`) et mathématiques (`_execute_phase2_splines` et `_build_re_run_context`) a été un succès total avec **100% des tests au vert (0 régression)**.

L'objectif de demain est de s'attaquer aux **11 fonctions restantes ≥ 500L**. Ces fonctions sont complexes car elles contiennent des fermetures (*closures*) profondes (optimizer callbacks, handlers d'événements) ou des couplages forts à l'état.

---

## Les Prochaines Cibles (To-Do List)

Voici les cibles prioritaires ordonnées par taille et complexité pour la prochaine session.

| Ordre | Fichier | Fonction | Taille Actuelle | Stratégie d'Extraction | Statut |
|---|---|---|---|---|---|
| **1** | `spline_profile_corridors.py` | `_setup_corridor_context` | 954L | Extraction séquentielle de la configuration vers un *Builder* dédié. | ✅ Fait |
| **2** | `spline_profile_corridors.py` | `compute_regular_grid_rmse_profile` | 950L | Modularisation des 6 closures internes via des *Context Dataclasses*. | ✅ Fait |
| **3** | `spline_workers.py` | `_run_free_knot_stage` | 881L | Réduction des 11 closures restantes via l'extraction de méthodes de classes. | ✅ Fait |
| **4** | `certus_re_workers.py` | `_execute_phase4_beam` | 874L | Ciblage de la logique de couplage profond des états (beam shaping). | ✅ Fait |
| **5** | `CERTUS_INDEX_SPLINE.py` | `_build_basic_step4_mesh_optimizer` | 796L | Extraction du GUI builder dans une sous-classe ou un *Builder Pattern*. | ✅ Fait |
| **6** | `spline_workers.py` | `_run_single_spline_stage` | 729L | Isolement des callbacks d'optimiseurs (`PGlobal`). | ✅ Fait |
| **7** | `CERTUS_RE.py` | `_show_re_results_window` | 617L | Application du script AST (comme pour SmartInit) pour extraire les closures GUI. | ✅ Fait |
| **8** | `certus_spline_report.py` | `build_report` | 557L | Continuation de la modularisation de l'écriture des fichiers (déjà 4 helpers extraits). | ✅ Fait |
| **9** | `spline_profile_corridors.py` | `_corridor_profile_walk_side` | 546L | Extraction de la grosse closure interne (96L). | ✅ Fait |
| **10** | `spline_pipeline.py` | `worker_spline_auto_clean_knots` | 527L | Élimination des 3 micro-closures restantes pour franchir le seuil des 500L. | ✅ Fait |
| **11** | `CERTUS_RE.py` | `load_reverse_engineering_from_path` | 516L | Découplage du script PyQt d'évaluation. | ✅ Fait |

> [!NOTE]
> **Intouchables :**
> - `_compute_gradient_analytic_kernel` (584L dans `_certus_physics_impl.py`) est un noyau **Numba @njit**. Il ne doit **pas** être modifié.
> - Les cibles déjà traitées (SmartInit, Phase 2, Phase 1 RE) ne sont plus affichées pour se concentrer sur l'avenir.

---

## Feuille de Route et Méthodologie

Pour les prochaines sessions, nous maintiendrons l'approche chirurgicale et conservatrice qui a fonctionné jusqu'à présent :

1. **Analyse de Dépendances Automatisée :** 
   Utiliser les scripts `ast` pour lister précisément quelles variables locales (`reads`/`writes`) sont capturées par les closures géantes.
2. **Context Dataclass Pattern :** 
   Créer des structures `@dataclass` (ex: `CorridorContext`, `REMseContext`) pour injecter proprement l'état dans les méthodes extraites sans polluer l'espace de noms.
3. **Moteurs AST sur-mesure :**
   Appliquer des scripts de transformation sur-mesure (comme `ext_p2.py`) pour réécrire massivement les fichiers sans se heurter aux erreurs de manipulation de regex manuelles.
4. **Validation Systématique :** 
   Maintenir la rigueur absolue via `pytest`. Le score doit rester à **0 régression** à chaque étape validée.
