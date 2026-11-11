# REPRISE — refactoring des corridors et audit UX

Fichier de reprise : tout ce qui est fait, en cours et à faire. Il est mis à jour à chaque étape, avant de passer à la
suivante. En cas de coupure, on repart d'ici. Le détail des phases est dans `REFACTOR_PLAN.md`, même dossier.

## Où est le travail

- Branche `claude/certus-refactor-audit-6cd1fc`, dans le worktree `.claude/worktrees/certus-refactor-audit-6cd1fc`.
- Ce dossier, `reports/refactor_corridors_2026-11-11/` : le plan, ce fichier, l'instantané de référence
  (`reference_snapshot.json`), les manifestes des phases (`manifests/`).
- Rien n'est poussé. Pousser publie le dépôt : seulement sur ordre.
- La copie `REFACTOR_PLAN.md` restée à la racine du checkout principal est périmée, et y fait échouer deux contrôles :
  à supprimer là-bas.

## Reprendre après une coupure

1. `python scripts/preflight.py` doit finir par `PREFLIGHT=GO`.
2. `git status -sb` puis `git log --oneline -n 8` : comparer à « Fait » et « En cours » ci-dessous.
3. Si des fichiers sont indexés mais pas commités, ils appartiennent à la phase « En cours » : relancer ses tests (liste
   dans la phase, au plan), puis la garde, puis la validation, avant de commiter.
4. Garde : `python scripts/refactor_guard.py snapshot --out <fichier temporaire>`, puis
   `python scripts/refactor_guard.py compare reports/refactor_corridors_2026-11-11/reference_snapshot.json <fichier temporaire> --manifest reports/refactor_corridors_2026-11-11/manifests/phase_1.json`
   (ajouter un `--manifest` par phase faite). Attendu : `GUARD=OK`.
5. Validation complète : `python scripts/validate_parallel.py`, environ 25 minutes, rien d'autre en même temps.
   **État connu** : `coherence_md` sort en erreur sur 3 commandes mortes de documents de campagne (laissé tel quel sur
   décision) ; un test qui chronomètre peut être rouge en parallèle et vert seul. Tout autre rouge est nouveau.

## Consignes reçues de 👤 (2026-11-11)

- Enchaîner les phases sans s'arrêter entre elles.
- Trancher soi-même les questions ouvertes, le plus intelligemment possible, et consigner la décision (plan, section 4).
- Inscrire toute tâche faite ou à faire dans ce fichier de reprise.
- Viser une UX « top 1 % mondial » : audit UX complet, à ajouter à l'audit (plan, section 5).

## Fait

| Quoi | Commit |
|---|---|
| Audit statique et plan (`REFACTOR_PLAN.md`), arbitrages Q1 à Q5 et Q16 | dans `211d561b` |
| Correctif ruff B905, `zip(..., strict=False)` dans un script de campagne | `9d011d68` |
| Correctif échappement invalide, chaîne brute dans un script de campagne | `15d518aa` |
| **Phase 0** : `scripts/refactor_guard.py`, ses 13 tests, instantané de référence, plan déplacé ici | `211d561b` |
| **Phase 1** : état déclaratif, contrats, 52 tests, manifeste ; toutes les questions ouvertes tranchées (plan, section 4) | `0e3d4b57` |
| **Audit UX** complet des 11 modules : plan, section 5 (constats A, B, C et feuille de route U1 à U13) | `74de941e` |
| **Phase 2a** : les trois constantes corridor n'ont plus qu'une définition | commit suivant `74de941e` |

## En cours

Rien : tout ce qui est fait est commité. La prochaine tâche est la première de la liste ci-dessous.

## À faire, dans l'ordre

1. Phase 2 du plan, suite : 2b `_apply_fixed_log_k_axis`, 2c constantes de fenêtre, 2d clés du
   smart-init, 2e classes `SmartInitPayload` en double.
2. Phase 3 : extraction des tranches 3a, 3b, 3c, 3d.
3. Phase 4 : tracé RMSE(d).
4. Phase 5 : 5a, 5b, 5c, puis 5d (les 8 fonctions statiques appelées par le mandataire).
5. Phase 6 : 6a garde-fous étendus aux autres fenêtres, 6b `_UIMixin` hors du MRO, 6c état initialisé dans `__init__`.
6. Phase 7 : 7a, 7b (arêtes entre familles).
7. Phase 8 : clôture. Phase 9 : couture de test périmée (Q5).
8. Phase 10 : correctifs révélés par l'audit, un commit chacun, chacun avec un test qui échoue avant (Q17, Q13, Q11, Q12).
9. Feuille de route UX, plan section 5.5 : U1 à U5 d'abord (défauts visibles) ; dans les fichiers du groupe INDEX SPLINE,
   seulement après la Phase 8. Hors de ce groupe, elles peuvent commencer quand on veut.
