# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 12 / 12**  `[############]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | objet |
|---|---|---|---|---|---|---|---|
| E0.ref | OK | `0.0027329534106323534` | **0.3 nm** | 2228 | 2 | 0.0% | neutral -- C1 GATE: must reproduce D0.ref to ~1e-10, no further |
| E1.1 | OK | `0.0033634956368793567` | **0.3 nm** | 900000446 | 3 | 0.0% | corridor 0.001, coherent stages |
| E1.2 | OK | `0.005542736295140752` | **0.5 nm** | 900000156 | 4 | 0.0% | corridor 0.0025, coherent stages |
| E1.3 | OK | `0.006573011625242959` | **0.6 nm** | 900000709 | 7 | 0.0% | corridor 0.005 -- THE model value, coherent stages |
| E1.4 | OK | `0.012734074130335598` | **1.2 nm** | 900000625 | 4 | 0.0% | corridor 0.010, coherent stages |
| E1.5 | OK | `0.024359627042271965` | **2.3 nm** | 900000584 | 5 | 0.0% | corridor 0.005 POEM OFF -- now Phase A also propagates without POEM |
| E2.yw | OK | `0.006573011625242959` | **0.6 nm** | 900000709 | 7 | 0.0% | dp_yield_weight 200 AT corridor 0.005 -- where crashes actually exist |
| E3.2 | OK | `0.0032746177708759595` | **0.3 nm** | 900000051 | 2 | 0.0% | POEM on, distortion on |
| E3.3 | OK | `0.006637109976145692` | **0.6 nm** | 900000775 | 5 | 0.0% | POEM OFF, distortion off |
| E3.4 | OK | `0.3279370792191264` | **31.3 nm** | 8800 | 8 | 59.3% | POEM OFF, distortion on -- the arm that decides |
| E4.77 | OK | `0.014093977928206033` | **1.3 nm** | 900000271 | 4 | 0.0% | corridor 0.005 at seed 77 |
| E4.101 | OK | `0.012534895342384519` | **1.2 nm** | 50182 | 48 | 0.7% | corridor 0.005 at seed 101 |

## Configurations appliquees

- **E0.ref** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E1.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.001, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E1.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0025, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E1.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E1.4** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E1.5** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E2.yw** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 200.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E3.2** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E3.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E3.4** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E4.77** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **E4.101** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 101, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
