# Passation CERTUS du 13 novembre 2026

- `master` local est à `6ff1bfb2`. Il contient DESIGN et les 21 mesures RICL. La dernière tête publiée vérifiée est `f30726ad`.
- **DESIGN.** Nettoyage final automatique et polisseur L-BFGS-B puis LM intégrés. Sur trois graines du 50/50, RMSE médiane −24 %, durée médiane +13 %. Validation complète avec le seul échec documentaire connu de `coherence_md`. [Bilan](bilan.md).
- **RICL.** Huit calculs récupérés. Sur le trois-raies traité, MF résolu de 0,016072 % à 0,013366 % à épaisseur optique totale fixée. Le manuscrit LaTeX garde ses chiffres actuels. [Résultats](ricl_lm_check.json).
- **STRAT local-search.** Six fichiers modifiés dans `.claude/worktrees/reprise-057fcd/`, branche `claude/reprise-057fcd` à `6ff1bfb2`. Le nombre de tours est chargé et sauvegardé depuis le JSON. Défaut d’un tour, graines décalées ensuite, arrêt au premier refus. 89 tests ciblés et 1 202 tests oracle passent. C1 tenu sur 9 092 tableaux au bit. Validation complète interrompue pour éteindre le PC. Patch de secours vérifié dans `scratch/memetic_polisher_default/strat_rounds_reprise_complete.patch` au checkout principal.

## Au redémarrage

1. Dans le worktree, lancer `python scripts\preflight.py`, puis `python scripts\orient.py`. Relancer `python scripts\validate_parallel.py --workers 12` avec un nouveau dossier de journaux. Si seuls les écarts connus restent, committer les six fichiers STRAT, puis avancer `master` local. La publication attend l’ordre de l’utilisateur.
2. Faire les essais [U13](../refactor_corridors_2026-11-11/U13_protocole.md) sur écran réel et avec les utilisateurs.
3. Reprendre [U12 B](../refactor_corridors_2026-11-11/U12_specification.md), dans l’ordre STRAT robustesse, DESIGN PGLOBAL, INDEX SPLINE. Vérifier l’interruption puis la reprise au bit par moteur.
