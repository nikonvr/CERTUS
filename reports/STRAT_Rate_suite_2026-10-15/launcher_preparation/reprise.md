# Lanceurs R0/R2 bornés — préparation du15 octobre2026

Les copies actuelles sont préparées et contrôlées statiquement ; **aucune vérification runtime de ces copies, aucun R0 ni R2 n’a encore été exécuté**. Ruff passe. Le contrôleur général RMSE tourne séparément ; ne pas lancer une autre validation ni une mesure scientifique pendant cette attente.

Autorisation : correctif RMSE puis programme borné R0–R6,24 processeurs logiques/0xffffff/Normal/23threads. Aucune nouvelle échéance horaire n’est inventée. Les anciens lanceurs, worktrees et gardes demeurent inchangés.

- `scratch/rate_fixed_replay_R0_bounded.py` : un contrôle des trois plans,300tirages/base101/consensus41/42/43 ; transport Workerfloat32 inchangé. Le verdict exige exactement12 appels physiques de300tirages ; snapshots du lanceur, de la garde et du helper conservés.
- `scratch/rate_native_pipeline_probe_bounded.py` : une seule base native480/240/six tours, préfixe0, équilibragefalse ; R0 et vérification passiveGO obligatoires, mêmes sources.
- `scratch/verify_rate_native_pipeline_trace_bounded.py` : contrôle passif de la factory réelle et de la restauration après exception, sans dépôt. Il doit être exécuté après validation généraleGO, dans le nouveau contexte.
- `scratch/rate_suite_bounded_guard.py` : autorisation actuelle, toutes les commandes requises terminéesGO, sources inchangées, A2complète et aucun autre processus Python. Une réservation permanente par emplacement R0/R2 ; un verrou commun n’est libéré que par son propriétaire. Après échec, conserver la réservation et auditer la reprise ; aucun second essai silencieux.

[Empreintes actuelles](preparation_current_03.json), [comparaison AST](static_review_02.json), [protocole R0](../protocol_R0_bounded.json), [plans complets inchangés](../selected_fixed_plans.json). Les fonctions de calcul R0 et le bloc nominal/Worker/évaluation externe sont identiques à l’AST ; générateur et observateur R2 inchangés. Les différences portent sur les gardes, ressources, provenance et assertions de contrôle. Les gardes attendent désormais `full_validation_02/validation.json` ; la première tentative échouée reste conservée.

## Prochaines opérations, dans cet ordre

1. Vérifier la fin du contrôleur général et de son enfant, toutes les commandesGO et les8 empreintes validées. En cas d’échec, conserver les journaux et expertiser ; aucun lancement scientifique.
2. Créer un nouveau worktree géré àHEADda1af082 et y transférer les5 sources exactes du candidat seulement aprèsGO. Ne pas modifier campagne-a2/rate-equilibre. Refaire preflight puis consigner le HEAD, les chemins modifiés, les SHA, la clé de cache, le diff et le lien vers la validation dans `../reference_context.json`.
3. Contrôler les rejets des nouvelles gardes et leurs quotas avec `scratch/verify_rate_suite_bounded_guard.py --output reports/STRAT_Rate_suite_2026-10-15/guard_verification`, sans toucher les réservations réelles ; les fixtures synthétiques sont conservées. [Préparation de cette vérification](guard_verification_prepared.json). Vérifier l’observateur passif, sauvegarder `../observer_verification/verification.json`. Les SHA doivent correspondre aux copies actuelles ; toute modification ultérieure impose une nouvelle vérification.
4. Faire les aperçus CLI puis le seul contrôle R0, sortie canonique `../R0_control/`. Vérifier le verdict, les3 plans complets, les12 appels et les scores attendus ; ne pas réécrire les attentes si un point fixe dérive.
5. Une fois ces preuvesGO et la machine libre, lancer la seule trace native R2, sortie canonique `../R2_native_base/`, tag unique. Vérifier ses ressources et sauvegardes, puis analyser avant de choisir un facteur R3.
6. Continuer les quotas/critères du guide ; aucune activation d’un nouveau défaut, aucun commit/push/publication.

Le contexte candidat n’est pas un feu vert : `../source_candidate_before_validation_end/candidate.json` porte explicitement la validation encore en cours. Les scripts à garde bornée ne sont pas une commande de reprise des anciennes mesures.
