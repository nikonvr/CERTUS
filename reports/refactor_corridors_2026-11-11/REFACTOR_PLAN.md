# REFACTOR_PLAN — CERTUS

**Objectif retenu** : extraire et restructurer la logique des corridors sous forme de mixins modulaires, assainir
l'héritage multiple et découpler les classes principales entre sous-modules, sans altérer le comportement métier.

**Emplacement** : ce plan vit dans `reports/refactor_corridors_2026-11-11/`, avec l'instantané de référence et les
manifestes des phases. Posé à la racine, il faisait échouer deux contrôles du dépôt : `scripts/coherence_md.py`, et
`tests/unit/test_the_ai_entry_points_stay_small.py` (un document de plus de 20 000 octets à la racine doit être masqué
des recherches).

**Nature de ce document** : audit statique du 2026-11-11, par lecture ciblée des seuls fichiers `.py` (Glob / Grep / Read).
Rien n'a été exécuté, aucun fichier `.md` n'a été lu, aucun fichier source n'a été modifié.

**Statut des affirmations**

- « vérifié » : lu dans le code, référence `fichier.py:ligne` donnée (chemins relatifs à `certus/`, sauf `tests/`, `scripts/`
  et les scripts racine `CERTUS_*.py`).
- « à confirmer en Phase 0 » : déduit d'un relevé par motif, pas d'une lecture complète du corps des méthodes
  (les 24 fichiers `ui/certus_index_spline*.py` font 15 229 lignes ; leur plan de classes et de méthodes a été relevé en
  entier, leurs corps seulement par extraits).
- `tests/architecture_debt.json` (pas un `.py`) : relevé par recherche ciblée le 2026-11-11, après l'arbitrage Q2 (§1.6) ;
  sa lecture complète reste une tâche de Phase 0.

**Arbitrages** : tous tranchés (section 4) ; les Phases 2b à 2e, 9 et 10 en découlent. Reprise : `REPRISE.md`. Les numéros de ligne sont ceux
de l'audit : chaque phase décale les suivantes, on repère donc par le nom.

**Ce que « garanti sans régression » veut dire ici** : la garantie n'est pas une affirmation de ce plan, c'est un mécanisme.
Chaque phase est soit un *ajout pur*, soit un *déplacement pur* de fonctions dont l'équivalence est prouvée par outil
(bytecode identique, mêmes objets globaux résolus, même résolution MRO, mêmes noms de module) avant de lancer la suite.
Tout ce qui sort de ces deux catégories est isolé dans une phase à part et soumis à arbitrage (section 4).

---

## 1. Diagnostic statique & Cartographie des couplages

### 1.1 Le découpage réel n'est pas celui de l'énoncé

- `re`, `index`, `design`, `strat` ne sont **pas des paquets** : ce sont des préfixes de fichiers (`certus_re_*`,
  `certus_index_*`, `certus_design_*`, `certus_strat_*`) répartis dans des paquets par **couche** :
  `domain < physics < core = utils < metal = spline < workers < ui` (`scripts/metrics.py:89-92`).
- `certus` est un paquet-espace de noms : seuls `domain/**/__init__.py` existent. Il n'y a aucun `__init__.py` à câbler.
- Aucun module ni paquet CERTUS ne s'appelle `re` (Glob `**/re.py`, `**/re/__init__.py` : vide). `import re` désigne
  partout la bibliothèque standard (ex. `CERTUS_HUB.py:38`).
- La logique « corridors » n'existe côté fenêtre que dans **INDEX SPLINE** (`ui/certus_index_spline*.py`), et côté
  algorithme dans `spline/`. Les familles `re`, `index`, `design`, `field`, `metal` n'en contiennent pas. STRAT a ses
  propres notions homonymes, sans import commun : `corridor_wl_range` (`physics/certus_strat_batch.py:22`),
  `corridor_monitor_span` (`core/certus_strat_robustness_noise.py:169`), `_add_corridor` (`ui/certus_strat_spectrum_ui.py:146`).

Le refactoring « corridors » porte donc sur une seule fenêtre, `CertusIndexSplineApp` ; le découplage inter-familles est
un chantier distinct, plus petit (§1.3, Phase 7).

### 1.2 Faiblesses structurelles

| # | Constat | Références |
|---|---------|------------|
| F1 | **La logique corridors est éparpillée sur 10 classes et 9 fichiers.** `_CorridorControlMixin`, `_CorridorGenMixin`, `_CorridorWorkerMixin`, `_CorridorTabMixin`, `_CorridorExportMixin`, `CertusIndexSplineCorridorUIMixin`, plus des méthodes corridors logées dans `CertusIndexSplineManualMeshMixin`, `_PlotMixin`, `_UIBuilderMixin`, `CertusIndexSplineEventsExtrasMixin`. | `_CorridorControlMixin` `ui/certus_index_spline_settings.py:749` ; `_CorridorGenMixin` `ui/certus_index_spline_corridor_gen.py:20` ; `_CorridorWorkerMixin` `ui/certus_index_spline_corridor_worker.py:28` ; `_CorridorTabMixin` `ui/certus_index_spline_corridor_tab.py:24` ; `_CorridorExportMixin` `ui/certus_index_spline_execution.py:90` ; `CertusIndexSplineCorridorUIMixin` `ui/certus_index_spline_corridorui_mixin.py:26` ; `_corridor_manual_half_width_nm` `ui/certus_index_spline_manualmesh_mixin.py:1015-1122` ; `_plot_rmse_data_scatter` `ui/certus_index_spline_rendering.py:247-1049, 1463, 1876, 1915` ; `_is_rmse_d_grid_worker_finalize_dict` `ui/certus_index_spline_eventsextras_mixin.py:319, 326, 372, 657, 959` |
| F2 | **L'état corridor n'a pas de propriétaire.** `self._corridor_rmse_*` est écrit depuis 9 fichiers. Il naît à trois endroits : dans `__init__`, dans un *constructeur de widgets*, et paresseusement au fil de l'eau. La remise à zéro n'en couvre qu'une partie. | naissance `__init__` : `ui/certus_index_spline_ui.py:110, 120-126, 139` ; naissance dans un builder : `ui/certus_index_spline_corridorui_mixin.py:152-161` ; naissance paresseuse : `ui/certus_index_spline_settings.py:1046-1056`, `ui/certus_index_spline_corridor_worker.py:883`, `ui/certus_index_spline_rendering.py:747, 849-859`, `ui/certus_index_spline_corridor_tab.py:154-157` ; remise à zéro partielle : `ui/certus_index_spline_state_mixin.py:85-119, 179-191` |
| F3 | **Contrat implicite par `getattr` / `hasattr`.** 208 `getattr(self, "…")` et 230 `hasattr(self, "…")` dans le groupe ; une soixantaine de `getattr(self, "_corridor_…", défaut)` recopient la même valeur par défaut à chaque site. Le même attribut est lu tantôt gardé, tantôt nu. | défauts recopiés : `_corridor_rmse_manual_slider_scale` = 100 en `ui/certus_index_spline_corridorui_mixin.py:342`, `ui/certus_index_spline_manualmesh_mixin.py:1020`, `ui/certus_index_spline_settings.py:1211` ; lecture nue puis gardée du même état : `ui/certus_index_spline_manualmesh_mixin.py:1062-1063` vs `:1100-1107` ; gardes sur des *méthodes* d'autres mixins : `ui/certus_index_spline_settings.py:241, 244, 1058, 1061, 1068` |
| F4 | **Responsabilités mélangées.** Le répartiteur général de fin de calcul (`_on_worker_done`, tous rôles de worker) vit dans le mixin corridors ; `_DataMixin` (tables n/k, décalage de substrat) vit dans le groupe « corridor » ; `_CorridorExportMixin` porte aussi l'export n/k générique. | `ui/certus_index_spline_corridor_worker.py:366, 600, 627, 689` ; `ui/certus_index_spline_corridor_data.py:24` ; `ui/certus_index_spline_execution.py:93, 402` |
| F5 | **Les mixins rappellent la classe hôte.** Un mandataire paresseux `CertusIndexSplineApp` importe la fenêtre à l'appel ; plus de 40 sites l'utilisent. S'y ajoutent des imports retardés du module de la fenêtre. Cycle d'exécution mixin ↔ hôte, invisible au niveau module. | mandataire : `ui/certus_index_spline_common.py:371-376` ; usages : `ui/certus_index_spline_manualmesh_mixin.py:46-975`, `ui/certus_index_spline_eventsextras_mixin.py:206, 302-307, 390, 718-728, 1057` ; imports retardés de la fenêtre : `ui/certus_index_spline_corridor_worker.py:893`, `ui/certus_index_spline_execution.py:869`, `ui/certus_index_spline_mixins_ui.py:478` |
| F6 | **Le code de production a pris la forme du harnais de test.** `self.__class__._prepare_worker_restart(self)` et `CertusIndexSplineApp._prepare_worker_restart(self)` n'existent que parce que les tests appellent les méthodes hors instance sur un faux hôte. | `ui/certus_index_spline_corridor_worker.py:889` ; `ui/certus_index_spline_execution.py:533, 706` ; `ui/certus_index_spline_settings.py:762` ; `ui/certus_index_spline_manualmesh_mixin.py:635, 764, 835, 903, 975` ; `ui/certus_index_spline_eventsextras_mixin.py:390` ; harnais : `tests/unit/test_mwir_gui_flow.py:6-49` |
| F7 | **Duplications.** `_apply_fixed_log_k_axis` défini 5 fois — une référence (`common:155`), une délégation vers elle (`monitor_ui:14`), trois copies locales identiques entre elles (`corridor_common:22`, `execution:44`, `rendering:71`) ; toutes règlent le même axe (log, 1e-6 à 1e-2), seuls les messages DEBUG divergent (journal « CERTUS » ou « CERTUS_INDEX_SPLINE », exception tue ou journalisée) ; `_DEFAULT_CORRIDOR_*` 3 fois ; 16 constantes de fenêtre (clés QSettings, révisions, épaisseurs SiO2) 2 à 3 fois, à valeurs égales, dont 13 définies dans le cœur spline sans y être utilisées ; `_QS_SMART_INIT_DEEP` et `_QS_SMART_INIT_TWO_PHASE` 2 fois, hors du cœur (`ui/certus_index_spline_smart_init.py:70-71`, `ui/certus_index_spline_common.py:92-94`) ; `SmartInitPayload` et ses deux classes d'état 2 fois ; `_SCRIPT_DIR` 2 fois avec deux modes de calcul. | `_apply_fixed_log_k_axis` `ui/certus_index_spline_corridor_common.py:22`, `ui/certus_index_spline_common.py:155`, `ui/certus_index_spline_execution.py:44`, `ui/certus_index_spline_monitor_ui.py:14`, `ui/certus_index_spline_rendering.py:71` ; `ui/certus_index_spline_common.py:110-115`, `ui/certus_index_spline_corridor_common.py:13-19`, `ui/certus_index_spline_settings.py:62-64` ; `spline/certus_index_spline_core.py:43, 2095-2107` vs `ui/certus_index_spline_common.py:70-123` et `ui/certus_index_spline_smart_init.py:68` ; `ui/certus_index_spline_smart_init.py:74-148` vs `ui/certus_index_spline_state_ui.py:11-85` ; `ui/certus_index_spline_common.py:66` vs `ui/certus_index_spline_corridor_common.py:10` |
| F8 | **Module-carrefour fragile.** `certus_index_spline_common.py` importe les mixins de 4 modules en tête, définit des constantes au milieu, calcule `__all__` par `dir()`, puis importe encore un module *après* `__all__`. Son bon chargement dépend de l'ordre ; il figure dans la liste des modules sortis d'un cycle. | `ui/certus_index_spline_common.py:37-53, 378, 396-401` ; `tests/unit/test_a_module_that_was_in_an_import_cycle_imports_first_and_alone.py:28-35` |
| F9 | **Code mort dans le MRO et dans le corps.** Deux mixins vides restent dans les bases de la fenêtre ; une branche lit un attribut que rien n'affecte et appelle une méthode qui n'existe nulle part. | `ui/certus_index_spline_mixins_ui.py:41, 736` (dans `ui/certus_index_spline_ui.py:62, 65`) ; `ui/certus_index_spline_execution.py:910-916` (`_corridor_rmse_profile_win`, `update_profile`) |
| F10 | **Éléments de fenêtre rangés hors de la couche `ui`, et l'inverse.** Un mixin de fenêtre et des clés QSettings vivent dans `spline/` ; trois points d'entrée de calcul vivent dans le carrefour `ui`. | `spline/certus_index_spline_excel_export.py:23, 31` ; `spline/certus_index_spline_core.py:2094-2107` ; `ui/certus_index_spline_common.py:278, 319, 348` |
| F11 | **Héritage de base à contre-sens.** `CertusBaseApp(QMainWindow, 13 mixins)` place la classe Qt en premier : ses 13 mixins ne peuvent redéfinir aucune méthode virtuelle Qt, et `super().__init__(parent)` n'atteint que `QMainWindow` — aucun `__init__` de mixin ne s'exécute. Les signaux `sig_numba_*` de la base sont redéfinis dans les sous-classes. | `ui/certus_base_app.py:276, 327, 277-278` ; `ui/certus_index_ui.py:75-76` ; `ui/certus_strat_ui.py:57-58` ; piège déjà documenté : `ui/certus_field_ui.py:19-20` |
| F12 | **Trois arêtes entre familles.** FIELD importe un utilitaire des workers STRAT ; DESIGN et RE importent une fonction des utilitaires INDEX. | `_resolve_strat_indices_db_path` (`ui/certus_field_ui.py:15`) ; `spectral_rmse_weights` (`workers/certus_design_workers.py:53` et `core/certus_re_worker_utils.py:35`) |
| F13 | **Noms trompeurs pour tout outillage par famille.** Le suffixe `_strat` veut dire « stratégie », pas STRAT ; `certus_design_tokens` est le système graphique, pas DESIGN. | `workers/certus_index_workers_ir_strat.py`, `workers/certus_index_workers_opt_strat.py`, `workers/certus_design_workers_strat.py` ; `core/certus_design_tokens.py:13` (importé par `ui/certus_index_spline_rendering.py:36`) |
| F14 | **Fichier long.** Seul `certus_index_spline_rendering.py` dépasse le seuil de 1 500 lignes (1 967) ; `certus_index_spline_settings.py` en fait 1 388. | seuil : `scripts/metrics.py:102` |
| F15 | **La fenêtre RE n'est pas dans `ui/`.** `CertusREApp` est définie dans le script racine, contrairement aux autres fenêtres. | `CERTUS_RE.py:166` ; comparer `ui/certus_strat_ui.py:46`, `ui/certus_design_ui.py:24`, `ui/certus_field_ui.py:18` |

### 1.3 Dépendances actuelles

**Entre couches** — aucune arête montante de niveau module n'a été trouvée depuis `core`, `physics`, `spline`, `metal` ou
`workers` vers une couche supérieure. Les imports montants sont indentés (dans une fonction ou un bloc conditionnel) :
`utils/certus_command_palette.py:265`, `utils/certus_badges.py:84, 180`, `utils/certus_progress_tracker.py:213, 394`,
`utils/certus_skeleton.py:64`, `utils/certus_ux.py:24, 305`, `utils/errors.py:87`, `workers/certus_spectral_workers.py:119`,
`physics/certus_optimizers.py:636, 690`, `physics/gradient_analytic.py:1115`, `physics/certus_material_db.py:82`.
Le registre `tests/architecture_debt.json` fait foi pour leur statut exact.

**Entre familles** — STRAT n'importe aucune autre famille. Aucune famille hors INDEX SPLINE n'importe `certus.spline`,
sauf `ui/certus_index_ui_utils.py:15` (import indenté). Les trois arêtes de F12 sont les seules trouvées.

**Dans le groupe INDEX SPLINE (niveau module)** — c'est un graphe sans cycle :

```
certus_index_spline_ui  ─► common, les 7 modules *_mixin, certus_ui
*_mixin (7)             ─► common          (eventsextras ─► execution ; smartinit ─► state_ui)
common                  ─► corridors (façade), execution, rendering, settings, certus_ui
                           puis, en fin de fichier ─► mixins_ui
mixins_ui               ─► managers_ui, settings, state_ui, certus_ui
corridors (façade)      ─► corridor_common, corridor_data, corridor_gen, corridor_worker
corridor_worker         ─► corridor_tab, corridor_ui
corridor_tab            ─► corridor_common, corridor_ui
corridor_gen, corridor_data ─► corridor_ui
corridor_ui (passerelle)─► certus_manual_sigma_knot_dialog, certus_plot, certus_ui
execution, rendering, settings, managers_ui, monitor_ui ─► certus_ui
```

Les retours vers la fenêtre sont tous retardés (dans une fonction) : `common:373`, `corridor_worker:893`, `execution:869`,
`mixins_ui:478` ; de même `managers_ui:340 ─► common`. `monitor_ui:15` importe `common` dans le corps d'une fonction (la délégation de
`_apply_fixed_log_k_axis`, `monitor_ui:14-16`) : retardé lui aussi.

### 1.4 MRO et états partagés

**Bases directes de `CertusIndexSplineApp`** (`ui/certus_index_spline_ui.py:51-74`), dans l'ordre :
`_CorridorControlMixin`, `_SettingsMixin`, `_CorridorGenMixin`, `_DataMixin`, `_RunMixin`, `_CorridorExportMixin`,
`_UIBuilderMixin`, `_PlotMixin`, `_CorridorWorkerMixin` (→ `_CorridorTabMixin`), `_SmartInitDialogMixin`,
`_ConfigBuilderMixin`, `_MeshOptimizationMixin`, `_ExcelExportMixin`, `_UIMixin`, `CertusIndexSplineStateMixin`,
`CertusIndexSplineSmartInitMixin`, `CertusIndexSplineManualMeshMixin`, `CertusIndexSplineCorridorUIMixin`,
`CertusIndexSplineSpectrumUIMixin`, `CertusIndexSplineLayoutExtrasMixin`, `CertusIndexSplineEventsExtrasMixin`,
`CertusBaseApp` (→ `QMainWindow` + 13 mixins).

- **Aucune méthode n'est définie par deux des 21 mixins** (relevé des 258 `def` de niveau classe du groupe, plus
  `export_excel` de `spline/certus_index_spline_excel_export.py:26`). L'ordre de ces 21 bases n'a donc aujourd'hui aucun
  effet sur la résolution des méthodes. Confirmé par l'exécution en Phase 0, attributs de classe compris (liste des 15 noms redéfinis dans la phase).
- **Redéfinitions voulues de la base** (les mixins précèdent `CertusBaseApp`) :
  `_setup_logger` (`ui/certus_index_spline_eventsextras_mixin.py:519` sur `ui/certus_base_app_engine_mixin.py:15`),
  `_warmup_numba` (`:60` sur `:37`), `_get_log_widget` (`:572` sur `:157`),
  `_collect_config` / `_apply_config` (`ui/certus_index_spline_state_mixin.py:24, 42` sur
  `ui/certus_base_app_config_mixin.py:117, 128`), `closeEvent` (`ui/certus_index_spline_state_mixin.py:204` sur
  `ui/certus_base_app.py:725`), `_build_ui` (`ui/certus_index_spline_rendering.py:1053` sur `ui/certus_base_app.py:635`),
  attribut de classe `_COMPUTATION_THREADS` (`ui/certus_index_spline_state_mixin.py:21` sur
  `ui/certus_base_app_run_mixin.py:110`).
- **Risque MRO propre à Qt** : un mixin ne doit hériter ni de `typing.Protocol` ni de `abc.ABC` à l'exécution (conflit
  de métaclasse avec celle de `QMainWindow`), et ne doit pas définir `__init__` (jamais appelé, cf. F11).
- **État partagé entre mixins** : outre l'état corridor (F2), le cycle de vie du worker est commun à tous :
  `_worker`, `_stop_event`, `_worker_role`, `_last_run_cfg`, `_last_result`, `_last_worker_result`, `_best_live_rmse`,
  `_best_live_result` (`ui/certus_index_spline_ui.py:102-118`), et `logger` (`ui/certus_base_app.py:367`).

### 1.5 Invariants stricts (ce que la suite de tests fige déjà)

| # | Invariant | Où il est figé |
|---|-----------|----------------|
| I1 | Tout nom de niveau module défini par une partie du groupe corridors reste attribut de la façade, même objet. | `tests/unit/test_the_corridors_split_keeps_every_name_and_the_layering_where_it_was.py:60-70` |
| I2 | `_plot_corridor_tab`, `_build_corridor_tab_rmse_controls` restent dans `_CorridorTabMixin.__dict__` ; `_finish_corridor_rmse_d_grid_worker_done`, `_on_worker_done`, `_start_corridor_rmse_grid_recalc` dans `_CorridorWorkerMixin.__dict__`. | même fichier `:81-84` |
| I3 | Dans le MRO de la fenêtre, `_CorridorTabMixin` suit immédiatement `_CorridorWorkerMixin`. | même fichier `:78-80` |
| I4 | Seule la passerelle `certus_index_spline_corridor_ui` importe `certus.ui.*` hors groupe, en **exactement 3 instructions** ; ni les autres parties ni la façade ne le font. | même fichier `:93-112` |
| I5 | Aucune partie ni la façade ne dépasse 1 500 lignes. | même fichier `:115-118` |
| I6 | Douze noms de mixins restent dans le MRO : `_ExcelExportMixin`, `_MeshOptimizationMixin`, `_ConfigBuilderMixin`, `_CorridorWorkerMixin`, `_PlotMixin`, `_UIBuilderMixin`, `_CorridorExportMixin`, `_RunMixin`, `_DataMixin`, `_CorridorGenMixin`, `_SettingsMixin`, `_CorridorControlMixin`. | `tests/unit/test_gui_smoke.py:218-238` |
| I7 | **Coutures de monkeypatch** : une fonction résout ses globaux dans *son* module. Noms patchés par module : `corridor_data` (`substrate_id_from_name`, `_get_substrate_n_array_spline`, `_sync_theoretical_tr_from_nk_dict`, `spectral_mse_rmse_masked_from_nk`) ; `corridor_worker` (`log_index_spline_d_trace`, `log_structured_json_event`, `uninstall_skeleton`) ; `rendering` (`pg`) ; `mixins_ui` (`canonical_spline_sigma_knots`) ; `manualmesh_mixin` (`GenericWorker`, `install_skeleton`) ; `corridorui_mixin` (`GenericWorker`) ; `execution` (`_plot_spectrum_raw_scatter`) ; `smart_init` (`SmartInitPreviewManager`). | `tests/unit/test_index_spline_handled_failures_stay_handled.py:42-43, 70-71` ; `tests/unit/test_corridor_worker_done_steps.py:183-184` ; `tests/unit/test_post_opt_option_unlock.py:134` ; `tests/unit/test_rmse_scatter_pieces.py:49` ; `tests/unit/test_build_opt_config_pieces.py:46` ; `tests/unit/test_mwir_gui_flow.py:256-257, 296-297, 354-355, 399, 435` ; `tests/unit/test_spectral_knot_markers.py:106` ; `tests/ui/test_the_two_unplugged_windows_are_plugged_back.py:58` |
| I8 | **Texte source figé** de `_on_worker_done`, `_finish_corridor_rmse_d_grid_worker_done`, `_plot_rmse_data_scatter`, `_plot_corridor_rmse_tab`, `_build_opt_config` (sous-chaînes lues par `inspect.getsource`). | `tests/unit/test_corridor_worker_done_steps.py:492-507` ; `tests/unit/test_corridor_worker_logs_the_regular_grid.py:112` ; `tests/unit/test_rmse_scatter_pieces.py:475-479` ; `tests/unit/test_rmse_tab_summary.py:230` ; `tests/unit/test_build_opt_config_pieces.py:135` |
| I9 | **Appels hors instance sur de faux hôtes** : `CertusIndexSplineApp.methode(SimpleNamespace(...))` et `_XxxMixin.methode(faux)`. Une méthode ne peut donc exiger de `self` aucun attribut nouveau, et l'état doit rester en attributs plats, sous les mêmes noms. | `tests/unit/test_mwir_gui_flow.py:143-613` ; `tests/unit/test_post_opt_option_unlock.py:77-254` ; `tests/unit/test_rmse_scatter_pieces.py:44-424` ; `tests/unit/test_rmse_tab_summary.py:24, 120` ; `tests/unit/test_data_th_tab.py:28, 75` ; `tests/unit/test_data_th_clipboard.py:42, 92` ; `tests/unit/test_spectral_knot_markers.py:115` ; `tests/unit/test_build_opt_config_pieces.py:58-104` |
| I10 | Un mixin est sous-classé seul par un test. | `tests/unit/test_index_spline_handled_failures_stay_handled.py:21` |
| I11 | Tout `self.nom` lu est défini quelque part ; les classes dont le nom ne contient pas « Mixin » sont balayées seules. | `tests/unit/test_self_attributes_are_defined.py:96-142` |
| I12 | Registre de dette : aucune arête montante nouvelle, aucun cycle nouveau, aucun fichier > 1 500 lignes ni fonction > 300 lignes ou de complexité > 60 qui ne soit déjà listé ; **un plafond qui baisse doit être réécrit dans le même commit**. | `tests/unit/test_the_architecture_debt_only_shrinks.py:62-155` |
| I13 | Les modules sortis d'un cycle s'importent seuls, en premier, dans un interpréteur neuf. | `tests/unit/test_a_module_that_was_in_an_import_cycle_imports_first_and_alone.py:64-68` |
| I14 | Tout `from certus… import nom` se résout, même dans une fonction ; balayage fondé sur `git ls-files` (un fichier non suivi n'est pas vu). | `tests/unit/test_project_imports_resolve.py:29-45` |
| I15 | `CERTUS_INDEX_SPLINE` relaie lecture **et écriture** d'attributs vers 4 sous-modules, dans cet ordre : cœur spline, `smart_init`, façade `corridors`, `certus_index_spline_ui`. Un nom ajouté à la façade masque donc le même nom du module de la fenêtre. | `CERTUS_INDEX_SPLINE.py:35-40` ; `core/certus_core.py:1229-1255` |
| I16 | Un indicateur compte les modules qu'aucun test ne nomme. | `scripts/metrics.py:65, 623` |

### 1.6 Registre de dette (relevé ciblé de `tests/architecture_debt.json`, autorisé par Q2)

- `aretes_montantes` et `fonctions_non_annotees` sont **vides** : toute arête montante de niveau module, et toute fonction
  non annotée de `domain`, `physics` ou `core`, fait échouer la suite (Phase 7b comprise).
- Aucun module `certus_index_spline*` n'est nommé dans un cycle.
- Entrées qui nomment le groupe — **aucune n'est une méthode de §2.3** :

| Section | Entrée | Plafond | Sort dans ce plan |
|---|---|---|---|
| `fichiers_longs` | `certus/ui/certus_index_spline_rendering.py` | 1 967 | baisse en 2b, 3b, 3c, 3d et 4 : à réécrire dans chacun de ces commits (I12) |
| `fichiers_longs` | `certus/spline/certus_index_spline_core.py` | 2 108 | **ne doit pas gagner une ligne** ; la Phase 2c ne le modifie pas |
| `fonctions_longues` | `certus_index_spline_managers_ui.py::Step4MeshOptimizerBuilder.build` | 804 | inchangée |
| `fonctions_longues` | `certus_index_spline_smart_init.py::SmartInitPreviewManager.__init__` | 572 | inchangée |
| `fonctions_longues`, `fonctions_complexes` | `certus_index_spline_manualmesh_mixin.py::CertusIndexSplineManualMeshMixin._open_manual_extra_knots_dialog` | 433, 75 | inchangée (ce n'est pas une des méthodes qui quittent ce mixin en 3c) |
| `fonctions_complexes` | `certus_index_spline_corridor_worker.py::_CorridorWorkerMixin._finish_corridor_rmse_d_grid_worker_done` | 72 | inchangée (I2) |
| `fonctions_complexes` | `certus_index_spline_mixins_ui.py::_MeshOptimizationMixin._build_opt_config` | 76 | inchangée (I8) |

Conséquence : le renommage d'entrée qu'autorise Q2 ne sert pour aucune fonction ; seul le plafond de `rendering.py` bouge.

---

## 2. Architecture Cible & Contrats d'Interface

### 2.1 Principes

1. **Déplacement pur** : une méthode déménage avec son texte exact, décorateurs compris. Aucun corps n'est retouché dans
   les phases de migration.
2. **L'état reste plat** sur `self`, sous les mêmes noms (I9). Il gagne un propriétaire *déclaratif*, pas un objet.
3. **Les noms historiques survivent**, dans leur module, comme classes de compatibilité qui héritent des tranches (I6).
4. **Les contrats sont structurels** : `Protocol` importés sous `if TYPE_CHECKING:` seulement, jamais en base d'un mixin.
5. **Une méthode épinglée par un test ne déménage pas** (I2, I7, I8) sans arbitrage explicite.
6. **Un module vidé garde les noms qu'il exposait** (I7 : `monkeypatch.setattr` échoue sur un nom absent).
7. Tout nouveau mixin a « Mixin » dans son nom (I11), n'a pas d'`__init__`, n'hérite que d'`object`.

### 2.2 Hiérarchie cible

Quatre **tranches** nouvelles, par fonctionnalité, dans des modules du groupe (`ui/certus_index_spline_corridor_*.py`) :

```
_CorridorRunMixin         cycle de vie : bascule, lancement différé, occupation et progression de la grille,
                          réparation, polissage profond, chaîne d'auto-raffinement
_CorridorRmseViewMixin    onglet RMSE(d) : construction, rafraîchissement, barre d'état, bornes, clic
_CorridorIntervalMixin    intervalle manuel / robuste et ses commandes
_CorridorNkMixin          onglet enveloppe n/k : table, réticule, presse-papiers, CSV
_CorridorRmsePlotMixin    tracé RMSE(d) (Phase 4, accordée par Q1)
```

Classes existantes conservées, au même endroit :

```
CertusIndexSplineCorridorUIMixin(_CorridorRunMixin, _CorridorRmseViewMixin, _CorridorIntervalMixin, _CorridorNkMixin)
    devient le composite « corridors » ; garde _launch_corridor_rmse_gap_heal (couture I7)
_CorridorControlMixin(_CorridorRunMixin, _CorridorRmseViewMixin, _CorridorIntervalMixin)
    coquille de compatibilité (I6) ; même ordre de bases que le composite, obligatoirement
_CorridorWorkerMixin(_CorridorTabMixin)   inchangé (I2, I3, I7, I8)
_CorridorGenMixin                         garde la génération depuis un intervalle
_DataMixin, _CorridorExportMixin          inchangés
_PlotMixin(_CorridorRmsePlotMixin)        Phase 4 seulement
```

**`ui/certus_index_spline_ui.py` n'est pas modifié** : la liste des bases de la fenêtre reste telle quelle, les tranches
entrent dans le MRO par les deux classes de compatibilité. L'adjacence I3 est conservée (aucune tranche n'hérite de
`_CorridorTabMixin`).

### 2.3 Table de migration des méthodes

| Tranche (module cible) | Méthode | Origine |
|---|---|---|
| `_CorridorRunMixin` (`certus_index_spline_corridor_run.py`) | `_start_deferred_corridor_worker` | `ui/certus_index_spline_settings.py:752` |
| | `_finish_curve_minimum_deep_worker_done` | `ui/certus_index_spline_settings.py:869` |
| | `_finish_rmse_heal_worker_done` | `ui/certus_index_spline_settings.py:961` |
| | `_set_corridor_grid_busy` | `ui/certus_index_spline_settings.py:1071` |
| | `_set_corridor_grid_progress_ui` | `ui/certus_index_spline_settings.py:1118` |
| | `_schedule_corridor_auto_refine` | `ui/certus_index_spline_corridorui_mixin.py:29` |
| | `_continue_corridor_auto_refine_after_deep` | `ui/certus_index_spline_corridorui_mixin.py:55` |
| | `_set_corridor_grid_completed_badge` | `ui/certus_index_spline_corridorui_mixin.py:210` |
| | `_refresh_corridors_gui_state_labels` | `ui/certus_index_spline_corridorui_mixin.py:428` |
| | `_on_btn_corridor_clicked` | `ui/certus_index_spline_corridorui_mixin.py:459` |
| | `_on_corridor_chk_state_changed` | `ui/certus_index_spline_corridorui_mixin.py:481` |
| | `_is_rmse_d_grid_worker_finalize_dict` | `ui/certus_index_spline_eventsextras_mixin.py:319` |
| | `_merge_rmse_grid_promotion_into_nominal` | `ui/certus_index_spline_eventsextras_mixin.py:326` |
| | `_on_corr_mode_changed` | `ui/certus_index_spline_eventsextras_mixin.py:959` |
| | `_on_corridor_rmse_grid_live_update` | `ui/certus_index_spline_corridor_gen.py:23` |
| | `_start_curve_minimum_deep_refit` (Phase 5 : utilise le mandataire, F5) | `ui/certus_index_spline_eventsextras_mixin.py:372` |
| `_CorridorRmseViewMixin` (`certus_index_spline_corridor_rmse_view.py`) | `_build_tab_corridor_rmse` | `ui/certus_index_spline_corridorui_mixin.py:132` |
| | `_refresh_corridor_rmse_robust_view` | `ui/certus_index_spline_corridorui_mixin.py:197` |
| | `_update_corridor_rmse_state_bar` | `ui/certus_index_spline_corridorui_mixin.py:221` |
| | `_corridor_profile_source_result` | `ui/certus_index_spline_corridorui_mixin.py:252` |
| | `_set_corridor_rmse_view_data_bounds` | `ui/certus_index_spline_corridorui_mixin.py:267` |
| | `_on_corridor_rmse_lock_scale_toggled` | `ui/certus_index_spline_corridorui_mixin.py:306` |
| | `_on_corridor_rmse_plot_clicked` | `ui/certus_index_spline_settings.py:1332` |
| | `_robust_interval_from_local_quadratic` | `ui/certus_index_spline_eventsextras_mixin.py:657` |
| | `_build_corridor_labels` | `ui/certus_index_spline_rendering.py:1876` |
| `_CorridorIntervalMixin` (`certus_index_spline_corridor_interval.py`) | `_apply_corridor_preset_auto_robust` | `ui/certus_index_spline_settings.py:1019` |
| | `_sync_corridor_manual_controls` | `ui/certus_index_spline_settings.py:1178` |
| | `_generate_corridor_from_current_grid` | `ui/certus_index_spline_settings.py:1250` |
| | `_use_robust_corridor_interval` | `ui/certus_index_spline_corridorui_mixin.py:319` |
| | `_corridor_manual_half_width_nm` | `ui/certus_index_spline_manualmesh_mixin.py:1015` |
| | `_set_corridor_manual_interval_preview` | `ui/certus_index_spline_manualmesh_mixin.py:1024` |
| | `_set_corridor_manual_bounds_labels` | `ui/certus_index_spline_manualmesh_mixin.py:1040` |
| | `_corridor_manual_max_half_width_nm` | `ui/certus_index_spline_manualmesh_mixin.py:1051` |
| | `_reset_corridor_manual_controls` | `ui/certus_index_spline_manualmesh_mixin.py:1071` |
| | `_on_corridor_manual_slider_changed` | `ui/certus_index_spline_manualmesh_mixin.py:1098` |
| | `_build_corridor_tab_generate` | `ui/certus_index_spline_rendering.py:1463` |
| `_CorridorNkMixin` (`certus_index_spline_corridor_nk.py`) | `_interp_corridor_value` (`@staticmethod`, décorateur en `:103`) | `ui/certus_index_spline_corridorui_mixin.py:104` |
| | `_k_corridor_crosshair_formatter` | `ui/certus_index_spline_corridorui_mixin.py:117` |
| | `_build_tab_data_corridor` | `ui/certus_index_spline_corridorui_mixin.py:354` |
| | `_copy_corridor_to_clipboard` | `ui/certus_index_spline_corridorui_mixin.py:391` |
| | `_export_corridor_csv` | `ui/certus_index_spline_corridorui_mixin.py:403` |
| | `_refresh_corridor_table` | `ui/certus_index_spline_corridor_gen.py:646` |
| | `_build_tab_corridor` | `ui/certus_index_spline_rendering.py:1915` |
| `_CorridorRmsePlotMixin` (`certus_index_spline_corridor_rmse_plot.py`, Phase 4) | `_plot_rmse_data_scatter`, `_plot_the_reversal_and_fallback_points`, `_plot_the_breakpoint_events`, `_draw_the_local_parabola`, `_corridor_profile_arrays`, `_prep_rmse_plot_data`, `_draw_corridor_curvature_label`, `_plot_corridor_rmse_tab`, `_manual_grid_note`, `_write_the_rmse_summary` | `ui/certus_index_spline_rendering.py:247, 425, 478, 548, 624, 633, 718, 749, 964, 992` |

**Ne déménagent pas** : les 5 méthodes de I2 ; `_log_regular_grid_result`, `_settle_a_run_that_returned_no_result_dict`,
`_log_the_result_dictionary_received`, `_hand_the_result_to_the_manual_dialog` (`ui/certus_index_spline_corridor_worker.py:314,
600, 627, 689` — I7, I8) ; toutes les méthodes de `_DataMixin` (I7, I10) ; `_launch_corridor_rmse_gap_heal`
(`ui/certus_index_spline_corridorui_mixin.py:75` — I7) ; les 5 méthodes de génération de `_CorridorGenMixin`
(`ui/certus_index_spline_corridor_gen.py:159, 262, 323, 440, 580`), déjà cohérentes.

### 2.4 Contrats explicites

Nouveau module `ui/certus_index_spline_corridor_host.py`, **de typage seulement** : il n'est importé que sous
`if TYPE_CHECKING:` et n'importe lui-même ses types que sous `if TYPE_CHECKING:`. Les signatures sont à recopier du
code aux lignes indiquées, sans les réinterpréter.

```python
class IndexSplineRunHost(Protocol):
    """Ce que le cycle de vie du worker offre à tout mixin (fourni par la fenêtre et CertusBaseApp)."""
    logger: logging.Logger | None            # ui/certus_base_app.py:367
    df: pd.DataFrame | None                  # ui/certus_index_spline_ui.py:100
    _worker: GenericWorker | None            # :102
    _stop_event: threading.Event             # :104
    _last_result: dict | None                # :106
    _last_worker_result: dict | None         # :108
    _last_run_cfg: SplineOptConfig | None    # :112
    _worker_role: str                        # :114
    _best_live_rmse: float                   # :116
    _best_live_result: dict | None           # :118
    _prog_ui_last: int                       # :94
    _last_live_log_mono: float               # :96
    _live_best_detail_log_mono: float        # :98
    btn_run: QPushButton; btn_stop: QPushButton; lbl_status: QLabel
    def _prepare_worker_restart(self) -> None: ...            # ui/certus_index_spline_eventsextras_mixin.py:170
    def _cleanup_thread(self) -> None: ...                    # :113
    def _on_worker_err(self, ...) -> None: ...                # :258
    def _prog_reset_bar(self) -> None: ...                    # :104
    def _refresh_post_optimization_option_controls(self) -> None: ...   # :986
    def _format_post_optimization_status(self, ...) -> str: ...         # :1047
    def _post_optimization_ready_status(self, ...) -> str: ...          # :1068
    def _on_worker_done(self, result: object) -> None: ...    # ui/certus_index_spline_corridor_worker.py:366
    def _on_progress(self, ...) -> None: ...                  # ui/certus_index_spline_mixins_ui.py:536
    def _build_opt_config(self, *, notify: bool = True) -> SplineOptConfig | None: ...   # :49
    def _cfg_with_result_substrate(self, cfg, result): ...    # ui/certus_index_spline_corridor_data.py:239
    def _plot_result(self, ...) -> None: ...                  # ui/certus_index_spline_execution.py:744
    def _refresh_data_table(self, ...) -> None: ...           # ui/certus_index_spline_corridor_data.py:541
    def _manual_postprocess_seed_result(self) -> dict | None: ...   # ui/certus_index_spline_manualmesh_mixin.py:1123
    @staticmethod
    def _rmse_from_result_dict(d: dict) -> float: ...         # ui/certus_index_spline_eventsextras_mixin.py:179

class IndexSplineViewHost(Protocol):
    """Aides de tracé et de mise en page que les tranches corridors empruntent."""
    def _add_curve(self, ...): ...                            # ui/certus_index_spline_eventsextras_mixin.py:821
    def _create_empty_context_widget(self, ...): ...          # :546
    def _lam_piecewise_report_grid_nm(self, lo, hi): ...      # :707
    def _apply_cell_style(self, ...): ...                     # :792
    def _add_context_page(self, widget): ...                  # ui/certus_index_spline_rendering.py:1834
    def _ensure_complete_manifest_for_secondary_export(self) -> bool: ...   # ui/certus_index_spline_execution.py:93

class CorridorStateHost(Protocol):
    """Les attributs d'état du tableau CORRIDOR_STATE (§2.5), annotés un à un."""

class CorridorWidgetsHost(Protocol):
    """Les widgets corridors et leur site de création."""
    # ui/certus_index_spline_corridor_tab.py:307-562 ; ui/certus_index_spline_corridorui_mixin.py:148, 162, 169, 368-381
    # ui/certus_index_spline_rendering.py:1185-1194, 1474-1522, 1799-1802, 1888-1906, 1938-1953
    # cb_corr_mode, sp_corr_rmse_delta, chk_corr_scientific_nominal : lus en ui/certus_index_spline_settings.py:1022-1038,
    #   site de création à relever en Phase 1

class CorridorHost(IndexSplineRunHost, IndexSplineViewHost, CorridorStateHost, CorridorWidgetsHost, Protocol): ...
```

Le même module publie `CONTRACTS: dict[str, tuple[str, ...]]`, qui associe à chaque nom de mixin corridors les
protocoles qu'il exige. Aucun attribut n'est ajouté aux classes de mixin : leur surface reste identique.

**Mise en application** — un test nouveau (Phase 1) rend ces contrats exécutoires, par analyse de l'arbre syntaxique :

- T1 — pour chaque mixin corridors, l'ensemble des `self.nom` lus et non définis par lui est inclus dans les membres de
  ses protocoles ;
- T2 — `CertusIndexSplineApp` fournit chaque membre (méthode : attribut de la classe ; état : affecté quelque part) ;
- T3 — la valeur par défaut de chaque `getattr(self, "_corridor_…", défaut)` est celle du tableau d'état ;
- T4 — aucune méthode n'est définie par deux mixins du MRO, hors liste blanche des redéfinitions de §1.4 ;
- T5 — aucun mixin du MRO ne définit `__init__` ;
- T6 — aucun mixin du MRO n'a `Protocol` ni `ABC` parmi ses bases.

### 2.5 État corridor déclaratif

Nouveau module feuille `ui/certus_index_spline_corridor_state.py` (n'importe que `numpy`) : un tableau
`CORRIDOR_STATE` — nom → type, fabrique de la valeur par défaut, site de naissance, remis à zéro ou non par
`_load_defaults`. Contenu relevé :

| Attribut | Défaut | Naissance actuelle |
|---|---|---|
| `_corridor_rmse_base_snapshot` | `None` | `ui/certus_index_spline_ui.py:110` |
| `_corridor_rmse_manual_active` / `_lo` / `_hi` | `False` / `nan` / `nan` | `ui/certus_index_spline_ui.py:120-124` |
| `_corridor_rmse_manual_slider_scale` | `100` | `ui/certus_index_spline_ui.py:126` |
| `_corridor_auto_refine_plan` | `None` | `ui/certus_index_spline_ui.py:139` |
| `_corridor_rmse_d_vals`, `_corridor_rmse_vals` | tableau vide `float64` | `ui/certus_index_spline_corridorui_mixin.py:152-153` |
| `_corridor_rmse_best_idx`, `_corridor_rmse_center_nm` | `-1`, `nan` | `ui/certus_index_spline_corridorui_mixin.py:154-155` |
| `_corridor_rmse_grid_live_t0`, `_corridor_rmse_live_last_plot_ts` | `nan`, `nan` | `ui/certus_index_spline_corridorui_mixin.py:156-157` |
| `_corridor_rmse_live_plot_min_interval_s` | `0.12` | `ui/certus_index_spline_corridorui_mixin.py:158` |
| `_corridor_rmse_robust_lo` / `_hi` / `_ok` | `nan` / `nan` / `False` | `ui/certus_index_spline_corridorui_mixin.py:159-161` |
| `_corridor_parabola_half_window_pts` | `4` | `ui/certus_index_spline_settings.py:1046` |
| `_corridor_symmetric_center_mode` | `"parabola"` | `ui/certus_index_spline_settings.py:1048` |
| `_corridor_adaptive_rmse_ref_half_width_nm` | `1.5` | `ui/certus_index_spline_settings.py:1050` |
| `_corridor_adaptive_rmse_probe_steps_each_side` | `3` | `ui/certus_index_spline_settings.py:1052` |
| `_corridor_adaptive_rmse_noise_factor` | `3.0` | `ui/certus_index_spline_settings.py:1054` |
| `_corridor_adaptive_rmse_min` | `_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN` | `ui/certus_index_spline_settings.py:239, 1056` |
| `_corridor_rmse_requested_grid` | tableau vide | `ui/certus_index_spline_corridor_worker.py:883` |
| `_corridor_rmse_smart_interval` | `None` | `ui/certus_index_spline_rendering.py:849-851` |
| `_corridor_rmse_parab_export`, `_corridor_rmse_robust_export` | `None` | `ui/certus_index_spline_rendering.py:858-859` |
| `_corridor_rmse_curvature_label` | `None` | `ui/certus_index_spline_rendering.py:747` |
| `_corridor_k_crosshair_lam` / `_nom` / `_lo` / `_hi` | liste vide | `ui/certus_index_spline_corridor_tab.py:154-157` |

Hors tableau, car ce sont des objets graphiques gardés par `hasattr` : `_corridor_rmse_curve`,
`_corridor_rmse_best_marker` (`ui/certus_index_spline_corridorui_mixin.py:162, 169` ; gardes
`ui/certus_index_spline_rendering.py:278, 311`).

Dans ce plan, le tableau **déclare et vérifie** (test T3) ; il n'initialise rien. L'initialisation anticipée de tout
l'état dans `__init__` est une option séparée (Phase 6, arbitrage Q8).

### 2.6 Graphe d'imports cible

```
corridor_common        feuille (numpy, os, logging) ; reçoit l'unique `_apply_fixed_log_k_axis` en 2b                                       existant
corridor_state         feuille (numpy)                                           nouveau
corridor_host          typage seul, importé sous TYPE_CHECKING                   nouveau
corridor_ui            passerelle ─► certus_ui, certus_plot, certus_manual_sigma_knot_dialog   existant, 3 instructions
corridor_jobs          ─► certus.spline.*                                        nouveau (Phase 5)
corridor_run, corridor_rmse_view, corridor_interval, corridor_nk, corridor_rmse_plot
                       ─► corridor_common, corridor_state, corridor_ui, corridor_jobs,
                          certus.spline.*, certus.core.*, certus.utils.*         nouveaux
corridor_tab, corridor_data, corridor_gen, corridor_worker                       existants, inchangés
corridors (façade)     ─► les parties existantes                                 inchangée
settings               ─► corridor_common, corridor_run, corridor_rmse_view, corridor_interval
corridorui_mixin       ─► common, corridor_run, corridor_rmse_view, corridor_interval, corridor_nk
rendering              ─► corridor_rmse_plot                                     Phase 4
common, execution, rendering ─► corridor_common                                  Phase 2b
common, smart_init     ─► certus.spline.certus_index_spline_core                 Phase 2c (settings le fait déjà)
smart_init             ─► common                                                 Phase 2d (mixins_ui ─► smart_init reste retardé)
common ─► corridors, execution, rendering, settings, mixins_ui ; certus_index_spline_ui ─► common, *_mixin
```

**Règles qui garantissent l'absence de cycle**

- R1 — Un module `certus_index_spline_corridor_*` n'importe jamais, au niveau module, `common`, `certus_index_spline_ui`,
  `settings`, `execution`, `rendering`, `mixins_ui` ni un module `*_mixin`. Ces modules sont au-dessus du groupe.
- R2 — Les tranches n'atteignent le reste de `certus.ui` que par la passerelle. Un nom manquant s'ajoute à
  l'instruction `from certus.ui.certus_ui import (...)` existante de la passerelle : le nombre d'instructions reste 3 (I4).
- R3 — Les aides de niveau module qu'une méthode déplacée utilise déménagent **avec elle** ; le module d'origine les
  réimporte (même objet). Jamais l'inverse, qui fermerait un cycle.
- R4 — La façade `corridors` n'exporte aucun nom qui existe aussi dans `certus_index_spline_ui` sous un autre objet
  (I15). En particulier, le mandataire `CertusIndexSplineApp` n'y entre jamais.
- R5 — Toute classe qui hérite de plusieurs tranches les cite dans l'ordre canonique Run, RmseView, Interval, Nk.
- R6 — Tout nouveau fichier est ajouté à l'index git avant de lancer les tests (I14, I11) et nommé dans un test (I16).

**Entre familles `re` / `index` / `design` / `strat`**

```
domain ─► physics ─► core, utils ─► metal, spline ─► workers ─► ui ─► scripts racine CERTUS_*.py
```

- R7 — Un module `certus_<famille>_*` importe des modules partagés (sans préfixe de famille) et ceux de sa famille ;
  jamais ceux d'une autre. Cible : résorber les trois arêtes de F12 en descendant l'utilitaire commun dans un module
  partagé, l'ancien emplacement le réexportant.
- R8 — La famille se reconnaît au **préfixe** `certus_<famille>_`, jamais à une sous-chaîne (F13).
- R9 — `re` standard : aucun fichier `re.py` ni dossier `re/` dans le dépôt, à aucune profondeur ; la famille s'écrit
  toujours `certus_re_*` ou `CERTUS_RE`. Les imports nouveaux sont absolus et complets
  (`from certus.ui.certus_re_ui import …`), jamais relatifs, et aucun module de bibliothèque ne touche `sys.path`.
  Un test de garde l'impose (Phase 1).

### 2.7 Filet de non-régression

Outil `scripts/refactor_guard.py` (écrit en Phase 0), lancé dans un interpréteur neuf, Qt hors écran. Trois
sous-commandes : `snapshot --out F`, `compare REF NEW [--manifest M …] [--full]`, `report F [--window NOM] [--full]`.
Il sort `GUARD=OK` (code 0), `GUARD=DIFF` (1) ou `GUARD=ERROR` (2 : mauvais arbre, deux versions de Python, fichier
illisible). Un manifeste nomme ce qu'une phase a le droit de changer — clés `moved_methods`, `moved_objects`,
`changed_code`, `rebound`, `new_classes`, `removed_from_mro`, `added_attributes`, `acknowledged_seams`, format en tête
du script ; les manifestes se cumulent, la comparaison se fait toujours contre la référence de Phase 0. Deux valeurs
refaites à chaque import sont relevées par leur nom et leur type seulement : `_env`, et les attributs `__pydantic_*`.

Il relève, pour les 9 fenêtres listées en `tests/unit/test_self_attributes_are_defined.py:35-45` (un test tient les deux
listes égales), et pour les classes que définissent les modules du groupe :

1. **Surface de classe** : pour chaque attribut, nature (fonction, `staticmethod`, `classmethod`, propriété, signal),
   classe et module de définition, empreinte du bytecode (constantes et fonctions imbriquées comprises), signature.
2. **Résolution des globaux** : pour chaque fonction, chaque nom global qu'elle charge et le descripteur de l'objet
   trouvé dans son module (`module:nom_qualifié` pour une classe ou une fonction, type et `repr` sinon).
3. **Espace de noms** de chaque module du groupe.
4. **MRO** de chaque fenêtre.
5. **Résolution par la façade** `CERTUS_INDEX_SPLINE` de chaque nom atteignable.
6. **Coutures** : cibles de `monkeypatch.setattr` et de `patch` des tests qui visent un module du groupe.

`compare` échoue sauf si : (1) seuls la classe et le module de définition changent, et seulement pour les entrées du
*manifeste de déplacement* de la phase, à empreinte identique ; (2) chaque global se résout au même objet — écarts admis
et listés : `__name__`, `__file__` ; (3) l'espace de noms de chaque module est un sur-ensemble de l'ancien ;
(4) les noms de I6 et l'adjacence de I3 tiennent ; (5) la résolution par la façade est identique ; (6) aucune fonction
déplacée n'utilise un global patché dans son module d'origine — sauf couture reconnue dans le manifeste, raison écrite
(`acknowledged_seams`).

**Ce que le filet ne couvre pas, à dire franchement** : le nom de module qui apparaît dans les messages de débogage
(`"Silenced exception in %s", __name__`) et le nom qualifié des méthodes dans les traces changent pour les méthodes
déplacées. Aucune entrée du registre de dette nommée par fonction n'est touchée (§1.6).

**Les deux écarts au « déplacement pur », isolés et listés** : la Phase 2b change des messages DEBUG, et rien d'autre
(détail dans la phase) ; les Phases 2a et 2c retirent du `__annotations__` du module `common` les constantes qui y
deviennent des imports — aucun lecteur : vérifié en Phase 0 (seul `tests/unit/test_self_attributes_are_defined.py:78`
lit des annotations, et ce sont celles des classes).

---

## 3. Séquence d'exécution atomique

Règles communes à toutes les phases : un commit par sous-phase ; `git add` des fichiers créés avant tout test ; une seule
commande de test à la fois ; en cas d'échec, on annule le commit, on ne corrige pas en avant. Commande type :
`pytest -q --no-cov <fichier>`.

**Garde, à la fin de chaque phase** (attendu : `GUARD=OK`) — le manifeste de la phase s'écrit dans
`reports/refactor_corridors_2026-11-11/manifests/`, se commite avec elle, et s'ajoute à ceux des phases déjà faites :

    python scripts/refactor_guard.py snapshot --out <fichier temporaire>
    python scripts/refactor_guard.py compare reports/refactor_corridors_2026-11-11/reference_snapshot.json <fichier temporaire> --manifest <manifeste> [--manifest …]

**État de départ connu** (Phase 0) : `coherence_md.py` sort en erreur sur 3 commandes mortes de documents de campagne,
hors périmètre ; une validation est bonne quand elle ne montre rien de plus.

**Lot de contrôle** (cité « LOT » ci-dessous), à lancer après le test principal de chaque phase qui touche du code :
`tests/unit/test_the_corridors_split_keeps_every_name_and_the_layering_where_it_was.py`,
`tests/unit/test_gui_smoke.py`, `tests/unit/test_self_attributes_are_defined.py`,
`tests/unit/test_project_imports_resolve.py`, `tests/unit/test_the_architecture_debt_only_shrinks.py`,
`tests/unit/test_a_module_that_was_in_an_import_cycle_imports_first_and_alone.py`,
`tests/unit/test_mwir_gui_flow.py`, `tests/unit/test_post_opt_option_unlock.py`,
`tests/integration/test_suite_ui_instantiation.py`, `tests/unit/test_certus_is_written_in_english.py`,
`tests/unit/test_tests_destroy_the_windows_they_build.py` (le garde-fou que le lot d'origine ne couvrait pas et que la
validation de Phase 1 a fait tomber), et les fichiers de test créés par les phases déjà faites. La validation complète
se lance à la fin de chaque phase entière, pas de chaque sous-phase.

### [x] Phase 0 — Filet (aucun code de production modifié) — faite le 2026-11-11

- **Créés** : `scripts/refactor_guard.py` ; `tests/unit/test_refactor_guard_compares_two_class_surfaces.py` — 13 tests
  sur un paquet synthétique écrit deux fois. Accepté : un déplacement pur avec son manifeste. Refusés : le même
  déplacement sans manifeste, un corps modifié, un global qui se résout ailleurs, un nom qui quitte l'ancien module, un
  MRO réordonné, une méthode qu'une autre classe gagne, une couture laissée derrière, deux versions de Python.
- **Instantané de référence** : `reports/refactor_corridors_2026-11-11/reference_snapshot.json` — 9 fenêtres,
  49 classes, 28 modules, 1 205 fonctions, 530 coutures ; Python 3.15.2 ; relevé sur `15d518aa`.
  - Stabilité : deux relevés dans deux interpréteurs donnent `problems=0`, `GUARD=OK`.
  - Contrôle négatif sur l'arbre réel : une chaîne changée dans `_start_deferred_corridor_worker` donne
    `BYTECODE | …_CorridorControlMixin._start_deferred_corridor_worker`, `problems=1`, `GUARD=DIFF` ; fichier restauré.
- **État de départ : il n'était pas vert.** `python scripts/preflight.py` rendait `PREFLIGHT=STOP`, puis
  `python scripts/validate_parallel.py` sur `9d011d68` rend `VALIDATION=NO-GO` (Python 3.15.2, ruff 0.16.9).

  | Étape | Échec | Cause | Suite donnée |
  |---|---|---|---|
  | ruff | 1 erreur B905 | `reports/RICL_ultimate_2026-11-05/exhaustive_clean_bs.py:43` (commit `9632f15b`) | corrigé, `strict=False`, commit `9d011d68` |
  | unit | `test_no_source_carries_an_invalid_escape` | `"\l"` en `reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_v2/oe_complex_figures_2026-11-03_before_print.py:83` (commit `ddf8bf24`) | corrigé, chaîne brute, commit `15d518aa` |
  | unit | `test_a_big_document_at_the_root_is_hidden_from_the_default_searches` | ce plan, posé à la racine | plan déplacé dans `reports/` : `10 passed` |
  | coherence_md | 3 commandes mortes | `PROCEDURE_2026-10-31_11-01.md:164-165` et `code1_README_2026-11-02_before_localmax.md:15` (dossier `envelope_v2`) citent `cissoid_metal_trade.py`, `take_record.py`, `hidden_resonances.py` | **échec connu, laissé tel quel sur décision** : hors périmètre |
  | rest | 1 artefact de charge | `tests/property/test_physics_properties.py::test_bare_substrate_transmission_bounds`, vert seul en série | signalé |

  Le reste passe : oracle `1186 passed` ; unit `5771 passed` ; ui `1356 passed` ; rest `320 passed` ; performance
  `29 passed` ; `check_claude_md`, `check_docs` : PASS.
- **Points « à confirmer » levés**
  - MRO (§1.4) : 44 classes ; 15 noms sont définis par plus d'une classe du projet, toujours une classe INDEX SPLINE
    au-dessus de la base : `APP_NAME`, `APP_TITLE`, `DEFAULT_WIDTH`, `DEFAULT_HEIGHT`, `MIN_WIDTH`, `MIN_HEIGHT`,
    `__init__`, `_COMPUTATION_THREADS`, `_apply_config`, `_collect_config`, `_build_ui`, `_get_log_widget`,
    `_setup_logger`, `_warmup_numba`, `closeEvent`. **Aucun nom, méthode ou attribut de classe, n'est défini par deux des
    21 mixins.** Ces 15 noms sont la liste blanche de T4.
  - Registre de dette : lu en entier, conforme à §1.6.
  - Coutures (I7) : l'inventaire mécanique retrouve les 8 modules et les 14 noms de I7, sans en ajouter au niveau module.
    `settings`, `eventsextras_mixin`, `corridor_gen`, `corridor_tab` et `common` n'en ont aucune. S'y ajoutent deux
    remplacements globaux, qu'un déplacement ne déplace pas : `pg.TextItem` (atteint par `corridors`, `execution` et la
    façade, `tests/unit/test_spectral_knot_markers.py:107-109`) et `QMessageBox.warning` (par la façade,
    `tests/unit/test_post_opt_option_unlock.py:165`).
  - `__annotations__` d'un module : aucun lecteur dans `certus/`, `tests/`, `scripts/`.
  - **Q5, par l'exécution** : dans chacun des deux tests, 0 faux worker construit, 1 vrai `GenericWorker` construit et
    **démarré**. Le fil lance le vrai calcul de corridor sur la fausse configuration et y échoue
    (`AttributeError: '_Cfg' object has no attribute 'corridor_view'`) sans que le test le voie. La Phase 9 est donc
    fondée ; d'ici là, ces deux tests démarrent un fil qu'ils n'attendent pas.
- **Validation après la phase** (`validate_parallel.py`, `15d518aa` plus les fichiers de la phase) : ruff PASS ; oracle
  `1186 passed` ; unit `5785 passed`, 1 artefact vert seul en série
  (`test_bench_kernels_measures_ratios_and_alerts_on_a_regression.py`, un test qui chronomètre) ; ui `1356 passed` ; rest
  `321 passed` ; performance `29 passed`. Seul rouge : `coherence_md`, l'échec connu.
- **Non fait** : `docs/ETAT.md` n'a pas été mis à jour.

### [x] Phase 1 — Contrats et état déclaratif (ajouts purs) — faite le 2026-11-11

- **Créés** : `certus/ui/certus_index_spline_corridor_state.py` ; `certus/ui/certus_index_spline_corridor_host.py` ;
  `tests/unit/test_the_corridor_mixins_declare_what_they_read_on_the_window.py` (T1 à T6, 48 tests) ;
  `tests/unit/test_no_module_shadows_the_standard_library.py` (R9, 4 tests) ;
  `reports/refactor_corridors_2026-11-11/manifests/phase_1.json`. Aucun fichier existant modifié.
- **Le contrat, tel qu'il est construit.** `CONTRACTS` donne pour chaque mixin corridor la liste **exacte** des noms
  qu'il lit sur `self` sans les définir (lectures directes, `getattr` / `hasattr`, `self.__class__.x`, `type(self).x`, et
  le mandataire `CertusIndexSplineApp.x`) ; le test exige l'égalité, dans les deux sens. Les protocoles typent l'union de
  ces noms : signatures recopiées mécaniquement des méthodes de la fenêtre, type des widgets pris sur leur constructeur.
  Un test vérifie que chaque méthode déclarée a les mêmes paramètres que celle de la fenêtre.

  | Mixin | Noms lus sur la fenêtre |
  |---|---|
  | `_CorridorControlMixin` | 72 |
  | `_CorridorWorkerMixin` (avec `_CorridorTabMixin`) | 56 |
  | `CertusIndexSplineCorridorUIMixin` | 44 |
  | `_CorridorGenMixin` | 29 |
  | `_CorridorExportMixin` | 15 |
  | `_CorridorTabMixin` | 14 |

  150 membres en tout : `IndexSplineRunHost` 85, `IndexSplineViewHost` 6, `CorridorStateHost` 24, `CorridorWidgetsHost`
  35 ; 13 sont typés `Any` (valeur construite de plus d'une façon).
- **L'état** : `CORRIDOR_STATE` compte 31 attributs ; s'y ajoutent 2 objets graphiques gardés par `hasattr` et 1 nom lu
  mais jamais affecté (`_corridor_rmse_profile_win`, Q13). Les tests exigent que la table nomme tout attribut
  `_corridor_*` que le groupe affecte, que chacun naisse dans la fonction indiquée, que `reset` dise ce que fait
  `_load_defaults`, et que chaque repli de `getattr` soit celui de la table.
- **Ce que la phase a appris**
  - T3 : **aucun attribut n'a deux replis différents.** Pas d'arbitrage à ouvrir de ce côté. Le repli diffère parfois de
    la valeur de naissance par le type seulement (`[]` pour un tableau vide `float64`).
  - Quatre widgets que les mixins corridors lisent ne sont posés par aucune classe de la fenêtre : `lbl_corridors_state_adv`,
    `cb_corr_mode`, `sp_corr_rmse_delta`, `chk_corr_scientific_nominal` sont écrits **sur** la fenêtre, de l'extérieur, par
    le constructeur de `ui/certus_index_spline_managers_ui.py:268, 284, 332, 353` (`app.x = …`). C'est le site de création
    que §2.4 laissait à relever ; les tests en tiennent compte.
  - `_corridor_rmse_best_idx` reçoit `None` dans `_PlotMixin._plot_rmse_data_scatter` (`ui/certus_index_spline_rendering.py:306`)
    alors que partout ailleurs « pas de minimum » vaut `-1`, repli compris : Q17.
  - Sept attributs d'état ne sont lus par aucun mixin corridor (les six réglages du préréglage robuste et
    `_corridor_rmse_curvature_label`) : leurs lecteurs sont dans `mixins_ui` et `rendering`.
  - R9 : rien à la racine ni sous `certus/` ne porte le nom d'un module standard ; aucun import relatif dans le groupe.
- **Preuves** : les deux fichiers de test, `52 passed` ; contrôle négatif (un repli `100` changé en `101`) : 1 échec,
  fichier restauré ; LOT `132 passed` ; garde sans manifeste : 6 classes nouvelles et rien d'autre ; avec
  `manifests/phase_1.json` : `problems=0`, `GUARD=OK`.
- **Validation** (`validate_parallel.py`) : oracle `1188 passed` ; unit `5836 passed` ; ui `1358 passed` ; rest
  `321 passed` ; performance `29 passed`. Un rouge nouveau, réel, causé par la phase et corrigé : le garde-fou
  `tests/unit/test_tests_destroy_the_windows_they_build.py` prenait le test des contrats pour un test qui construit une
  fenêtre, parce qu'il y lisait des noms de fenêtre écrits en chaînes à côté d'un `getattr` ; le test compare
  maintenant les classes elles-mêmes. Rejoué : le garde-fou et les fichiers de la phase, `58 passed`. La validation
  complète n'a pas été relancée après cette retouche de deux lignes d'un fichier de test. Reste rouge : `coherence_md`,
  l'échec connu ; un artefact de charge, vert seul (`test_the_default_pytest_run_is_quiet.py`).
- **Pour la Phase 3** : toute classe du MRO dont le nom contient « Corridor » doit avoir son entrée dans `CONTRACTS`.
  Chaque sous-phase 3x y inscrit sa tranche et retire des mixins d'origine les noms que leurs méthodes parties lisaient.

### [x] Phase 2 — Sources uniques (cinq sous-phases, un commit chacune) — faite le 2026-11-11

**Validation de la phase** (`validate_parallel.py`, `de79f62e`, Python 3.15.2) : ruff PASS ; oracle `1188 passed` ; unit
`5894 passed` ; ui `1358 passed` ; rest `320 passed` et 1 artefact de charge, vert seul en série
(`test_bare_substrate_transmission_bounds`, déjà vu en Phase 0) ; performance `29 passed` ; `check_claude_md`,
`check_docs` PASS. Seul rouge : `coherence_md`, l'échec connu (3 commandes mortes). Sa section F signale en plus 5
renvois `fichier.py:N` de ce plan qui ne pointent plus sur leur symbole : les numéros de ligne du plan sont ceux du
relevé de Phase 0 (`15d518aa`), et chaque phase qui déplace du code en décale d'autres. Ce n'est pas un échec de l'outil.

Test nouveau, créé en 2a, complété en 2b, 2c puis 2d : `tests/unit/test_the_index_spline_shared_names_have_one_definition.py`.
Par analyse syntaxique, chaque nom listé n'est défini ou affecté au niveau module que dans un seul fichier de `certus/` ;
partout ailleurs c'est le même objet, importé. Chaque cas ajouté doit échouer sur le code d'avant sa sous-phase.

- [x] **2a — Constantes corridor** (valeurs égales, aucun comportement changé) — faite le 2026-11-11 : le test nouveau
  échouait avant (`6 failed`) et passe ; ruff PASS sur le dépôt ; lot de contrôle `191 passed` ; garde avec
  `manifests/phase_2a.json` : `problems=0`, `GUARD=OK`. Les deux commentaires qui expliquaient les valeurs ont suivi
  les définitions dans `corridor_common`.
  Créer : le test ci-dessus, avec le cas des trois constantes.
  Modifier : `certus/ui/certus_index_spline_common.py` (lignes 110-115) et `certus/ui/certus_index_spline_settings.py`
  (lignes 62-64) : remplacer la définition de `_DEFAULT_CORRIDOR_RMSE_DELTA`, `_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN`,
  `_CORRIDOR_K_TAB_MIN_HALF_WIDTH` par un import depuis `certus/ui/certus_index_spline_corridor_common.py`.
  Vérifier : `refactor_guard compare` — valeurs égales, mêmes noms dans chaque module, `__all__` de `common` inchangé.
  Test : le test nouveau, puis `tests/unit/test_spectral_knot_markers.py`, puis LOT.

- [x] **2b — `_apply_fixed_log_k_axis` (Q3 : unifier) — seule sous-phase du plan qui change un comportement** — faite le
  2026-11-11 : les 7 cas nouveaux du test échouaient avant (`7 failed, 6 passed`) et passent (`13 passed`) ; ruff PASS sur
  le dépôt ; lot de contrôle et `test_spectral_knot_markers.py` `215 passed` ; garde avec `manifests/phase_2b.json` :
  `problems=0`, `GUARD=OK`. Écarts au texte ci-dessous : `common` reçoit les trois noms par son import existant de la
  façade `corridors` (mêmes objets que la feuille) ; plafond de `rendering.py` 1967 → 1952 ; le test admet la délégation
  de `monitor_ui` par une table `DELEGATES` et vérifie qu'elle atteint la définition unique.
  Référence retenue : le corps de `ui/certus_index_spline_common.py:155-177`.
  Modifier :
  - `certus/ui/certus_index_spline_corridor_common.py` : `import logging` en tête ; y définir `_K_PLOT_YMIN` et
    `_K_PLOT_YMAX` (valeurs de `ui/certus_index_spline_common.py:152-153`) ; donner à `_apply_fixed_log_k_axis` le corps
    de référence, le journal y étant obtenu sur place par `logging.getLogger("CERTUS_INDEX_SPLINE")`. **Aucun nom
    `logger` de niveau module n'y est ajouté** : I1 l'imposerait à la façade, où il masquerait celui de la fenêtre (I15).
  - `certus/ui/certus_index_spline_corridors.py` (façade) : ajouter `_K_PLOT_YMIN` et `_K_PLOT_YMAX` à l'import existant
    depuis `corridor_common` (I1 : tout nom affecté par une partie est attribut de la façade).
  - `certus/ui/certus_index_spline_common.py` : retirer les lignes 152-177, importer les trois noms de la feuille
    (`tests/unit/test_spectral_knot_markers.py:9` les lit ici : ils doivent y rester).
  - `certus/ui/certus_index_spline_execution.py` (lignes 44-58) et `certus/ui/certus_index_spline_rendering.py`
    (lignes 71-85) : remplacer la copie locale par le même import.
  - `tests/architecture_debt.json` : plafond de `rendering.py` abaissé (I12).
  - le test nouveau : cas « une seule définition ; `monitor_ui` ne fait que déléguer ».
  Ne pas toucher : `certus/ui/certus_index_spline_monitor_ui.py:14-16` (sa délégation paresseuse vers `common` atteint
  désormais la feuille), `certus/ui/certus_index_spline_corridor_tab.py:14`,
  `certus/ui/certus_index_spline_layoutextras_mixin.py:6`, `tests/unit/test_spectral_knot_markers.py`.
  Écarts admis, et eux seuls — `refactor_guard` en reçoit la liste :
  1. le bytecode de `corridor_common._apply_fixed_log_k_axis` ;
  2. `_apply_fixed_log_k_axis` de `common`, `execution` et `rendering` devient l'objet de la feuille ;
  3. pour les appelants de `execution`, `rendering` et `corridor_tab` : l'échec de `logYCheck` émet un message DEBUG sur
     le journal « CERTUS » au lieu de se taire ;
  4. pour les appelants de `corridor_tab` (`:274, 277`) : l'échec global est journalisé sur « CERTUS_INDEX_SPLINE » au
     lieu de « CERTUS » (`execution`, `rendering` et `common` utilisaient déjà ce journal : `:42`, `:69`, `:68`) ;
  5. `__name__` dans le message interne (module de la feuille au lieu de `common`).
  L'axe réglé — mode log, bornes 1e-6 et 1e-2 — est le même avant et après, pour tous les appelants.
  Vérifié à l'audit : `_K_PLOT_YMIN` / `_K_PLOT_YMAX` ne sont écrits nulle part dans `certus/`, `tests/`, `scripts/`.
  Test : le test nouveau, puis `tests/unit/test_spectral_knot_markers.py`
  (`test_apply_fixed_log_k_axis_forces_requested_bounds`), puis
  `tests/unit/test_the_corridors_split_keeps_every_name_and_the_layering_where_it_was.py`, puis LOT.

- [x] **2c — Constantes de fenêtre (Q4 : source = cœur spline)** (valeurs égales, aucun comportement changé) — faite le
  2026-11-11 : les cas nouveaux échouaient avant (`18 failed, 27 passed` : les 16 définitions, et l'identité des deux
  flottants `SIO2_DEFAULT_D_*`) et passent (`45 passed`) ; ruff PASS ; lot de contrôle `247 passed` ; garde avec
  `manifests/phase_2c.json` : `problems=0`, `GUARD=OK`. Le commentaire de `_UNCERTAINTY_DEFAULTS_REV` reste dans
  `common`, où il renvoie au cœur.
  Source, **non modifiée** : `certus/spline/certus_index_spline_core.py:43-45, 2095-2107` (16 noms). Ce fichier est au
  registre à 2 108 lignes (§1.6) : il ne reçoit rien.
  Modifier :
  - `certus/ui/certus_index_spline_common.py` : remplacer les 16 définitions (lignes 70-84, 90, 96-102, 106, 121-123)
    par un import depuis `certus.spline.certus_index_spline_core` — import descendant, que `settings` fait déjà (`:34`).
  - `certus/ui/certus_index_spline_smart_init.py` : `_QS_SPLINE_ORG` et `_QS_SPLINE_APP` (lignes 68-69) rejoignent
    l'import existant depuis le cœur (`:40`).
  - le test nouveau : cas des 16 noms.
  Ne pas toucher : `_QS_SMART_INIT_DEEP` et `_QS_SMART_INIT_TWO_PHASE` (Phase 2d) ; `_QS_NK_PROFILE_INTERP`,
  `_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY`, `SIO2_DEFAULT_NK_PROFILE_INTERP` (absents du cœur, une seule définition trouvée) ;
  `SmartInitPayload` (Q9).
  Vérifier : `refactor_guard compare` — valeurs égales, mêmes noms dans chaque module, `__all__` de `common` inchangé,
  résolution par la façade `CERTUS_INDEX_SPLINE` identique (le cœur y est interrogé en premier, I15) ;
  `common` s'importe toujours seul et en premier (I13).
  Test : le test nouveau, puis `tests/unit/test_gui_smoke.py`, puis LOT.

- [x] **2d — Clés du smart-init (Q16 : source = `common`)** (valeurs égales, aucun comportement changé) — faite le
  2026-11-11 : les cas nouveaux échouaient avant (`3 failed, 47 passed`) et passent ; ruff PASS ; les trois tests cités
  ci-dessous et le lot de contrôle `255 passed` ; garde avec `manifests/phase_2d.json` : `problems=0`, `GUARD=OK`. Le
  cas « seul et en premier » lance un interpréteur neuf et y exige que `smart_init` ait chargé `common` et en tienne
  les deux clés.
  Source, **non modifiée** : `certus/ui/certus_index_spline_common.py:92-94` (`_QS_SMART_INIT_DEEP`,
  `_QS_SMART_INIT_TWO_PHASE`).
  Modifier :
  - `certus/ui/certus_index_spline_smart_init.py` : remplacer les définitions des lignes 70-71 par
    `from certus.ui.certus_index_spline_common import _QS_SMART_INIT_DEEP, _QS_SMART_INIT_TWO_PHASE` (absolu, niveau
    module). Les lectures de `:667` et `:673` y trouvent toujours leurs globaux.
  - le test nouveau : cas des deux noms, et `smart_init` importé seul et en premier dans un interpréteur neuf.
  Préalable vérifié le 2026-11-11 : `common` n'importe `smart_init` à aucun niveau. Dans tout `certus/`, le seul import
  de `smart_init` est retardé (`ui/certus_index_spline_mixins_ui.py:394`, dans une fonction) : aucun module que `common`
  charge ne l'importe au niveau module, donc pas de cycle.
  Garde-fous :
  - l'import de `ui/certus_index_spline_mixins_ui.py:394` doit rester dans sa fonction : le hisser fermerait le cycle
    `smart_init → common → mixins_ui → smart_init` (`common` et `mixins_ui` sont deux des modules sortis d'un cycle, I13) ;
  - effet de bord accepté : importer `smart_init` charge désormais `common`, donc `corridors`, `execution`, `rendering`,
    `settings` et `mixins_ui`. `CERTUS_INDEX_SPLINE.py:26` importe `smart_init` avant la fenêtre : l'ordre de chargement
    des modules change, pas leur contenu.
  Vérifier : `refactor_guard compare` — valeurs égales, mêmes noms dans `smart_init`, résolution par la façade identique.
  Test : le test nouveau, puis `tests/unit/test_a_module_that_was_in_an_import_cycle_imports_first_and_alone.py`, puis
  `tests/unit/test_the_architecture_debt_only_shrinks.py`, puis
  `tests/ui/test_the_two_unplugged_windows_are_plugged_back.py`, puis LOT.

- [x] **2e — Classes du smart-init en double (Q9)** — sous condition — faite le 2026-11-11. Préalable mesuré, aucun
  écart : mêmes champs (10, 11 et 11), mêmes valeurs par défaut, même configuration, même bytecode pour `from_dict`,
  `__post_init__` et `update` ; les sources ne diffèrent que par des lignes vides et l'écriture `dataclass` /
  `dataclasses.dataclass`. Les cas nouveaux échouaient avant (`6 failed, 50 passed`) et passent ; ruff PASS ; lot de
  contrôle `261 passed` ; garde avec `manifests/phase_2e.json` : `problems=0`, `GUARD=OK`. Suite visible : la façade
  `CERTUS_INDEX_SPLINE` résout les trois noms dans `state_ui`. Laissés en place, sans lecteur : les imports
  `dataclass`, `field`, `BaseModel`, `ConfigDict` de `smart_init` (un nom qu'un module exposait y reste ; Phase 8).
  Préalable, avant toute écriture : comparer les deux définitions de `SmartInitPayload` et de ses deux classes d'état,
  dans `certus/ui/certus_index_spline_smart_init.py` et `certus/ui/certus_index_spline_state_ui.py` — champs, valeurs par
  défaut, empreintes des méthodes dans l'instantané. **Au moindre écart : s'arrêter, le consigner, ne rien unifier.**
  Modifier : `certus/ui/certus_index_spline_smart_init.py` importe les trois classes de `state_ui` au lieu de les
  définir ; le test nouveau gagne le cas des trois noms.
  Test : le test nouveau, puis `tests/ui/test_the_two_unplugged_windows_are_plugged_back.py`, puis LOT.

### [x] Phase 3 — Extraction des tranches (déplacements purs ; un registre de test suit, Q22) — faite le 2026-11-11

Une sous-phase par tranche, dans cet ordre. Pour chacune : créer le module, y coller les méthodes de §2.3 à
l'identique, importer leurs globaux depuis les mêmes origines (R2, R3), ajouter la tranche aux bases des classes de
compatibilité (R5), conserver dans les modules d'origine les noms qu'ils exposaient (principe 6), écrire le manifeste
de déplacement, lancer `refactor_guard compare`, puis les tests. Si `certus_index_spline_rendering.py` raccourcit,
régénérer `tests/architecture_debt.json` dans le même commit (I12).

- [x] **3a — `_CorridorRunMixin`** — faite le 2026-11-11 : 15 méthodes déplacées, texte inchangé ; garde avec
  `manifests/phase_3a.json` : `problems=0`, `GUARD=OK` ; ruff PASS ; `test_mwir_gui_flow.py`,
  `test_post_opt_option_unlock.py` et le test nouveau `33 passed` ; lot de contrôle `269 passed`. Ce que la sous-phase a
  appris, et qui vaut pour 3b à 3d :
  - **Un nom lié par `import` et un nom affecté ne donnent pas le même bytecode** (Python 3.15 : `logger.debug(...)`
    n'est pas compilé pareil). `logger` est donc **importé** du cœur spline (`certus.spline.certus_index_spline_core`,
    même objet que celui de `common`), jamais réaffecté dans une tranche.
  - **La garde ne savait pas dire « cette méthode a quitté sa classe pour une tranche dont elle n'hérite pas »**
    (`_CorridorGenMixin`, `CertusIndexSplineEventsExtrasMixin`). Étendue dans un commit à part (`85e5d24f`, 4 tests,
    dont 3 rouges avant) : l'entrée `moved_methods` l'autorise si la classe d'arrivée définit la méthode, inchangée.
  - Les classes de compatibilité héritent de méthodes qu'elles ne définissaient pas : `added_attributes` au manifeste.
  - Contrats : `CONTRACTS` régénéré depuis le code (`_CorridorRunMixin` 58 noms ; `_CorridorControlMixin` 72 → 30,
    `CertusIndexSplineCorridorUIMixin` 44 → 32, `_CorridorGenMixin` 29 → 22) ; protocoles : 4 noms ajoutés (`df`,
    `lbl_corr_alpha`, `lbl_corr_rmse_delta`, `sp_corr_alpha`), 6 retirés (désormais fournis par la tranche).
  - Test nouveau (R6) : `tests/unit/test_the_corridor_slices_hold_the_methods_they_were_given.py` — la fenêtre prend
    chaque méthode dans sa tranche, la tranche est un mixin nu, ordre canonique des bases, aucun import montant.
  - La passerelle `corridor_ui` n'a pas eu à changer ; aucune couture de test touchée ; aucun test existant retouché.
  Créer : `certus/ui/certus_index_spline_corridor_run.py`.
  Modifier : `certus/ui/certus_index_spline_settings.py`, `certus/ui/certus_index_spline_corridorui_mixin.py`,
  `certus/ui/certus_index_spline_eventsextras_mixin.py`, `certus/ui/certus_index_spline_corridor_gen.py`,
  `certus/ui/certus_index_spline_corridor_ui.py` (noms ajoutés à l'instruction existante), `certus/ui/certus_index_spline_corridor_host.py`.
  Test : `tests/unit/test_mwir_gui_flow.py`, puis `tests/unit/test_post_opt_option_unlock.py`, puis LOT.
  Q5 : `tests/unit/test_mwir_gui_flow.py` n'est pas retouché ici. `GenericWorker` reste importé dans `corridorui_mixin`
  (la couture `:399, 435` doit y trouver ce nom) ; `_start_deferred_corridor_worker`, une fois déplacée, le lit par la
  passerelle, comme elle le lisait dans `settings` : ce que ces deux tests construisent ne change pas.
- [x] **3b — `_CorridorRmseViewMixin`** — faite le 2026-11-11 : 9 méthodes déplacées, texte inchangé ; garde avec
  `manifests/phase_3b.json` : `problems=0`, `GUARD=OK` ; ruff PASS ; lot de contrôle, `test_rmse_tab_summary.py` et
  `test_rmse_scatter_pieces.py` `366 passed`. La passerelle prête deux noms de plus (`CertusCard`,
  `wrap_scientific_plot_with_toolbar`), toujours en 3 instructions ; plafond de `rendering.py` 1952 → 1913 ; la table
  d'état suit (`_corridor_rmse_grid_live_t0` naît dans la tranche) ; contrats : `_CorridorRmseViewMixin` 15 noms,
  `_CorridorControlMixin` 30 → 23, `CertusIndexSplineCorridorUIMixin` 32 → 23 ; protocoles : 1 nom ajouté, 3 retirés.
  Créer : `certus/ui/certus_index_spline_corridor_rmse_view.py`.
  Modifier : `certus/ui/certus_index_spline_corridorui_mixin.py`, `certus/ui/certus_index_spline_settings.py`,
  `certus/ui/certus_index_spline_eventsextras_mixin.py`, `certus/ui/certus_index_spline_rendering.py`,
  `certus/ui/certus_index_spline_corridor_ui.py`, `certus/ui/certus_index_spline_corridor_host.py`, `tests/architecture_debt.json`.
  Test : `tests/unit/test_rmse_tab_summary.py`, puis `tests/unit/test_rmse_scatter_pieces.py`, puis LOT.
- [x] **3c — `_CorridorIntervalMixin`** — faite le 2026-11-11 : 11 méthodes déplacées, texte inchangé ; garde avec
  `manifests/phase_3c.json` : `problems=0`, `GUARD=OK` ; ruff PASS ; lot de contrôle et
  `test_manual_rmse_grid_integration.py` `280 passed`. `_CorridorControlMixin` n'a plus de méthode propre : il ne porte
  que son héritage. Plafond de `rendering.py` 1913 → 1835. Contrats : `_CorridorIntervalMixin` 24 noms,
  `_CorridorControlMixin` 23 → 0, `CertusIndexSplineCorridorUIMixin` 23 → 14 ; protocoles : 3 méthodes ajoutées, 8
  membres retirés.
  **Un écart de bytecode, déclaré (`changed_code`) et mesuré** : `_apply_corridor_preset_auto_robust`, texte inchangé.
  `settings` affectait `logger`, `manualmesh_mixin` l'importait ; une tranche ne peut faire que l'un des deux (leçon de
  3a), et elle l'importe. Mesure : 182 instructions avant, 183 après, mêmes constantes, mêmes noms ; seule différence,
  `LOAD_ATTR debug + NULL|self` devient `LOAD_ATTR debug` puis `PUSH_NULL`. `_on_corridor_manual_slider_changed`, qui
  lit le même journal, garde son bytecode exact.
  Créer : `certus/ui/certus_index_spline_corridor_interval.py`.
  Modifier : `certus/ui/certus_index_spline_settings.py`, `certus/ui/certus_index_spline_corridorui_mixin.py`,
  `certus/ui/certus_index_spline_manualmesh_mixin.py`, `certus/ui/certus_index_spline_rendering.py`,
  `certus/ui/certus_index_spline_corridor_ui.py`, `certus/ui/certus_index_spline_corridor_host.py`, `tests/architecture_debt.json`.
  Test : `tests/unit/test_manual_rmse_grid_integration.py`, puis `tests/unit/test_mwir_gui_flow.py`, puis LOT.
- [x] **3d — `_CorridorNkMixin`** — faite le 2026-11-11 : 7 méthodes déplacées avec `tools/`, texte inchangé, aucun
  écart de bytecode (aucune ne lit le journal de module) ; garde avec `manifests/phase_3d.json` : `problems=0`,
  `GUARD=OK` ; ruff PASS ; test principal, tranches et contrats `92 passed` ; lot de contrôle et
  `test_manual_rmse_grid_integration.py` `285 passed`. Seul `CertusIndexSplineCorridorUIMixin` hérite de la tranche
  (§2.2), en dernière base ; la passerelle prête `ExcelTableWidget` en plus, toujours en 3 instructions. Plafond de
  `rendering.py` 1835 → 1781. Contrats : `_CorridorNkMixin` 9 noms, `CertusIndexSplineCorridorUIMixin` 14 → 7,
  `_CorridorGenMixin` 22 → 17 ; protocoles : 3 membres retirés (`btn_copy_corridor`, `btn_export_corridor`,
  `table_corridor`, que la tranche crée et lit seule), aucun ajouté. Aucune couture touchée, aucun test existant retouché.
  Créer : `certus/ui/certus_index_spline_corridor_nk.py`.
  Modifier : `certus/ui/certus_index_spline_corridorui_mixin.py`, `certus/ui/certus_index_spline_corridor_gen.py`,
  `certus/ui/certus_index_spline_rendering.py`, `certus/ui/certus_index_spline_corridor_ui.py`,
  `certus/ui/certus_index_spline_corridor_host.py`, `tests/architecture_debt.json`.
  Test : `tests/unit/test_the_corridors_split_keeps_every_name_and_the_layering_where_it_was.py`, puis LOT.

Sortie de la phase : `_CorridorControlMixin` et `CertusIndexSplineCorridorUIMixin` ne portent plus que leur héritage
(et `_launch_corridor_rmse_gap_heal` pour le second) ; `certus/ui/certus_index_spline_ui.py` est intact.

**Validation de la phase** (`validate_parallel.py`, `d3118167`, Python 3.15.2) : `VALIDATION=NO-GO`. ruff PASS ; oracle
`1192 passed` ; unit `5918 passed`, 2 rouges en parallèle ; ui `1362 passed` ; rest `320 passed` et le même artefact de
charge, vert seul en série ; performance `29 passed` ; `check_claude_md`, `check_docs` PASS ; `coherence_md` : l'échec
connu (3 commandes mortes). Des deux rouges de unit, l'un est le test qui chronomètre
(`test_bench_kernels_measures_ratios_and_alerts_on_a_regression.py`), vert seul en série ; l'autre est **réel et dû à
3a** : `tests/unit/test_progress_imports.py` tient une liste des modules qui lisent `build_progress_snapshot`, et
`settings` n'en fait plus partie depuis que `_start_deferred_corridor_worker` est dans `corridor_run`. Le lot de
contrôle ne lançait pas ce test. Corrigé dans un commit à part (Q22) : l'entrée de la liste désigne `corridor_run` ; le
fichier `12 passed`, et il entre dans le lot (`tools/lot.py`). La validation complète n'a pas été relancée après ce
commit, qui ne touche qu'une liste de test : la prochaine est celle de la Phase 4.

### [x] Phase 4 — Tracé RMSE(d) (déplacement pur + une retouche mécanique de test, accordée par Q1) — faite le 2026-11-11

Faite avec `tools/` : 10 méthodes déplacées dans `_CorridorRmsePlotMixin`, texte inchangé, aucun écart de bytecode
(`logger` affecté comme dans `rendering`, Q18) ; aucune aide de niveau module à déplacer (relevé : les dix méthodes ne
lisent que des noms importés et `logger`). Garde avec `manifests/phase_4.json` : `problems=0`, `GUARD=OK`, sans couture
à reconnaître puisque le test suit le code ; ruff PASS ; `test_rmse_scatter_pieces.py` et `test_rmse_tab_summary.py`
`92 passed` ; lot de contrôle et les trois tests RMSE `395 passed`. `rendering.py` : 1781 → 978 lignes, sorti de
`fichiers_longs`. Contrats : `_CorridorRmsePlotMixin` 18 noms (ces lectures n'étaient pas déclarées tant que les
méthodes étaient dans `_PlotMixin`) ; protocoles : 2 méthodes ajoutées, 5 attributs typés à la main
(`_corridor_rmse_curvature_label` dans l'état ; `_corridor_rmse_curve`, `_corridor_rmse_best_marker`,
`chk_corridor_rmse_live_parabola`, `chk_corridor_rmse_lock_scale` dans les widgets), aucun retiré. Table d'état : 2
renvois `born_in` repointés.

- Créer : `certus/ui/certus_index_spline_corridor_rmse_plot.py` (les 10 méthodes de §2.3 et les aides de niveau module
  qu'elles utilisent, R3).
- Modifier : `certus/ui/certus_index_spline_rendering.py` (`_PlotMixin` hérite de la tranche et réimporte les aides) ;
  `tests/unit/test_rmse_scatter_pieces.py:21` (l'alias `module` désigne le nouveau module, puisque le test patche `pg`
  là où le code le lit) ; `tests/architecture_debt.json` (le fichier passe sous 1 500 lignes : il quitte la liste).
- Test : `tests/unit/test_rmse_scatter_pieces.py`, puis `tests/unit/test_rmse_tab_summary.py`, puis LOT.
- La retouche du test part dans le même commit que le déplacement et se limite à cette ligne.
- **Liaison de `logger` (Q18)** : les dix méthodes viennent d'un seul module, `rendering`, qui **affecte** `logger` ;
  deux le lisent (`_plot_rmse_data_scatter`, `_plot_corridor_rmse_tab`). Le nouveau module l'affecte donc aussi
  (`logger = logging.getLogger("CERTUS_INDEX_SPLINE")`), et ne l'importe pas : le bytecode reste identique. Six
  méthodes lisent `pg`, que le test remplace dans `rendering` : c'est la couture que la retouche de Q1 suit.

### [ ] Phase 5 — Découpler les mixins de la fenêtre

- [ ] **5a** — Créer `certus/ui/certus_index_spline_corridor_jobs.py` : y déplacer `_worker_corridor_rmse_regular_grid`,
  `_worker_corridor_rmse_healer`, `_worker_curve_minimum_deep_refit` (`ui/certus_index_spline_common.py:278, 319, 348`).
  Modifier `certus/ui/certus_index_spline_common.py` (réimport, mêmes objets). L'import retardé
  `ui/certus_index_spline_corridor_worker.py:893` reste tel quel (couture de la façade, I15).
  Test : `tests/unit/test_manual_rmse_grid_integration.py`, puis LOT.
  Q18 : `common` affecte `logger` ; si l'une des trois fonctions le lit, `corridor_jobs` l'affecte aussi.
- [ ] **5b** — Créer `certus/ui/certus_index_spline_lazy_app.py` : y déplacer `_LazyCertusIndexSplineApp` et son
  instance (`ui/certus_index_spline_common.py:371-376`). Modifier `certus/ui/certus_index_spline_common.py` (réimport).
  Ne pas l'exporter par la façade (R4).
  Test : `tests/unit/test_gui_smoke.py`, puis LOT.
- [ ] **5c** — Déplacer `_start_curve_minimum_deep_refit` dans `_CorridorRunMixin`. Modifier
  `certus/ui/certus_index_spline_corridor_run.py`, `certus/ui/certus_index_spline_eventsextras_mixin.py`.
  Test : `tests/unit/test_post_opt_option_unlock.py`, puis LOT.
- [ ] **5d (Q6 : oui, pour les 8 méthodes statiques)** — Remplacer les appels `CertusIndexSplineApp.<statique>(…)` par des fonctions pures d'un module
  feuille, les méthodes statiques devenant des alias. Ce n'est plus un déplacement pur : `refactor_guard` doit recevoir la
  liste exacte des fonctions dont le bytecode change, et rien d'autre ne doit bouger.
  Test : `tests/unit/test_mwir_gui_flow.py`, puis LOT.

### [ ] Phase 6 — Assainir l'héritage (garde-fous, puis options)

- [ ] **6a** — Le test T4 à T6 de la Phase 1 est étendu aux huit autres fenêtres de
  `tests/unit/test_self_attributes_are_defined.py:35-45`, avec leur liste blanche de redéfinitions. Il gagne le garde-fou de F11 (Q10) : aucun attribut défini par une classe
  du projet n'est masqué par une classe Qt placée avant elle dans le MRO (0 aujourd'hui, dans les 9 fenêtres).
  Modifier : `tests/unit/test_the_corridor_mixins_declare_what_they_read_on_the_window.py`.
  Test : ce fichier, puis LOT.
- [ ] **6b (Q7 : oui pour `_UIMixin`)** — Retirer `_UIMixin` des bases de la fenêtre (`ui/certus_index_spline_ui.py:65`), la classe
  restant définie et importable. `_ConfigBuilderMixin` ne peut sortir du MRO sans retoucher
  `tests/unit/test_gui_smoke.py:226`.
  Test : `tests/unit/test_gui_smoke.py`, puis LOT.
- [ ] **6c (Q8 : oui)** — Initialiser tout l'état du tableau §2.5 au début de `__init__`. Préalable vérifié : aucun
  `hasattr` ne garde ces attributs, et ni `vars(self)` ni `self.__dict__` ne sont lus dans le groupe ou la base.
  Modifier : `certus/ui/certus_index_spline_ui.py`, `certus/ui/certus_index_spline_corridor_state.py`.
  Test : `tests/integration/test_suite_ui_instantiation.py`, puis LOT.

### [ ] Phase 7 — Découplage entre familles (chantier séparé, Q10)

Chaque arête se traite seule, par descente de l'utilitaire dans un module partagé et réexport à l'ancien emplacement.
**Placée après la Phase 10 (Q21)** : c'est un autre chantier, et 7b touche au calcul.
La liste des tests propres à chaque famille est à compléter par un Grep du nom déplacé dans `tests/` en début de sous-phase.

- [ ] **7a** — `_resolve_strat_indices_db_path` : `certus/workers/certus_strat_workers.py` → module partagé ;
  modifier `certus/ui/certus_field_ui.py:15`.
  Test : `tests/unit/test_gui_apps_smoke.py`, puis LOT.
- [ ] **7b** — `spectral_rmse_weights` : `certus/utils/certus_index_utils.py` → module partagé ; modifier
  `certus/workers/certus_design_workers.py:53`, `certus/core/certus_re_worker_utils.py:35`,
  `certus/physics/gradient_analytic.py:1115`.
  Test : `tests/unit/test_gui_apps_smoke.py`, puis LOT.
  **Protocole de noyau, obligatoire (Q21)** : `physics/gradient_analytic.py` et `utils/certus_index_utils.py` citent
  Numba ; les modifier change la clé du cache (premier passage à froid). Avant : oracle (`pytest tests/oracle/`).
  Après : oracle, puis `python scripts/c1_diff.py HEAD`, froid contre froid, avant de commiter (CLAUDE.md §2 et §5).
  Le module partagé doit être au niveau de `physics` ou en dessous (`domain`) : `physics` l'importe, et un module de
  `utils` laisserait l'arête montante en place. Si `c1_diff` ne rend pas « C1 TENU » : annuler, ne pas corriger en avant.

### [ ] Phase 8 — Clôture

- Régénérer `tests/architecture_debt.json` ; lancer la suite complète ; comparer l'instantané final à la référence de
  Phase 0 avec le manifeste cumulé. **L'instantané de référence reste (Q20)** : les Phases 9, 10, 7 et la feuille de
  route UX déclarent leurs écarts dans un manifeste, donc contre cette référence, et c'est un résultat versionné de
  `reports/`.
- Relever, sans les retirer, les imports que les déplacements ont laissés sans lecteur dans les modules d'origine
  (principe 6 : un module garde les noms qu'il exposait) ; mettre `docs/ETAT.md` à jour.
- Test : suite complète, puis `tests/unit/test_the_architecture_debt_only_shrinks.py` seul.

### [ ] Phase 9 — Réparer la couture de test périmée (Q5 ; un commit de test, aucun code de production)

- Modifier : `tests/unit/test_mwir_gui_flow.py:399, 435` — le remplacement de `GenericWorker` vise le module où
  `_start_deferred_corridor_worker` le lit depuis la Phase 3a (`certus.ui.certus_index_spline_corridor_run`) ; chacun des
  deux tests gagne l'assertion `isinstance(app._worker, _FakeWorker)`.
- Preuve exigée : cette assertion, ajoutée seule, **échoue** sur le test d'avant (elle montre que le vrai worker était
  construit), puis passe une fois la cible corrigée.
- Si la Phase 0 a montré que le faux worker était déjà utilisé : la phase est annulée, et I7 est corrigé.
- Test : `tests/unit/test_mwir_gui_flow.py`.

### [ ] Phase 10 — Correctifs révélés par l'audit (un commit chacun, chacun avec un test qui échoue avant)

Ces changements modifient un comportement : ils viennent après la clôture, jamais dans une phase de déplacement, et
chacun inscrit ses fonctions dans `changed_code` d'un manifeste.

- [ ] **10a — `-1`, pas `None` (Q17)** : `_plot_rmse_data_scatter` affecte `-1` à `_corridor_rmse_best_idx` quand la
  courbe est vide. Test : courbe vide tracée, puis lecture par un des lecteurs, sans `TypeError`. La table d'état
  redevient `int`.
- [ ] **10b — Branche morte (Q13)** : retirer de `_plot_result` le bloc qui lit `_corridor_rmse_profile_win` ;
  `NEVER_ASSIGNED` devient vide.
- [ ] **10c — Remise à zéro complète (Q11)** : d'abord le test qui montre l'intervalle périmé après `_load_defaults` ;
  s'il échoue comme prévu, `_load_defaults` remet à leur valeur par défaut `_corridor_rmse_smart_interval`, les deux
  exports, la grille demandée et les quatre tableaux du réticule ; la colonne `reset` de la table suit. Si le test
  n'arrive pas à produire le défaut : ne rien changer, et le dire.
- [ ] **10d — Un nom pour `2e-4` (Q12)** : une constante dans `certus_index_spline_corridor_common.py`, utilisée aux
  trois endroits ; valeur inchangée.

---

## 4. Arbitrages requis

**Tranchés le 2026-11-11 — plus rien ne bloque le codage**

| # | Question | Décision | Effet sur le plan |
|---|---|---|---|
| Q1 | Retoucher un test quand le code qu'il patche déménage ? | **Oui**, une ligne (`tests/unit/test_rmse_scatter_pieces.py:21`), dans le commit du déplacement. | Phase 4 exécutée ; `rendering.py` vise moins de 1 500 lignes. |
| Q2 | Lire `tests/architecture_debt.json` et le réécrire quand un plafond baisse ? | **Oui** aux deux. | Relevé ciblé fait (§1.6) ; lecture complète en Phase 0 ; registre réécrit en 2b, 3b, 3c, 3d, 4 et 8. |
| Q3 | `_apply_fixed_log_k_axis` en 5 exemplaires : laisser ou unifier ? | **Unifier**, commit isolé, sur le corps de `ui/certus_index_spline_common.py:155`. | Phase 2b ; seule sous-phase qui change un comportement (messages DEBUG). |
| Q4 | Source unique des constantes de fenêtre ? | **Le cœur spline**, non modifié. | Phase 2c ; la règle vaut pour les 16 noms que le cœur définit (`:43-45` et `:2095-2107`). |
| Q5 | Couture de test périmée sur `GenericWorker` ? | **Conserver** pendant la migration, **réparer après**, dans un commit de test séparé. | Note en 3a ; constat en Phase 0 ; Phase 9. |
| Q16 | `_QS_SMART_INIT_DEEP` et `_QS_SMART_INIT_TWO_PHASE`, en double hors du cœur : quelle source ? | **`ui/certus_index_spline_common.py`** ; `smart_init` les importe. Préalable vérifié : `common` n'importe `smart_init` à aucun niveau. | Phase 2d ; `smart_init` dépend désormais du carrefour `common`. |

**Tranchés par l'assistant le 2026-11-11, sur consigne de 👤 (« réponds toi-même aux questions »)** — chaque décision
repose sur une lecture du code ou une mesure.

| # | Question | Décision | Ce qui la fonde |
|---|---|---|---|
| Q6 | Phase 5d : remplacer le mandataire par des fonctions pures ? | **Oui, pour les 8 méthodes statiques seulement** (33 appels), une par commit, en dernier de la Phase 5. Les 6 appels à `_prepare_worker_restart` restent. | Relevé : 10 noms passent par le mandataire, dont 8 statiques. En faire des fonctions d'un module feuille supprime le rappel du mixin vers la fenêtre ; la méthode statique reste comme alias, donc les tests ne bougent pas. `_prepare_worker_restart` est appelée hors instance sur de faux hôtes (I9) : y toucher casserait ces tests. |
| Q7 | Phase 6b : sortir les mixins vides du MRO ? | **Oui pour `_UIMixin`** (la classe reste définie et importable). **Non pour `_ConfigBuilderMixin`**. | Le second est épinglé par `tests/unit/test_gui_smoke.py` (I6). |
| Q8 | Phase 6c : initialiser tout l'état corridor dans le constructeur ? | **Oui**, après les Phases 3 à 5, avec un test qui échoue avant. | La Phase 1 l'a rendu sûr : chaque repli de `getattr` donne la valeur par défaut de la table, et aucun `hasattr` ne garde un attribut d'état. Initialiser tôt ne change aucune valeur lue, et donne à l'état un seul lieu de naissance (F2). |
| Q9 | Les classes du smart-init en double : ce chantier ou un autre ? | **Ce chantier, Phase 2e**, à condition que les deux définitions soient identiques, ce qui se vérifie avant. | Les mixins importent déjà la copie de `state_ui`. Depuis Q16, `smart_init` charge `common`, donc `state_ui` : l'import n'ajoute aucune dépendance. Deux classes pydantic de même nom qui divergeraient seraient un défaut silencieux. |
| Q10 | Phase 7, puis F11, F10, F15, signaux redéfinis ? | **Phase 7 : oui**, en fin de chantier. **F11 : ne pas toucher à l'ordre des bases**, mais poser le garde-fou en 6a. **F10, F15 et les signaux : autre chantier.** | Mesuré dans l'instantané de référence : dans les 9 fenêtres, **aucune** méthode du projet n'est masquée par une classe Qt. F11 est un piège, pas un défaut actif ; inverser les bases changerait le MRO de 9 fenêtres pour un gain nul. Un test « aucun attribut du projet masqué par Qt » tient le piège fermé. |
| Q11 | Remise à zéro incomplète : voulu ou oubli ? | **Oubli probable : à prouver par un test, puis à corriger en Phase 10.** | `_load_defaults` vide la courbe RMSE(d) sans retracer l'onglet : `_corridor_rmse_smart_interval` garde l'intervalle de l'échantillon précédent. La génération de `_CorridorGenMixin` le prend en premier choix dès qu'il est fini, et `_plot_corridor_rmse_tab` sort tôt, sans le remettre à `None`, quand le résultat n'a pas de profil. C'est le chemin suspect d'un corridor calculé sur un intervalle périmé. |
| Q12 | `2e-4` et `2.5e-4` : deux réglages, ou une constante oubliée ? | **Deux réglages distincts : ne rien unifier.** En Phase 10, donner un nom à `2e-4`. | `sp_corr_rmse_delta` (2.5e-4) est la tolérance du **calcul** du corridor : elle part dans la configuration du solveur. `sp_corridor_rmse_delta` (2e-4) est l'amplitude de l'**intervalle robuste** affiché sous la parabole. `2e-4` est écrit trois fois, de façon cohérente (création, préréglage, repli) ; le nommer évite qu'on le confonde avec l'autre. |
| Q13 | Branche morte : supprimer ? | **Oui**, Phase 10. | `_corridor_rmse_profile_win` n'est affecté nulle part (un test de Phase 1 le tient) : le `getattr` rend toujours `None`, le bloc ne s'exécute jamais, et la méthode qu'il appellerait n'existe pas. |
| Q14 | Noms trompeurs (`_on_worker_done` dans le mixin corridor, `_DataMixin` dans le groupe corridor) : acceptable ? | **Oui, pour ce chantier.** | Les renommer exige de retoucher les tests qui épinglent ces méthodes par classe et par texte (I2, I7, I8), sans gain de comportement. Dette de nommage notée. |
| Q15 | Imports relatifs existants : les convertir ? | **Non : la règle vaut pour le code nouveau.** | Les 43 imports sont dans `physics`, `spline`, `domain`, `core` : les convertir touche des fichiers à noyaux compilés (clé du cache Numba, contrôle au bit) pour un gain nul ici. Un test de Phase 1 tient déjà le groupe INDEX SPLINE en imports absolus. |
| Q17 | `_corridor_rmse_best_idx` reçoit `None` : voulu ? | **Non : c'est un `-1` oublié, défaut latent.** Correctif en Phase 10. | Ses lecteurs font `int(getattr(self, "_corridor_rmse_best_idx", -1))` : avec `None`, la conversion lève `TypeError`. `None` est affecté quand la courbe tracée est vide. |

**Tranchés par l'assistant le 2026-11-11 au soir, à la relecture des étapes restantes demandée par 👤**

| # | Question | Décision | Ce qui la fonde |
|---|---|---|---|
| Q18 | Comment lier `logger` dans un module nouveau ? | **Comme le module d'origine quand il est unique** (affecté pour ce qui vient de `rendering`, `common`, `settings` ; importé du cœur spline pour ce qui l'importait). Quand deux origines diffèrent, on importe, et l'écart de la méthode minoritaire est déclaré (`changed_code`) et mesuré. | Mesuré en 3a et 3c : Python 3.15 ne compile pas `logger.debug(...)` de la même façon selon que le nom est lié par un import ou par une affectation. |
| Q20 | Retirer l'instantané de référence à la clôture ? | **Non.** | Les Phases 9, 10, 7 et la feuille de route UX s'appuient sur la garde ; `reports/` ne se vide pas (CLAUDE.md §3). |
| Q21 | Phase 7 : où, et sous quel contrôle ? | **Après la Phase 10** ; 7b sous le protocole de noyau (oracle avant et après, `c1_diff.py HEAD`). | Relevé : `gradient_analytic.py` et `certus_index_utils.py` citent Numba ; le plan n'y prévoyait que des tests d'interface. |

**Tranché par l'assistant dans la nuit du 2026-11-11, en autonomie**

| # | Question | Décision | Ce qui la fonde |
|---|---|---|---|
| Q22 | Un test qui tient une liste de modules « par ce qu'ils lisent » devient rouge quand la méthode lectrice déménage : le retoucher ? | **Oui : l'entrée suit la méthode**, dans un commit de test à part, et le test entre dans le lot. | `tests/unit/test_progress_imports.py` le demande lui-même (« take it off the list ») et l'a déjà fait une fois (`corridor_worker`, S5.3). Ce n'est pas une couture : aucun comportement n'est épinglé, seulement l'adresse d'un lecteur. |

**Proposé à 👤, non appliqué** — Q19 : avancer la Phase 9 juste après la Phase 3. La méthode que la couture vise est
à sa place définitive depuis 3a, et d'ici la Phase 9 deux tests de `test_mwir_gui_flow.py` lancent un vrai fil de
calcul qu'ils n'attendent pas, à chaque validation. Cela revient sur l'ordre que 👤 a fixé en Q5 : à lui de le dire.

Il ne reste aucune autre question ouverte.

---

## 5. Audit UX — viser le premier centile

Demandé le 2026-11-11. Objet : les 11 modules graphiques de la suite, pas seulement INDEX SPLINE.

### 5.1 Méthode, et ce qu'elle ne voit pas

| Source | Ce qu'elle donne |
|---|---|
| `python scripts/audit_ux_certus.py`, 1920×1080 | **0 module en défaut sur 11** : part du tracé, clavier, tables, infobulles, taille des cibles. |
| Mesures sur l'arbre de widgets, 1440×900, un processus par module | libellés et en-têtes tronqués, textes en double, emojis, langue, tailles de police, temps de construction. |
| 14 captures hors écran (11 en clair, 3 en sombre), 1440×900 | hiérarchie, densité, cohérence visuelle. Non versionnées. |
| Balayages du code de `certus/ui` | symboles perdus, titres, dialogues, raccourcis. |

**Limites, à garder en tête.** Le rendu est hors écran : sur les captures, deux cartes paraissaient vides (STRAT, METAL)
alors que l'arbre de widgets les montre peuplées — artefact de capture. Aucun constat ci-dessous ne repose donc sur une
capture seule ; ceux qui en dépendent sont marqués « à confirmer à l'écran ». Non couverts : un parcours complet avec des
données réelles, les dialogues secondaires, la réactivité pendant un calcul, un écran HiDPI réel, un lecteur d'écran, et
tout essai avec de vrais utilisateurs. « Premier centile » ne se prouve pas sans eux.

### 5.2 Ce qui est déjà au niveau

- Le socle ergonomique est mesuré et tenu par une centaine de tests `tests/ui/test_ux_*` et un cliquet.
- Toutes les fenêtres se construisent en moins d'une seconde (de 187 ms à 911 ms).
- Thème sombre complet ; visite guidée au premier lancement ; bandeau d'indicateurs en tête de chaque module ; palette
  de commandes ; confirmation avant de fermer pendant un calcul ; états vides avec appel à l'action dans RE.

### 5.3 Constats

**A — Défauts visibles, peu risqués à corriger**

| # | Constat | Preuve | Modules |
|---|---|---|---|
| A1 | **Des symboles perdus s'affichent « ? ».** Huit chaînes : `interval ? [..]`, `Deltad code ? [..]`, `? best d*`, `manual .. ? [..]`, `? QWOT`, `(or ? if monotonicity active)`, et l'infobulle `Demi-fen?tre locale`. Un nettoyage d'encodage a retiré les caractères non ASCII. | balayage du code | INDEX SPLINE, base commune |
| A2 | **Le même nettoyage a ôté les tirets des titres** : `"CERTUS  Reverse Engineering"`, `"CERTUS  Index Spline Optimization"` (double espace). | balayage du code | RE, INDEX SPLINE |
| A3 | **Titres de fenêtre sans règle** : vide pour SUBSTRATE INDEX ; sans nom de module pour METAL SINGLE ; `CERTUS_RE  CERTUS  Reverse Engineering` (le nom deux fois, un tiret bas) ; la version dans un seul. | mesure | 6 sur 11 |
| A4 | **16 libellés tronqués à 1440×900.** INDEX SPLINE : « Nominal thickness (nm): » demande 138 px et en a 84 ; « Substrate (n) & layer thickness » 187 pour 113. « Copy Logs » déborde dans 5 modules. En-têtes de table coupés : « λ min (nm) », « λ max (nm) » (DESIGN), « n@lambda₀ » (RE), « Mat. » (FIELD). | mesure | 8 sur 11 |
| A5 | **« Zoom 100% » deux fois dans la barre d'état** de DESIGN, STRAT et RE ; dans INDEX SPLINE, un « Zoom 100% » est placé sous la barre de menus, qui le recouvre. | mesure | 4 |
| A6 | **Deux toasts identiques au démarrage de DESIGN** (« Evaluation OK. RMSE: 0.368035 »), posés sur « Add Target » et « Remove ». | mesure (deux boutons de fermeture) et capture | DESIGN |
| A7 | **Conflit de raccourci journalisé au démarrage** : `Ctrl+S` demandé pour « save » alors qu'il est déjà pris. | journal | DESIGN |
| A8 | **Deux langues.** Infobulles en français dans une interface anglaise : « Mode d'exécution du solveur : … » (STRAT), « Amplitude DeltaRMSE (Profilage Robuste) », « Demi-fen?tre » (INDEX SPLINE). | mesure | STRAT, INDEX SPLINE |
| A9 | **Cinq dialogues d'erreur montrent le texte brut de l'exception.** | balayage du code | suite |
| A10 | Le mot du logo est illisible en thème sombre ; le bouton de thème n'a pas de glyphe dans 5 modules. | capture seule : **à confirmer à l'écran** | — |

**B — Incohérences de la suite**

| # | Constat | Preuve |
|---|---|---|
| B1 | **Trois façons de montrer le déroulé** : pastilles numérotées (INDEX SPLINE), ligne à flèches (DESIGN, RE, METAL), phrase à points médians (STRAT). | captures |
| B2 | **Le même geste, quatre vocabulaires** : « RUN FULL WORKFLOW » / « STOP Calculation » (STRAT), « Run » / « Halt » (METAL), « Run RE » (RE), « Run » (INDEX SPLINE). Trois casses : capitales, titre, phrase. | mesure |
| B3 | **FIELD parle un autre langage visuel** : onglets encadrés, boutons marine, champs d'aspect natif, boutons carrés dans la visite guidée. | capture |
| B4 | **Le bleu « action principale » est donné à des actions secondaires** : « Show Details » (STRAT), « Logs » (DESIGN), « Scientific Documentation » (HUB), « Detach ». L'œil ne trouve pas le geste suivant. | captures |
| B5 | « Clear / Reset » est brun, hors palette, en haut et pleine largeur dans FIELD, en bas ailleurs. | captures |
| B6 | **Les icônes sont des emojis** (42 textes, les 9 tuiles du HUB) : rendu qui dépend du système, styles hétérogènes ; METAL SINGLE et METAL BILAYER ont la même. Compteurs de barre d'état sans libellé : « ♟ 0 \| 🎲 0 \| 🌈 0 », et « 0 \| 0 \| 0 » dans METAL. | mesure |
| B7 | **Six à sept tailles de police par fenêtre** (de 8 à 14 pt, plus les héritées) : pas d'échelle typographique. | mesure |
| B8 | Noms d'en-tête sans règle : « STRAT », « RE », « INDEX-SPLINE », « CERTUS-METAL-SINGLE ». | captures |
| B9 | Neuf onglets dans INDEX SPLINE et dans DESIGN, dont un nommé « CERTUS », et trois « Data ». | mesure |
| B10 | Barres d'outils des tracés en texte seul, répétées sur chaque graphe ; « Pub copy » est du jargon. | capture |

**C — Écart au premier centile**

| # | Constat | Preuve |
|---|---|---|
| C1 | Tracés vides aux axes 0 à 1 au lieu d'un état vide qui dit quoi faire (INDEX SPLINE, FIELD), alors que RE a de vrais états vides. | captures |
| C2 | Espace perdu au démarrage : la zone de synthèse est vide sous le bandeau (DESIGN, RE, METAL) ; l'accueil de STRAT est occupé par des slogans plutôt que par des actions (exemple, récents, reprise). | captures |
| C3 | HUB : près de la moitié de l'écran vide, pas de reprise de session, une liste sans libellé. | capture |
| C4 | **175 boîtes de dialogue modales** (22 critiques, 78 avertissements, 75 informations) pour 88 toasts : l'information interrompt. | balayage du code |
| C5 | Aide contextuelle : aucun texte de barre d'état ni « Qu'est-ce que c'est ? » ; tout passe par l'infobulle et F1. | balayage du code |
| C6 | Densité : DESIGN montre 89 contrôles à l'ouverture, INDEX SPLINE 49. | mesure |
| C7 | Pas de reprise d'un calcul ou d'une session après une coupure (à auditer : c'est la demande de reprise, côté produit). | non mesuré |

### 5.4 Position par dimension (jugement, pas mesure)

| Dimension | Aujourd'hui | Ce qui manque pour le premier centile |
|---|---|---|
| Performance perçue | forte | la tenir pendant un calcul |
| Retour d'état, prévention d'erreur | forte | moins de modales, erreurs qui disent quoi faire |
| Accessibilité | bonne, testée | un essai avec lecteur d'écran |
| Efficacité experte | bonne | la palette comme chemin principal, raccourcis sans conflit |
| Premier usage | correcte | états vides et accueils orientés action |
| Finition visuelle | inégale | icônes, typographie, rien de tronqué, symboles restaurés |
| Rédaction | inégale | une langue, un vocabulaire, pas de slogans |
| **Cohérence de la suite** | **faible** | un seul système pour onze modules : c'est le premier écart |

### 5.5 Feuille de route UX

Chaque étape est un commit ou une série courte, avec un test qui échoue avant et qui devient un cliquet. Les étapes U1 à
U5 corrigent des défauts visibles à faible risque : elles passent en premier. Dans les fichiers du groupe INDEX SPLINE,
elles viennent **après** la clôture du refactoring (Phase 8) — plusieurs chaînes sont dans des méthodes que la Phase 4
déplace à l'identique — et chacune inscrit ses fonctions dans `changed_code` d'un manifeste.

| # | Étape | Constats | Test cliquet à ajouter |
|---|---|---|---|
| U1 | Texte sans perte : restaurer les symboles et les tirets, une seule langue | A1, A2, A8 | aucune chaîne visible avec « ? » entre deux lettres ou double espace ; aucune infobulle en français, sur les 11 modules |
| U2 | Un format de titre et de nom pour les 11 fenêtres | A3, B8 | titre non vide, au format unique |
| U3 | Rien de tronqué à 1366×768 ni à 1440×900 | A4 | 0 libellé et 0 en-tête tronqué, mesuré par l'outil d'audit |
| U4 | Une barre d'état commune : un seul zoom, des compteurs libellés | A5, B6 | aucun texte d'état en double ; aucun compteur sans nom |
| U5 | Toasts dédoublonnés, raccourcis sans conflit | A6, A7 | deux toasts identiques n'en font qu'un ; aucun avertissement de raccourci au démarrage |
| U6 | Un système d'actions : un vocabulaire (Run, Stop, Reset), une seule action principale par écran, le style destructif des jetons | B2, B4, B5 | vocabulaire et nombre d'actions principales mesurés |
| U7 | FIELD rejoint le système ; un seul composant de déroulé | B1, B3 | — |
| U8 | Des icônes vectorielles à la place des emojis | B6 | aucun emoji dans un libellé |
| U9 | Une échelle typographique à quatre tailles | B7 | nombre de tailles par fenêtre |
| U10 | États vides actionnables partout ; accueils de STRAT et du HUB orientés action | C1, C2, C3 | chaque tracé vide dit quoi faire |
| U11 | Messages : l'information en toast, la modale pour les décisions, des erreurs qui disent la cause et le geste | A9, C4 | aucun texte d'exception brut dans un dialogue |
| U12 | Reprise d'une session et d'un calcul après coupure — à spécifier : elle touche au calcul | C7 | — |
| U13 | Ce que cet audit ne pouvait pas faire : écran réel et HiDPI, thème sombre, lecteur d'écran, cinq utilisateurs sur trois tâches | A10 | — |
