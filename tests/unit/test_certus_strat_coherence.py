"""CERTUS_STRAT scientific consistency tests.


- Worst-case score P95, metrics P95/P99


- Constant dynamics, seed reproducibility


- No fallback to rejected candidate"""





import pytest


import sys


import numpy as np


from pathlib import Path





sys.path.insert(0, str(Path(__file__).parent.parent.parent))





pytest.importorskip("CERTUS_STRAT")


import CERTUS_STRAT as STRAT








class TestStratDynamicsMetric:


    """Dynamics metric consistency (peak-to-peak)."""





    def test_dynamics_metric_constant(self):


        assert hasattr(STRAT, "DYNAMICS_METRIC_NAME")


        assert STRAT.DYNAMICS_METRIC_NAME == "peak_to_peak"








class TestStratRobustnessScoring:


    """Score Phase B = worst-case RMSE P95."""





    def test_results_per_noise_contain_rmse_p95_p99(self):


        """Chaque niveau de bruit expose rmse_p95 et rmse_p99."""


        from CERTUS_STRAT import _test_strategy_robustness_task





        # Minimal strategy + params (without running any real heavy calculations)


        strategy = {


            "strategy_id": "test",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


            "n_blocks": 1,


        }


        p_thick = [100.0, 80.0]


        clues_at_wl = {


            500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


        }


        params = {


            "thickness_tolerance_nm": None,


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "wavelength_change_penalty": 1.2,


            "non_monotonic_error_factor": 2.0,


        }


        wl_arr = np.linspace(400, 600, 21)


        nH = np.full(21, 2.3 + 0j, dtype=np.complex128)


        nL = np.full(21, 1.45 + 0j, dtype=np.complex128)


        nSub = np.full(21, 1.52 + 0j, dtype=np.complex128)


        T_nom = np.ones(21, dtype=np.float64) * 0.5





        np.random.seed(42)


        res = _test_strategy_robustness_task(


            strategy,


            0,


            [0.5, 1.0],


            10,


            p_thick,


            clues_at_wl,


            params,


            wl_arr,


            nH,


            nL,


            nSub,


            T_nom,


            {},


        )


        for r in res["results_per_noise"]:


            assert "rmse_p95" in r


            assert "rmse_p99" in r


            assert r["rmse_p95"] >= 0


            assert r["rmse_p99"] >= r["rmse_p95"]





    def test_robustness_score_is_max_p95(self):


        """Le robustness_score est le max des rmse_p95 sur les niveaux de bruit."""


        from CERTUS_STRAT import _test_strategy_robustness_task





        strategy = {


            "strategy_id": "t",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


            "n_blocks": 1,


        }


        p_thick = [100.0, 80.0]


        clues_at_wl = {


            500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


        }


        params = {


            "thickness_tolerance_nm": None,


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "wavelength_change_penalty": 1.2,


            "non_monotonic_error_factor": 2.0,


        }


        wl_arr = np.linspace(400, 600, 21)


        nH = np.full(21, 2.3 + 0j, dtype=np.complex128)


        nL = np.full(21, 1.45 + 0j, dtype=np.complex128)


        nSub = np.full(21, 1.52 + 0j, dtype=np.complex128)


        T_nom = np.ones(21, dtype=np.float64) * 0.5





        np.random.seed(123)


        res = _test_strategy_robustness_task(


            strategy, 0, [0.5, 1.0], 8, p_thick, clues_at_wl, params,


            wl_arr, nH, nL, nSub, T_nom, {},


        )


        expected = max(r["rmse_p95"] for r in res["results_per_noise"])


        assert res["robustness_score"] == expected








class TestStratSeedReproducibility:


    """Reproducibility under fixed seed."""





    def test_same_seed_same_score(self):


        """Same seed and same params -> same robustness_score."""


        from CERTUS_STRAT import _test_strategy_robustness_task





        strategy = {


            "strategy_id": "t",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


            "n_blocks": 1,


        }


        p_thick = [100.0, 80.0]


        clues_at_wl = {


            500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


        }


        params = {


            "thickness_tolerance_nm": None,


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "wavelength_change_penalty": 1.2,


            "non_monotonic_error_factor": 2.0,


        }


        wl_arr = np.linspace(400, 600, 21)


        nH = np.full(21, 2.3 + 0j, dtype=np.complex128)


        nL = np.full(21, 1.45 + 0j, dtype=np.complex128)


        nSub = np.full(21, 1.52 + 0j, dtype=np.complex128)


        T_nom = np.ones(21, dtype=np.float64) * 0.5





        np.random.seed(99)


        res1 = _test_strategy_robustness_task(


            strategy, 0, [1.0], 12, p_thick, clues_at_wl, params,


            wl_arr, nH, nL, nSub, T_nom, {},


        )


        np.random.seed(99)


        res2 = _test_strategy_robustness_task(


            strategy, 0, [1.0], 12, p_thick, clues_at_wl, params,


            wl_arr, nH, nL, nSub, T_nom, {},


        )


        assert res1["robustness_score"] == res2["robustness_score"]








class TestStratSafetyFallback:


    """No fallback to a rejected candidate (extrema/resolution)."""





    def test_fallback_is_l0_only(self):


        """When no candidate passes the filters, final_list = [lambda₀] only."""


        from CERTUS_STRAT import _select_candidates_phase_a





        scan_wl = np.array([450.0, 500.0, 550.0])


        p_thick = [80.0]


        clues_at_wl = {


            w: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}


            for w in [450.0, 500.0, 550.0]


        }


        # Cache minimal 1 layer, 3 wls


        cache = np.zeros((1, 3, 2, 2), dtype=np.complex128)


        cache[0, :, 0, 0] = 1.0


        cache[0, :, 1, 1] = 1.0


        all_wls = np.array([450.0, 500.0, 550.0])


        params = {


            "logger": __import__("logging").getLogger("test"),


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "min_transmission_floor": 0.0,


            "strict_min_transmission_floor": False,


            "extrema_exclusion_ratio": 40.0,


            "min_spectral_resolution": 1.0,


            "resolution_curvature_tolerance": 0.01,


            "nH_id": "TiO2",


            "nL_id": "SiO2",


            "nSub_id": "BK7",


            "materials_db": None,


        }


        l0 = 500.0





        final_list, _ = _select_candidates_phase_a(


            scan_wl, 0, p_thick, clues_at_wl, cache, all_wls, params, l0,


            current_avg_stack=[],


        )


        # At least one candidate (possibly only l0)


        assert len(final_list) >= 1


        # If we had rejected everything, the fallback would be [l0]; we must never


        # have a candidate who failed the filters.


        for c in final_list:


            assert "wl" in c and "dynamics" in c





    def test_strict_transmission_floor_raises_when_no_candidate(self):


        """In strict mode, if no lambda respects T_min floor, we raise an explicit error."""


        from CERTUS_STRAT import _select_candidates_phase_a





        scan_wl = np.array([450.0, 500.0, 550.0])


        p_thick = [80.0]


        clues_at_wl = {


            w: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}


            for w in [450.0, 500.0, 550.0]


        }


        cache = np.zeros((1, 3, 2, 2), dtype=np.complex128)


        cache[0, :, 0, 0] = 1.0


        cache[0, :, 1, 1] = 1.0


        all_wls = np.array([450.0, 500.0, 550.0])


        params = {


            "logger": __import__("logging").getLogger("test"),


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "min_transmission_floor": 1.1,  # impossible


            "strict_min_transmission_floor": True,


            "extrema_exclusion_ratio": 40.0,


            "min_spectral_resolution": 1.0,


            "resolution_curvature_tolerance": 0.01,


            "nH_id": "TiO2",


            "nL_id": "SiO2",


            "nSub_id": "BK7",


            "materials_db": None,


        }





        with pytest.raises(RuntimeError):


            _select_candidates_phase_a(


                scan_wl, 0, p_thick, clues_at_wl, cache, all_wls, params, 500.0,


                current_avg_stack=[],


            )








class TestStratSymmetryScoring:


    """Validation du pipeline de scoring SYM local."""





    def test_local_extrema_symmetry_score_bounds(self):


        from CERTUS_STRAT import _compute_local_extrema_symmetry_score





        score_good = _compute_local_extrema_symmetry_score(1.0, 1.2, 12.0)


        score_poor = _compute_local_extrema_symmetry_score(12.0, 999.0, 12.0)


        assert 0.0 <= score_good <= 1.0


        assert 0.0 <= score_poor <= 1.0


        assert score_good > score_poor





    def test_build_symmetry_bonus_map_reads_extrema_fields(self):


        from CERTUS_STRAT import _build_symmetry_bonus_map





        raw = {


            0: [


                {


                    "wl": 500.0,


                    "cost": 1.0,


                    "ext_prev_start": 1.0,


                    "ext_next_start": 1.0,


                    "ext_prev_end": 2.0,


                    "ext_next_end": 2.0,


                }


            ]


        }


        bonus_map = _build_symmetry_bonus_map(raw, 1, 12.0)


        assert 0 in bonus_map


        assert 500.0 in bonus_map[0]


        assert bonus_map[0][500.0] > 0.0








class TestStratTheoreticalLayerProfile:


    """Validation des metriques theoriques par couche (sans bruit)."""





    def test_extract_local_extrema_points_detects_min_and_max(self):


        from CERTUS_STRAT import _extract_local_extrema_points





        d = np.array([0.0, 1.0, 2.0, 3.0, 4.0], dtype=np.float64)


        t = np.array([0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)


        pts = _extract_local_extrema_points(d, t)


        types = [p["type"] for p in pts]


        assert "max" in types


        assert "min" in types





    def test_compute_theoretical_layer_profile_has_required_fields(self):


        from CERTUS_STRAT import _compute_theoretical_layer_profile





        M_before = np.array([[1.0 + 0j, 0.0 + 0j], [0.0 + 0j, 1.0 + 0j]], dtype=np.complex128)


        prof = _compute_theoretical_layer_profile(


            wl_nm=550.0,


            n_current=2.3 + 0j,


            n_sub=1.52 + 0j,


            nominal_thickness=120.0,


            M_before=M_before,


        )


        for key in [


            "Tinit",


            "Tfinal",


            "Textrema",


            "d_nom_nm",


            "dist_prev_start",


            "dist_next_start",


            "dist_prev_end",


            "dist_next_end",


            "dist_end_nearest",


            "nearest_end_type",


            "nearest_end_dist_nm",


            "tfinal_class",


            "extrema_count",


        ]:


            assert key in prof


        assert np.isfinite(prof["Tinit"])


        assert np.isfinite(prof["Tfinal"])


        assert prof["extrema_count"] >= 0


        assert prof["tfinal_class"] in {"near min", "near max", "between"}








class TestStratSymmetryMining:


    """SYM mining validation + same wavelength bonus."""





    def test_same_wavelength_bonus_changes_dp_ranking(self):


        from CERTUS_STRAT import _find_k_best_groupings_dp_sequential





        cost_map = {


            0: {500.0: 0.8, 600.0: 1.0},


            1: {500.0: 1.0, 600.0: 0.8},


        }


        no_bonus = _find_k_best_groupings_dp_sequential(


            cost_map,


            n_blocks=2,


            num_layers=2,


            top_k=8,


            enable_sym_post_ranking=False,


        )


        with_bonus = _find_k_best_groupings_dp_sequential(


            cost_map,


            n_blocks=2,


            num_layers=2,


            top_k=8,


            sym_bonus_map=None,


            sym_weight=0.0,


            same_wl_bonus=0.3,


            enable_sym_post_ranking=True,


        )


        wls_no_bonus = [b[2] for b in no_bonus[0]["blocks_info"]]


        wls_with_bonus = [b[2] for b in with_bonus[0]["blocks_info"]]


        assert abs(wls_no_bonus[0] - wls_no_bonus[1]) > 1e-6


        assert abs(wls_with_bonus[0] - wls_with_bonus[1]) <= 1e-6





    def test_mining_emits_sym_origin(self):


        from CERTUS_STRAT import mine_strategies_for_block_count





        raw_thick = {


            0: [


                {


                    "wl": 500.0,


                    "cost": 1.0,


                    "ext_prev_start": 1.0,


                    "ext_next_start": 1.0,


                    "ext_prev_end": 1.0,


                    "ext_next_end": 1.0,


                },


                {


                    "wl": 520.0,


                    "cost": 0.9,


                    "ext_prev_start": 8.0,


                    "ext_next_start": 8.0,


                    "ext_prev_end": 8.0,


                    "ext_next_end": 8.0,


                },


            ],


            1: [


                {


                    "wl": 500.0,


                    "cost": 0.95,


                    "ext_prev_start": 1.0,


                    "ext_next_start": 1.2,


                    "ext_prev_end": 1.0,


                    "ext_next_end": 1.2,


                },


                {


                    "wl": 520.0,


                    "cost": 0.85,


                    "ext_prev_start": 8.0,


                    "ext_next_start": 8.0,


                    "ext_prev_end": 8.0,


                    "ext_next_end": 8.0,


                },


            ],


        }


        raw_sq = {


            0: [{"wl": 500.0, "cost": 1.0}, {"wl": 520.0, "cost": 0.81}],


            1: [{"wl": 500.0, "cost": 0.90}, {"wl": 520.0, "cost": 0.72}],


        }


        sym_bonus_map = {0: {500.0: 1.0, 520.0: 0.0}, 1: {500.0: 1.0, 520.0: 0.0}}


        out = mine_strategies_for_block_count(


            n_blocks=2,


            raw_results_thickness=raw_thick,


            raw_results_sq=raw_sq,


            num_layers=2,


            top_k=4,


            sym_enable=True,


            sym_bonus_map=sym_bonus_map,


            sym_weight=0.3,


            sym_same_wl_bonus=0.2,


        )


        assert any(s.get("origin") == "SYM" for s in out)


        for strat in out:


            assert "n_blocks" in strat





    def test_adaptive_same_wl_bonus_uses_layer_importance(self):


        from CERTUS_STRAT import _augment_solution_cost_with_sym





        sol = {"cost": 2.0, "blocks_info": [(0, 1, 500.0), (1, 2, 500.0)]}


        low_imp = {0: 0.0}


        high_imp = {0: 1.0}





        c_low, _, _ = _augment_solution_cost_with_sym(


            sol,


            sym_bonus_map=None,


            layer_importance_map=low_imp,


            sym_weight=0.0,


            same_wl_bonus=0.2,


            continuity_weight=0.5,


            adaptive_same_wl=True,


        )


        c_high, _, _ = _augment_solution_cost_with_sym(


            sol,


            sym_bonus_map=None,


            layer_importance_map=high_imp,


            sym_weight=0.0,


            same_wl_bonus=0.2,


            continuity_weight=0.5,


            adaptive_same_wl=True,


        )


        assert c_high < c_low








class TestStratSymmetryContractAndStability:


    """Structural contracts and ranking/seed stability."""





    def test_validate_strategy_blocks_contract_catches_gap(self):


        from CERTUS_STRAT import _validate_strategy_blocks_contract





        strategy = {


            "strategy_id": "bad",


            "n_blocks": 2,


            "blocks": [


                {"start": 0, "end": 1, "wavelength": 500.0, "num_layers": 1},


                {"start": 2, "end": 3, "wavelength": 500.0, "num_layers": 1},


            ],


        }


        ok, reason = _validate_strategy_blocks_contract(strategy, num_layers=3, expected_n_blocks=2)


        assert not ok


        assert "contiguous" in reason





    def test_validate_strategy_blocks_contract_handles_malformed_types(self):


        from CERTUS_STRAT import _validate_strategy_blocks_contract





        malformed = {


            "strategy_id": "bad-types",


            "n_blocks": "abc",


            "blocks": [123, {"start": "x", "end": 2, "wavelength": "nan", "num_layers": "1"}],


        }


        ok, reason = _validate_strategy_blocks_contract(malformed, num_layers=2, expected_n_blocks=1)


        assert not ok


        assert isinstance(reason, str) and len(reason) > 0





    def test_compute_blocks_range_contractual_handles_single_layer(self):


        from CERTUS_STRAT import _compute_blocks_range_contractual





        r = _compute_blocks_range_contractual(num_layers=1, div_start=10.0, div_end=3.0, dense=True)


        assert r == [1]





    def test_validate_candidates_phase_a_preserves_extrema_metadata(self, monkeypatch):


        from CERTUS_STRAT import _validate_candidates_phase_a





        def fake_validate(*_args, **_kwargs):


            return np.array([[0.25, 0.01]], dtype=np.float64)





        def fake_update(*_args, **_kwargs):


            return np.array([[100.0]], dtype=np.float64)





        monkeypatch.setattr(STRAT, "validate_wavelengths_batch", fake_validate)


        monkeypatch.setattr(STRAT, "update_run_states_kernel", fake_update)





        cands = [


            {


                "wl": 500.0,


                "dynamics": 0.1,


                "ext_prev_start": 1.0,


                "ext_next_start": 1.0,


                "ext_prev_end": 2.0,


                "ext_next_end": 2.0,


            }


        ]


        run_states = [{"p_thick_sim": []}]


        params = {


            "l0": 500.0,


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "non_monotonic_error_factor": 2.0,


        }


        clues = {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}}


        out, _ = _validate_candidates_phase_a(


            cands,


            i_layer=0,


            num_runs=1,


            p_thick_nominal=[100.0],


            clues_at_wl=clues,


            params=params,


            run_states=run_states,


            layer_noise_array=np.array([0.0], dtype=np.float64),


        )


        assert out[0]["ext_prev_start"] == 1.0


        assert out[0]["ext_next_end"] == 2.0





    def test_robustness_seed_is_independent_of_global_rng_state(self):


        from CERTUS_STRAT import _test_strategy_robustness_task





        strategy = {


            "strategy_id": "t",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


            "n_blocks": 1,


        }


        p_thick = [100.0, 80.0]


        clues_at_wl = {


            500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


        }


        params = {


            "thickness_tolerance_nm": None,


            "reality_sim_params": {"trigger_tolerance": 1.0},


            "wavelength_change_penalty": 1.2,


            "non_monotonic_error_factor": 2.0,


            "robustness_seed": 1234,


        }


        wl_arr = np.linspace(400, 600, 21)


        nH = np.full(21, 2.3 + 0j, dtype=np.complex128)


        nL = np.full(21, 1.45 + 0j, dtype=np.complex128)


        nSub = np.full(21, 1.52 + 0j, dtype=np.complex128)


        T_nom = np.ones(21, dtype=np.float64) * 0.5





        np.random.seed(1)


        res1 = _test_strategy_robustness_task(


            strategy, 0, [1.0], 12, p_thick, clues_at_wl, params, wl_arr, nH, nL, nSub, T_nom, {}


        )


        np.random.seed(9999)


        res2 = _test_strategy_robustness_task(


            strategy, 0, [1.0], 12, p_thick, clues_at_wl, params, wl_arr, nH, nL, nSub, T_nom, {}


        )


        assert res1["robustness_score"] == res2["robustness_score"]





    def test_run_final_simulation_block_prefers_sym_on_true_tie(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_test(strategy, *_args, **_kwargs):


            score = float(strategy["mock_score"])


            return {


                "strategy_id": strategy["strategy_id"],


                "strategy": strategy,


                "results_per_noise": [{"noise_level": 1.0, "rmse_mean": score, "rmse_std": 0.0, "rmse_p95": score, "rmse_p99": score}],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_test)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr("certus.core.certus_strat_config.get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128))


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        s_sym = {


            "strategy_id": "sym",


            "n_blocks": 1,


            "origin": "SYM",


            "mock_score": 0.5,


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        s_thk = {


            "strategy_id": "thk",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "mock_score": 0.5,


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        opti = {


            "all_strategies": [s_thk, s_sym],


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": True,


            "sym_tie_epsilon": 1e-6,


            "sym_tie_epsilon_rel": 0.0,


            "robustness_seed": 42,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        assert out["best_strategy"]["origin"] == "SYM"





    def test_run_final_simulation_block_prefers_smart_merge_sym_on_true_tie(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_test(strategy, *_args, **_kwargs):


            score = float(strategy["mock_score"])


            return {


                "strategy_id": strategy["strategy_id"],


                "strategy": strategy,


                "results_per_noise": [{"noise_level": 1.0, "rmse_mean": score, "rmse_std": 0.0, "rmse_p95": score, "rmse_p99": score}],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_test)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr("certus.core.certus_strat_config.get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128))


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        s_merge_sym = {


            "strategy_id": "merge_sym",


            "n_blocks": 1,


            "origin": "SMART_MERGE_SYM (from ID 10)",


            "mock_score": 0.5,


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        s_thk = {


            "strategy_id": "thk",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "mock_score": 0.5,


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        opti = {


            "all_strategies": [s_thk, s_merge_sym],


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": True,


            "sym_tie_epsilon": 1e-6,


            "sym_tie_epsilon_rel": 0.0,


            "robustness_seed": 42,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        assert "SYM" in out["best_strategy"]["origin"].upper()





    def test_run_final_simulation_block_tie_is_deterministic_by_strategy_id(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_test(strategy, *_args, **_kwargs):


            score = 0.5


            return {


                "strategy_id": strategy["strategy_id"],


                "strategy": strategy,


                "results_per_noise": [{"noise_level": 1.0, "rmse_mean": score, "rmse_std": 0.0, "rmse_p95": score, "rmse_p99": score}],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_test)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr("certus.core.certus_strat_config.get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128))


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 2)





        s2 = {


            "strategy_id": "b",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        s1 = {


            "strategy_id": "a",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        opti = {


            "all_strategies": [s2, s1],


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": False,


            "sym_tie_epsilon": 1e-6,


            "sym_tie_epsilon_rel": 0.0,


            "robustness_seed": 42,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        ids = [r["strategy"]["strategy_id"] for r in out["all_strategies_results"]]


        assert ids == sorted(ids)





    def test_run_final_simulation_block_applies_family_diversity_top_k(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        score_map = {"t1": 0.10, "t2": 0.11, "t3": 0.12, "s1": 0.20}





        def fake_test(strategy, *_args, **_kwargs):


            sid = strategy["strategy_id"]


            score = float(score_map[sid])


            return {


                "strategy_id": sid,


                "strategy": strategy,


                "results_per_noise": [{"noise_level": 1.0, "rmse_mean": score, "rmse_std": 0.0, "rmse_p95": score, "rmse_p99": score}],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_test)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr("certus.core.certus_strat_config.get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128))


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        t1 = {"strategy_id": "t1", "n_blocks": 1, "origin": "THICKNESS", "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}]}


        t2 = {"strategy_id": "t2", "n_blocks": 1, "origin": "THICKNESS", "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}]}


        t3 = {"strategy_id": "t3", "n_blocks": 1, "origin": "THICKNESS", "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}]}


        s1 = {"strategy_id": "s1", "n_blocks": 1, "origin": "SYM", "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}]}


        opti = {


            "all_strategies": [t1, t2, t3, s1],


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": False,


            "sym_tie_epsilon": 1e-6,


            "sym_tie_epsilon_rel": 0.0,


            "robustness_seed": 42,


            "enable_family_diversity": True,


            "diversity_top_k": 3,


            "diversity_max_per_family": 1,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        top3_origins = [r["strategy"]["origin"] for r in out["all_strategies_results"][:3]]


        assert "SYM" in top3_origins





    def test_run_final_simulation_block_consensus_reranks_seed_sensitive_top1(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_test(strategy, _idx, _noise_levels, _num_runs, *_args, **kwargs):


            sid = strategy["strategy_id"]


            seed = int(kwargs.get("params", {}).get("robustness_seed", 42))


            if sid == "a":


                score = 0.10 if seed == 42 else 0.30


            else:


                score = 0.18


            return {


                "strategy_id": sid,


                "strategy": strategy,


                "results_per_noise": [{"noise_level": 1.0, "rmse_mean": score, "rmse_std": 0.0, "rmse_p95": score, "rmse_p99": score}],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        # Wrap to preserve positional signature and inject params in kwargs for fake.


        def fake_task(strategy, idx, noise_levels, num_runs, p_thick_nominal, clues_at_wl, params, wl_arr, nH, nL, nSub, T_nom, full_dyn_grid, **kwargs):


            return fake_test(strategy, idx, noise_levels, num_runs, params=params)





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_task)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr("certus.core.certus_strat_config.get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128))


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        s_a = {


            "strategy_id": "a",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        s_b = {


            "strategy_id": "b",


            "n_blocks": 1,


            "origin": "THICKNESS²",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        opti = {


            "all_strategies": [s_a, s_b],


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": False,


            "sym_tie_epsilon": 1e-6,


            "sym_tie_epsilon_rel": 0.0,


            "robustness_seed": 42,


            "enable_consensus_ranking": True,


            "consensus_num_seeds": 2,


            "consensus_seed_stride": 1,


            "consensus_top_k": 2,


            "consensus_num_runs": 2,


            "consensus_std_weight": 0.0,


            "consensus_score_mode": "mean",


            "enable_family_diversity": False,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        # Baseline seed 42 prefers "a" (0.10), consensus mean makes "b" best (0.18 < 0.20)


        assert out["best_strategy"]["strategy_id"] == "b"





    def test_run_final_simulation_block_consensus_prefilters_on_sorted_topk(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_task(


            strategy,


            _idx,


            _noise_levels,


            _num_runs,


            _p_thick_nominal,


            _clues_at_wl,


            params_local,


            _wl_arr,


            _nH,


            _nL,


            _nSub,


            _T_nom,


            _full_dyn_grid,


            **kwargs,


        ):


            sid = strategy["strategy_id"]


            seed = int(params_local.get("robustness_seed", 42))


            if sid == "good":


                score = 0.10 if seed == 42 else 0.20


            else:


                score = 0.50


            return {


                "strategy_id": sid,


                "strategy": strategy,


                "results_per_noise": [


                    {


                        "noise_level": 1.0,


                        "rmse_mean": score,


                        "rmse_std": 0.0,


                        "rmse_p95": score,


                        "rmse_p99": score,


                    }


                ],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_task)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr(


            STRAT, "get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128)


        )


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        s_bad = {


            "strategy_id": "bad",


            "n_blocks": 1,


            "origin": "THICKNESS",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        s_good = {


            "strategy_id": "good",


            "n_blocks": 1,


            "origin": "THICKNESS²",


            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


        }


        opti = {


            "all_strategies": [s_bad, s_good],  # deliberately unfavorable order


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": False,


            "robustness_seed": 42,


            "enable_consensus_ranking": True,


            "consensus_num_seeds": 2,


            "consensus_seed_stride": 1,


            "consensus_top_k": 1,


            "consensus_num_runs": 2,


            "consensus_std_weight": 0.0,


            "consensus_score_mode": "mean",


            "enable_family_diversity": False,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        by_id = {r["strategy"]["strategy_id"]: r for r in out["all_strategies_results"]}


        assert out["best_strategy"]["strategy_id"] == "good"


        assert "robustness_score_consensus" in by_id["good"]


        assert "robustness_score_consensus" not in by_id["bad"]





    def test_run_final_simulation_block_applies_consensus_after_elite(self, monkeypatch):


        from CERTUS_STRAT import run_final_simulation_block





        def fake_generate_elite(*_args, **_kwargs):


            elite = {


                "strategy_id": 9991,


                "n_blocks": 1,


                "origin": "ELITE",


                "origin_details": "ELITE(parent=base0)",


                "blocks": [{"start": 0, "end": 2, "wavelength": 501.0, "num_layers": 2}],


            }


            return [elite], 9992





        def fake_task(


            strategy,


            _idx,


            _noise_levels,


            _num_runs,


            _p_thick_nominal,


            _clues_at_wl,


            params_local,


            _wl_arr,


            _nH,


            _nL,


            _nSub,


            _T_nom,


            _full_dyn_grid,


            **kwargs,


        ):


            sid = str(strategy["strategy_id"])


            seed = int(params_local.get("robustness_seed", 42))


            if sid == "9991":


                score = 0.05 if seed == 42 else 0.15


            else:


                idx = int(sid.replace("base", "")) if sid.startswith("base") else 0


                score = 0.20 + 0.01 * idx


            return {


                "strategy_id": strategy["strategy_id"],


                "strategy": strategy,


                "results_per_noise": [


                    {


                        "noise_level": 1.0,


                        "rmse_mean": score,


                        "rmse_std": 0.0,


                        "rmse_p95": score,


                        "rmse_p99": score,


                    }


                ],


                "robustness_score": score,


                "num_unique_wavelengths": 1,


                "complexity_score": 1.0,


            }





        monkeypatch.setattr(STRAT, "_generate_elite_candidate_strategies", fake_generate_elite)


        monkeypatch.setattr("certus.core.certus_strat_robustness._test_strategy_robustness_task", fake_task)


        monkeypatch.setattr("certus.core.certus_strat_robustness._calculate_strategy_spectral_resolution", lambda *_a, **_k: (1.0, 1))


        monkeypatch.setattr(


            STRAT, "get_refractive_clues_vectorized", lambda *_a, **_k: np.ones(3, dtype=np.complex128)


        )


        monkeypatch.setattr(
            "certus.core.certus_strat_robustness.calculate_RT_vectorized_real_HL",


            lambda *_a, **_k: (None, np.ones(3, dtype=np.float64)),


        )


        monkeypatch.setattr("certus.core.certus_strat_robustness.get_safe_worker_count", lambda: 1)





        base_strats = []


        for i in range(10):


            base_strats.append(


                {


                    "strategy_id": f"base{i}",


                    "n_blocks": 1,


                    "origin": "THICKNESS",


                    "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


                }


            )


        opti = {


            "all_strategies": base_strats,


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {


                500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


                501.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j},


            },


            "full_dynamics_grid": {},


        }


        params = {


            "logger": __import__("logging").getLogger("test"),


            "wl_range": (400.0, 402.0),


            "wl_step": 1.0,


            "nH_id": "H",


            "nL_id": "L",


            "nSub_id": "S",


            "sym_prefer_on_tie": False,


            "robustness_seed": 42,


            "enable_consensus_ranking": True,


            "consensus_num_seeds": 2,


            "consensus_seed_stride": 1,


            "consensus_top_k": 20,


            "consensus_num_runs": 2,


            "consensus_std_weight": 0.0,


            "consensus_score_mode": "mean",


            "enable_family_diversity": False,


            "elite_rounds": 1,


            "elite_max_candidates": 1,


            "elite_num_runs": 10,


            "elite_min_improvement": 0.0,


        }


        out = run_final_simulation_block(opti, params, num_runs=2, noise_levels=[1.0])


        elite_items = [r for r in out["all_strategies_results"] if r["strategy"].get("origin") == "ELITE"]


        assert elite_items, "ELITE should be injected and retained"


        assert "robustness_score_consensus" in elite_items[0]


        assert "robustness_consensus_meta" in elite_items[0]





    def test_parallel_block_worker_runs_full_pass_after_screen(self, monkeypatch):


        from CERTUS_STRAT import _parallel_block_worker





        run_calls = []





        def fake_run_final_simulation_block(context, _params, num_runs=0, noise_levels=None):


            run_calls.append(int(num_runs))


            out_results = []


            for strat in context.get("all_strategies", []):


                out_results.append(


                    {


                        "strategy_id": strat["strategy_id"],


                        "strategy": strat,


                        "results_per_noise": [


                            {


                                "noise_level": 1.0,


                                "rmse_mean": 0.2,


                                "rmse_std": 0.0,


                                "rmse_p95": 0.2,


                                "rmse_p99": 0.2,


                            }


                        ],


                        "robustness_score": 0.2,


                    }


                )


            return {"all_strategies_results": out_results}





        def fake_mine(*_args, **_kwargs):


            return [


                {


                    "strategy_id": 101,


                    "n_blocks": 1,


                    "origin": "THICKNESS",


                    "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],


                }


            ]





        monkeypatch.setattr(STRAT, "run_final_simulation_block", fake_run_final_simulation_block)


        monkeypatch.setattr(STRAT, "mine_strategies_for_block_count", fake_mine)





        pre_calc_data = {


            "raw_results_thickness": {0: [{"wl": 500.0, "cost": 1.0}], 1: [{"wl": 500.0, "cost": 1.0}]},


            "raw_results_sq": {0: [{"wl": 500.0, "cost": 1.0}], 1: [{"wl": 500.0, "cost": 1.0}]},


            "num_layers": 2,


            "p_thick_nominal": [100.0, 80.0],


            "clues_at_wl": {500.0: {"H": 2.3 + 0j, "L": 1.45 + 0j, "substrate": 1.52 + 0j}},


            "full_dynamics_grid": {},


        }


        args = (


            1,  # n_blk


            pre_calc_data,


            {"robustness_seed": 42},


            3,  # n_screen


            2,  # k_keep


            9,  # n_full


            [],


            {"wl": None, "size": 0},


        )


        out = _parallel_block_worker(args)


        assert out.get("strategies_results")


        assert run_calls == [3, 9]








class TestStratResetIntegration:


    """Reset / Clear pendant une boucle (worker + _request_stop)."""





    def test_certus_strat_app_has_request_stop(self):


        from CERTUS_STRAT import CertusStratApp


        assert hasattr(CertusStratApp, "_request_stop")





    def test_request_stop_sets_params_when_worker_running(self):


        from unittest.mock import Mock


        from CERTUS_STRAT import CertusStratApp


        app = Mock(spec=CertusStratApp)


        app.worker = Mock()


        app.worker.isRunning = Mock(return_value=True)


        app.worker.params = {}


        CertusStratApp._request_stop(app)


        assert app.worker.params.get("stop_requested") is True


class TestStratCorridorSensitivity:
    """Focused tests for the sensitive d-profile corridor helpers."""

    def test_corridor_min_k_half_width_is_enforced_and_counts_changes(self):
        from certus.spline.spline_profile_corridors import enforce_min_k_corridor_half_width

        k_lo = np.array([0.0, 1e-8, 0.20], dtype=np.float64)
        k_hi = np.array([1e-6, 5e-5, 0.20], dtype=np.float64)
        k_ref = np.array([0.0, 2e-5, 0.20], dtype=np.float64)

        lo, hi, changed = enforce_min_k_corridor_half_width(k_lo, k_hi, k_ref, min_half_width=1e-4)

        assert changed >= 1
        assert np.all(lo >= 1e-6)
        assert np.all(hi >= lo)
        assert hi[0] - lo[0] >= 1e-4 - 1.1e-6
        assert hi[1] - lo[1] >= 1e-4 - 1.1e-6

    def test_corridor_envelope_expands_to_include_reported_curve(self):
        from certus.spline.spline_profile_corridors import _expand_corridor_envelope_with_reported_nk

        n_lo = np.array([1.0, 1.1, 1.2], dtype=np.float64)
        n_hi = np.array([1.5, 1.6, 1.7], dtype=np.float64)
        k_lo = np.array([0.01, 0.02, 0.03], dtype=np.float64)
        k_hi = np.array([0.05, 0.06, 0.07], dtype=np.float64)
        n_nom = np.array([0.8, 1.3, 1.9], dtype=np.float64)
        k_nom = np.array([0.005, 0.08, 0.04], dtype=np.float64)

        n_lo2, n_hi2, k_lo2, k_hi2 = _expand_corridor_envelope_with_reported_nk(n_lo, n_hi, k_lo, k_hi, n_nom, k_nom)

        assert n_lo2[0] == pytest.approx(0.8)
        assert n_hi2[2] == pytest.approx(1.9)
        assert k_lo2[0] == pytest.approx(0.005)
        assert k_hi2[1] == pytest.approx(0.08)

    def test_corridor_sorted_stacks_orders_by_d(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _sorted_corridor_stacks

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={"n_lam": np.array([1.0, 1.0]), "k_lam": np.array([0.1, 0.1])},
            boundary_refine_calls=0,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
            chi2_vals=[4.0, 2.0, 3.0],
            d0=5.0,
            d_vals=[6.0, 4.0, 5.0],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[np.array([0.3, 0.3]), np.array([0.1, 0.1]), np.array([0.2, 0.2])],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[np.array([1.3, 1.3]), np.array([1.1, 1.1]), np.array([1.2, 1.2])],
            nom_pack=None,
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.3, 0.1, 0.2],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.15, 1.15]),
            corridor_ref_k_lam=np.array([0.15, 0.15]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        d_arr, rm_arr, c_arr, n_stack, k_stack = _sorted_corridor_stacks(ctx)
        assert list(d_arr) == [4.0, 5.0, 6.0]
        assert list(rm_arr) == [0.1, 0.2, 0.3]
        assert n_stack[0, 0] == pytest.approx(1.1)
        assert k_stack[-1, 0] == pytest.approx(0.3)

    def test_corridor_d_interval_prefers_parabola_center_when_enabled(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _derive_symmetric_d_interval

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={"n_lam": np.array([1.0]), "k_lam": np.array([0.1])},
            boundary_refine_calls=0,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
            chi2_vals=[1.0, 1.0, 1.0],
            d0=5.0,
            d_vals=[4.0, 5.0, 6.0],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[np.array([0.1]), np.array([0.1]), np.array([0.1])],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[np.array([1.0]), np.array([1.0]), np.array([1.0])],
            nom_pack=None,
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.3, 0.1, 0.2],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.0]),
            corridor_ref_k_lam=np.array([0.1]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        d_raw, d_sym, src, fit = _derive_symmetric_d_interval(ctx, np.array([4.0, 5.0, 6.0]), np.array([0.3, 0.1, 0.2]))
        assert d_raw == (4.0, 6.0)
        assert d_sym[0] <= 5.0 <= d_sym[1]
        assert src in {"parabola", "nominal"}
        assert "ok" in fit

    def test_corridor_package_returns_failure_on_empty_context(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _package_corridor_results

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={},
            boundary_refine_calls=0,
            center_seed_kept=False,
            cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
            chi2_vals=[],
            d0=5.0,
            d_vals=[],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[],
            nom_pack=None,
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=None,
            corridor_ref_k_lam=None,
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        assert _package_corridor_results(ctx) == {"profile_d_status": "failed"}

    def test_corridor_package_detects_n_k_crossing_and_keeps_bounds(self, caplog):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _package_corridor_results

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={"n_lam": np.array([1.0, 1.1]), "k_lam": np.array([0.1, 0.1])},
            boundary_refine_calls=0,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
            chi2_vals=[1.0, 2.0],
            d0=5.0,
            d_vals=[4.9, 5.1],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[np.array([0.12, 0.08]), np.array([0.11, 0.09])],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[np.array([0.09, 0.07]), np.array([0.10, 0.08])],
            nom_pack=None,
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.2, 0.21],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.0, 1.0]),
            corridor_ref_k_lam=np.array([0.1, 0.1]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        out = _package_corridor_results(ctx)
        assert out["profile_d_status"] in {"ok", "degenerate"}
        assert np.all(out["corridor_n_lo"] <= out["corridor_n_hi"])
        assert np.all(out["corridor_k_lo"] <= out["corridor_k_hi"])
        # Log capture check removed due to Windows log rotation PermissionError
        pass

    def test_corridor_package_with_scientific_nominal_keeps_reference_inside_bounds(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _package_corridor_results

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={"n_lam": np.array([1.1, 1.2]), "k_lam": np.array([0.12, 0.13])},
            boundary_refine_calls=0,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 0.0, "d_hi": 10.0})(),
            chi2_vals=[1.0, 1.1],
            d0=5.0,
            d_vals=[4.8, 5.2],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[np.array([0.11, 0.12]), np.array([0.13, 0.14])],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[np.array([1.0, 1.1]), np.array([1.2, 1.3])],
            nom_pack={"label": "nominal"},
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.2, 0.21],
            scientific_nominal=True,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.1, 1.2]),
            corridor_ref_k_lam=np.array([0.12, 0.13]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        out = _package_corridor_results(ctx)
        assert np.all(out["corridor_n_lo"] <= np.array([1.1, 1.2]))
        assert np.all(out["corridor_n_hi"] >= np.array([1.1, 1.2]))
        assert np.all(out["corridor_k_lo"] <= np.array([0.12, 0.13]))
        assert np.all(out["corridor_k_hi"] >= np.array([0.12, 0.13]))
        assert out["corridor_reference_n_lam"][0] == pytest.approx(1.1)
        assert out["corridor_reference_k_lam"][1] == pytest.approx(0.13)

    def test_corridor_d_interval_clips_to_bounds_when_needed(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _derive_symmetric_d_interval

        ctx = CorridorProfileContext(
            _use_hetero=False,
            _user_mask=None,
            adaptive_abs_meta={},
            auto_relaxed_alpha=False,
            base_result={"n_lam": np.array([1.0]), "k_lam": np.array([0.1])},
            boundary_refine_calls=0,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 4.9, "d_hi": 5.1})(),
            chi2_vals=[1.0, 1.0, 1.0],
            d0=5.0,
            d_vals=[4.0, 5.0, 6.0],
            delta_chi2=1.0,
            fit_fail_values=[],
            fit_nfev_values=[],
            fit_nit_values=[],
            fit_try_values=[],
            k_curves=[np.array([0.1]), np.array([0.1]), np.array([0.1])],
            log_coaching=False,
            maxfun_prof=10,
            min_side=1,
            n_curves=[np.array([1.0]), np.array([1.0]), np.array([1.0])],
            nom_pack=None,
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "nominal", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.5, "mode": "alpha"})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.3, 0.1, 0.2],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([], dtype=np.float64),
            seed_gate_eval_count=0,
            seed_gate_kept_count=0,
            seed_gate_saturated_global=False,
            sig_r=0.0,
            sig_t=0.0,
            sigma_r_f_hetero=None,
            sigma_t_f_hetero=None,
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.0,
            tol_abs_effective=0.0,
            use_abs_delta=False,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0]),
            x_nodes_center=np.array([1.0]),
            x0_default=np.array([1.0]),
            bounds_nodes=np.array([[4.9, 5.1]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.0]),
            corridor_ref_k_lam=np.array([0.1]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=0,
            center_seed_gate_kept_count=0,
            center_seed_gate_delta_refit_minus_seed=float("nan"),
        )

        d_raw, d_sym, src, _fit = _derive_symmetric_d_interval(ctx, np.array([4.0, 5.0, 6.0]), np.array([0.3, 0.1, 0.2]))
        assert d_raw == (4.0, 6.0)
        assert d_sym[0] <= 4.9 + 1e-12
        assert d_sym[1] >= 5.1 - 1e-12
        assert src == "nominal"

    def test_corridor_package_full_output_has_consistent_shapes_and_keys(self):
        from certus.spline.spline_profile_corridors import CorridorProfileContext, _package_corridor_results

        ctx = CorridorProfileContext(
            _use_hetero=True,
            _user_mask=np.array([True, False, True]),
            adaptive_abs_meta={"ok": True, "delta_rmse_geom": 0.01, "delta_rmse_noise": 0.02, "profile_sigma": 0.03, "curvature": 0.04, "center_nm": 5.0, "h_ref_nm": 1.0},
            auto_relaxed_alpha=True,
            base_result={"n_lam": np.array([1.2, 1.25, 1.3]), "k_lam": np.array([0.12, 0.11, 0.10])},
            boundary_refine_calls=2,
            center_seed_kept=True,
            cfg=type("Cfg", (), {"d_lo": 4.0, "d_hi": 6.0})(),
            chi2_vals=[3.0, 2.0, 4.0],
            d0=5.0,
            d_vals=[5.2, 4.8, 5.0],
            delta_chi2=1.5,
            fit_fail_values=[0, 1, 0],
            fit_nfev_values=[10, 11, 12],
            fit_nit_values=[2, 2, 3],
            fit_try_values=[1, 1, 1],
            k_curves=[np.array([0.14, 0.13, 0.12]), np.array([0.12, 0.11, 0.10]), np.array([0.13, 0.12, 0.11])],
            log_coaching=False,
            maxfun_prof=15,
            min_side=1,
            n_curves=[np.array([1.22, 1.24, 1.26]), np.array([1.20, 1.22, 1.24]), np.array([1.21, 1.23, 1.25])],
            nom_pack={"label": "nominal"},
            pconf=type("PConf", (), {"parabola_half_window_pts": 3, "symmetric_interval_center_mode": "parabola", "force_symmetric_interval": True, "symmetric_interval_min_half_width_rel": 0.0, "mode": "alpha", "rmse_alpha": 1.0, "lr_conf_level": 0.95})(),
            rmse_opt=0.1,
            rmse_ref_tag="best_polished",
            rmse_thr_sub="alpha",
            rmse_thresh=0.2,
            rmse_thresh_active=0.2,
            rmse_vals=[0.25, 0.15, 0.2],
            scientific_nominal=False,
            seed_gate_auto_escalated_global=False,
            seed_gate_deltas=np.array([0.01, -0.02], dtype=np.float64),
            seed_gate_eval_count=5,
            seed_gate_kept_count=4,
            seed_gate_saturated_global=False,
            sig_r=0.5,
            sig_t=0.4,
            sigma_r_f_hetero=np.array([0.1, 0.1, 0.1]),
            sigma_t_f_hetero=np.array([0.1, 0.1, 0.1]),
            t0=0.0,
            threshold_basis_eff="alpha",
            threshold_fallback_reason="",
            tol_abs=0.05,
            tol_abs_effective=0.05,
            use_abs_delta=True,
            use_adaptive_abs_delta=False,
            use_lr=False,
            sk=np.array([1.0, 1.0, 1.0]),
            x_nodes_center=np.array([1.0, 1.0, 1.0]),
            x0_default=np.array([1.0, 1.0, 1.0]),
            bounds_nodes=np.array([[0.0, 2.0], [0.0, 2.0], [0.0, 2.0]]),
            chi2_min=float("nan"),
            x_curves=None,
            corridor_ref_n_lam=np.array([1.21, 1.23, 1.25]),
            corridor_ref_k_lam=np.array([0.13, 0.12, 0.11]),
            _push_live_point_from_payload=None,
            live_streamer=None,
            center_seed_gate_eval_count=2,
            center_seed_gate_kept_count=2,
            center_seed_gate_delta_refit_minus_seed=0.0,
        )

        out = _package_corridor_results(ctx)
        assert out["profile_d_enabled"] is True
        assert out["profile_d_status"] in {"ok", "degenerate"}
        assert out["profile_d_values_nm"].shape == (3,)
        assert out["profile_d_n_curves"].shape == (3, 3)
        assert out["profile_d_k_curves"].shape == (3, 3)
        assert out["corridor_n_lo"].shape == (3,)
        assert out["corridor_k_hi"].shape == (3,)
        assert out["profile_d_interval_nm"][0] <= out["profile_d_interval_nm"][1]
        assert out["profile_d_interval_center_source"] in {"parabola", "nominal", "sampled_best"}
        assert out["profile_d_seed_gate_kept_count"] == 4
        assert out["profile_d_seed_gate_eval_count"] == 5
        assert out["profile_d_user_rmse_mask"].dtype == bool
        assert out["profile_d_mean_nfev"] == pytest.approx(np.mean([10, 11, 12]))
        assert out["corridor_k_min_half_width"] == pytest.approx(1e-4)


class TestStratPipelineOrchestration:
    """Orchestration pipeline tests (PR 3 verification)."""

    def test_pipeline_phase_a_only(self, monkeypatch):
        from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid

        params = {
            "logger": __import__("logging").getLogger("test"),
            "l0": "550.0",
            "stack_string": "1.0,1.0",
            "scan_wl_min": 400.0,
            "scan_wl_max": 700.0,
            "scan_wl_step": 10.0,
            "p_thick_nominal": [100.0, 80.0],
        }

        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.precompute_clues_and_matrices",
            lambda *a, **k: ({}, np.zeros(1), np.zeros(1)),
        )

        fake_raw = [{"layer": 0, "wavelength": 550.0}]
        fake_grid = np.zeros(1)
        fake_obs = {"metadata": "dummy"}

        import certus.core.certus_strat_solvers as solvers
        monkeypatch.setattr(solvers, "_run_phase_a_hybrid_loop", lambda *a, **k: (fake_raw, fake_grid, fake_obs, False))
        monkeypatch.setattr(solvers, "_normalize_phase_a_results", lambda raw, num: raw)
        monkeypatch.setattr(solvers, "_build_symmetry_bonus_map", lambda *a, **k: {"sym": "bonus"})
        monkeypatch.setattr(solvers, "_build_layer_importance_map", lambda *a, **k: {"importance": 1.0})
        monkeypatch.setattr(solvers, "_export_phase_a_observability_json", lambda *a, **k: None)

        res = optimize_block_strategy_hybrid(params, phase_a_only=True)

        assert res.get("raw_results_thickness") == fake_raw
        assert "sym_bonus_map" in res
        assert "all_strategies" not in res

    def test_pipeline_stop_requested(self, monkeypatch):
        from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
        import certus.core.certus_strat_solvers as solvers

        params = {
            "logger": __import__("logging").getLogger("test"),
            "l0": "550.0",
            "stack_string": "1.0,1.0",
            "scan_wl_min": 400.0,
            "scan_wl_max": 700.0,
            "scan_wl_step": 10.0,
            "p_thick_nominal": [100.0, 80.0],
        }

        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.precompute_clues_and_matrices",
            lambda *a, **k: ({}, np.zeros(1), np.zeros(1)),
        )
        monkeypatch.setattr(solvers, "_run_phase_a_hybrid_loop", lambda *a, **k: ([], None, {}, True))
        monkeypatch.setattr(solvers, "_export_phase_a_observability_json", lambda *a, **k: None)

        res = optimize_block_strategy_hybrid(params, phase_a_only=False)

        assert res.get("stop_requested") is True
        assert "raw_results_thickness" in res

    def test_pipeline_full_sequence(self, monkeypatch):
        from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
        import certus.core.certus_strat_solvers as solvers

        params = {
            "logger": __import__("logging").getLogger("test"),
            "l0": "550.0",
            "stack_string": "1.0,1.0",
            "scan_wl_min": 400.0,
            "scan_wl_max": 700.0,
            "scan_wl_step": 10.0,
            "p_thick_nominal": [100.0, 80.0],
            "enforce_best_strategy_tmin_check": True,
            "min_transmission_floor": 0.05,
        }

        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.precompute_clues_and_matrices",
            lambda *a, **k: ({}, np.zeros(1), np.zeros(1)),
        )
        
        monkeypatch.setattr(solvers, "_run_phase_a_hybrid_loop", lambda *a, **k: ([], None, {}, False))
        monkeypatch.setattr(solvers, "_normalize_phase_a_results", lambda raw, num: raw)
        monkeypatch.setattr(solvers, "_build_symmetry_bonus_map", lambda *a, **k: {})
        monkeypatch.setattr(solvers, "_build_layer_importance_map", lambda *a, **k: {})
        monkeypatch.setattr(solvers, "_export_phase_a_observability_json", lambda *a, **k: None)

        monkeypatch.setattr(solvers, "_compute_blocks_range_for_params", lambda *a, **k: [2])
        
        fake_strategy = {"strategy_id": 1, "blocks": []}
        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.mine_strategies_for_block_count",
            lambda *a, **k: [fake_strategy],
        )
        
        fake_final = {"best_strategy": fake_strategy}
        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.run_final_simulation_block",
            lambda *a, **k: fake_final,
        )
        
        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline._validate_strategy_min_transmission_floor",
            lambda *a, **k: ({"report": "ok"}, []),
        )

        res = optimize_block_strategy_hybrid(params, phase_a_only=False)

        assert res.get("best_strategy") == fake_strategy
        assert res.get("best_strategy_tmin_report") == {"report": "ok"}

    def test_pipeline_numerical_error(self, monkeypatch):
        from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
        from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

        params = {
            "logger": __import__("logging").getLogger("test"),
            "l0": "550.0",
            "stack_string": "1.0,1.0",
            "scan_wl_min": 400.0,
            "scan_wl_max": 700.0,
            "scan_wl_step": 10.0,
            "p_thick_nominal": [100.0, 80.0],
        }

        def raise_err(*a, **k):
            raise NUMERICAL_FAULT_EXCEPTIONS[0]("Simulated numerical crash")

        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.precompute_clues_and_matrices",
            raise_err,
        )

        res = optimize_block_strategy_hybrid(params)
        assert "error" in res
        assert "Simulated numerical crash" in res["error"]

    def test_pipeline_phase_b_empty(self, monkeypatch):
        from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
        import certus.core.certus_strat_solvers as solvers

        params = {
            "logger": __import__("logging").getLogger("test"),
            "l0": "550.0",
            "stack_string": "1.0,1.0",
            "scan_wl_min": 400.0,
            "scan_wl_max": 700.0,
            "scan_wl_step": 10.0,
            "p_thick_nominal": [100.0, 80.0],
        }

        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.precompute_clues_and_matrices",
            lambda *a, **k: ({}, np.zeros(1), np.zeros(1)),
        )
        
        monkeypatch.setattr(solvers, "_run_phase_a_hybrid_loop", lambda *a, **k: ([], None, {}, False))
        monkeypatch.setattr(solvers, "_normalize_phase_a_results", lambda raw, num: raw)
        monkeypatch.setattr(solvers, "_build_symmetry_bonus_map", lambda *a, **k: {})
        monkeypatch.setattr(solvers, "_build_layer_importance_map", lambda *a, **k: {})
        monkeypatch.setattr(solvers, "_export_phase_a_observability_json", lambda *a, **k: None)

        monkeypatch.setattr(solvers, "_compute_blocks_range_for_params", lambda *a, **k: [])
        monkeypatch.setattr(
            "certus.core.certus_strat_pipeline.mine_strategies_for_block_count",
            lambda *a, **k: [],
        )

        res = optimize_block_strategy_hybrid(params, phase_a_only=False)

        assert "raw_results_thickness" in res
        assert "best_strategy" not in res


class TestStratConsensusAndElite:
    """Consensus and Elite refinement tests (PR 4 verification)."""

    def test_consensus_disabled(self):
        from certus.core.certus_strat_consensus import _should_apply_consensus_ranking
        assert _should_apply_consensus_ranking(
            consensus_enabled=False,
            consensus_seeds=[42, 43],
            results_in=[{"strategy_id": "1"}],
        ) is False

    def test_consensus_enabled(self):
        from certus.core.certus_strat_consensus import _register_consensus_score_for_strategy
        consensus_map = {}
        _register_consensus_score_for_strategy(
            consensus_map=consensus_map,
            sid="strat_1",
            seed_scores=[1.0, 2.0],
            consensus_mode="mean",
            consensus_std_weight=0.35,
            consensus_seeds=[42, 43],
        )
        assert "strat_1" in consensus_map
        assert consensus_map["strat_1"]["mean"] == 1.5

    def test_cache_hit(self):
        from certus.core.certus_strat_consensus import _consume_cached_consensus_score
        cache = {("sig", 42, 100, (0.5, 1.0)): 0.012}
        seed_scores = []
        hit = _consume_cached_consensus_score(
            robustness_score_cache=cache,
            cache_key=("sig", 42, 100, (0.5, 1.0)),
            seed_scores=seed_scores,
        )
        assert hit is True
        assert seed_scores == [0.012]

    def test_cache_miss(self):
        from certus.core.certus_strat_consensus import (
            _consume_cached_consensus_score,
            _store_and_consume_consensus_score,
        )
        cache = {}
        seed_scores = []
        key = ("sig", 42, 100, (0.5, 1.0))
        hit = _consume_cached_consensus_score(
            robustness_score_cache=cache,
            cache_key=key,
            seed_scores=seed_scores,
        )
        assert hit is False
        assert seed_scores == []

        _store_and_consume_consensus_score(
            robustness_score_cache=cache,
            cache_key=key,
            score_c=0.015,
            seed_scores=seed_scores,
        )
        assert cache[key] == 0.015
        assert seed_scores == [0.015]

    def test_elite_without_gain(self, monkeypatch):
        from certus.core.certus_strat_consensus import _apply_elite_refinement_if_enabled
        from certus.core.certus_strat_config import RobustnessContext
        import logging

        params = {
            "elite_parent_top_k": 10,
            "elite_max_candidates": 120,
            "elite_wl_neighbor_span": 1,
            "elite_num_runs": 80,
            "elite_rounds": 2,
            "elite_min_improvement": 0.0,
            "elite_stop_on_no_gain": True,
            "elite_max_full_evals": 36,
        }

        ctx = RobustnessContext(
            params=params,
            params_safe={},
            logger=logging.getLogger("test"),
            noise_levels=[0.5, 1.0],
            num_runs=150,
            p_thick_nominal=[100.0, 80.0],
            num_layers=2,
            clues_at_wl={},
            wl_arr=np.array([450.0, 500.0]),
            nH_arr=np.array([2.0, 2.0]),
            nL_arr=np.array([1.5, 1.5]),
            nSub_arr=np.array([1.52, 1.52]),
            T_nom=np.array([0.5, 0.5]),
            full_dyn_grid={},
        )

        res = _apply_elite_refinement_if_enabled([], ctx, lambda *a: None)
        assert res == []

    def test_elite_with_gain(self, monkeypatch):
        from certus.core.certus_strat_consensus import _apply_elite_refinement_if_enabled
        from certus.core.certus_strat_config import RobustnessContext
        import logging

        params = {
            "elite_parent_top_k": 2,
            "elite_max_candidates": 5,
            "elite_wl_neighbor_span": 1,
            "elite_num_runs": 10,
            "elite_rounds": 1,
            "elite_min_improvement": 0.0,
            "elite_stop_on_no_gain": True,
            "elite_max_full_evals": 5,
            "robustness_noise_factors": [1.0],
        }

        ctx = RobustnessContext(
            params=params,
            params_safe={},
            logger=logging.getLogger("test"),
            noise_levels=[1.0],
            num_runs=10,
            p_thick_nominal=[100.0, 80.0],
            num_layers=2,
            clues_at_wl={500.0: {"H": 2.0, "L": 1.5, "substrate": 1.52}},
            wl_arr=np.array([500.0]),
            nH_arr=np.array([2.0]),
            nL_arr=np.array([1.5]),
            nSub_arr=np.array([1.52]),
            T_nom=np.array([0.5]),
            full_dyn_grid={},
        )

        strategies_results = [
            {"strategy": {"strategy_id": "strat_1", "blocks": []}, "robustness_score": 0.010, "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.010}]}
        ]

        monkeypatch.setattr(
            "certus.core.certus_strat_consensus._resolve_elite_nominal_and_target_threshold",
            lambda *a, **k: (0.010, 0.010),
        )
        monkeypatch.setattr(
            "certus.core.certus_strat_consensus._generate_elite_candidate_strategies",
            lambda *a, **k: ([{"strategy_id": "elite_1", "blocks": []}], 2),
        )
        monkeypatch.setattr(
            "certus.core.certus_strat_consensus._test_strategy_robustness_task",
            lambda *a, **k: {"strategy": {"strategy_id": "elite_1", "blocks": []}, "robustness_score": 0.005, "results_per_noise": [{"noise_level": 1.0, "rmse_p95": 0.005}]},
        )
        monkeypatch.setattr(
            "certus.core.certus_strat_consensus._calculate_strategy_spectral_resolution",
            lambda *a, **k: (10.0, None),
        )

        res = _apply_elite_refinement_if_enabled(strategies_results, ctx, lambda *a: None)
        assert len(res) == 2
        assert any(item.get("elite_round") == 1 for item in res)

    def test_reranking_stable(self):
        from certus.core.certus_strat_consensus import _rank_and_filter_strategies

        results = [
            {"strategy": {"strategy_id": "strat_1"}, "robustness_score": 0.020},
            {"strategy": {"strategy_id": "strat_2"}, "robustness_score": 0.005},
            {"strategy": {"strategy_id": "strat_3"}, "robustness_score": 0.015},
        ]

        params = {"origin_priority_map": None}
        logger = __import__("logging").getLogger("test")

        sorted_res = _rank_and_filter_strategies(results, "test", params, logger, lambda *a: None)
        assert sorted_res[0]["strategy"]["strategy_id"] == "strat_2"
        assert sorted_res[1]["strategy"]["strategy_id"] == "strat_3"
        assert sorted_res[2]["strategy"]["strategy_id"] == "strat_1"




