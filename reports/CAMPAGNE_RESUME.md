# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` apres chaque run. Ce fichier est une SORTIE.

Runs termines : 6 / 6

| run | statut | RESULT | objet |
|---|---|---|---|
| C1.0 | OK | `0.002948627371226749` | post-A10 baseline, corridor 0 -- re-establishes the reference after recompilation |
| C1.1 | OK | `0.005823435585164766` | corridor 0.001 -- was x1.98 with growth only |
| C1.2 | OK | `0.009213270883532371` | corridor 0.0025 -- was x3.35 with growth only |
| C1.3 | OK | `0.017080605971392195` | corridor 0.005, the model value -- was x5.16 with growth only |
| C1.4 | OK | `0.030862310655207868` | corridor 0.010 -- was x8.19 with growth only |
| C1.5 | OK | `0.23108226297877293` | corridor 0.005 with POEM OFF -- does the x7.6 protection survive? |

## Configurations appliquees

- **C1.0** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **C1.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.001, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **C1.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0025, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **C1.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.005, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **C1.4** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.01, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **C1.5** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.005, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
