"""Chantier 21: the analytic spline gradient through the monotone n reparametrization (``n_mono_band_nm``).

With ``n_mono_band_nm`` set, the n block of ``x`` holds xi, decoded chain by chain into physical n knots
(``decode_xi_n_to_physical_n``). The INDEX SPLINE window sets this band from the spectrum, so the L-BFGS-B polish used
finite differences (29 cost evaluations per gradient on ``TSIO2-1700-1.xlsx``). ``spline_mono_analytic_gradient``
(on by default) adds the chain rule through the decode; these tests check it against centered finite differences of
the objective's own cost, on the branches of the decode (several chains, saturated span, clamp at |xi| = 60), the
penalty across a chain break, the k floor, R and R+T data, and the T ratio.
"""

from __future__ import annotations

import inspect
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from gradient_harness import GradientMismatch, central_difference, check_gradient

from certus.core.certus_core import N_MAX_LIMIT, N_MIN_LIMIT
from certus.spline.certus_index_spline_config import SplineOptConfig
from certus.spline.certus_index_spline_core import (
    DataType,
    decode_xi_n_to_physical_n,
    n_mono_knot_chains,
    n_mono_segment_flags,
    physical_nodes_to_x_slice_n,
    x_slice_n_to_physical_nodes,
)
from certus.spline.spline_mono_gradient import decode_xi_n_vjp
from certus.spline.spline_objective import SplinePWLObjective, spline_pwl_analytic_grad_supported

# Mono band narrower than the 420-900 nm grid: the knots outside it break the monotone chains.
MONO_BAND = (500.0, 760.0)


def _config(kind: str = "T", *, on: bool = True, ratio: bool = False, n_points: int = 60) -> SplineOptConfig:
    lam = np.linspace(420.0, 900.0, n_points)
    data_type = {"T": DataType.TRANSMISSION, "R": DataType.REFLECTION, "RT": DataType.BOTH}[kind]
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=None if kind == "R" else 0.80 + 0.06 * np.sin(lam / 90.0),
        r_exp=None if kind == "T" else 0.15 + 0.05 * np.cos(lam / 70.0),
        n_sub=np.full(n_points, 1.52),
        data_type=data_type,
        n_seg=3,
        d_lo=50.0,
        d_hi=400.0,
        weight_t=0.0 if kind == "R" else 1.0,
        weight_r=0.0 if kind == "T" else 0.7,
        substrate_name="test",
        t_is_ratio=ratio,
        n_mono_band_nm=MONO_BAND,
        spline_mono_analytic_gradient=on,
        spline_polish_fd_prefix_maxfun=0,
    )


def _knots(config: SplineOptConfig, count: int) -> np.ndarray:
    lam = np.asarray(config.lam_nm, dtype=np.float64)
    return np.linspace(1.0 / lam.max(), 1.0 / lam.min(), count)


def _chains(knots: np.ndarray) -> list[tuple[int, int]]:
    return n_mono_knot_chains(n_mono_segment_flags(knots, *MONO_BAND))


def _point(knots: np.ndarray, thickness_nm: float, *, k_floor: bool = False) -> np.ndarray:
    """A realistic point: physical n from 1.9 to 2.3, rising with sigma (normal dispersion), encoded to xi; ln k curved.

    A point with n up to 5 and a fall of 4 across a chain break puts the n(lambda) penalty at 5e4: the cost rounding
    then swamps the thickness derivative at a step of 1e-6 nm (measured: a gap of 1e-2 at 1e-6, 8e-6 at 1e-3).
    """
    knot_count = int(knots.size)
    positions = np.linspace(0.0, 1.0, knot_count)
    n_phys = 1.9 + 0.3 * positions + 0.1 * positions**2
    xi = physical_nodes_to_x_slice_n(n_phys, knots, MONO_BAND)
    lnk = np.log(0.004 + 0.016 * positions**2)
    if k_floor:
        lnk[: max(1, knot_count // 3)] = np.log(1e-8)
    return np.concatenate(([thickness_nm], xi, lnk))


def _blocks(knot_count: int) -> list[tuple[int, int]]:
    return [(0, 1), (1, 1 + knot_count), (1 + knot_count, 1 + 2 * knot_count)]


# --- the decode alone ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    ["chains", "saturated", "clamped"],
)
def test_the_decode_vjp_is_the_transpose_of_its_jacobian(case: str) -> None:
    """g . J(xi) from ``decode_xi_n_vjp`` against finite differences of g . decode(xi), on each branch of the decode."""
    knots = _knots(_config(), 14)
    chains = _chains(knots)
    assert len(chains) >= 3, f"the band must split the knots into several chains, got {chains}"
    xi = _point(knots, 100.0)[1:15]
    if case == "saturated":
        # Three steps at xi = 14 shrink the span below 1e-14: the later knots of the longest chain copy their predecessor.
        a, b = max(chains, key=lambda c: c[1] - c[0])
        xi[a + 1 : b + 1] = 14.0
    elif case == "clamped":
        xi[0] = 70.0
        xi[5] = -75.0
    g = np.linspace(0.3, 2.1, 14) * np.where(np.arange(14) % 2, 1.0, -1.0)

    analytic = decode_xi_n_vjp(xi, chains, N_MIN_LIMIT, N_MAX_LIMIT, g)
    numerical = central_difference(
        lambda v: float(np.dot(g, decode_xi_n_to_physical_n(v, chains, N_MIN_LIMIT, N_MAX_LIMIT))), xi, 1e-6
    )
    np.testing.assert_allclose(analytic, numerical, rtol=0.0, atol=1e-8 * float(np.max(np.abs(numerical))))
    if case == "saturated":
        n = decode_xi_n_to_physical_n(xi, chains, N_MIN_LIMIT, N_MAX_LIMIT)
        assert N_MAX_LIMIT - n[b] < 1e-14, "the saturated branch is not reached"
        assert analytic[b] == 0.0
    if case == "clamped":
        assert analytic[0] == 0.0
        assert analytic[5] == 0.0


# --- the objective ---------------------------------------------------------------------------------------------------


def test_the_option_is_on_by_default_and_off_falls_back_to_finite_differences() -> None:
    """On by default (the user's order of 2026-11-19); off, the monotone path keeps no analytic gradient."""
    config = _config(on=False)
    assert SplineOptConfig.spline_mono_analytic_gradient is True
    assert inspect.signature(SplineOptConfig.__init__).parameters["spline_mono_analytic_gradient"].default is True
    assert not spline_pwl_analytic_grad_supported(config)
    objective = SplinePWLObjective(config, _knots(config, 6))
    assert objective._compute_analytic_gradient(_point(_knots(config, 6), 120.0)) is None
    assert spline_pwl_analytic_grad_supported(config.replace(n_mono_band_nm=None))


@pytest.mark.parametrize(
    ("kind", "knot_count", "thickness_nm", "ratio", "k_floor", "step"),
    [
        ("T", 3, 120.0, False, False, 1e-6),
        ("T", 6, 120.0, False, False, 1e-6),
        ("T", 14, 1700.0, False, False, 1e-6),
        ("T", 14, 380.0, False, True, 1e-6),
        ("T", 6, 380.0, True, False, 1e-6),
        ("R", 6, 120.0, False, False, 1e-4),
        ("RT", 14, 380.0, False, False, 1e-4),
        ("RT", 4, 120.0, True, False, 1e-4),
    ],
    ids=["T-K3-pwl", "T-K6", "T-K14-d1700", "T-K14-kfloor", "T-ratio", "R-K6", "RT-K14", "RT-ratio-K4"],
)
def test_the_mono_gradient_matches_finite_differences(
    kind: str, knot_count: int, thickness_nm: float, ratio: bool, k_floor: bool, step: float
) -> None:
    """Analytic gradient (option on) against centered finite differences of the objective's own cost, block by block.

    The R step is 1e-4 as in ``test_spline_gradient_vs_fd.py``: the R sensitivities are themselves central differences
    at 1e-7 in ``_compute_analytic_gradient``, and the cost rounding dominates a smaller step.
    """
    config = _config(kind, ratio=ratio)
    knots = _knots(config, knot_count)
    objective = SplinePWLObjective(config, knots)
    params = _point(knots, thickness_nm, k_floor=k_floor)
    if knot_count >= 6:
        assert len(_chains(knots)) >= 2

    if k_floor:
        _, k_l, _ = objective._fast_nk(params)
        assert np.any(k_l == objective.k_lo_eff), "the k floor is not reached at this point"

    if objective._compute_analytic_gradient(params) is None:
        pytest.fail("no analytic gradient with the option on")

    def cost_and_grad(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        return float(objective(candidate)), objective._compute_analytic_gradient(candidate)

    check_gradient(
        cost_and_grad,
        params,
        step=step,
        rtol=1e-4,
        blocks=_blocks(knot_count),
        label=f"mono spline gradient {kind} K={knot_count} d={thickness_nm:.0f}",
    )


def test_the_penalty_across_a_chain_break_is_differentiated() -> None:
    """A chain that starts below the end of the previous one, inside the n(lambda) penalty band: the penalty is active
    and its gradient goes through the decode too."""
    config = _config()
    knots = _knots(config, 14)
    objective = SplinePWLObjective(config, knots)
    chains = _chains(knots)
    a = chains[-1][0]
    positions = np.linspace(0.0, 1.0, 14)
    n_phys = 1.9 + 0.3 * positions
    n_phys[a:] -= 0.08
    params = _point(knots, 380.0)
    params[1:15] = physical_nodes_to_x_slice_n(n_phys, knots, MONO_BAND)
    n_n = x_slice_n_to_physical_nodes(params[1:15], knots, MONO_BAND)
    assert objective._fast_penalty(n_n) > 0.0, "the penalty is not active at this point"

    check_gradient(
        lambda c: (float(objective(c)), objective._compute_analytic_gradient(c)),
        params,
        step=1e-6,
        rtol=1e-4,
        blocks=_blocks(14),
        label="mono spline gradient with an active penalty",
    )


def test_the_check_sees_a_missing_chain_rule() -> None:
    """GUARD: a gradient on physical n knots, handed over as a gradient on xi, is refused."""
    config = _config()
    knots = _knots(config, 6)
    objective = SplinePWLObjective(config, knots)
    physical = SplinePWLObjective(config.replace(n_mono_band_nm=None), knots)

    def wrong(candidate: np.ndarray) -> tuple[float, np.ndarray]:
        x_phys = candidate.copy()
        x_phys[1:7] = x_slice_n_to_physical_nodes(candidate[1:7], knots, MONO_BAND)
        return float(objective(candidate)), physical._compute_analytic_gradient(x_phys)

    with pytest.raises(GradientMismatch):
        check_gradient(wrong, _point(knots, 120.0), step=1e-6, rtol=1e-4, blocks=_blocks(6), label="no chain rule")


# --- the polish ------------------------------------------------------------------------------------------------------


class _CountingObjective(SplinePWLObjective):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.gradient_calls = 0
        self.cost_calls = 0

    def __call__(self, xv: np.ndarray) -> float:
        self.cost_calls += 1
        return super().__call__(xv)

    def analytic_gradient(self, xv: np.ndarray) -> np.ndarray | None:
        self.gradient_calls += 1
        return super().analytic_gradient(xv)


@pytest.mark.parametrize("on", [False, True], ids=["off", "on"])
def test_the_polish_uses_the_gradient_only_with_the_option(on: bool) -> None:
    """``_polish_lbfgsb_chunked`` takes the analytic gradient when the option is on, finite differences otherwise; a
    start on the xi bound (14) is handled; the returned point is no worse than the start."""
    from certus.spline.spline_workers import _polish_lbfgsb_chunked

    config = _config(on=on)
    knots = _knots(config, 6)
    objective = _CountingObjective(config, knots)
    x0 = _point(knots, 150.0)
    x0[2] = 14.0
    bounds = np.array([[100.0, 200.0]] + [[-14.0, 14.0]] * 6 + [[np.log(1e-6), np.log(1.0)]] * 6)
    start = float(objective(x0))

    x, cost, _ = _polish_lbfgsb_chunked(objective, x0, bounds, 400, threading.Event())

    assert np.all(np.isfinite(x))
    assert np.isfinite(cost)
    assert cost <= start
    assert cost == float(objective(x))
    if on:
        assert objective.gradient_calls > 0
        assert objective.cost_calls < 400
    else:
        assert objective.gradient_calls == 0


# --- the mixed polish (spline_polish_fd_prefix_maxfun) ---------------------------------------------------------------


def _record_minimize(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from certus.spline import spline_polish_mixed

    calls: list[dict] = []
    real = spline_polish_mixed.minimize

    def recording(fun, x0, **kwargs):
        res = real(fun, x0, **kwargs)
        calls.append({"jac": kwargs.get("jac"), "maxfun": kwargs["options"]["maxfun"], "nfev": int(res.nfev)})
        return res

    monkeypatch.setattr(spline_polish_mixed, "minimize", recording)
    return calls


def _polish_with(config: SplineOptConfig, maxfun: int) -> tuple[_CountingObjective, float, float, int]:
    from certus.spline.spline_workers import _polish_lbfgsb_chunked

    knots = _knots(config, 6)
    objective = _CountingObjective(config, knots)
    x0 = _point(knots, 150.0)
    bounds = np.array([[100.0, 200.0]] + [[-14.0, 14.0]] * 6 + [[np.log(1e-6), np.log(1.0)]] * 6)
    start = float(objective(x0))
    _, cost, nfev = _polish_lbfgsb_chunked(objective, x0, bounds, maxfun, threading.Event())
    return objective, start, cost, nfev


def test_the_fd_prefix_is_3000_by_default() -> None:
    """3000 by default (the user's order of 2026-11-19); 0 gives back the single L-BFGS-B call."""
    assert SplineOptConfig.spline_polish_fd_prefix_maxfun == 3000
    assert inspect.signature(SplineOptConfig.__init__).parameters["spline_polish_fd_prefix_maxfun"].default == 3000


@pytest.mark.parametrize("on", [False, True], ids=["fd", "analytic"])
def test_without_a_prefix_the_polish_makes_one_call(monkeypatch: pytest.MonkeyPatch, on: bool) -> None:
    calls = _record_minimize(monkeypatch)
    _polish_with(_config(on=on), 400)
    assert [(c["jac"], c["maxfun"]) for c in calls] == [(True if on else None, 400)]


def test_the_prefix_runs_finite_differences_then_the_analytic_gradient(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the analytic gradient on and a prefix of 60, a finite-difference pass of at most 60 evaluations, then the
    analytic pass with the rest of the 400; the reported count is the sum, and the result is no worse than the start."""
    calls = _record_minimize(monkeypatch)
    objective, start, cost, nfev = _polish_with(_config(on=True).replace(spline_polish_fd_prefix_maxfun=60), 400)
    assert len(calls) == 2
    first, second = calls
    assert (first["jac"], first["maxfun"]) == (None, 60)
    assert (second["jac"], second["maxfun"]) == (True, 400 - first["nfev"])
    assert nfev == first["nfev"] + second["nfev"]
    assert objective.gradient_calls > 1
    assert cost <= start


def test_the_prefix_needs_the_analytic_gradient(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the analytic gradient the prefix changes nothing: one finite-difference call with the whole budget."""
    calls = _record_minimize(monkeypatch)
    _polish_with(_config(on=False).replace(spline_polish_fd_prefix_maxfun=60), 400)
    assert [(c["jac"], c["maxfun"]) for c in calls] == [(None, 400)]


def test_a_prefix_beyond_the_budget_is_a_finite_difference_polish(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record_minimize(monkeypatch)
    _polish_with(_config(on=True).replace(spline_polish_fd_prefix_maxfun=10_000), 40)
    assert [(c["jac"], c["maxfun"]) for c in calls] in ([(None, 40)], [(None, 40), (True, 40 - calls[0]["nfev"])])
