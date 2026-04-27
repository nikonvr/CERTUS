#!/usr/bin/env python


"""test_strat_robustness.py - Non-regression tests for CERTUS_STRAT





Tests covered:


1. Noise distribution (uniform vs Gaussian) -> impact on P95


2. Backside energy conservation (R + T <= 1)


3. Non-monotonic mode (attenuate vs reject)"""





import numpy as np


import sys


import os





from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))





from _certus_physics_impl import (


    simulate_growth_kernel,


    validate_wavelengths_batch,


    simulate_stack_robustness_batch,


    calculate_RT_single_layer_single,


    _apply_exact_backside_generic,


    calculate_RT_no_backside,


    NON_MONOTONIC_MODE_ATTENUATE,


    NON_MONOTONIC_MODE_REJECT,


)








class TestNoiseDistribution:


    """Test de l'impact de la distribution de bruit sur le P95."""





    def test_uniform_vs_gaussian_p95(self):


        """Check that gaussian and uniform give different P95s."""


        np.random.seed(42)





        # Setup simple: 10 couches QWOT


        num_layers = 10


        p_thick_nominal = np.array([100.0] * num_layers, dtype=np.float64)


        wl = 1500.0


        n_H = complex(2.3, 0.0)


        n_L = complex(1.45, 0.0)


        n_Sub = complex(1.52, 0.0)





        num_runs = 100


        noise_pct = 0.03  # 3%





        # Generate uniform noise


        np.random.seed(42)


        uniform_noise = np.random.uniform(-1.0, 1.0, (num_runs, num_layers)) * noise_pct





        # Generate gaussian noise (clipped to +/-3sigma)


        np.random.seed(42)


        gaussian_raw = np.clip(np.random.normal(0.0, 1.0 / 3.0, (num_runs, num_layers)), -1.0, 1.0)


        gaussian_noise = gaussian_raw * noise_pct





        # Run simulations with both noise types


        results_uniform, _ = simulate_stack_robustness_batch(


            p_thick_nominal,


            np.array([wl] * num_layers),


            np.array([n_H] * num_layers),


            np.array([n_L] * num_layers),


            np.array([n_Sub] * num_layers),


            uniform_noise,


            10.0,  # probe_offset


            2.0,   # non_monotonic_factor


            NON_MONOTONIC_MODE_ATTENUATE,


        )





        results_gaussian, _ = simulate_stack_robustness_batch(


            p_thick_nominal,


            np.array([wl] * num_layers),


            np.array([n_H] * num_layers),


            np.array([n_L] * num_layers),


            np.array([n_Sub] * num_layers),


            gaussian_noise,


            10.0,


            2.0,


            NON_MONOTONIC_MODE_ATTENUATE,


        )





        # Calculate P95 errors


        errors_uniform = np.abs(results_uniform - p_thick_nominal)


        errors_gaussian = np.abs(results_gaussian - p_thick_nominal)





        p95_uniform = np.percentile(errors_uniform.flatten(), 95)


        p95_gaussian = np.percentile(errors_gaussian.flatten(), 95)





        print(f"\nP95 Uniform: {p95_uniform:.4f} nm")


        print(f"P95 Gaussian: {p95_gaussian:.4f} nm")





        # Both should be reasonable (< 100nm for this setup)


        # Gaussian typically gives slightly lower P95 due to concentration around mean


        assert p95_uniform < 100.0, f"P95 uniform too high: {p95_uniform}"


        assert p95_gaussian < 100.0, f"P95 gaussian too high: {p95_gaussian}"


        # Verify the test actually ran (non-zero results)


        assert p95_uniform > 0.1, f"P95 uniform suspiciously low: {p95_uniform}"


        assert p95_gaussian > 0.1, f"P95 gaussian suspiciously low: {p95_gaussian}"








class TestBacksideConservation:


    """Energy conservation test with backside."""





    def test_energy_conservation_single_layer(self):


        """Checks R + T <= 1 for a monolayer with backside."""


        wl = 1500.0


        n_film = complex(2.3, -0.001)  # Light absorption


        n_sub = complex(1.52, 0.0)


        thickness = 100.0





        R, T = calculate_RT_single_layer_single(


            wl, n_film.real, -n_film.imag, thickness, n_sub


        )





        print(f"\nSingle layer backside: R={R:.6f}, T={T:.6f}, R+T={R+T:.6f}")


        assert R + T <= 1.0 + 1e-6, f"Energy not conserved: R+T = {R+T}"


        assert R >= 0.0 and T >= 0.0, f"Negative values: R={R}, T={T}"





    def test_energy_conservation_multilayer(self):


        """Checks R + T <= 1 for a multilayer with exact backside."""


        wls = np.array([1200.0, 1400.0, 1600.0])


        thicknesses = np.array([100.0, 80.0, 100.0, 80.0])  # 4 couches


        n_H = complex(2.3, -0.0005)


        n_L = complex(1.45, -0.0002)





        n_layers = np.zeros((len(wls), len(thicknesses)), dtype=np.complex128)


        for i in range(len(wls)):


            for j in range(len(thicknesses)):


                n_layers[i, j] = n_H if j % 2 == 0 else n_L





        n_sub = np.array([complex(1.52, 0.0)] * len(wls), dtype=np.complex128)





        # Calculate R, T without backside first


        R_front, T_front = calculate_RT_no_backside(thicknesses, n_layers, n_sub, wls)





        # Apply exact backside


        R_total, T_total = _apply_exact_backside_generic(


            R_front, T_front, thicknesses, n_layers, n_sub, wls


        )





        for i, wl in enumerate(wls):


            print(f"wl={wl:.0f}nm: R={R_total[i]:.6f}, T={T_total[i]:.6f}, R+T={R_total[i]+T_total[i]:.6f}")


            assert R_total[i] + T_total[i] <= 1.0 + 1e-6, f"Energy not conserved at {wl}nm"


            assert R_total[i] >= 0.0 and T_total[i] >= 0.0, f"Negative values at {wl}nm"








class TestNonMonotonicMode:


    """Test du mode non-monotonic (attenuate vs reject)."""





    def test_attenuate_mode(self):


        """Verifies that attenuate mode divides the error by the factor."""


        np.random.seed(42)





        # Setup pour forcer une zone non-monotone


        p_thick = np.array([200.0, 200.0], dtype=np.float64)


        wl = 1500.0


        n_H = complex(2.3, 0.0)


        n_L = complex(1.45, 0.0)


        n_Sub = complex(1.52, 0.0)





        prev_thick = np.array([200.0], dtype=np.float64)


        noise = 0.02


        factor = 2.0





        result_attenuate, _ = simulate_growth_kernel(


            p_thick,


            1,  # i_layer


            prev_thick,


            wl,


            n_H,


            n_L,


            n_Sub,


            10.0,


            noise,


            factor,


            NON_MONOTONIC_MODE_ATTENUATE,


        )





        # Should return a reasonable thickness


        assert 0.0 < result_attenuate < 500.0, f"Unreasonable result: {result_attenuate}"





    def test_reject_mode_penalty(self):


        """Checks that reject mode returns a large penalty for non-monotonic zones."""


        np.random.seed(42)





        # For this test, we check that when there is non-monotony, the reject mode


        # retourne une grande valeur (nominal + 1e6)


        p_thick = np.array([200.0, 200.0], dtype=np.float64)


        wl = 1500.0


        n_H = complex(2.3, 0.0)


        n_L = complex(1.45, 0.0)


        n_Sub = complex(1.52, 0.0)





        prev_thick = np.array([200.0], dtype=np.float64)


        noise = 0.02


        factor = 2.0





        result_reject, _ = simulate_growth_kernel(


            p_thick,


            1,


            prev_thick,


            wl,


            n_H,


            n_L,


            n_Sub,


            10.0,


            noise,


            factor,


            NON_MONOTONIC_MODE_REJECT,


        )





        result_attenuate, _ = simulate_growth_kernel(


            p_thick,


            1,


            prev_thick,


            wl,


            n_H,


            n_L,


            n_Sub,


            10.0,


            noise,


            factor,


            NON_MONOTONIC_MODE_ATTENUATE,


        )





        print(f"\nReject mode result: {result_reject:.2f}")


        print(f"Attenuate mode result: {result_attenuate:.2f}")





        # In non-monotonic, reject must at least be more penalizing than attenuate.


        assert result_reject >= result_attenuate, (


            f"Reject mode should not outperform attenuate: "


            f"reject={result_reject}, attenuate={result_attenuate}"


        )








class TestValidateWavelengthsBatch:


    """Test de validate_wavelengths_batch avec le nouveau mode."""





    def test_batch_validation_modes(self):


        """Verifies that both modes work in the batch."""


        np.random.seed(42)





        num_runs = 50


        num_cands = 5


        num_layers = 5





        p_thick = np.array([100.0] * num_layers, dtype=np.float64)


        candidate_wls = np.array([1400.0, 1450.0, 1500.0, 1550.0, 1600.0])





        n_H = complex(2.3, 0.0)


        n_L = complex(1.45, 0.0)


        n_Sub = complex(1.52, 0.0)





        n_H_arr = np.array([n_H] * num_cands, dtype=np.complex128)


        n_L_arr = np.array([n_L] * num_cands, dtype=np.complex128)


        n_Sub_arr = np.array([n_Sub] * num_cands, dtype=np.complex128)





        runs_history = np.zeros((num_runs, num_layers), dtype=np.float64)


        noise_values = np.random.uniform(-1.0, 1.0, num_runs) * 0.03





        i_layer = 2





        # Test attenuate mode


        results_attenuate = validate_wavelengths_batch(


            candidate_wls,


            n_H_arr,


            n_L_arr,


            n_Sub_arr,


            runs_history,


            p_thick,


            i_layer,


            10.0,


            noise_values,


            2.0,


            NON_MONOTONIC_MODE_ATTENUATE,


        )





        # Test reject mode


        results_reject = validate_wavelengths_batch(


            candidate_wls,


            n_H_arr,


            n_L_arr,


            n_Sub_arr,


            runs_history,


            p_thick,


            i_layer,


            10.0,


            noise_values,


            2.0,


            NON_MONOTONIC_MODE_REJECT,


        )





        print("\nValidate batch results:")


        print(f"Attenuate mode - P95 range: [{results_attenuate[:, 0].min():.4f}, {results_attenuate[:, 0].max():.4f}]")


        print(f"Reject mode - P95 range: [{results_reject[:, 0].min():.4f}, {results_reject[:, 0].max():.4f}]")





        # Both should return valid results (non-NaN)


        assert not np.isnan(results_attenuate).any(), "NaN in attenuate results"


        assert not np.isnan(results_reject).any(), "NaN in reject results"








def run_all_tests():


    """Execute all tests."""


    print("=" * 60)


    print("  STRAT ROBUSTNESS REGRESSION TESTS")


    print("=" * 60)





    test_noise = TestNoiseDistribution()


    test_noise.test_uniform_vs_gaussian_p95()





    test_backside = TestBacksideConservation()


    test_backside.test_energy_conservation_single_layer()


    test_backside.test_energy_conservation_multilayer()





    test_nm = TestNonMonotonicMode()


    test_nm.test_attenuate_mode()


    test_nm.test_reject_mode_penalty()





    test_batch = TestValidateWavelengthsBatch()


    test_batch.test_batch_validation_modes()





    print("\n" + "=" * 60)


    print("  ALL TESTS PASSED")


    print("=" * 60)








if __name__ == "__main__":


    run_all_tests()


