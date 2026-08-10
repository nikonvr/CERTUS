# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` apres chaque run. Ce fichier est une SORTIE.

Runs termines : 10 / 10

| run | statut | RESULT | objet |
|---|---|---|---|
| B0.recompile | OK | `0.002948627371226749` | cold numba cache, unchanged code -- must it reproduce 0.002948627371309867 ? |
| B1.1 | OK | `0.003552737817426423` | seed 77 -- POEM on, distortion off |
| B1.2 | OK | `0.007044331215249108` | seed 77 -- POEM on, distortion on |
| B1.3 | OK | `0.009136355766277806` | seed 77 -- POEM OFF, distortion off |
| B1.4 | OK | `0.2757192112775556` | seed 77 -- POEM OFF, distortion on |
| B2.1 | OK | `0.22864785676622182` | corridor 0.005 with POEM OFF -- the boundary of POEM's protection |
| B3.1 | OK | `0.0031920381104074743` | tp_hysteresis 2.00 A -- the anti-fabrication bound |
| B3.2 | OK | `0.0031920381104074743` | tp_hysteresis 2.40 A -- where fabrication measured 0 % |
| B4.1 | OK | `0.0058416969924860035` | index corridor 0.001 |
| B4.2 | OK | `0.02415974757101489` | index corridor 0.010 -- twice the model value |

## Configurations appliquees

- **B0.recompile** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B1.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B1.2** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B1.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B1.4** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B2.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.005, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B3.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 2.0}`
- **B3.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 2.4}`
- **B4.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.001, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **B4.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.01, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
