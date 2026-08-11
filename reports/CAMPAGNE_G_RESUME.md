# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 6 / 6**  `[######]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | objet |
|---|---|---|---|---|---|---|---|
| G1.0075 | OK | `0.010759861471280425` | **1.0 nm** | 900000073 | 2 | 0.0% | seed 77 at corridor 0.0075 -- bracket the cliff from below |
| G1.0060 | OK | `0.007690832306623568` | **0.7 nm** | 900000360 | 3 | 0.0% | seed 77 at corridor 0.0060 -- just above the model value |
| G2.202a | OK | `0.013727779993298168` | **1.3 nm** | 48836 | 48 | 0.0% | seed 202 at the model corridor 0.005 |
| G2.202b | OK | `0.09457390925219354` | **9.1 nm** | 900000010 | 2 | 37.3% | seed 202 at 0.010 -- is the cliff there too? |
| G3.303a | OK | `0.0059789415722207575` | **0.6 nm** | 900000643 | 5 | 0.0% | seed 303 at the model corridor 0.005 |
| G3.303b | OK | `0.014663982592690448` | **1.4 nm** | 900000162 | 2 | 0.0% | seed 303 at 0.010 |

## Configurations appliquees

- **G1.0075** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0075, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **G1.0060** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.006, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **G2.202a** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 202, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **G2.202b** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 202, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **G3.303a** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 303, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **G3.303b** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 303, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
