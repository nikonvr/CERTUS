# Plan des corrections — audit du 2026-11-15 (reprise prête à exécuter)

## 0. Démarrer (nouvelle session, même PC, autre compte possible)

1. Avancer la branche de la session sur `claude/claude-code-question-0aa978` (`git merge --ff-only claude/claude-code-question-0aa978`).
2. `python scripts\preflight.py` → `PREFLIGHT=GO`.
3. Lire la fin de `reports/audit_general_2026-11-14/REPRISE.md` (dernières lignes datées) puis ce fichier. Rien d'autre :
   les détails de chaque défaut sont ci-dessous ; `a_verifier.md` et `contre_verification.md` seulement en cas de doute.

## 1. Méthode (décidée avec 👤 : corrections groupées ; commits après tests ciblés, validation complète avant toute fusion)

Par groupe : (1) écrire tous les tests rouges ; (2) **un** passage des seuls nouveaux tests → ils doivent échouer ;
(3) corriger ; (4) `python scripts\verify_changed.py --c1` (tests ciblés par le graphe d'imports + `c1_diff` si noyau) ;
(5) `python -m ruff check .` ; (6) **un commit par défaut** (message : défaut, mécanisme, chiffre, « the new test fails
on the old code », résultats). Une ligne datée dans `REPRISE.md` par groupe.

Pièges déjà rencontrés : fichiers longs sous cliquet (`tests/architecture_debt.json`, `fichiers_longs`) — un fichier
au plafond ne doit pas grandir : sortir le code dans un petit module, ou compacter ; s'il raccourcit, baisser son
plafond dans le même commit. Ruff I001 (ordre des imports) dans les tests. Ne jamais chaîner `ruff ; git commit` :
s'arrêter si ruff est rouge. Une seule exécution à la fois (banc, tests).

## 2. Fait

C-L3 `e8cef838` · M-L5a `4711e35b` · M-L6g `d6d28437` · C-L6b `3735ec1f` · M-L6e `31971c6c` (+ plafond `0942633e`) · M-L4a, b, c `203f9e13`. Groupe RE : M-L4c suite `23fc49a5` · M-L6a `7837c5d3` · M-L6b `50d00fd1` · M-L6c `d7c5a30a`. C-L4 `5be9f704` ; banc **après** : RESULT 0,0073399, **SEEL 0,1713 nm** (+11,9 %), gagnant différent (`recensement_sio2.md`).
Banc juge de paix **avant** C-L4 (code `31971c6c`) : RESULT 0,0058619, **SEEL 0,1531 nm**, RUN_S 1 750 s (`bancs/juge_de_paix_avant_C-L4.txt`).

## 3. À faire, dans cet ordre

Décision 👤 = imposée ; décision par défaut = la mienne, à garder sauf raison mesurée.

### Groupe RE (fait)

| id | où | mécanisme | correction | test |
|---|---|---|---|---|
| M-L4a, b, c | `certus/utils/certus_re_helpers.py` : `_re_header_normalize_for_tokens`, `_re_measurement_values_are_percent` | « R45p » lu 0° s ; `arri[eee]res?` a perdu ses accents ; seuil % à 1,25 | **fait (`203f9e13`)** : regex `^([RT])(\d+)([SPsp])?` éclatée ; `[eèé]` ; seuil 1,05 | `tests/unit/test_re_headers_and_units_are_read_as_written.py` |
| M-L4c (suite) | `certus/ui/certus_re_excel_mixin.py` ≈ l. 559-591 (`_parse_re_measurement`) ; INDEX/METAL : seuil 1,5 de `load_spectrum_columns` (`certus/utils/certus_data.py`) | décision % **par colonne** : un R d'antireflet en % (max < 1) à côté d'un T en % est lu en fraction | par défaut : **une unité par feuille** — si une colonne non vide dépasse 1,05, toutes en % ; même seuil 1,05 dans `load_spectrum_columns` | feuille R max 0,8 + T max 92 → R / 100 |
| M-L6a | `certus_re_excel_mixin.py:1188-1190` (`back_check` coché si une colonne est BK) → `certus_spectrum_eval_ui.py:297` `cfg["back"]` → `certus_spectral_workers.py:779-790, 503-530` | l'évaluation affichée applique la face arrière globale à toutes les colonnes ; le REWorker respecte chaque colonne (`certus_re_workers_context.py:134-139`) | passer `include_backside` de chaque colonne au noyau d'évaluation, comme le chemin phase 4 (`:752-777`) | classeur BK + noBK : courbe évaluée noBK = calcul sans face arrière |
| M-L6b | `certus/ui/certus_re_workers_mixin.py::_on_re_done`, `_compute_re_rmse` | `_re_loaded_exact_ep` (épaisseurs chargées) prioritaire après la fin du calcul → RMSE du titre et méta d'export sur le design initial | **fait (`50d00fd1`)** : `_on_re_done` efface `_re_loaded_exact_ep` | `tests/ui/test_re_rmse_follows_the_optimised_thicknesses.py` |
| M-L6c | `certus_re_workers_mixin.py:492` `rw.wait(300000)`, `:511`, `:526` | gèle l'UI 5 min ; puis lâche la référence d'un QThread en marche | arrêt non bloquant : drapeau stop + `finished` → `_force_idle` ; garder la référence jusqu'à `finished` | `stop_optim` rend la main sans attendre ; la référence reste jusqu'à la fin |

### Groupe STRAT, première partie (fait)

| id | où | correction | test / mesure |
|---|---|---|---|
| C-L4 | `certus/utils/certus_strat_db.py::get_refractive_index`, `MergedMaterialDict.__contains__` (correspondance approximative), `certus/utils/certus_db_helpers.py::find_matching_sheets` ; preuve `preuves/p_substrat_sio2.*` | 👤 : le substrat « SiO2 » prend le Sellmeier de la silice fondue **partout** ; `__contains__` ne doit plus répondre oui par sous-chaîne pour un substrat | n(550) = 1,45991 (pas 1,48625) ; puis **banc juge de paix après** (`python scripts\bench_examples.py strat --auto-yes > reports\audit_code_2026-11-15\bancs\juge_de_paix_apres_C-L4.txt`), seul processus ; écrire l'écart (SEEL, classement) dans `recensement_sio2.md` et `docs/ETAT_acquis.md` |

### Groupe INDEX

| id | où | correction | test |
|---|---|---|---|
| M-L1 | `certus/physics/certus_optical_models.py::epsilon1_TL_analytic` (`max(val, 1.0)`) contre `certus/physics/gradient_analytic.py::_compute_epsilon1_gradient_kernel` | 👤 : garder le plafond (bits du coût inchangés), gradient **nul** là où ε1 est plafonnée | `preuves/p_epsilon1_plafond.*` : gradient = différences finies partout (86/161 points aujourd'hui faux) ; **oracle + c1_diff** |
| M-L5g | `certus/ui/certus_index_ui_events.py:278-291` (`n_approx` du substrat) | 👤 : diviser par le **n initial du film à 550 nm** (paramètres de départ du modèle) ; bornes [0,5 ; 2] d̂ | `preuves/p_epaisseur_fft_indice.py` : SiO2 500 nm sur Si → vraie épaisseur dans les bornes |
| M-L5b (INDEX) | `certus/ui/certus_index_ui_state.py:158-247` | relire `exclude_min/max` ; sauver et relire `sb_lmin/lmax`, `sb_sub_thickness_mm`, `chk_high_precision`, `chk_oh_band` | aller-retour `_collect_config` → `_apply_config` sur une fenêtre neuve, widgets non défaut |

### Groupe SPLINE et fils

| id | où | correction | test |
|---|---|---|---|
| M-L3a | `certus/spline/spline_objective.py::sigma_knots_decode` | imposer une croissance stricte (écart minimal `SIGMA_KNOTS_MIN_SEP_REL`) | `preuves/p_noeuds_et_export.*` : deux derniers intervalles minuscules → maillage croissant |
| M-L3c | `certus/spline/certus_corridor_orchestrator_utils.py:808-827`, courbe l. 1150-1175 | par défaut : exclure `point_status_code == 3` de la courbe qui fixe le corridor (les garder dans la sortie, marqués) | un point de secours n'entre pas dans le minimum ni dans le seuil |
| M-L3b | `certus/workers/certus_base_workers.py:93` | ajouter `KeyError, IndexError, TypeError, AttributeError` au tuple attrapé (pas un `except Exception` muet) | `preuves/p_generic_worker_signaux.py` : toute exception → `error` |

### Groupe DESIGN et interface

| id | où | correction | test |
|---|---|---|---|
| C-L6a | `certus/ui/certus_spectrum_eval_ui.py:135-172` ; mode monotone `certus_base_app_plot_mixin.py:531` | 👤 : remettre le « meilleur » à zéro quand une entrée de l'évaluation change (face arrière, substrat, cibles) ; ne jamais réafficher un résultat calculé avec d'autres réglages | changer la face arrière après une évaluation → la courbe affichée = nouveau calcul |
| M-L5c | `certus/ui/certus_design_ui_export.py:467` | `if len(ep):` (ou `ep_current` toujours `ndarray`) | export Excel avec `ep_current` ndarray → fichier écrit |
| M-L5d | `certus/ui/certus_design_ui_core.py:183-200` | 👤 : refuser le retour en mode normal s'il existe des cibles R ou d'angle ≠ 0, avec un message ; convertir seulement les cibles T à 0° | cible R 45° → bascule refusée, cibles intactes |
| M-L5b (DESIGN, FIELD) | `certus_design_ui_state.py:141-369`, `certus_field_state_mixin.py:342-407` | sauver `mc_sigma_rel_spin`, `mc_sigma_ot_spin`, `mc_rmse_threshold_spin` ; FIELD `opt_panel.edit_dmin` | aller-retour de configuration |
| M-L5e | `certus/ui/certus_curve_smoother.py:437-446` | 👤 : ne jamais réécrire le classeur source ; écrire `<nom>_lisse.xlsx` à côté, par fichier temporaire + `os.replace` | le fichier source est inchangé (octets) |
| M-L5f | `certus_design_ui_worker.py:782-827`, `certus_design_ui_core.py:963`, `certus_design_ui.py:286`, `certus_design_ui_events.py:557-575` | désactiver le bouton MC pendant le calcul ; `smc_thread` dans `_COMPUTATION_THREADS` et dans `closeEvent` | bouton désactivé ; fermeture demande/arrête |
| M-L4d | `certus/utils/certus_export.py:70-71` (`getData()`) | exporter les données d'origine (`xData`/`yData` de l'item), pas l'affiché | graphe zoomé + log → CSV complet, linéaire |

### Groupe STRAT, fin

| id | où | correction | test |
|---|---|---|---|
| M-L2 | `certus/core/certus_strat_consensus.py::_store_and_consume_consensus_score`, `certus/core/certus_strat_robustness.py::_apply_consensus_ranking_inplace` | 👤 : une graine rejetée (score infini) → consensus infini, stratégie classée derrière toute stratégie stable | `preuves/p_consensus_graine_rejetee.py` : [0,007 ; inf ; 0,0071] → inf |
| M-L6d | `certus/ui/certus_strat_ui_state.py:580-627` | sauver et relire `thickness_tolerance_nm` | aller-retour : la valeur revient |
| M-L6f | `certus/ui/certus_strat_ui_export.py:385, 532, 633` ; clés réelles `nH_id`, `nL_id`, `nSub_id` (`certus_strat_ui_state.py:1124-1131`) ; « Best RMSE » dans `certus_strat_service.py` | écrire les vrais indices, substrat, nombre de couches, statut de graine ; écrire le **SEEL** ; ne pas étiqueter le score de robustesse « RMSE » | export : plus de « N/A », SEEL présent |

## 4. Fin

`python scripts\validate_parallel.py` (≈ 17 min, seul) + `python scripts\coherence_md.py`, `check_claude_md.py`,
`check_docs.py`. Documentation : l'audit des `.md` du 2026-11-15 est appliqué (ETAT §0, §2, §3, §7 ; CHANTIERS ligne 45 ;
en-tête de CLAUDE.md ; REGLES §2). Restent, avec leurs corrections : `docs/ETAT.md` §2 — chiffrer l'écart du juge de
paix après C-L4 et le renvoyer à `ETAT_acquis.md` ; §3 — dire M-L2 fait dans son commit ; §0 — dernière validation ;
`docs/ETAT_acquis.md` — entrée C-L4 (mesures invalidées) ; `docs/CHANTIERS_RESTANTS.md` — ligne 45 à jour ou sortie.

**Fusion dans `master` sur ordre de 👤 seulement** ; juste avant, 👤 lance dans `certus1111` la commande qui supprime
les 14 non-suivis restants (commande 1 donnée le 2026-11-15 ; copie hors dépôt :
`CERTUS/certus1111_hors_git_2026-11-15/notes_certus1111/`). Ne rien pousser sans ordre. Le dépôt est dans Google
Drive (`ETAT.md` §3) : un seul PC à la fois.
