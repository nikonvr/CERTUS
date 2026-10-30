"""Distance between designs and RMSE barrier of DESIGN (certus.core.certus_design_landscape)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from certus.core.certus_design_landscape import (
    align_designs,
    aligned_path,
    design_residual_jacobian,
    mf_barrier,
    optical_layers,
)

STUDY = (Path(__file__).resolve().parents[2] / "reports" / "DESIGN_bs5050_2026-10-22" / "tikhonravov" / "envelope_v2"
         / "design_distance.py")
N_IDX = {"H": 2.35, "L": 1.45}


def _random_design(rng, n: int, first: str = "H"):
    mats = [first if k % 2 == 0 else ("L" if first == "H" else "H") for k in range(n)]
    return [(m, float(t)) for m, t in zip(mats, rng.uniform(5.0, 300.0, n), strict=True)]


def _profile(design):
    """Index profile up to merges: zero layers dropped, equal neighbours merged."""
    out: list[list] = []
    for m, t in design:
        if t <= 1e-9:
            continue
        if out and out[-1][0] == m:
            out[-1][1] += t
        else:
            out.append([m, t])
    return [(m, t) for m, t in out]


def test_identical_designs_are_at_distance_zero():
    a = _random_design(np.random.default_rng(0), 12)
    al = align_designs(a, a)
    assert al.cost_nm == 0.0
    assert al.fraction == 0.0
    assert all(kind == "match" for kind, *_ in al.moves)


def test_a_needle_costs_its_thickness_through_a_merge():
    a = [("H", 100.0), ("L", 5.0), ("H", 200.0)]
    b = [("H", 300.0)]
    al = align_designs(a, b)
    assert al.cost_nm == pytest.approx(5.0)
    assert [m[0] for m in al.moves] == ["merge A"]
    assert align_designs(b, a).cost_nm == pytest.approx(5.0)


def test_an_impedance_matching_prefix_is_free_up_to_the_cap():
    core = _random_design(np.random.default_rng(1), 10)
    b = [("L", 60.0), *core]
    assert align_designs(core, b, free_nm=0.0).cost_nm == pytest.approx(60.0)
    assert align_designs(core, b, free_nm=100.0).cost_nm == pytest.approx(0.0)
    assert align_designs(core, b, free_nm=40.0).cost_nm == pytest.approx(20.0)


def test_the_distance_is_symmetric():
    rng = np.random.default_rng(2)
    for _ in range(5):
        a, b = _random_design(rng, int(rng.integers(5, 15))), _random_design(rng, int(rng.integers(5, 15)), "L")
        assert align_designs(a, b).cost_nm == pytest.approx(align_designs(b, a).cost_nm)


def test_same_costs_as_the_study_script():
    spec = importlib.util.spec_from_file_location("study_design_distance", STUDY)
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    rng = np.random.default_rng(3)
    for free in (0.0, 150.0):
        for _ in range(4):
            a, b = _random_design(rng, int(rng.integers(6, 20))), _random_design(rng, int(rng.integers(6, 20)))
            assert align_designs(a, b, free).cost_nm == pytest.approx(study.align(a, b, free)[0], abs=1e-9)


def test_the_aligned_path_starts_at_a_and_ends_at_b():
    rng = np.random.default_rng(4)
    a, b = _random_design(rng, 9), [("L", 70.0), *_random_design(rng, 11)]
    path = aligned_path(a, b, align_designs(a, b, free_nm=80.0), N_IDX.get)
    n = np.array([N_IDX[m] for m in path.materials])
    ends = [list(zip(path.materials, n * x, strict=True)) for x in (path.ep_a, path.ep_b)]
    for design, end in zip((a, b), ends, strict=True):
        got, want = _profile(end), _profile(design)
        assert [m for m, _t in got] == [m for m, _t in want]
        assert np.allclose([t for _m, t in got], [t for _m, t in want])


def _double_well(curved: bool):
    """r = (x^2 - 1, y - c (1 - x^2)): minima at (+-1, 0); the valley y = c (1 - x^2) has its pass at RMSE 1."""
    c = 0.5 if curved else 0.0

    def rj(p):
        x, y = p
        r = np.array([x * x - 1.0, y - c * (1.0 - x * x)])
        return r, np.array([[2.0 * x, 0.0], [2.0 * c * x, 1.0]])

    return rj


def test_straight_path_barrier_of_a_symmetric_double_well():
    b = mf_barrier(_double_well(False), np.array([-1.0, 0.0]), np.array([1.0, 0.0]), iterations=0,
                   lower=np.array([-5.0, -5.0]), upper=np.array([5.0, 5.0]))
    assert b.rmse_a == pytest.approx(0.0, abs=1e-12)
    assert b.rmse_straight.max() == pytest.approx(1.0)
    assert b.barrier == pytest.approx(1.0)


def test_the_string_finds_the_lower_pass_of_a_curved_valley():
    b = mf_barrier(_double_well(True), np.array([-1.0, 0.0]), np.array([1.0, 0.0]), iterations=3000, step_nm=0.02,
                   lower=np.array([-5.0, -5.0]), upper=np.array([5.0, 5.0]))
    assert b.rmse_straight.max() == pytest.approx(np.sqrt(1.25), rel=1e-6)
    assert b.rmse_string.max() == pytest.approx(1.0, rel=0.02)
    assert b.local_minima == 0


class _Constant:
    def __init__(self, n: complex):
        self.n = n

    def get_nk(self, wls):
        return np.full(len(wls), self.n, dtype=np.complex128)


def _problem(k: float = 0.0):
    from certus_physics import Target

    mats = {"H": _Constant(2.35 - 1j * k), "L": _Constant(1.45), "Substrate": _Constant(1.52)}
    wls = np.linspace(400.0, 1200.0, 161)
    return mats, wls, [Target(400.0, 1200.0, 50.0, 50.0)]


@pytest.mark.parametrize("k", [0.0, 1e-3])
def test_residuals_are_those_of_the_design_cost_and_the_jacobian_is_exact(k):
    from certus.core.certus_design_tolerance import design_residual_function
    from certus_physics import Layer

    mats, wls, tgts = _problem(k)
    seq = ["H", "L", "H", "L", "H", "L"]
    ep = np.array([60.0, 90.0, 20.0, 130.0, 55.0, 80.0])
    rj = design_residual_jacobian(mats, seq, wls, tgts)
    r, jac = rj(ep)
    ref = design_residual_function(mats, [Layer(m, 0.0) for m in seq], wls, tgts)
    assert r == pytest.approx(ref(ep), abs=1e-12)
    for i in range(ep.size):
        e = np.zeros(ep.size)
        e[i] = 1e-4
        assert jac[:, i] == pytest.approx((ref(ep + e) - ref(ep - e)) / 2e-4, abs=1e-7)


def test_the_superset_has_the_rmse_of_each_design():
    from certus.core.certus_design_tolerance import design_residual_function
    from certus_physics import Layer

    mats, wls, tgts = _problem()
    rng = np.random.default_rng(5)
    a, b = _random_design(rng, 8), _random_design(rng, 11, "L")
    path = aligned_path(a, b, align_designs(a, b), N_IDX.get)
    rj = design_residual_jacobian(mats, path.materials, wls, tgts)
    for design, ep in ((a, path.ep_a), (b, path.ep_b)):
        seq = [m for m, _t in design]
        alone = design_residual_function(mats, [Layer(m, 0.0) for m in seq], wls, tgts)(
            np.array([t / N_IDX[m] for m, t in design]))
        assert np.linalg.norm(rj(ep)[0]) == pytest.approx(np.linalg.norm(alone), rel=1e-12)


def test_optical_layers_checks_its_inputs():
    assert optical_layers(["H", "L"], np.array([10.0, 20.0]), np.array([2.0, 1.5])) == [("H", 20.0), ("L", 30.0)]
    with pytest.raises(ValueError, match="one index per layer"):
        optical_layers(["H"], np.array([10.0, 20.0]), np.array([2.0, 1.5]))
