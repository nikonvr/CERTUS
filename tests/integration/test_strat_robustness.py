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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))





from certus.core._certus_physics_impl import (


    simulate_growth_kernel,


    validate_wavelengths_batch,


    simulate_stack_robustness_batch,


    _apply_exact_backside_generic,


    calculate_RT_no_backside,


    calculate_transmission_single,


    NON_MONOTONIC_MODE_ATTENUATE,


    NON_MONOTONIC_MODE_REJECT,


)








class TestNoiseDistribution:


    """Test de l'impact de la distribution de bruit sur le P95."""





    def test_uniform_vs_gaussian_p95(self):
        """Uniforme contre gaussienne : la queue de distribution doit se voir.

        🔴 CONFIGURATION CHOISIE POUR ETRE MONITORABLE, et ce n'est pas un detail.

        The old version took 10 layers of 100 nm monitored at 1500 nm with
        3 points de transmission de bruit, soit six fois le bruit nominal du
        example file. In this regime almost all runs are declared
        NON TERMINABLE et le P95 vaut la sentinelle 1e6 : le test ne mesurait plus
        la distribution du bruit, il mesurait un taux de plantage. Il echouait
        by the way on HEAD since commit 932c744.

        We therefore take a quarter-wave stack at 1500 nm monitored at 1300 nm —
        loin des points tournants, la ou la coupure de niveau a de la sensibilite
        — and the actual noise of the example file.
        """
        num_layers = 10
        l0 = 1500.0
        n_H = complex(2.3, 0.0)
        n_L = complex(1.45, 0.0)
        n_Sub = complex(1.52, 0.0)
        p_thick_nominal = np.array(
            [l0 / (4.0 * (2.3 if i % 2 == 0 else 1.45)) for i in range(num_layers)],
            dtype=np.float64,
        )
        wl_monitor = 1300.0
        sigma = 0.001  # 0,1 point de transmission

        rng = np.random.default_rng(42)
        uniform_noise = rng.uniform(-1.0, 1.0, (200, num_layers)) * sigma
        rng = np.random.default_rng(42)
        gaussian_noise = np.clip(rng.normal(0.0, 1.0 / 3.0, (200, num_layers)), -1.0, 1.0) * sigma

        def run(noise):
            sim, _, _, _, _ = simulate_stack_robustness_batch(
                p_thick_nominal,
                np.full(num_layers, wl_monitor),
                np.full(num_layers, n_H),
                np.full(num_layers, n_L),
                np.full(num_layers, n_Sub),
                noise,
                2.0,   # probe_offset
                2.0,   # non_monotonic_factor (sans effet, cf. test dedie)
                NON_MONOTONIC_MODE_ATTENUATE,
            )
            crashed = np.any(sim > 1e5, axis=1)
            completed = sim[~crashed]
            # Le P95 se mesure sur les runs qui se TERMINENT. Y laisser la
            # sentinelle melangerait des nanometres et un compteur d'echecs.
            p95 = float(np.percentile(np.abs(completed - p_thick_nominal), 95)) if completed.size else float("nan")
            return crashed.mean(), p95

        crash_uniform, p95_uniform = run(uniform_noise)
        crash_gaussian, p95_gaussian = run(gaussian_noise)

        print(f"Uniforme  : plantage {crash_uniform:.1%}  P95 {p95_uniform:.4f} nm")
        print(f"Gaussienne: plantage {crash_gaussian:.1%}  P95 {p95_gaussian:.4f} nm")

        #1. The configuration must be monitorable, otherwise the test measures nothing.
        assert crash_uniform == 0.0, f"configuration non monitorable : {crash_uniform:.1%} de plantage"
        assert crash_gaussian == 0.0, f"configuration non monitorable : {crash_gaussian:.1%} de plantage"

        # 2. Les deux P95 doivent etre physiquement significatifs : au-dessus de
        #0.05 nm (less than one atom) and well below the nominal thickness.
        for name, p95 in (("uniforme", p95_uniform), ("gaussienne", p95_gaussian)):
            assert 0.05 < p95 < 0.2 * p_thick_nominal.min(), f"P95 {name} invraisemblable : {p95}"

        # 3. La gaussienne clippee concentre le bruit autour de zero : son P95 doit
        # be STRICTLY lower than that of the uniform, which loads the edges.
        assert p95_gaussian < p95_uniform, (
            f"la gaussienne devrait donner un P95 plus faible que l'uniforme "
            f"({p95_gaussian:.4f} vs {p95_uniform:.4f})"
        )



class TestBacksideConservation:


    """Energy conservation test with backside."""





    def test_energy_conservation_single_layer(self):


        """Checks R + T <= 1 for a monolayer with backside."""


        wl = 1500.0


        n_film = complex(2.3, -0.001)  # Light absorption


        n_sub = complex(1.52, 0.0)


        thickness = 100.0





        R, T = calculate_transmission_single(


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
        """ATTENUATE mode should NO LONGER divide the error by the factor.

        Ce test verifiait autrefois l'inverse. `non_monotonic_factor` divisait
        the error by a constant as soon as an extremum was crossed: the form
        reduite du gain d'information apporte par le swing, rendue necessaire
        because the model could not produce this gain itself.

        Avec la cible figee sur le nominal et POEM, ce gain est devenu STRUCTUREL
        — il varie avec le contraste reellement observe et avec le nombre
        d'extrema. Continuer a diviser en plus compterait deux fois le meme effet.
        The parameter is only kept for REJECT mode.

        The old version took 2% transmission noise on a layer of
        200 nm monitoree a 1500 nm : dans ce regime le depot n'est plus
        terminable et le test ne mesurait plus le facteur.
        """
        l0 = 1500.0
        p_thick = np.array([l0 / (4.0 * 2.3), l0 / (4.0 * 1.45)], dtype=np.float64)
        wl = 1300.0            # loin du point tournant : la coupure a de la sensibilite
        n_H = complex(2.3, 0.0)
        n_L = complex(1.45, 0.0)
        n_Sub = complex(1.52, 0.0)
        prev_thick = np.array([p_thick[0] + 1.0], dtype=np.float64)  # erreur amont de 1 nm
        noise = 0.001          # 0,1 point de transmission

        results = [
            simulate_growth_kernel(
                p_thick, 1, prev_thick, wl, n_H, n_L, n_Sub,
                2.0, noise, factor, NON_MONOTONIC_MODE_ATTENUATE,
            )[0]
            for factor in (1.0, 2.0, 5.0)
        ]

        assert all(r < 1e5 for r in results), f"depot declare non terminable : {results}"
        assert all(0.0 < r < 2.0 * p_thick[1] for r in results), f"epaisseurs invraisemblables : {results}"
        assert max(results) - min(results) < 1e-9, (
            f"non_monotonic_factor influe encore sur le resultat : {results}"
        )


    def test_reject_mode_penalty(self):


        """Checks that reject mode returns a large penalty for non-monotonic zones."""


        np.random.seed(42)





        # For this test, we check that when there is non-monotony, the reject mode


        #returns a large value (nominal + 1e6)


        p_thick = np.array([200.0, 200.0], dtype=np.float64)


        wl = 1500.0


        n_H = complex(2.3, 0.0)


        n_L = complex(1.45, 0.0)


        n_Sub = complex(1.52, 0.0)





        prev_thick = np.array([200.0], dtype=np.float64)


        noise = 0.02


        factor = 2.0





        result_reject, _, _, _, _ = simulate_growth_kernel(


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





        result_attenuate, _, _, _, _ = simulate_growth_kernel(


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


    """Testing validate_wavelengths_batch with the new mode."""





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


