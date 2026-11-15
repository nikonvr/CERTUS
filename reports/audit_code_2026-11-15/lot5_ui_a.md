# Lot 5 — `certus/ui/`, première moitié (a11y → index_ui_worker)

2026-11-15, worktree `claude-code-suije-bf4f1f`. Lecture seule : aucun test, banc ni calcul lancé, rien ici n'est mesuré.

## 1. Périmètre lu

- **En entier** : `certus_design_ui_worker`, `certus_index_ui_state`, `certus_index_spline_state_mixin`, `certus_design_ui_final_cleanup`, `certus_field_workers_mixin`, `certus_base_app_run_mixin`.
- **En partie** (UI → calcul, sauvegarde, export, fermeture) : `certus_design_ui*`, `certus_design_resonances_dialog`, `certus_base_app*`, `certus_field_state_mixin`, `certus_index_ui*`, trois `certus_index_spline_*`, `certus_curve_smoother`.
- **Survolés par Grep** : le reste (`corridor_*`, a11y, thème, icônes).
- ≈ 7 200 lignes sur 39 679 : **~18 %**. Lus hors lot pour suivre un flux : `certus_design_workers`, `certus_index_workers_opt_strat`, un noyau de `_certus_physics_impl`.

## 2. Notes sur 10

| critère | note | preuves | confiance |
|---|---|---|---|
| Exactitude (UI → calcul) | 5 | M1, M2, M4 ; à l'inverse `WorkerManager._capped_global_budgets` journalise valeur affichée → appliquée | moyenne |
| Tests | 6 | 139 fichiers de test touchent le lot, nommés d'après des bugs ; mais `test_ux_a_resumed_session_gives_back_the_configuration` compare deux fenêtres **par défaut** (aveugle à M2), les tests d'absorption prennent un `k_sub` constant (aveugles à M1), `test_exports_are_written_atomically` ne voit que `open(…, "w")` | forte |
| Architecture, couplage | 5 | gestionnaires qui lisent `self.ui` par `getattr` (m2) ; `ep_current` tantôt `list` (`_update_thickness_display`), tantôt `ndarray` (M3) ; estimation FFT dans `_auto_detect_from_file` (chantier 38) | moyenne |
| Lisibilité, maintenance | 5 | dix fichiers > 1 000 lignes ; docstrings mal placées (`ExportManager.export_results`, `WorkerManager.run_optim` : « ±2 nm » contre `local_delta_nm: 10.0`) | forte |
| Robustesse, concurrence | 5 | bon : `_keep_until_finished`, `DesignResonanceDialog.closeEvent` ; mauvais : M6, m3 | moyenne |
| Ergonomie, accessibilité | 7 | `certus_a11y::derive_accessible_name`, `audit_palette` ; `confirm_close_during_run` ; contre : m6, m7 | moyenne |
| Performance | 6 | évaluation différée (`_schedule_eval`) ; mais `WorkerManager.run_robust_n` calcule dans le fil GUI, `_update_spectral_response` (FIELD) refait 200 λ × 4 indices + TMM à chaque édition | faible |

## 3. Défauts

**Critique : aucun trouvé.**

**Majeurs**

- **M1** `CertusIndexWorkerMixin._resolve_substrate_absorption_inputs` construit `k_sub` sur toute la grille du fichier ; `certus_index_workers_opt_strat` (hors lot) masque `wls` (fenêtre λ, NaN) mais passe `c.k_sub_data` entier, et le noyau lit `k_sub_full[i]`. Si de 0,5 mm (absorbant par défaut), λ min relevé à 400 nm sur un fichier qui commence à 250 nm → k du substrat lu 150 points trop tôt, ajustement faux au bord de bande, sans message. VÉRIFIÉ en lecture.
- **M2** Configurations sans aller-retour. INDEX : `_collect_config` écrit `exclude_min/max`, `_apply_config` ne les relit pas (case recochée sur 400–450 nm) ; bande OH, haute précision, épaisseur Si non sauvées. FIELD : `dmin` absent. DESIGN : sigmas relatif et OT, seuil de rendement absents. Recharger → autre ajustement, couches plus minces tolérées, autre rendement. VÉRIFIÉ.
- **M3** `ExportManager.export_excel` : `if ep:` sur `ep_current`, un `ndarray` après un STOP (`_handle_stopped_workflow_result`) → `ValueError` attrapée, « Export error », aucun fichier. VÉRIFIÉ en lecture, non exécuté.
- **M4** `CoreManager._toggle_oblique_mode` : décocher « Oblique » change une cible R ≥ 0,99 à 45° en cible T ≥ 0,99 normale, sans message : on optimise l'inverse. VÉRIFIÉ.
- **M5** `CurveSmootherGUI.save_file` sur le fichier source : `pd.ExcelWriter(mode="a")` réécrit le classeur de mesure original, non atomique ; openpyxl perd graphiques et images d'un classeur relu (limite documentée), sans avertissement. VÉRIFIÉ en lecture.
- **M6** `WorkerManager.run_spectral_mc` : bouton actif pendant le calcul (`_update_busy_ui` l'oublie) ; un second clic réaffecte `smc_thread` en cours ; `smc_thread` manque à `_COMPUTATION_THREADS` et à `EventsManager.closeEvent` (fermeture sans question). Bouton VÉRIFIÉ ; abandon « QThread destroyed while running » SOUPÇONNÉ.
- **M7** `_auto_detect_from_file` divise le chemin optique par l'indice du **substrat** (Si : 3,5) pris pour celui du film, puis impose `[0,5 d̂ ; 2 d̂]` aux bornes d'épaisseur : SiO₂ sur Si donne d̂ ≈ 0,41 d, la vraie épaisseur sort des bornes. Logique VÉRIFIÉE, effet sur l'ajustement SOUPÇONNÉ.

**Mineurs**

- m1 `export_excel` et `save_config` lancent `smart_cleanup` (modifient le dessin) ; la feuille « Spectrum » reste celle d'avant (évaluation asynchrone). VÉRIFIÉ.
- m2 `WorkerManager.stop_all` supprime les attributs d'aiguille sur lui-même, pas sur l'orchestrateur : sans effet. VÉRIFIÉ.
- m3 `CertusFieldWorkersMixin.on_worker_finished` (synthèse) : `_start_worker` rend la main en silence si le fil précédent n'a pas fini → boutons désactivés pour de bon. SOUPÇONNÉ.
- m4 Exports non atomiques : `wb.save` (`_export_results_excel`), `pd.ExcelWriter` (FIELD, INDEX SPLINE) ; le garde-fou ne les voit pas. VÉRIFIÉ.
- m5 `CertusFieldStateMixin._apply_config` : `seuil1`/`seuil2` absents → 0,5/0,5, la fenêtre propose 3/25. VÉRIFIÉ.
- m6 `_ask_keep_raw_or_smoothed` : sans réponse en 5 s, la mesure est lissée (délai imposé, donnée modifiée). VÉRIFIÉ.
- m7 `certus_design_ui_plot` : couleurs de cibles en hexadécimal, hors thème. VÉRIFIÉ.
- m8 `CertusFieldStateMixin._get_n_for_material` : base en échec → indices constants codés en dur, trace `debug` seule. VÉRIFIÉ.

## 4. Ce qui est bien fait

- `certus_index_ui_worker::_keep_until_finished` : débranche un fil qui ne s'arrête pas et le garde vivant, sans `terminate()`.
- `DesignResonanceDialog._apply` refuse d'appliquer si le dessin ou les cibles ont changé depuis le calcul ; arrêt coopératif.
- `CertusAppRunStateMixin.running_worker_count` compte les fils qui tournent vraiment ; question avant fermeture non sauvée (`confirm_close_unsaved`).
- `CertusIndexStateMixin._config_load_problems` (D88) refuse un substrat inconnu au lieu de calculer avec un autre.
- `certus_a11y` : noms accessibles dérivés des étiquettes, audit de contraste WCAG.

## 5. Trois recommandations

1. **Test d'aller-retour réel par fenêtre** : chaque widget sur une valeur non défaut, `_collect_config` → `_apply_config` sur une fenêtre neuve, comparer les **widgets** ; rouge aujourd'hui (M2). ½ jour, puis ~1 h par fenêtre.
2. **Aligner `k_sub` sur la grille ajustée** (masquer ou interpoler avec `wls`), test à `k_sub` variable et λ min relevé, rouge sur le code actuel. ~2 h.
3. **`ep_current` toujours `ndarray`**, `len(ep)` au lieu de `if ep:` ; désactiver `spectral_mc_btn`/`robust_n_btn` pendant un calcul, `smc_thread` dans `_COMPUTATION_THREADS` et à la fermeture. ~3 h.
