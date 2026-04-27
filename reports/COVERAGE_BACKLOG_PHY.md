# Coverage Function Audit — _certus_physics_impl.py

*Auto-generated from `tools/coverage_function_audit.py --xml coverage_phy.xml --top 30 --min-loc 20`. Date: 2026-04-26.*

*Suite de tests utilisée:* `test_physics_*.py` (+ TMM/gradient/energy legacy). Total = 77 tests, 12 fichiers.

- Missed lines (raw): **4280**
- Functions analysed: **173**
- Fully uncovered (>= 20 LOC): **0**
- Partially uncovered (>= 20 LOC): **124**

## Top 30 fully uncovered functions (by LOC desc)

| Rank | Qualname | Lines | LOC |
| ---: | :--- | :---: | ---: |

## Top 30 partially uncovered functions (by missed lines desc)

| Rank | Qualname | Lines | LOC | Missed | Cover % |
| ---: | :--- | :---: | ---: | ---: | ---: |
| 1 | `_compute_gradient_analytic_kernel` | 9950-10563 | 614 | 270 | 56.0% |
| 2 | `_compute_oblique_gradient_contrib_kernel` | 10569-11000 | 432 | 184 | 57.4% |
| 3 | `_compute_oblique_rt_and_grads_kernel` | 11084-11503 | 420 | 184 | 56.2% |
| 4 | `_compute_epsilon1_gradient_kernel` | 8521-8944 | 424 | 170 | 59.9% |
| 5 | `needle_scan_cached` | 4692-5147 | 456 | 167 | 63.4% |
| 6 | `_compute_single_layer_sensitivity_kernel` | 9037-9462 | 426 | 120 | 71.8% |
| 7 | `calculate_detailed_growth` | 15081-15388 | 308 | 116 | 62.3% |
| 8 | `_compute_metal_tmm_gradient_kernel` | 11984-12225 | 242 | 100 | 58.7% |
| 9 | `_calc_spectrum_oblique_parallel` | 3176-3449 | 274 | 96 | 65.0% |
| 10 | `_compute_ir_global_cost_gradient_kernel` | 15693-15946 | 254 | 94 | 63.0% |
| 11 | `simulate_growth_kernel` | 13401-13664 | 264 | 91 | 65.5% |
| 12 | `check_extrema_proximity` | 12548-12833 | 286 | 90 | 68.5% |
| 13 | `calc_spectrum_full_oblique_exact` | 3920-4155 | 236 | 69 | 70.8% |
| 14 | `_compute_valid_blocks_kernel` | 13042-13193 | 152 | 68 | 55.3% |
| 15 | `_compute_phase2_derivatives_kernel` | 15544-15687 | 144 | 65 | 54.9% |
| 16 | `_compute_index_cost_gradient_kernel` | 9474-9657 | 184 | 61 | 66.8% |
| 17 | `_oblique_stack_rt_single` | 3569-3724 | 156 | 61 | 60.9% |
| 18 | `calculate_extrema_distances` | 12842-13009 | 168 | 60 | 64.3% |
| 19 | `_dp_kernel` | 13199-13336 | 138 | 57 | 58.7% |
| 20 | `_compute_epsilon2_gradient_kernel` | 8382-8509 | 128 | 57 | 55.5% |
| 21 | `compute_gradient_all_layers_analytic` | 11777-11972 | 196 | 52 | 73.5% |
| 22 | `_calculate_RT_HL_single_point` | 14439-14567 | 129 | 52 | 59.7% |
| 23 | `PGlobalOptimizer.optimize` | 6002-6152 | 151 | 51 | 66.2% |
| 24 | `compute_metal_bilayer_gradient_analytic` | 12234-12357 | 124 | 50 | 59.7% |
| 25 | `warmup_physics` | 15949-16073 | 125 | 49 | 60.8% |
| 26 | `compute_dynamics_kernel` | 14307-14427 | 121 | 49 | 59.5% |
| 27 | `calculate_reflection_infinite_substrate_single` | 7994-8147 | 154 | 48 | 68.8% |
| 28 | `delta_e_2000` | 7053-7171 | 119 | 48 | 59.7% |
| 29 | `_calculate_RT_absorbing_sub_single` | 2196-2313 | 118 | 44 | 62.7% |
| 30 | `calculate_RT_single_layer_single` | 1814-2007 | 194 | 43 | 77.8% |
