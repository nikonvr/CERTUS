"""Compare fixed and adaptive RICL grids from the same record at fixed optical thickness."""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

import numpy as np
from _artefact import ecrire_json
from numba import njit, prange
from numba.extending import register_jitable
from probe_auto_grid import ROOT, problem, quadrature_weights, target_of, uniform_grid
from probe_local_convergence import _record
from scipy.optimize import LinearConstraint, minimize

ROUNDS = 4
ITERATIONS_PER_ROUND = 5_000
FLOOR_NM = 5.0
TOT_CAP_NM = 14_171.1
JUDGE_STEPS_NM = (0.001, 0.0002, 0.0001, 0.00005)
CHUNK = 8_192


def constrained_polish(engine, seq, d0, lam, constraint, iterations):
    """Fit the wavelength-weighted residual with fixed TOT and physical bounds."""
    prob = problem(engine, lam, quadrature_weights(engine, lam))

    def cost(d):
        residual, jacobian = prob.res_jac(seq, d)
        return 10_000.0 * float(residual @ residual), 20_000.0 * (jacobian.T @ residual)

    result = minimize(
        cost, d0, jac=True, method="SLSQP", bounds=[(FLOOR_NM, None)] * len(d0),
        constraints=[constraint], options={"maxiter": iterations, "ftol": 1e-16},
    )
    return result.x, {
        "points": len(lam), "iterations": int(result.nit), "evaluations": int(result.nfev),
        "success": bool(result.success), "message": str(result.message),
    }


def adaptive_polish(engine, seq, d0, constraint):
    from certus.core.certus_design_auto_grid import base_grid, refine_grid

    bands = [(lo, hi) for lo, hi, _ in engine.THREELINE_BANDS]
    lam = base_grid(bands, engine.total_ot(seq, d0))
    d = d0
    rounds = []
    for _ in range(ROUNDS):
        d, stats = constrained_polish(engine, seq, d, lam, constraint, ITERATIONS_PER_ROUND)

        def squared(wavelengths, thickness=d):
            p = problem(engine, wavelengths)
            p.sqw = np.ones_like(wavelengths)
            residual, _ = p.res_jac(seq, thickness)
            return residual**2 * wavelengths

        refined = refine_grid(bands, lam, squared)
        n_next = len(refined.wavelengths)
        rounds.append({**stats, "points_after": n_next, "quadrature_converged": bool(refined.converged)})
        print(f"adaptive {stats['points']} points -> {n_next}, {stats['iterations']} iterations", flush=True)
        if n_next == len(lam):
            break
        lam = refined.wavelengths
    return d, rounds


def compile_oracle(oracle):
    """JIT the independent scalar oracle as written, with one call per wavelength."""
    for fn in (oracle.characteristic_matrix, oracle.stack_matrix, oracle.rt_from_assembly):
        register_jitable(fn)
    rt_stack = register_jitable(oracle.rt_stack)

    @njit(parallel=True)
    def transmission(wavelengths, n, d, n_sub):
        result = np.empty(len(wavelengths))
        for i in prange(len(wavelengths)):
            result[i] = rt_stack(wavelengths[i], n, d, 1.0 + 0.0j, n_sub)[1]
        return result

    return transmission


def scores(engine, seq, thickness, lam, oracle_transmission=None):
    weights = quadrature_weights(engine, lam)
    targets = target_of(engine, lam)
    total_weight = float(weights.sum())
    native_loss = oracle_loss = 0.0
    indices = engine.nvec(seq).astype(np.complex128)
    for first in range(0, len(lam), CHUNK):
        part = slice(first, first + CHUNK)
        p = engine.Problem("threeline", lam[part], targets[part], 100.0)
        p.sqw = np.sqrt(weights[part] / total_weight)
        residual, _ = p.res_jac(seq, thickness)
        native_loss += float(residual @ residual)
        if oracle_transmission is not None:
            error = oracle_transmission(lam[part], indices, thickness, complex(engine.N_SUB)) - targets[part]
            oracle_loss += float(weights[part] @ (error**2)) / total_weight
    native = 100.0 * np.sqrt(native_loss)
    oracle = 100.0 * np.sqrt(oracle_loss) if oracle_transmission is not None else None
    return float(native), None if oracle is None else float(oracle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=ROOT / "reports/questions_design_2026-11-13/probe_ricl_fixed_tot.json")
    args = parser.parse_args()
    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    import engine

    seq, original, _, source = _record("*tl*_best.csv")
    start = np.asarray(original, dtype=np.float64)
    tot = engine.total_ot(seq, start)
    rules = engine.Rules(nmax=101, floor=FLOOR_NM, tot=TOT_CAP_NM, tot_le=True)
    constraint = LinearConstraint(engine.nvec(seq), tot, tot)
    print(f"Starting {source}, {len(seq)} layers, fixed TOT {tot:.9f} nm", flush=True)
    cases = {"record": (start, [], 0.0)}
    fixed = uniform_grid(engine, 0.1)
    started = perf_counter()
    d, stats = constrained_polish(engine, seq, start, fixed, constraint, ROUNDS * ITERATIONS_PER_ROUND)
    cases["fixed_0.1_nm"] = (d, [stats], perf_counter() - started)
    print(f"fixed: {stats}", flush=True)
    started = perf_counter()
    d, rounds = adaptive_polish(engine, seq, start, constraint)
    cases["adaptive"] = (d, rounds, perf_counter() - started)

    oracle_transmission = compile_oracle(engine.oracle)
    step_scores = {label: {} for label in cases}
    relative_changes = {}
    for step in JUDGE_STEPS_NM:
        grid = uniform_grid(engine, step)
        for label, (d, _, _) in cases.items():
            history = step_scores[label]
            previous = next(reversed(history.values()), None)
            mf, _ = scores(engine, seq, d, grid)
            history[str(step)] = mf
            relative_changes[label] = abs(mf - previous) / max(mf, 1e-15) if previous is not None else float("inf")
        if step <= 0.0001 and max(relative_changes.values()) <= 0.01:
            break

    rows = {}
    for label, (d, stats, seconds) in cases.items():
        actual_tot = engine.total_ot(seq, d)
        admissible = (
            bool(np.isfinite(d).all()) and engine.admissible(rules, seq, d)
            and abs(actual_tot - tot) <= 1e-6
        )
        assert admissible, (label, actual_tot, float(d.min()))
        mf, oracle_mf = scores(engine, seq, d, grid, oracle_transmission)
        assert oracle_mf is not None
        assert abs(mf - oracle_mf) <= 1e-9, label
        relative_change = relative_changes[label]
        converged = relative_change <= 0.01
        rows[label] = {
            "layers": len(seq), "tot_nm": actual_tot, "min_thickness_nm": float(d.min()),
            "admissible": admissible, "d_nm": d.tolist(), "polish_seconds": seconds, "rounds": stats,
            "nominal_mf_pct_1nm": 100.0 * engine.threeline().rmse(seq, d),
            "mf_pct_by_step_nm": step_scores[label], "relative_change_finest_steps": relative_change,
            "converged": converged, "oracle_mf_pct": oracle_mf, "oracle_step_nm": step,
        }
        print(f"{label}: MF {mf:.8g}%, oracle {oracle_mf:.8g}% at {step:g} nm, stable={converged}", flush=True)
    ecrire_json(Path(args.out), {
        "source": source, "sequence": seq, "tot_fixed_nm": tot, "tot_cap_nm": TOT_CAP_NM,
        "floor_nm": FLOOR_NM, "nmax": rules.nmax, "quadrature": "trapezoid per target band in wavelength",
        "solver": "SLSQP", "max_iterations_per_arm": ROUNDS * ITERATIONS_PER_ROUND, "results": rows,
    })
    return 0 if all(row["converged"] for row in rows.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
