# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 6 / 6**  `[######]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

🔴 `forcees` = couches ou la Phase A n'avait AUCUNE lambda admissible et a garde
la moins mauvaise (17-37). Une valeur non nulle veut dire que la strategie est
SUBIE, pas choisie : son score n'est pas comparable a celui d'un run libre.

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | forcees | objet |
|---|---|---|---|---|---|---|---|---|
| G0.c1 | FAILED | `0.00611049163380679` | **0.6 nm** | 900000066 | 6 | 0.0% | 0 | gate INACTIVE, N=300 scr=10 -- must reproduce 0.006151532415266679 |
| G1.off | FAILED | `0.006138704636203437` | **0.6 nm** | 900000127 | 5 | 0.0% | 0 | working point, gate OFF -- the control of G1.on |
| G1.on | FAILED | `0.006138704636203437` | **0.6 nm** | 900000116 | 5 | 0.0% | 0 | working point, gate ARMED at 95 % |
| G2.150 | FAILED | `0.006325267261458552` | **0.6 nm** | 900000125 | 5 | 0.0% | 0 | armed, 150 draws -- is the ranking now depth-insensitive? |
| G2.500 | FAILED | `0.006806535500774607` | **0.6 nm** | 900000192 | 5 | 0.0% | 0 | armed, 500 draws -- same question, other end |
| G3.scr10on | FAILED | `0.006101296866429275` | **0.6 nm** | 900000242 | 6 | 0.0% | 0 | n_screen=10, gate ARMED -- control is G0.c1 |

## Ecarts entre demande et configuration appliquee

- **G0.c1** : crash_gate_confidence: asked 0.0, applied '<absent>'
- **G1.off** : crash_gate_confidence: asked 0.0, applied '<absent>'
- **G1.on** : crash_gate_confidence: asked 0.95, applied '<absent>'
- **G2.150** : crash_gate_confidence: asked 0.95, applied '<absent>'
- **G2.500** : crash_gate_confidence: asked 0.95, applied '<absent>'
- **G3.scr10on** : crash_gate_confidence: asked 0.95, applied '<absent>'

## Configurations appliquees

- **G0.c1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **G1.off** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **G1.on** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **G2.150** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **G2.500** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 500, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`
- **G3.scr10on** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "allow_rate": true, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "machine_sampling_dd": 0.0, "monochromator_resolution_nm": 2.0, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "photometric_curvature_amp": 0.00375, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "search_resolution": true, "slit_bias_enabled": true, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
