
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
- Renforcer les tests des helpers, invariants et flux # Protocole d'execution du refactoring CERTUS

Ce document verrouille l'ordre d'execution et les garde-fous pour maintenir l'objectif "zero casse".

## Ordre de vagues (verrouille)

1. Vague 2: REWorker (desenclavement des closures restantes).
2. Vague 3: filets de tests unitaires spectral / utils RE.
3. Vague 4: separation structures/utilitaires physiques vs noyaux Numba.
4. Vague 5: harmonisation UI/logger.

## Definition of Done (DoD) globale

- Perimetre strict: uniquement les fichiers de la vague en cours.
- Reversibilite: changements en petits lots, chacun annulable sans effet de bord.
- Non-regression: tests unitaires cibles verts.
- Contrats stables: aucune rupture d'API implicite pour les modules existants.
- Traçabilite: chaque lot documente son objectif et son critere de validation.

## Lots reversibles recommandes - Vague 2

### Lot V2.1
- Introduire des points d'entree de phase (`_execute_phase1_p4_scan`, `_execute_phase2_splines`, `_execute_phase3_shakes`, `_execute_phase4_beam`) avec `self.ctx`.
- Garder les closures existantes en fallback transitoire.

### Lot V2.2
- Basculer `run()` sur les methodes d'instance.
- Conserver la meme orchestration (ordre d'appel, emissions de progression, garde `_stop`).

### Lot V2.3
- Supprimer progressivement les closures redondantes quand la parite fonctionnelle est confirmee.
- Verifier le chemin "staged order" et les cas "skip".

## Couverture minimale requise avant Vague 4

- `tests/unit/test_certus_re_worker_utils.py`
  - `resolve_re_qwot_alphas`: mode schedule off/on + bornage adaptatif.
  - `re_ranking_combined_rmse`: monotonie et positivite.
  - `p2_result_to_correc_tuple`: branches `spline` et `spline_sub3`.
  - `shake_sigmas_adaptive`: bornes `scale_min/scale_max`.
- `tests/unit/test_certus_spectral_preproc.py`
  - preservation des shapes 1D/2D.
  - robustesse des presets d'auto-tuning.

## Garde-fous Vague 4 (_certus_physics_impl.py)

- Interdiction de scinder les noyaux math/Numba marques "DO NOT SPLIT".
- Creation autorisee d'un module de facade pour les structures non-Numba.
- Compatibilite descendante: les imports historiques depuis `_certus_physics_impl.py` doivent continuer a fonctionner.
- Verifier que les classes exposees (`Layer`, `Target`, `NKCache`, `PGlobalOptimizer`) restent resolvables.


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