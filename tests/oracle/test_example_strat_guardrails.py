"""Oracle guardrails for STRAT reference configuration and growth physics (Action 6.1)."""

import json
from pathlib import Path
import numpy as np
import pytest

import certus_physics
from certus_physics import simulate_growth_kernel
from certus.physics.certus_opt_tmm import compute_RT_from_matrix
from certus.physics.certus_strat_math import _solve_quadratic_target

REF_JSON_PATH = Path(r"C:\dev\gemini\example\example_strat\JSON-strat-example.json")


def test_reference_config_anti_drift_guardrail():
    """Action 6.1 #4 — Verify reference JSON configuration keys against unintended drift."""
    assert REF_JSON_PATH.exists(), f"Missing reference file: {REF_JSON_PATH}"
    with open(REF_JSON_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Check key calibration values
    assert str(cfg.get("scan_wl_step")) == "1.0", "scan_wl_step drift from 1.0"
    assert str(cfg.get("wl_step")) == "1.0", "wl_step drift from 1.0"
    assert str(cfg.get("trigger_tolerance")) == "0.05", "trigger_tolerance drift from 0.05"
    assert str(cfg.get("execution_mode")) == "premium", "execution_mode drift from premium"


def test_spectral_sanity_dichroic_guardrail():
    """Action 6.1 #2 — Verify 48-layer dichroic design is a valid passband/stopband filter."""
    with open(REF_JSON_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    mults = np.array(cfg["stack_multipliers"], dtype=np.float64)
    l0 = float(cfg["l0"])  # 550 nm
    # Calculate physical thicknesses: d_i = mult_i * l0 / (4 * n_i)
    # Layer 0 is High (Nb2O5, n ~ 2.35), Layer 1 is Low (SiO2, n ~ 1.48)
    n_H = 2.3579
    n_L = 1.4868
    n_sub = 1.4868

    thicknesses = np.array(
        [mults[i] * l0 / (4.0 * (n_H if i % 2 == 0 else n_L)) for i in range(len(mults))],
        dtype=np.float64,
    )

    # Calculate T at 450 nm (passband) and 650 nm (stopband)
    wls = [450.0, 650.0]
    T_vals = []
    for wl in wls:
        # Build transfer matrix
        M = np.eye(2, dtype=np.complex128)
        two_pi = 2.0 * np.pi
        for i, th in enumerate(thicknesses):
            n_i = n_H if i % 2 == 0 else n_L
            phi = two_pi / wl * n_i * th
            c = np.cos(phi)
            s = np.sin(phi)
            m = np.array([[c, 1j * s / n_i], [1j * n_i * s, c]], dtype=np.complex128)
            M = M @ m
        R, T = compute_RT_from_matrix(M[0, 0], M[0, 1], M[1, 0], M[1, 1], 1.0 + 0j, complex(n_sub, 0.0))
        T_vals.append(T)

    assert T_vals[0] > 0.80, f"Dichroic passband transmission @ 450nm too low: {T_vals[0]:.4f}"
    assert T_vals[1] < 0.005, f"Dichroic stopband transmission @ 650nm too high: {T_vals[1]:.4f}"


def test_growth_kernel_parabola_oracle():
    """Action 6.1 #3 — Verify _solve_quadratic_target vertex matches exact root for smooth parabola."""
    # Test a smooth parabola y(x) = 0.5 - 0.001 * (x - 100)^2
    # target y = 0.490 => exact sol x = 100 - sqrt(0.01 / 0.001) = 100 - 3.16227766
    a = -0.001
    b = 0.2
    c = -9.5  # y = -0.001*x^2 + 0.2*x - 9.5 = 0.5 - 0.001*(x - 100)^2
    target_y = 0.490
    current_x = 95.0

    sol = _solve_quadratic_target(a, b, c, target_y, current_x)
    exact_sol = 100.0 - np.sqrt((0.5 - target_y) / 0.001)
    assert abs(sol - exact_sol) < 1e-6, f"Parabola solver error: sol={sol}, exact={exact_sol}"
