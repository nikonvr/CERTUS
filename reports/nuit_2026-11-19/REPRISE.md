# Nuit du 2026-11-19 — reprise

Ordre de 👤 (2026-11-19 ~21 h) : faire tous les lots de `docs/CHANTIERS_RESTANTS.md` en autonomie complète jusqu'au
2026-11-20 10 h ; l'IA tranche. Arbre : worktree `.claude/worktrees/nice-haslett-744eaa` (dans le dépôt Drive),
branche `claude/repertoire-courant-fb8caf`, départ `0d95cc60`. **Aucune poussée** (non ordonnée).

## Décisions de l'IA (motif)

- Un commit par changement (C3), local ; validation entre lots.
- 👤 ajoute : contrôle toutes les 30 min (job cron de session `aca40f15`, 13 et 43 de chaque heure) ; autres
  améliorations permises si besoin.
- 1a : `mypy`, `pytest-benchmark` installés dans le Python 3.15 global (pip) pour vérifier localement ; `pytest-xdist`
  y était déjà (3.8.0). `mypy` rendait 30 erreurs dans 11 fichiers : corrigées par annotations seules (`cast`,
  `assert` sur un `None` qui plantait déjà, renommage local), prouvées par `c1_diff.py HEAD`, avant de le rendre bloquant.
  `bench_kernels` reste non bloquant (base mesurée sous Windows, CI sous Linux).

## Lots

- [x] 1a CI (D110) : `f9ae8766` types (C1 tenu, 9172 tableaux), `82f9f558` deps + locks (ajouts seuls),
      `6dccffe7` lint.yml, `41afbdae` mypy bloquant. Validation complète lancée (`/tmp/val_1a.txt`).
      Préparé pour 1b : `tests/unit/test_unphysical_inputs_are_refused.py`, mis de côté dans `/tmp/pending_1b/` pendant
      la validation (rouge attendu) — à remettre dans `tests/unit/`.
  Validation 1a : `VALIDATION=GO` sur `41afbdae` (oracle 1252, unit 6427, ui 1704, rest 322, performance 41 : +11 car
  `pytest-benchmark` est installé).
- [ ] 1b ValueError entrées (D108/D109/D114) — rouge vérifié (18 échecs, 7 verts) ; gardes dans `certus_inputs.py`
      (`require_non_negative_thickness`, `require_non_negative_extinction`, `require_positive_substrate`,
      `require_physical_substrate`) branchées dans `calculate_RT_vectorized_real`, les 2 enveloppes obliques (d, n_sub
      seulement : indices des couches trop coûteux par appel, mesuré 0,15/1,5 ms), `get_nk_from_spline`,
      `xyz_from_spectrum` (fini + croissant ; couverture 380–780 non exigée : extrapolation constante gardée),
      `optim_prepare_stack_nk_back` (tous les matériaux, substrat, épaisseurs arrière). Décision : pas de garde par appel
      dans les boucles `cost_numba_fast` (les objectifs DESIGN rendent déjà la pénalité 1e30 pour un vecteur non fini).
      C1 tenu (9172) ; commit `053835d8`. Validation : NO-GO, 2 échecs réels : (1) montage de
      `test_design_compute_oblique_error_common_no_weight` avec substrat n = 0 → indices physiques (1,52 / 1,9), corrigé ;
      (2) `tests/mutation_baseline.json` : `certus_inputs.py` passe de 63 à 83 fautes → `mutation_pilot.py` relancé
      (`/tmp/mut_inputs.txt`) : 12 survivants dans les nouvelles gardes (les tests de bout en bout ne nomment pas le
      module) → tests de bornes directs, 12 tués, base 83/82/1, score 0,988. Commits `1d62746a` (montage), `73075f7a`
      (bornes + base). Validation relancée (`/tmp/val_1b2.txt`).
  Validation 1b : `VALIDATION=GO` sur `73075f7a` (2 artefacts de charge `test_the_default_pytest_run_is_quiet`, verts
  seuls en série).
- [x] 1b
- [ ] 2a retrait plancher ε1 ≥ 1 — rouge vérifié (`test_epsilon1_has_no_floor.py`, renommé depuis
      `test_epsilon1_gradient_follows_the_floor.py` : 7 échecs) ; 4 sites retirés (`epsilon1_TL_analytic`,
      `_epsilon1_TL_overdamped`, `epsilon1_gradient_overdamped`, `_compute_epsilon1_gradient_kernel`) ; tests KK mis à
      jour (comparaison à toute énergie : passe à 1e-3 jusqu'à −38,8). `c1_diff` lancé pour mesurer l'étendue
      (`/tmp/c1_2a.txt`) : 9172 identiques, mais le corpus n'appelle pas Tauc-Lorentz (INDEX seul l'utilise) → mesure
      directe [`p2a_floor_reach.py`](p2a_floor_reach.py) ([sortie](p2a_floor_reach.txt)) : sur les 11 ajustements
      certifiés, le plancher n'agissait dans la bande que pour `mesures-c1b-sio2` (186–800 nm : 29/2000 points sous
      224 nm) ; les 10 autres ont ε1 ≥ 2,17. `bench_examples.py index` (H400) : RESULT 0,002543 avant (stash étiqueté,
      réappliqué puis supprimé), 0,002558 après (INDEX non reproductible). Commit `37a6bfef` (amendé : le premier
      `6a814638` n'avait que le renommage). Validation lancée (`/tmp/val_2a.txt`).
  Validation 2a : 1 échec réel, le cliquet `fichiers_longs` (`gradient_analytic.py` 1655 → 1653) : plafond réécrit
  (`metrics.py --dette`) et amendé dans le commit → `230fadff` ; tout le reste vert.
- [x] 2a
- [ ] 2b `strat_local_search_fresh_id` actif — rouge (`test_the_fresh_id_is_on_by_default`) ; levier `defaut=True`,
      statut `VALIDE`, worker `params.get(..., True)` ; `test_strat_leviers.py` lit aussi le worker (là où le noyau lit
      ce réglage) ; ligne d'exception C1 ajoutée dans `ETAT.md` §3. Tests ciblés lancés (`/tmp/vc_2b.txt`).
  Tests ciblés : 2813 verts, 2 artefacts de charge connus verts seuls. Commit `4fd783cb`.
- [x] 2b
- [x] 2c SUBSTRATE `sellmeier_ir_pole` : [bilan](bilan_2c_sellmeier_ir_pole.md), commit `37564e45`. n de T seul : courbes
      identiques (bruit 1,5e-2 à 8,5e-2) ; NAVG : pôle IR retenu, HPFS 2,1e-3 → 9,2e-4, saphir 1,78e-2 → 2,6e-3.
- [ ] 2d base dépôts — (b) option `tlu_full_range` (inactive) : `index_uses_two_stage` + `TLU_TWO_STAGE_MAX_NM` dans
      `certus_index_config.py`, 2 sites UI, `OptimizationConfig.tlu_full_range`, drapeau `--tlu-pleine-plage` du banc,
      README ; tests rouges puis verts (10) ; C1 tenu (9172) → `f326a4a1`.
      (a) appariement T/R lu (pas stocké : les identifiants de `references_index.json` restent) : 13 paires mutuelles,
      `paired_entry` + `write_side_by_side` (sortis du banc), case « autre voie » décochée par défaut dans la boîte de la
      base, INDEX charge côte à côte → `de529a94`.
      (c) dépôt dans RE : `certus_depots_re.write_re_workbook` + `scripts/re_depuis_depot.py` ; la fenêtre RE charge le
      classeur (test). **Décision** : référence normalisée (10/11, T/T_sub) refusée avec motif — dénormaliser demande un
      modèle de substrat, à trancher par 👤 → `9c83fe17`. Validation : NO-GO, 4 échecs réels dans ces fichiers
      (script sans `ensure_numba_cache_dir`, `workbook.save` direct → `atomic_save_workbook`, `\c` dans une docstring,
      fenêtre RE hors `qt_lifecycle`) corrigés et amendés → `343c7473`. Validation : `VALIDATION=GO` (5 artefacts de
      charge verts seuls en série), 00:43.
- [x] 2d
- Ordre décidé pour la fin de nuit (tout en série, aucune mesure parallèle) : 2d → validation → lot 4 (chrono SPLINE) →
  lot 3 (6 bancs ≈ 3,1 h au 21/10 + 99c graine 42 seule ≈ 53 min, décision : temps) → gel → docs → validation finale.
- [ ] 3 repères et gel — pilotes prêts dans `lot3/` (copies des pilotes du 21/10 et du 24/10 : dossier, souches
      2026-11-20, date limite de lancement 06:30 UTC ; 99c graine 42 seule, cache `reports/intervalles_99c_nuit1120`).
      Le pilote exige un arbre suivi propre : tout commiter avant.
- [ ] 4 SPLINE — l'étage « nœuds libres » n'est plus dans le pipeline (log [03/09]) ; il ne tourne qu'en passe 2
      d'Auto-Best (`worker_auto_best_split_knot_refinement`). Sonde [`p4_spline_chrono.py`](p4_spline_chrono.py) prête
      (Smart Init chronométré dans le run, passe 2 à part), à lancer après la validation.
      **Bogue trouvé** : la passe 2 d'Auto-Best plantait toujours (`IndexError` dans `phase_progress_bounds`) : depuis
      `0b7f4f0d`, le contexte gardait `phase_maxfun_list=[]`. Test rouge
      `test_auto_best_pass_two_gets_its_phase_budgets.py` (rouge vérifié), correctif dans `_run_free_knot_stage` (vert).
      Commit `ba8e8290`. Mesure ([bilan](bilan_4_spline_chrono.md), `7a6fca38`) : Smart Init 1 ms (0 %) ; passe 2
      6,99 s (70,5 %) TOTAL, 34,15 s (92,4 %) TSIO2 → seuil franchi ; gain RMSE nul (TOTAL), −1,5 % (TSIO2).
      **Décision de l'IA** : dérivées analytiques NON écrites cette nuit — l'objectif recolle les maillages n et ln k
      (`_snap_nk_mesh_sol3_split`, non lisse) : gradient risqué (erreur silencieuse), testable seulement après les
      bancs, juste avant le gel ; gain mesuré faible. Options pour 👤 : (a) jac hybride (d et valeurs analytiques, σ par
      DF : ~50 % d'évaluations en moins), (b) budgets de la passe 2 réduits (16 000 / 40 000 évaluations), (c) statu quo.
- [~] 4 : mesuré, bogue corrigé, dérivées en attente de 👤.
- Lot 3 lancé 00:52 (`lot3/sortie_6bancs.txt`, puis `lot3/sortie_99c.txt`), HEAD `7a6fca38`.
  48c premium : valide, SEEL 0,1820 nm (21/10 : 0,1721 ; juge de paix 16/11 : 0,1704), 1215 s.
  75c fast : valide, SEEL 0,2142 (21/10 : 0,2225), 1934 s. 35c deep : valide, SEEL 0,3466 (21/10 : 0,4907, −29 %),
  576 s — **meilleur que prévu (§11)** : DESIGN_JSON juste, 0/1515 éliminé, RANK00 = LOCAL_SEARCH (la recherche locale
  avec garde date du 22/10, après ces repères) ; à signaler à 👤 sans en affirmer la cause. Les trois RANK00 portent un
  identifiant neuf (90xx50000 : `fresh_id` actif).
  36c deep livré : valide, SEEL 0,3628 (21/10 : 0,3238, **+12 %**, au-delà des ~8 % de bruit), 610 s. r75x2 natif en
  cours depuis ~02:10 (63 min au 21/10), puis rampes (~61 min), puis 99c (~53 min) : fin estimée ~05:30.
  r75x2 natif 1 nm : valide, SEEL 0,4878 (21/10 : 0,5833, −16 % ; la garde au corridor du 22/10 donnait −13,3 %),
  3847 s. Rampes : 0,5157 (21/10 : 0,5092), 3901 s. 99c graine 42 : 0,544 (24/10 gr. 42 : 0,597), 4 tranches
  déposables. Fin 04:21. [Bilan](lot3/bilan.md), commit `183ebcd9` (journaux `.log` 425 Mo non commités).
  Constat : `DYN-ALERT` compare la sentinelle `dyn = −1` (couche Rate) → fausses alertes massives, et `avg_dynamics`
  moyenne la sentinelle (`_worst_layer_swing` faux) : diagnostic seulement, correctif proposé à part (non fait).
- Gel : construit depuis ce worktree, sorties dans `%TEMP%\certus_gel_1120` (pas de 420 Mo synchronisés par Drive ;
  le clone hors Drive du 17/11 est désormais interdit). Lancé ~04:35 sur `183ebcd9`.
  1er essai : `VCOMP140.DLL` non résolu (System32 absent du `PATH` du shell de l'agent) → refusé par `release_checks`.
  Reconstruit avec System32 : `release_checks --check-frozen --check-frozen-run` **PASSED** ([bilan](gel/bilan.md)).
- [x] 3 (bancs `183ebcd9`, gel vert).
- Docs : `CHANTIERS_RESTANTS.md` réécrit (ouverts : 5 DYN-ALERT, 6 écarts 35c/36c, 4 SPLINE ; décisions 👤),
  `ETAT.md` §1, §2, §5 → `fea0c0b2`. Validation finale : NO-GO, cliquet de dette (`_run_free_knot_stage` 678 → 682,
  `spline_workers.py` 1974 → 1978, ajoutés par `ba8e8290`) → correctif réécrit à longueur nulle (budgets directement
  dans le contexte) `36f636fe` ; comportement identique (le gel `183ebcd9` porte la version précédente, équivalente).
  Validation finale : `VALIDATION=GO` sur `36f636fe` (5 artefacts de charge verts seuls en série), 05:27 ; §0 à jour.
- [x] docs et validation finale. Suite décidée : chantier 5 (DYN-ALERT) si le temps le permet, avec revalidation.
- [ ] 5 DYN-ALERT (05:35) : rouge (`test_rate_layers_are_not_counted_as_flat_layers.py`) ; `average_monitored_dynamics`
      (njit, sentinelle −1 exclue, même ordre de somme), `dynamics_alerts` (pure, pas de ligne sur la sentinelle),
      `_worst_layer_swing` sur les couches surveillées ; plafonds de dette abaissés (tâche 794 → 782 lignes, 73 → 69).
      6 tests verts, mypy 0. `c1_diff` 1er essai : 9 tableaux `strat.batch#…#1` (avg_dyns) à 1 ulp (somme
      conditionnelle sous fastmath) → boucle d'origine gardée pour le cas sans sentinelle : C1 TENU (9172). Commit
      `b17a5844` — **fait par erreur avec 1 test rouge** (commande chaînée par `;`) : à identifier par la validation
      (`/tmp/val_ch5.txt`) et à amender. → 2 échecs : `dynamics_alerts` absent de la façade
      `certus_strat_robustness` ; égalité exacte d'une moyenne sous fastmath → tolérance 1e-15 ; amendé `ce4adfba`.
- **Décisions de 👤 (2026-11-20, ~05 h 45)** : fusion locale dans `master` (sans pousser) une fois tout vert ; RE garde le
  refus des références normalisées ; SPLINE : réduire les budgets de la passe 2 ; chantier 6 à instruire maintenant.
- [x] 6 instruit ([bilan](bilan_6_ecarts_35c_36c.md)) : les deux écarts viennent du contrôle d'acceptation de la
  recherche locale (2 graines, arrêts), pas d'ELITE (−9 %, −1 %). Décision ouverte pour 👤 : plus de graines au contrôle,
  ou publier le meilleur ELITE à côté du RESULT.
- [x] 4 budgets : sonde [`p4_pass2_budgets.py`](p4_pass2_budgets.py) ; facteur 0,25 retenu (TSIO2 8,4 s au lieu de
      33,9 s, 84 % du gain ; TOTAL inchangé) → `babd2f9a` ; chantier 21 archivé. Docs (ETAT §3, §5 ; CHANTIERS :
      reste le 7, contrôle de la recherche locale, à 👤). Reste : validation complète, puis fusion locale dans `master`. **Ne toucher aucun
  fichier suivi pendant les bancs** (le pilote exige un arbre suivi propre avant chaque banc).
- Docs à appliquer après les bancs : `CHANTIERS_RESTANTS.md` (1a, 1b, 2a, 2b, 2c, 2d faits ; 3 remesuré ; 4 en attente
  de 👤 ; 2d normalisation RE à 👤), `ETAT.md` §0 (validation), §1 (base de dépôts : RE possible pour les absolues ;
  qualité : mypy bloquant), §2 (repères remesurés), §5 (2 décisions pour 👤 : dénormalisation RE, dérivées passe 2).
- [ ] validation complète, docs
