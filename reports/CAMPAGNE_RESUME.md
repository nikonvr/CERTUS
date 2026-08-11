# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 22 / 22**  `[######################]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | objet |
|---|---|---|---|---|---|---|---|
| D0.ref | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | reference on the corrected envelope -- the anchor for this campaign |
| D1.1 | OK | `0.0033865463438199077` | **0.3 nm** | 900000390 | 3 | 0.0% | corridor 0.001, corrected normalisation |
| D1.2 | OK | `0.005089493987474638` | **0.5 nm** | 900000567 | 4 | 0.0% | corridor 0.0025, corrected |
| D1.3 | OK | `0.006727492320190995` | **0.6 nm** | 900000705 | 5 | 0.0% | corridor 0.005 -- THE model value, corrected |
| D1.4 | OK | `0.011805431613875829` | **1.1 nm** | 900001202 | 8 | 0.0% | corridor 0.010, corrected |
| D1.5 | OK | `0.23406418640706575` | **22.3 nm** | 900000005 | 3 | 29.3% | corridor 0.005 POEM OFF -- does the x6.85 protection hold on the corrected corridor? |
| D2.25 | OK | `0.0027033774715332737` | **0.3 nm** | 2228 | 2 | 0.0% | N = 25 -- ranking convergence |
| D2.50 | OK | `0.0026936808135072676` | **0.3 nm** | 2218 | 2 | 0.0% | N = 50 |
| D2.100 | OK | `0.0028493314298188876` | **0.3 nm** | 2228 | 2 | 0.0% | N = 100 |
| D2.300 | OK | `0.002936783731341741` | **0.3 nm** | 2228 | 2 | 0.0% | N = 300 |
| D2.600 | OK | `0.0030362390971507233` | **0.3 nm** | 2228 | 2 | 0.0% | N = 600 |
| D2.1200 | OK | `0.0030268860002336706` | **0.3 nm** | 2218 | 2 | 0.0% | N = 1200 -- certification depth |
| D3.10 | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | screening at 10 draws |
| D3.50 | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | screening at 50 draws |
| D3.100 | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | screening at 100 draws |
| D3.keep30 | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | keep 30 survivors instead of 10 -- does the funnel leak? |
| D4.77 | OK | `0.002743103557596595` | **0.3 nm** | 900000298 | 3 | 0.0% | seed 77 |
| D4.101 | OK | `0.003478085428571205` | **0.3 nm** | 900000173 | 3 | 0.0% | seed 101 |
| D4.202 | OK | `0.00362290759837916` | **0.3 nm** | 900000029 | 2 | 0.0% | seed 202 |
| D4.consensus | OK | `0.002948627371309867` | **0.3 nm** | 2228 | 2 | 0.0% | multi-seed consensus ranking, built and switched off since forever |
| D5.marg | OK | `0.0027329534107462224` | **0.3 nm** | 2226 | 2 | 0.0% | Phase A margin 3.33 -- was bit-identical to 1.66 |
| D5.yw200 | OK | `0.0027329534107462224` | **0.3 nm** | 2228 | 2 | 0.0% | dp_yield_weight 200 -- was inert across three decades |

## Configurations appliquees

- **D0.ref** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D1.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.001, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D1.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0025, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D1.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D1.4** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D1.5** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.25** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 25, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.50** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 50, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.100** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 100, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.300** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 300, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.600** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 600, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D2.1200** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 1200, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D3.10** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D3.50** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 50, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D3.100** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 100, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D3.keep30** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 30, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D4.77** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D4.101** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 101, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D4.202** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 202, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D4.consensus** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": true, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D5.marg** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 3.33, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **D5.yw200** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 200.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
