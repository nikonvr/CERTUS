# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 7 / 7**  `[#######]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | objet |
|---|---|---|---|---|---|---|---|
| S0.base | OK | `0.0027212100781054643` | **0.3 nm** | 2226 | 2 | 0.0% | the plain path |
| S1.corridor | OK | `0.00690007927269489` | **0.7 nm** | 900000607 | 5 | 0.0% | corridor on the NEW envelope -- never run end to end |
| S2.poemoff | OK | `0.2337454256503927` | **22.3 nm** | 900000014 | 4 | 35.0% | POEM off, with corridor |
| S3.affine | OK | `0.0027226943089580027` | **0.3 nm** | 2225 | 2 | 0.0% | affine distortion |
| S4.knobs | OK | `0.0027212100781054643` | **0.3 nm** | 2224 | 2 | 0.0% | Phase A margin and survivor count -- never run since the changes |
| S5.consensus | OK | `0.002948627371309867` | **0.3 nm** | 2228 | 2 | 0.0% | multi-seed consensus -- switched off since forever, never exercised |
| S6.seed | OK | `0.0027377813697974365` | **0.3 nm** | 900000423 | 3 | 0.0% | another seed, and dp_yield_weight through argument 4 |

## Configurations appliquees

- **S0.base** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S1.corridor** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S2.poemoff** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.005, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S3.affine** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S4.knobs** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 30, "n_screen_runs": 10, "phase_a_level_margin_factor": 3.33, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S5.consensus** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": true, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **S6.seed** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 200.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 10, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 20, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
