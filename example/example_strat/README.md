# Dictionnaire des Paramètres de Configuration STRAT (.json)

Ce guide détaille l'intégralité des paramètres utilisés par le solveur et l'interface **CERTUS STRAT**.

---

## 1. Profil & Modes d'Exécution

| Clé JSON | Type | Valeurs possibles | Description |
|---|---|---|---|
| `execution_mode` | `string` | `"fast"`, `"premium"`, `"deep"` | Profil global de calcul. Mappe automatiquement les budgets Monte-Carlo ($N=50, 150, 300$), le criblage ($n_{\text{screen}}=10, 25, 50$) et la largeur de faisceau ($dp\_top\_k=20, 40, 100$). |
| `strategy_phase_timeout` | `float` | Ex: `120` (s) | Temps limite d'exécution alloué par phase de calcul. |

---

## 2. Définition de l'Empilement & Matériaux

| Clé JSON | Type | Description |
|---|---|---|
| `l0` | `float` | Longueur d'onde centrale de référence (nm) pour les épaisseurs quart d'onde (QWOT). |
| `stack_multipliers` | `list[float]` | Liste des épaisseurs relatives en multiples de QWOT ($d_i / d_{\text{QWOT}}$) de chaque couche du substrat vers l'air. |
| `h_material_file` | `string` | Fichier d'indice dispersif du matériau Haut indice (ex: `"H800-Nb2O5"`). |
| `l_material_file` | `string` | Fichier d'indice dispersif du matériau Bas indice (ex: `"H800-SiO2"`). |
| `substrate_choice` | `string` | Matériau du substrat (ex: `"SiO2"`, `"Air"`, `"Custom"`). |
| `h_type_custom` | `bool` | `true` si indice constant personnalisé, `false` si fichier dispersif. |
| `l_type_custom` | `bool` | `true` si indice constant personnalisé, `false` si fichier dispersif. |
| `nH_r` / `nL_r` | `string`/`float` | Partie réelle de l'indice si mode Custom activé. |
| `nSub_custom` | `string`/`float` | Indice du substrat personnalisé si `substrate_choice="Custom"`. |

---

## 3. Domaine Spectral & Résolution Monochromateur

| Clé JSON | Type | Valeur défaut | Description |
|---|---|---|---|
| `wl_range_start` | `float` | `400.0` (nm) | Début de la plage spectrale cible pour l'évaluation du filtre. |
| `wl_range_end` | `float` | `700.0` (nm) | Fin de la plage spectrale cible. |
| `wl_step` | `float` | `1.0` (nm) | Pas de calcul du spectre de transmission/réflexion. |
| `scan_wl_min` | `float` | `450.0` (nm) | Borne basse des longueurs d'onde de monitoring optique autorisées. |
| `scan_wl_max` | `float` | `700.0` (nm) | Borne haute des longueurs d'onde de monitoring optique. |
| `scan_wl_step` | `float` | `1.0` (nm) | Pas d'échantillonnage pour la recherche des $\lambda$ de suivi (1 nm standard). |
| `monochromator_resolution_nm` | `float` | `2.0` (nm) | Résolution de fente du monochromateur (choix parmi `0.5`, `1.0`, `2.0`, `5.0`). |
| `slit_bias_enabled` | `int`/`bool` | `1` | `1` pour modéliser le profil spectral réel du monochromateur (convolution fente). |
| `search_resolution` | `int`/`bool` | `1` | `1` pour explorer la résolution optimale en Phase B. |

---

## 4. Modèle Physique & Sources d'Erreurs de Dépôt

| Clé JSON | Type | Valeur recommandée | Description |
|---|---|---|---|
| `allow_rate` | `int`/`bool` | `1` | `1` = autorise le mode Rate (surveillance au chrono sur couches sans extremum franc), `0` = optique pure. |
| `poem_anchor_noise` | `int`/`bool` | `1` | `1` = active le modèle de compensation de croissance POEM sous bruit de lecture. |
| `poem_anchor_noise_phase_a` | `int`/`bool` | `1` | `1` = applique le bruit dès la pré-sélection Phase A. |
| `index_corridor` | `float` | `0.005` | Demi-largeur du couloir de dérive d'indice de réfraction admissible. |
| `photometric_curvature_amp` | `float` | `0.00375` | Amplitude de la courbure photométrique résiduelle du spectrophotomètre. |
| `affine_scale_amp` | `float` | `0.0` | Amplitude de distorsion affine d'échelle sur la transmission ($a \in [1-\delta, 1+\delta]$). |
| `affine_offset_amp` | `float` | `0.0` | Amplitude de décalage affine de ligne de base ($b \in [-\delta, +\delta]$). |
| `reading_smoothing_window` | `int` | `1` | Taille de la fenêtre de lissage des lectures machine (1 = désactivé/neutre). |
| `machine_sampling_dd` | `float` | `0.0` | Grille d'échantillonnage d'épaisseur machine (0.0 = continue). |
| `tp_hysteresis_factor` | `float` | `1.66` | Seuil d'hystérésis pour la détection anti-bruit des points tournants. |
| `phase_a_level_margin_factor` | `float` | `1.66` | Marge de sécurité requise entre le niveau de transmission visé et les extrema. |
| `trigger_tolerance` | `float` | `0.05` | Tolérance photométrique sur le déclenchement d'arrêt. |

---

## 5. Programmation Dynamique & Découpage en Blocs (Phase A & B)

| Clé JSON | Type | Valeur défaut | Description |
|---|---|---|---|
| `iter_divider_start` | `float` | `18` | Diviseur de départ pour le balayage de découpage en blocs ($N_{\text{couches}} / \text{div}$). |
| `iter_divider_end` | `float` | `5` | Diviseur de fin pour le balayage de découpage en blocs. |
| `dp_top_k` | `int` | `40` | Largeur du faisceau DP : nombre de meilleures candidates conservées par bloc. |
| `k_keep_survivors` | `int` | `10` | Nombre de survivantes transmises pour la recombinaison entre blocs. |
| `n_screen_runs` | `int` | `25` | Nombre de tirages Monte-Carlo de pré-sélection (criblage) avant Phase B. |
| `mining_candidates_limit` | `int` | `3000` | Budget maximal de variantes combinatoires explorées (stochastique + symétrie). |
| `top_k_parents` | `int` | `20` | Nombre de stratégies parentes retenues pour les hybridations élites. |
| `max_fusions_per_parent` | `int` | `5` | Nombre maximal de fusions produites par parent élite. |
| `phase_a_scan_limit` | `int` | `300` | Limite de balayage brut des candidats en Phase A. |
| `phase_a_keep_limit` | `int` | `50` | Nombre maximal de nœuds retenus en sortie de Phase A. |

---

## 6. Évaluation Robuste & Consensus Multi-Graines

| Clé JSON | Type | Valeur défaut | Description |
|---|---|---|---|
| `robustness_num_runs` | `int` | `150` | Nombre de simulations Monte-Carlo finales par stratégie ($N$). |
| `robustness_noise_factors` | `string`/`list` | `"[0.5, 1.0, 2.0]"` | Multiplicateurs de bruit appliqués lors de l'audit de robustesse. |
| `enable_consensus_ranking` | `int`/`bool` | `1` | `1` = active le classement par consensus multi-graines pour éliminer la gigue. |
| `consensus_num_seeds` | `int` | `3` | Nombre de graines aléatoires indépendantes évaluées. |
| `consensus_num_runs` | `int` | `150` | Nombre de tirages Monte-Carlo par graine consensus. |
| `consensus_top_k` | `int` | `60` | Nombre de meilleures stratégies soumises au vote consensus. |
| `consensus_std_weight` | `float` | `0.35` | Poids de la pénalité sur l'écart-type inter-graines ($\text{Score} = \mu + w \cdot \sigma$). |
| `consensus_score_mode` | `string` | `"mean_std"` | Mode de calcul du score consensus (`"mean_std"` ou `"mean"`). |
| `consensus_seed_list` | `string` | `"41,42,43,44,45"` | Liste des graines explicites pour le consensus. |

---

## 7. Critères de Symétrie & Continuité

| Clé JSON | Type | Valeur | Description |
|---|---|---|---|
| `sym_enable` | `int`/`bool` | `1` | Active la génération de stratégies à symétrie / extrema synchronisés. |
| `sym_weight` | `float` | `0.5` | Poids du bonus de symétrie spectrale dans le score combiné. |
| `sym_same_wl_bonus` | `float` | `0.2` | Bonus accordé aux couches successives surveillées à la même $\lambda$. |
| `sym_extrema_window` | `float` | `5.0` | Fenêtre de proximité en nm pour regrouper les extrema de même longueur d'onde. |
| `sym_continuity_weight` | `float` | `0.1` | Poids accordé à la continuité spectrale entre couches adjacentes. |
| `sym_adaptive_same_wl` | `int`/`bool` | `1` | Activation de la synchronisation adaptative des longueurs d'onde. |
| `sym_scoring_mode` | `string` | `"post"` | Moment d'application du score symétrique (`"post"` = Phase B). |

---

## 8. Exportation & Affichage

| Clé JSON | Type | Valeur | Description |
|---|---|---|---|
| `show_plots` | `bool` | `true`/`false` | Affichage automatique des tracés graphiques à l'issue du solveur. |
| `export_excel` | `bool` | `true`/`false` | Génération automatique des classeurs Excel détaillés (rapport de stratégie). |
| `force_first_layer_same_wl` | `bool` | `true` | Fixe la première couche sur la même longueur d'onde que la couche de calibration. |
