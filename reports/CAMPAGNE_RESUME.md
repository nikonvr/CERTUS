# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 8 / 8**  `[########]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

🔴 `forcees` = couches ou la Phase A n'avait AUCUNE lambda admissible et a garde
la moins mauvaise (17-37). Une valeur non nulle veut dire que la strategie est
SUBIE, pas choisie : son score n'est pas comparable a celui d'un run libre.

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | forcees | objet |
|---|---|---|---|---|---|---|---|---|
| N48.50 | OK | `0.0061535326732558345` | **0.6 nm** | 900000248 | 7 | 0.0% | 0 | 48-layer dichroic, 50 draws -- depth against wall-clock |
| N48.150 | OK | `0.0059725813338143575` | **0.6 nm** | 900000255 | 6 | 0.0% | 0 | 48-layer dichroic, 150 draws -- depth against wall-clock |
| N48.300 | OK | `0.006110491633768144` | **0.6 nm** | 900000064 | 6 | 0.0% | 0 | 48-layer dichroic, 300 draws -- depth against wall-clock |
| N48.500 | OK | `0.006110491633768144` | **0.6 nm** | 900000016 | 6 | 0.0% | 0 | 48-layer dichroic, 500 draws -- depth against wall-clock |
| N35.50 | OK | `0.046350294829477535` | **1.2 nm** | 37172 | 35 | 0.0% | 0 | 35-layer bandpass, 50 draws -- depth against wall-clock |
| N35.150 | OK | `0.05645656956518977` | **1.4 nm** | 35838 | 35 | 0.0% | 0 | 35-layer bandpass, 150 draws -- depth against wall-clock |
| N35.300 | OK | `0.05507479034893577` | **1.4 nm** | 35838 | 35 | 0.0% | 0 | 35-layer bandpass, 300 draws -- depth against wall-clock |
| N35.500 | OK | `0.046350294829477535` | **1.2 nm** | 37413 | 35 | 0.0% | 0 | 35-layer bandpass, 500 draws -- depth against wall-clock |

## Configurations appliquees

- **N48.50** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 50, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N48.150** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N48.300** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N48.500** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 500, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N35.50** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 50, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N35.150** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N35.300** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **N35.500** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 500, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
