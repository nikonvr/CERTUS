# RESUME DE CAMPAGNE

Ecrit par `scripts/run_campaign.py` **apres chaque run**. Ce fichier est une SORTIE.

**Avancement : 4 / 4**  `[####]`

SEEL = erreur aleatoire equivalente par couche, en nm, quantifiee a 0,1 nm.
C'est la seule colonne lisible sans conversion. RESULT est le PIRE des trois
niveaux de bruit ; il ne se compare a aucune valeur par strategie (voir 10).

| run | statut | RESULT | SEEL | gagnante | blocs | plantage | objet |
|---|---|---|---|---|---|---|---|
| F1.yw | OK | `0.3279370792191264` | **31.3 nm** | 8800 | 8 | 59.3% | dp_yield_weight 200 where crashes REALLY exist: POEM off + distortion |
| F2.101 | OK | `0.01381160857961636` | **1.3 nm** | 900000116 | 3 | 0.0% | corridor 0.010 at seed 101 -- does 48-block monitoring win harder? |
| F2.77 | OK | `0.32955376104682704` | **30.3 nm** | 900000007 | 4 | 100.0% | corridor 0.010 at seed 77 -- same question, second seed |
| F2.42 | OK | `0.3861091481717704` | **36.8 nm** | 900000001 | 3 | 99.3% | corridor 0.020 at seed 42 -- push past the model value |

## Configurations appliquees

- **F1.yw** — `{"affine_offset_amp": 0.02, "affine_scale_amp": 0.05, "dp_yield_weight": 200.0, "enable_consensus_ranking": false, "index_corridor": 0.0, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": false, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **F2.101** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 101, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **F2.77** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.01, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 77, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`
- **F2.42** — `{"affine_offset_amp": 0.0, "affine_scale_amp": 0.0, "dp_yield_weight": 0.0, "enable_consensus_ranking": false, "index_corridor": 0.02, "k_keep_survivors": 10, "n_screen_runs": 25, "phase_a_level_margin_factor": 1.66, "poem_anchor_noise": true, "poem_enabled": true, "reading_smoothing_window": 1, "robustness_num_runs": 150, "robustness_seed": 42, "scan_wl_step": 1.0, "tp_hysteresis_factor": 1.66}`

Transcriptions completes : `reports/campagne_*.log`.
