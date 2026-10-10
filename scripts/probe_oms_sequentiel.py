"""SEQUENTIAL OMS REFERENCE: one deposition replayed reading by reading, set against the STRAT kernel.

The STRAT kernel (`simulate_growth_kernel`) does not run the machine in time. It computes, for each layer,
the signal on a coarse grid (64 points over three nominal thicknesses for the layer being grown, 16 per
replayed layer of its block), counts the turning points by their POSITION, then solves for the stopping
thickness by a parabola around the nominal one. This probe runs the machine instead: one reading every
`dd` nm of deposit (0.125 nm = 4 Hz at 0.5 nm/s, ETAT section 3), each with its own noise draw, a causal
turning-point detector, and a stop that can only happen once the controller has COUNTED the turning points
the plan expects (arming).

It answers three questions that the kernel cannot ask itself:

    1. arming -- an extremum is only known once the signal has retraced by the hysteresis threshold; is
       the stop level ever crossed before that, so that the controller is not yet waiting for it?
    2. reading density -- does the machine grid (0.125 nm) fabricate or miss turning points that the
       coarse grid of the kernel does not see?
    3. the stopping event -- `anticipated` (the controller predicts the crossing, the frozen model of
       ETAT section 3: no delay, one stopping-reading draw) or `reading` (the shutter closes on the
       first reading past the level: quantised and first-passage).

Physics deliberately LEFT OUT so that the comparison isolates the trigger logic: slit bias, photometric
curvature, affine drift, index corridor, Rate layers, witness swaps, smoothing. The kernel is called with
the same switches off. T(d) comes from the independent oracle (`tests/oracle/tmm_reference.py`), never
from `certus`: CLAUDE.md, prohibition 7.

    python scripts/probe_oms_sequentiel.py <config.json> <plans.json> [--rank 0] [--runs 300]
        [--noise 1.0] [--dd 0.125] [--stop anticipated|reading] [--lookback 4] [--seed 42] [--json out.json]

`plans.json` is a `reports/STRAT_bench_*.json` dump: a list of {"id", "score", "blocks": [[start, end, wl]]}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

# The Numba cache of the compiled kernels is keyed by their sources (ETAT D49): without this call a script reads the one
# next to the sources, where a caller keeps the machine code of an OLD callee of another file.
from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import numpy as np  # noqa: E402
import tmm_reference as ref  # noqa: E402

CRASH_NONE = 0
CRASH_LEVEL_UNREACHABLE = 1
CRASH_TP_MISCOUNT = 2
SWING_MIN = 0.04  # the kernel's POEM conditioning floor (`_read_poem_anchors`)
_QAPP = None


def load_params(config_path: Path) -> dict:
    """The parameters STRAT itself collects from the configuration (materials resolved by its database)."""
    from PyQt6.QtWidgets import QApplication

    global _QAPP
    _QAPP = QApplication.instance() or QApplication([])
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app._post_load_config = lambda *a: None
    app.load_configuration(str(config_path))
    params = app.collect_params()
    params["_keep_app_alive"] = app
    return params


def material_index(params: dict, mat_id, wl: float) -> complex:
    from certus.core._certus_physics_impl import get_refractive_index

    db = params.get("materials_db_instance") or params.get("materials_db")
    return complex(get_refractive_index(mat_id, wl, db))


def nominal_thicknesses(params: dict) -> np.ndarray:
    l0 = float(params["l0"])
    mults = [float(e) for e in params["stack_string"].split(",") if e.strip()]
    nH = material_index(params, params["nH_id"], l0).real
    nL = material_index(params, params["nL_id"], l0).real
    return np.array([(m * l0) / (4.0 * (nH if i % 2 == 0 else nL)) for i, m in enumerate(mults)])


class Detector:
    """Causal hysteresis detector, the rule of `detect_turning_points`, run reading by reading.

    Records every extremum as (index of the extremum, its value, index at which it was DECLARED).
    """

    def __init__(self, first_value: float, h: float, start_is_tp: bool, start_dir: int = 0):
        self.h = h
        self.maxv = self.minv = first_value
        self.maxi = self.mini = 0
        # When the start IS a turning point (bare substrate), the controller knows which way the signal leaves
        # it: -1 after a maximum (it now tracks the minimum), +1 after a minimum. Left at 0, a reading that noise
        # lifts above the start becomes a SECOND maximum a few readings later, counted on top of the start.
        # The plan gives the same direction at every window start (`Machine.plan`), as the kernel's machine grid
        # does (`_read_poem_anchors`): the start is then counted only when the plan counts it, never because
        # noise moved its first readings.
        self.dirn = start_dir
        self.known = start_dir != 0
        self.k = 0
        self.start_is_tp = start_is_tp
        self.extrema: list[tuple[int, float, int]] = [(0, first_value, 0)] if start_is_tp else []

    def push(self, v: float) -> None:
        self.k += 1
        k = self.k
        if v > self.maxv:
            self.maxv, self.maxi = v, k
        if v < self.minv:
            self.minv, self.mini = v, k
        # A known direction: a move the other way from the START reading is noise on that reading, not an extremum
        # at the start (the two rules of `detect_turning_points`).
        if self.known and self.dirn < 0 and self.mini == 0 and v - self.minv > self.h:
            self.minv, self.mini = v, k
            return
        if self.known and self.dirn > 0 and self.maxi == 0 and self.maxv - v > self.h:
            self.maxv, self.maxi = v, k
            return
        if self.dirn >= 0 and self.maxv - v > self.h:
            if not (self.start_is_tp and self.maxi == 0):
                self.extrema.append((self.maxi, self.maxv, k))
            self.dirn, self.minv, self.mini = -1, v, k
        elif self.dirn <= 0 and v - self.minv > self.h:
            if not (self.start_is_tp and self.mini == 0):
                self.extrema.append((self.mini, self.minv, k))
            self.dirn, self.maxv, self.maxi = 1, v, k


class RunningMean:
    """Causal running mean over the last k readings (fewer at the start: the mean of what has been read)."""

    def __init__(self, k: int):
        self.k = max(1, int(k))
        self.buf: list[float] = []
        self.acc = 0.0

    def push(self, v: float) -> float:
        if self.k == 1:
            return v
        self.buf.append(v)
        self.acc += v
        if len(self.buf) > self.k:
            self.acc -= self.buf.pop(0)
        return self.acc / len(self.buf)


class Plan:
    """What the controller is handed for one layer, computed offline on the NOMINAL stack."""

    def __init__(self, n_exp, poem_ok, p_frac, target_abs, direction, stop_k_nom, start_is_tp=False, start_dir=0):
        self.n_exp = n_exp
        self.poem_ok = poem_ok
        self.p_frac = p_frac
        self.target_abs = target_abs
        self.direction = direction
        self.stop_k_nom = stop_k_nom
        # How the window start is counted: as an extremum of known kind (the bare substrate, or a start the plan counts
        # as POEM's first anchor), and which way the nominal signal leaves it.
        self.start_is_tp = start_is_tp
        self.start_dir = start_dir


class Machine:
    def __init__(self, params, thick, blocks, dd, h_factor, lookback, A, smoothing=1):
        self.params = params
        self.thick = np.asarray(thick, dtype=float)
        self.n = len(thick)
        self.dd = dd
        self.h_factor = h_factor
        self.lookback = lookback
        self.A = A
        self.smoothing = int(smoothing)
        self.layer_wl = np.zeros(self.n)
        self.block_start = np.zeros(self.n, dtype=int)
        for b0, b1, wl in blocks:
            for i in range(int(b0), int(b1)):
                self.layer_wl[i] = float(wl)
                self.block_start[i] = int(b0)
        self._idx = {}
        self._plans = {}

    def indices(self, wl):
        if wl not in self._idx:
            p = self.params
            self._idx[wl] = (material_index(p, p["nH_id"], wl), material_index(p, p["nL_id"], wl),
                             material_index(p, p["nSub_id"], wl))
        return self._idx[wl]

    def n_of(self, j, wl):
        nH, nL, _ = self.indices(wl)
        return nH if j % 2 == 0 else nL

    def T_curve(self, thick_below, i_layer, wl, ds):
        """Oracle T of the witness when layer `i_layer` has thickness d, for every d of `ds`."""
        nS = self.indices(wl)[2]
        if i_layer > 0:
            M = ref.stack_matrix([self.n_of(j, wl) for j in range(i_layer)], thick_below[:i_layer], wl)
        else:
            M = np.eye(2, dtype=complex)
        n_cur = self.n_of(i_layer, wl)
        out = np.empty(len(ds))
        for m, d in enumerate(ds):
            out[m] = ref.rt_from_assembly(ref.characteristic_matrix(n_cur, d, wl) @ M, 1.0 + 0j, nS)[1]
        return out

    def start_direction(self, wl):
        """Which way the first layer leaves the bare substrate: -1 if T falls (the start is a maximum), +1 if it rises."""
        q = wl / (4.0 * self.n_of(0, wl).real)
        t0, t1 = self.T_curve(self.thick, 0, wl, np.array([0.0, 0.25 * q]))
        return -1 if t1 < t0 else 1

    def layer_grid(self, d_end):
        """Depths of the readings inside a layer grown to `d_end`: dd, 2dd, ... (depth 0 is the layer below)."""
        m = int(np.floor(d_end / self.dd + 1e-9))
        return self.dd * np.arange(1, m + 1)

    def plan(self, i, h):
        """Offline plan of layer i at threshold h: expected count, POEM fraction, level, direction."""
        key = (i, h)
        if key in self._plans:
            return self._plans[key]
        wl = self.layer_wl[i]
        j0 = max(int(self.block_start[i]), i - self.lookback)
        start_is_tp = i == 0 and j0 == 0
        # Signal of the NOMINAL stack at the reading positions the plan assumes (nominal thicknesses).
        vals = [self.T_curve(self.thick, j0, wl, np.array([0.0]))[0]]
        for j in range(j0, i):
            vals.extend(self.T_curve(self.thick, j, wl, self.layer_grid(self.thick[j])))
        k_cur0 = len(vals) - 1  # index of depth 0 of the current layer
        ds_cur = self.dd * np.arange(1, int(np.ceil(3.0 * self.thick[i] / self.dd)) + 1)
        vals.extend(self.T_curve(self.thick, i, wl, ds_cur))
        vals = np.asarray(vals)
        stop_k = k_cur0 + round(float(self.thick[i]) / self.dd)
        if start_is_tp:
            start_dir = self.start_direction(wl)
        else:
            # Any other window start: the direction of the nominal signal there, and the start is POEM's first anchor
            # when the nominal signal, read without that direction, counts it (`_read_poem_anchors`).
            moved = np.nonzero(vals[1:] != vals[0])[0]
            start_dir = 0 if moved.size == 0 else (1 if vals[1 + moved[0]] > vals[0] else -1)
            sm = RunningMean(self.smoothing)
            free = Detector(sm.push(vals[0]), h, False, 0)
            for v in vals[1:]:
                free.push(sm.push(v))
            start_is_tp = start_dir != 0 and bool(free.extrema) and free.extrema[0][0] == 0
        sm = RunningMean(self.smoothing)
        det = Detector(sm.push(vals[0]), h, start_is_tp, start_dir)
        for v in vals[1:]:
            det.push(sm.push(v))
        before = [e for e in det.extrema if e[0] <= stop_k]
        n_exp = len(before)
        target_abs = self.T_curve(self.thick, i, wl, np.array([self.thick[i]]))[0]
        poem_ok, p_frac = False, 0.0
        if len(before) >= 2:
            t_prev, t_last = before[-2][1], before[-1][1]
            if abs(t_last - t_prev) > SWING_MIN:
                poem_ok = True
                p_frac = (target_abs - t_prev) / (t_last - t_prev)
        eps = min(0.05, 0.1 * self.thick[i])
        t_lo, t_hi = self.T_curve(self.thick, i, wl, np.array([self.thick[i] - eps, self.thick[i] + eps]))
        direction = 1.0 if t_hi > t_lo else -1.0
        pl = Plan(n_exp, poem_ok, p_frac, target_abs, direction, stop_k, start_is_tp, start_dir)
        self._plans[key] = pl
        return pl

    def run(self, rng, f_noise, stop_mode):
        """One deposition. Returns (real thicknesses, crash cause, crash layer, per-layer flags)."""
        A_f = self.A * f_noise
        h = self.h_factor * A_f
        real = self.thick.copy()
        log: dict[tuple[int, float], np.ndarray] = {}  # measured readings of each layer (the machine's memory)
        start_level: dict[int, float] = {}
        # Per layer: late arming, POEM planned but fell back to the level, armed with more turning points than
        # planned, turned back after arming (an unexpected extremum before the level).
        flags = np.zeros((self.n, 4), dtype=bool)
        for i in range(self.n):
            wl = self.layer_wl[i]
            pl = self.plan(i, h)
            j0 = max(int(self.block_start[i]), i - self.lookback)
            # Replay the machine's memory of the window: what it measured on layers j0..i-1.
            if j0 not in start_level:
                t0 = self.T_curve(real, j0, wl, np.array([0.0]))[0]
                start_level[j0] = t0 + A_f * float(np.clip(rng.normal(0.0, 1.0 / 3.0), -1.0, 1.0))
            hist = [start_level[j0]]
            for j in range(j0, i):
                hist.extend(log.get((j, wl), ()))
            sm = RunningMean(self.smoothing)
            det = Detector(sm.push(hist[0]), h, pl.start_is_tp, pl.start_dir)
            for v in hist[1:]:
                det.push(sm.push(v))
            # The layer grows: one reading every dd, up to three nominal thicknesses, evaluated in chunks.
            ds = self.dd * np.arange(1, int(np.ceil(3.0 * self.thick[i] / self.dd)) + 1)
            true_T = np.empty(0)
            noise = A_f * np.clip(rng.normal(0.0, 1.0 / 3.0, size=len(ds)), -1.0, 1.0)
            stop_noise = A_f * float(np.clip(rng.normal(0.0, 1.0 / 3.0), -1.0, 1.0))
            t_at_0 = self.T_curve(real, i, wl, np.array([0.0]))[0]
            armed = False
            n_arm = 0
            level = 0.0
            d_stop = None
            crash = CRASH_NONE
            chunk = 256
            for m in range(len(ds)):
                if m >= len(true_T):
                    true_T = np.concatenate([true_T, self.T_curve(real, i, wl, ds[len(true_T):len(true_T) + chunk])])
                v_meas = sm.push(true_T[m] + noise[m])
                det.push(v_meas)
                n_decl = len(det.extrema)
                if not armed and n_decl >= pl.n_exp:
                    armed = True
                    n_arm = n_decl
                    flags[i, 2] = n_decl > pl.n_exp
                    target = pl.target_abs
                    if pl.poem_ok and pl.n_exp >= 2:
                        a_prev, a_last = det.extrema[pl.n_exp - 2][1], det.extrema[pl.n_exp - 1][1]
                        if abs(a_last - a_prev) > SWING_MIN:
                            target = a_prev + pl.p_frac * (a_last - a_prev)
                        else:
                            flags[i, 1] = True
                    level = target + (stop_noise if stop_mode == "anticipated" else 0.0)
                    prev_true = true_T[m - 1] if m > 0 else t_at_0
                    if m > 0 and (prev_true - level) * pl.direction >= 0.0 and (true_T[m] - level) * pl.direction >= 0.0:
                        # The signal was already past the level when the count completed: the stop comes late.
                        flags[i, 0] = True
                        d_stop = ds[m]
                        break
                if not armed:
                    continue
                if n_decl > n_arm:
                    # An extremum the plan did not expect, declared after arming and before the stop: the
                    # signal turned back before reaching the level.
                    flags[i, 3] = True
                    crash = CRASH_LEVEL_UNREACHABLE
                    break
                if stop_mode == "reading":
                    if (v_meas - level) * pl.direction >= 0.0:
                        d_stop = ds[m]
                        break
                else:
                    prev_true = true_T[m - 1] if m > 0 else t_at_0
                    a, b = prev_true - level, true_T[m] - level
                    if a * pl.direction < 0.0 <= b * pl.direction:
                        d_prev = ds[m - 1] if m > 0 else 0.0
                        d_stop = d_prev + (ds[m] - d_prev) * a / (a - b) if a != b else ds[m]
                        break
            if d_stop is None and crash == CRASH_NONE:
                crash = CRASH_LEVEL_UNREACHABLE
            if crash != CRASH_NONE:
                return real, crash, i, flags
            real[i] = d_stop
            m_last = int(np.searchsorted(ds, d_stop, side="right"))
            log[(i, wl)] = true_T[:m_last] + noise[:m_last]
        return real, CRASH_NONE, -1, flags


def kernel_runs(params, thick, blocks, n_runs, f_noise, h_factor, A, seed, smoothing=1):
    """The production kernel on the same plan, with the same physics switched off."""
    from certus.physics.certus_strat_batch import simulate_stack_robustness_batch
    from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio

    n = len(thick)
    lw = np.zeros(n)
    nH = np.zeros(n, dtype=complex)
    nL = np.zeros(n, dtype=complex)
    nS = np.zeros(n, dtype=complex)
    for b0, b1, wl in blocks:
        for i in range(int(b0), int(b1)):
            lw[i] = float(wl)
            nH[i] = material_index(params, params["nH_id"], wl)
            nL[i] = material_index(params, params["nL_id"], wl)
            nS[i] = material_index(params, params["nSub_id"], wl)
    rng = np.random.default_rng(seed)
    stop_noise = A * f_noise * np.clip(rng.normal(0.0, 1.0 / 3.0, size=(n_runs, n)), -1.0, 1.0)
    sig = np.full(n, A * f_noise)
    res, _dyn, _ml, _mm, _mf = simulate_stack_robustness_batch(
        np.asarray(thick, dtype=float), lw, nH, nL, nS, stop_noise,
        compute_probe_offset_nm_from_ratio(params), float(params.get("non_monotonic_error_factor", 2.0)),
        0, sig, int(seed) * 7919 + 17, h_factor * A * f_noise,
        0.0, 0.0, 0.0, 0, True, int(smoothing), 0.0, 0, 0.0, 0.0, None, None, None,
    )
    crash = np.zeros(n_runs, dtype=int)
    crash_layer = np.full(n_runs, -1)
    for r in range(n_runs):
        bad = np.nonzero(res[r] > 1e5)[0]
        if bad.size:
            crash_layer[r] = int(bad[0])
            crash[r] = int(res[r, bad[0]] // 1e6)
    return res, crash, crash_layer


def summarise(name, thick, res, crash, crash_layer):
    ok = crash == 0
    err = res[ok] - thick[None, :]
    rms = np.sqrt(np.mean(err * err, axis=1)) if ok.any() else np.array([np.nan])
    by_cause = {c: int(np.sum(crash == c)) for c in (1, 2, 3)}
    layers = sorted(set(int(x) for x in crash_layer[crash > 0]))
    print(f"  {name:28s} crash {np.mean(~ok) * 100:6.2f} % (level {by_cause[1]}, miscount {by_cause[2]}, "
          f"non-monotonic {by_cause[3]}) at layers {layers[:12]}")
    if ok.any():
        print(f"  {'':28s} RMS thickness error per run: mean {np.mean(rms):.4f} nm, P95 {np.percentile(rms, 95):.4f} nm;"
              f" mean error per layer {np.mean(err):+.4f} nm")
    return {
        "crash_rate": float(np.mean(~ok)),
        "crash_by_cause": by_cause,
        "crash_layers": layers,
        "rms_mean_nm": float(np.mean(rms)) if ok.any() else None,
        "rms_p95_nm": float(np.percentile(rms, 95)) if ok.any() else None,
        "bias_nm_per_layer": [float(x) for x in np.mean(err, axis=0)] if ok.any() else None,
        "std_nm_per_layer": [float(x) for x in np.std(err, axis=0)] if ok.any() else None,
    }


def spectral_rmse(params: dict, thick_batch: np.ndarray, thick_nom: np.ndarray) -> np.ndarray:
    """RMSE of the finished filter's spectrum against the nominal one, by the production scoring kernel.

    One function for both sides, kernel and machine: the comparison then differs by the thicknesses only.
    Unweighted and without index perturbation, like the rest of this probe.
    """
    from certus.physics.certus_strat_batch import calculate_RT_batch_kernel, compute_batch_rmse

    lo, hi = (float(x) for x in params["wl_range"])
    step = float(params.get("wl_step", 1.0) or 1.0)
    wls = np.arange(lo, hi + 0.5 * step, step)
    nH = np.array([material_index(params, params["nH_id"], w) for w in wls])
    nL = np.array([material_index(params, params["nL_id"], w) for w in wls])
    nS = np.array([material_index(params, params["nSub_id"], w) for w in wls])
    n_layers = len(thick_nom)
    flat = np.where((np.arange(n_layers) % 2 == 0)[None, :], nH[:, None], nL[:, None]).astype(np.complex128)
    _, T_nom = calculate_RT_batch_kernel(wls, nH, nL, nS, np.asarray(thick_nom, dtype=float).reshape(1, -1))
    return compute_batch_rmse(np.ascontiguousarray(thick_batch, dtype=float), wls, nH, nL, nS, T_nom[0], flat)


def compare_one(params, thick, plan, rank, noise, args, h_config, h_factor, A, out_rows):
    blocks = plan["blocks"]
    t0 = time.perf_counter()
    h_kernel = h_config if args.kernel_hyst is None else args.kernel_hyst
    res_k, crash_k, layer_k = kernel_runs(params, thick, blocks, args.runs, noise, h_kernel, A, args.seed,
                                          args.kernel_smoothing)
    t_k = time.perf_counter() - t0
    machine = Machine(params, thick, blocks, args.dd, h_factor, args.lookback, A, args.smoothing)
    rng = np.random.default_rng([args.seed, int(noise * 1000), int(args.dd * 1000), rank])
    res_s = np.zeros((args.runs, len(thick)))
    crash_s = np.zeros(args.runs, dtype=int)
    layer_s = np.full(args.runs, -1)
    flags_total = np.zeros((len(thick), 4), dtype=int)
    t1 = time.perf_counter()
    for r in range(args.runs):
        real, cause, layer, flags = machine.run(rng, noise, args.stop)
        res_s[r] = real
        crash_s[r] = cause
        layer_s[r] = layer
        flags_total += flags
        if cause:
            res_s[r, layer] = 1e6 * cause + thick[layer]
    t_s = time.perf_counter() - t1
    print(f"\nrank {rank} id={plan.get('id')} noise x{noise}: kernel {t_k:.1f} s, machine {t_s:.1f} s")
    row = {"rank": rank, "plan_id": plan.get("id"), "noise_factor": noise, "blocks": blocks}
    for name, res, crash, layers in (("kernel", res_k, crash_k, layer_k), ("sequential", res_s, crash_s, layer_s)):
        label = (f"kernel k={args.kernel_smoothing}" if name == "kernel" else f"machine dd={args.dd} {args.stop}")
        row[name] = summarise(label, thick, res, crash, layers)
        ok = crash == 0
        if ok.any():
            rm = spectral_rmse(params, res[ok], thick)
            row[name]["spectral_rmse_p95"] = float(np.percentile(rm, 95))
            row[name]["spectral_rmse_mean"] = float(np.mean(rm))
            print(f"  {'':28s} spectral RMSE: P95 {row[name]['spectral_rmse_p95']:.6f}, mean {row[name]['spectral_rmse_mean']:.6f}")
    late = {int(i): int(c) for i, c in enumerate(flags_total[:, 0]) if c}
    fell = {int(i): int(c) for i, c in enumerate(flags_total[:, 1]) if c}
    extra = {int(i): int(c) for i, c in enumerate(flags_total[:, 2]) if c}
    turned = {int(i): int(c) for i, c in enumerate(flags_total[:, 3]) if c}
    ok = crash_s == 0
    gross = int(np.sum(np.abs(res_s[ok] - thick[None, :]) > 2.0))
    print(f"  late arming {late} | POEM fell back {fell} | extra TP at arming {extra} | turned back {turned} | "
          f"stops > 2 nm off: {gross}")
    row["sequential"].update({"late_arming": late, "poem_fallback": fell, "extra_tp_at_arming": extra,
                              "turned_back_after_arming": turned, "stops_over_2nm": gross})
    out_rows.append(row)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("plans")
    ap.add_argument("--ranks", default="0", help="comma-separated ranks of the plans file")
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--noises", default="1.0", help="comma-separated noise factors")
    ap.add_argument("--dd", type=float, default=0.125)
    ap.add_argument("--stop", choices=("anticipated", "reading"), default="anticipated")
    ap.add_argument("--lookback", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--smoothing", type=int, default=1, help="running mean over k readings (frozen model: 8)")
    ap.add_argument("--hyst", type=float, default=None, help="hysteresis factor in A (default: the config's)")
    ap.add_argument("--kernel-smoothing", type=int, default=1, help="smoothing window passed to the kernel (> 1: fine grid)")
    ap.add_argument("--kernel-hyst", type=float, default=None, help="kernel hysteresis factor (default: the config's)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    params = load_params(Path(args.config))
    thick = nominal_thicknesses(params)
    A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    h_config = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    h_factor = h_config if args.hyst is None else args.hyst
    all_plans = json.load(open(args.plans))
    ranks = [int(x) for x in args.ranks.split(",") if x.strip()]
    noises = [float(x) for x in args.noises.split(",") if x.strip()]
    print(f"config={Path(args.config).name} plans={Path(args.plans).name} ranks={ranks} noises={noises}")
    print(f"layers={len(thick)} A={A:g} machine h={h_factor:g} A x noise (kernel: {h_config:g}) dd={args.dd} nm "
          f"stop={args.stop} lookback={args.lookback} smoothing={args.smoothing} runs={args.runs} seed={args.seed} "
          f"python={sys.version.split()[0]}")
    rows: list[dict] = []
    for rank in ranks:
        for noise in noises:
            compare_one(params, thick, all_plans[rank], rank, noise, args, h_config, h_factor, A, rows)
            if args.json:
                meta = {"config": Path(args.config).name, "plans": Path(args.plans).name, "dd_nm": args.dd,
                        "stop_mode": args.stop, "lookback": args.lookback, "runs": args.runs, "seed": args.seed,
                        "A": A, "smoothing": args.smoothing, "machine_hysteresis_factor": h_factor,
                        "kernel_hysteresis_factor": h_config if args.kernel_hyst is None else args.kernel_hyst,
                        "kernel_smoothing": args.kernel_smoothing, "python": sys.version.split()[0]}
                with open(args.json, "w", encoding="utf-8") as fh:
                    json.dump({"meta": meta, "rows": rows}, fh, indent=1)


if __name__ == "__main__":
    main()
