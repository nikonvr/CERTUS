# Chantier 7 — reprise

Décision de 👤 (2026-11-20, ~06 h 50) : « les deux » — (1) publier le meilleur ELITE à côté du RESULT, (2) plus de graines
au contrôle d'acceptation de la recherche locale. Session détachée de celle de la nuit ; worktree `sad-perlman-32940e`,
branche `claude/busy-visvesvaraya-1d8b72`, départ `80f06867`. Aucune poussée sans ordre de 👤.

- [x] (1) `STRAT_BEST_ELITE=` dans `scripts/bench_examples.py` (`80f06867`).
- [ ] (2) `strat_local_search_check_seeds` (défaut 2 = graines 7 100 003 et 7 100 011, au pas 8 au-delà) :
      `check_seed_offsets`, `check_seeds_setting`, `check_seeds_for` (core), worker, `collect_params` et
      `_collect_config` (une ligne chacun, fichier à son plafond), levier `RESERVE`. Tests rouges vérifiés.
      Plafond `certus_strat_ui_state.py` 1662 → 1661. Tests JSON (3), mypy 0, C1 tenu (9172) → `a059cf47`.
- [x] (2) réglage.
- [x] Mesure (lancée 07:24, finie 08:04 ; [bilan](bilan.md) : verdict du plan final inchangé à 6 graines, repli du 36c refusé, RESULT +13 % ; témoin pas au bit, population variable : chantier 8), [script](run_mesure.sh), `sortie_mesure.txt`) : témoin 36c 2 graines, 36c 6 graines, 35c
      6 graines. Au lancement, 2 processus python d'une autre session (relecture HTML ?) tournaient peut-être : durées
      sous réserve, RESULT déterministe.
- [x] Bilan, docs (CHANTIERS : 7 mesuré, 8 ouvert ; ETAT §3, §5) → `80f13adf` ; validation `VALIDATION=GO` (1 artefact de charge vert seul en série), ETAT §0.
- [ ] Vraie fusion locale dans `master` (dossier principal), sans pousser.
- Note de la session « Répertoire courant » (07:30) : `master` local est à `16855e2e` (relecture HTML : pages/*.html,
  reports/relecture_html_2026-11-20/, non poussée). Fusion finale = vraie fusion `git merge` (pas d'avance rapide) ;
  pas de rebase, pour garder `a059cf47`, le commit mesuré, dans l'historique.
