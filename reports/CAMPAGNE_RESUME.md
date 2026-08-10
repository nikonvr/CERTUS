# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` apres chaque run. Ce fichier est une SORTIE.

Runs termines : 10 / 10

| run | statut | RESULT | objet |
|---|---|---|---|
| A12.1 | OK | `0.002948627371309867` | POEM on, distortion off -- the reference arm of the POEM test |
| A12.2 | OK | `0.0029742829447752268` | POEM on, distortion on |
| A12.3 | OK | `0.005824599272270286` | POEM OFF, distortion off |
| A12.4 | OK | `0.10256954814393225` | POEM OFF, distortion on -- the arm that decides |
| A15.1 | OK | `0.002948627371309867` | Phase A margin 3.33 instead of 1.66 |
| A14.1 | OK | `0.009877098892570137` | index corridor 0.0025 -- half width |
| A14.2 | OK | `0.015225307261493397` | index corridor 0.005 -- the model value |
| A6.1 | OK | `0.002948627371309867` | neutral repeat -- measures the bench's own jitter |
| A6.2 | OK | `0.002948627371309867` | neutral repeat -- measures the bench's own jitter |
| A6.3 | OK | `0.002948627371309867` | neutral repeat -- measures the bench's own jitter |

## Configurations appliquees

- **A12.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A12.2** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A12.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A12.4** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A15.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 3.33, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A14.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0025, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A14.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.005, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A6.1** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A6.2** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **A6.3** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "index_corridor": 0.0, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
