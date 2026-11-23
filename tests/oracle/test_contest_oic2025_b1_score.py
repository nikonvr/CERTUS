"""The score of OIC 2025 Problem B.1 (`certus.domain.contest_oic2025_b1`), on spectra from the CERTUS kernels.

The spectra of an immersed stack are computed by the oblique kernels through `to_air_equivalent`, and again by the
independent oracle directly in immersion; both must give the same score. The formula itself is checked on spectra
built by hand, including the inclusive threshold H(0) = 1 of the contest report.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from tmm_reference import rt_stack_oblique

from certus.domain import contest_oic2025_b1 as b1


def _random_design(n_layers: int, seed: int, d_max: float = 250.0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = np.where(np.arange(n_layers) % 2 == 0, b1.MATERIALS["H"], b1.MATERIALS["M"]).astype(np.float64)
    d = rng.uniform(1.0, d_max, n_layers)
    return n, d


def _kernel_spectra(n: np.ndarray, d: np.ndarray, wls: np.ndarray, polarization: str) -> tuple[np.ndarray, np.ndarray]:
    from certus.domain.immersion import to_air_equivalent
    from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_vectorized

    n_t = np.tile(n.astype(np.complex128), (wls.size, 1))
    n_sub = np.full(wls.size, complex(b1.INCIDENT_INDEX, 0.0))
    n_eq, d_eq, sub_eq = to_air_equivalent(n_t, d, n_sub, b1.INCIDENT_INDEX)
    return calc_spectrum_oblique_vectorized(wls, n_eq, d_eq, sub_eq, b1.ANGLE_DEG, polarization)


def _oracle_spectra(n: np.ndarray, d: np.ndarray, wls: np.ndarray, polarization: str) -> tuple[np.ndarray, np.ndarray]:
    out = [
        rt_stack_oblique(
            float(w), n.astype(np.complex128), d, b1.ANGLE_DEG, polarization == "s",
            n_inc=complex(b1.INCIDENT_INDEX, 0.0), n_sub=complex(b1.INCIDENT_INDEX, 0.0),
        )
        for w in wls
    ]
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])


def _score(spectra) -> b1.B1Score:
    grid, lines = b1.contest_grid(), np.array(b1.LINES_NM)
    rs, ts = spectra(grid, "s")
    _rl, tsl = spectra(lines, "s")
    _rp, tpl = spectra(lines, "p")
    return b1.b1_score(rs, ts, tsl, tpl)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_kernel_score_matches_the_oracle_score(seed) -> None:
    # Very thin stacks transmit more than 99 % somewhere (finite score); two H/M layers of 20 nm already reflect
    # 1.2 % of s-light in the cube, and a thick stack reflects it almost everywhere.
    n, d = _random_design(4, seed, d_max=8.0)
    s_kernel = _score(lambda w, p: _kernel_spectra(n, d, w, p))
    s_oracle = _score(lambda w, p: _oracle_spectra(n, d, w, p))
    assert s_kernel.n_rs_at_least_99 == s_oracle.n_rs_at_least_99
    assert s_kernel.n_ts_at_least_99 == s_oracle.n_ts_at_least_99
    assert s_kernel.total == pytest.approx(s_oracle.total, rel=1e-9)
    assert s_kernel.n_ts_at_least_99 > 0  # a score of infinity would match trivially


def test_the_formula_on_spectra_built_by_hand() -> None:
    grid = b1.contest_grid()
    rs = np.where(grid < 410.0, 0.995, 0.0)  # 100 points at 400.0 .. 409.9 nm
    ts = np.where(grid >= 600.0, 0.999, 0.5)  # 1001 points at 600.0 .. 700.0 nm
    score = b1.b1_score(rs, ts, np.array([1e-4, 2e-4, 3e-4]), np.array([0.5, 1.0, 1.0]))
    assert score.n_rs_at_least_99 == 100
    assert score.n_ts_at_least_99 == 1001
    assert score.contrast_term == pytest.approx(500.0 / 3.0 * (2e-4 + 2e-4 + 3e-4))
    assert score.total == pytest.approx(score.contrast_term + 100 / 1001)
    assert score.contrast_at_lines == pytest.approx((5000.0, 5000.0, 1000.0 / 0.3))


def test_the_threshold_is_inclusive_as_in_the_contest_report() -> None:
    grid = b1.contest_grid()
    at = np.full(grid.size, b1.THRESHOLD)
    score = b1.b1_score(at, at, np.ones(3), np.ones(3))
    assert score.n_rs_at_least_99 == grid.size
    assert score.n_ts_at_least_99 == grid.size


def test_no_point_above_99_percent_in_transmission_gives_an_infinite_score() -> None:
    grid = b1.contest_grid()
    score = b1.b1_score(np.zeros(grid.size), np.full(grid.size, 0.5), np.ones(3), np.ones(3))
    assert math.isinf(score.total)


def test_the_grid_and_the_rules() -> None:
    grid = b1.contest_grid()
    assert grid.size == 3001
    assert grid[0] == 400.0
    assert grid[-1] == 700.0
    assert grid[500] == 450.0
    assert grid[1500] == 550.0
    assert grid[2500] == 650.0
    n, d = _random_design(40, 1)
    assert b1.within_contest_rules(d, n)
    assert not b1.within_contest_rules(np.full(101, 10.0), np.full(101, 2.25))
    assert not b1.within_contest_rules(np.full(50, 401.0), np.full(50, 2.25))
    assert not b1.within_contest_rules(d, np.full(d.size, 2.35))


def test_spectra_on_another_grid_are_refused() -> None:
    with pytest.raises(ValueError, match="3001 contest wavelengths"):
        b1.b1_score(np.zeros(10), np.zeros(10), np.ones(3), np.ones(3))


def test_the_reflected_points_are_counted_as_the_oracle_counts_them() -> None:
    # A thick H/M stack reflects s-light at 99 % over much of the band: the Rs count, which the thin stacks above
    # leave at zero, is compared here.
    n, d = _random_design(40, 4)
    s_kernel = _score(lambda w, p: _kernel_spectra(n, d, w, p))
    s_oracle = _score(lambda w, p: _oracle_spectra(n, d, w, p))
    assert s_kernel.n_rs_at_least_99 == s_oracle.n_rs_at_least_99
    assert s_kernel.n_rs_at_least_99 > 100


@pytest.mark.parametrize("where", ["rs", "ts", "ts_lines", "tp_lines"])
def test_a_spectrum_that_is_not_finite_is_refused(where) -> None:
    grid = b1.contest_grid()
    args = {"rs": np.zeros(grid.size), "ts": np.full(grid.size, 0.995), "ts_lines": np.ones(3), "tp_lines": np.ones(3)}
    args[where] = args[where].copy()
    args[where][0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        b1.b1_score(args["rs"], args["ts"], args["ts_lines"], args["tp_lines"])


def test_indices_and_thicknesses_of_different_lengths_are_not_a_design() -> None:
    assert not b1.within_contest_rules(np.full(10, 50.0), np.full(9, 2.25))

