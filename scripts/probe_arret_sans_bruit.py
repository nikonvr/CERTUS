"""NOISE-FREE STOP OF EACH LAYER UNDER KNOWN UPSTREAM ERRORS: the STRAT kernel against the exact POEM stop.

With no noise at all, the kernel and a machine that reads the oracle T every 0.05 nm differ only in how the signal is
sampled and how the stop is solved. The kernel reads its anchors and counts its turning points on 16 points per
replayed layer and 64 over three thicknesses of the layer being grown (D96), and solves the level on a parabola through
three probes around the nominal thickness (D97). The reference is the controller of `scripts/probe_oms_sequentiel.py`
(causal detector, arming, the plan's fraction) replayed on the independent oracle (`tests/oracle/tmm_reference.py`)
every 0.05 nm, its crossing refined by bisection on the oracle.

Upstream errors: every layer is drawn once per realisation, N(0, sigma) nm, the same for both. `--exact-inversion` and
`--exact-anchors` turn on the kernel's options of D97 and D96; `--no-poem` stops both on the absolute level.

    python scripts/probe_arret_sans_bruit.py <config.json> <plans.json> [--rank 0] [--sigma 0.3] [--realisations 3]
        [--exact-inversion] [--exact-anchors] [--no-poem]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# The Numba cache of the compiled kernels is keyed by their sources (ETAT D49): without this call a script reads the one
# next to the sources, where a caller keeps the machine code of an OLD callee of another file.
from certus.core.certus_core import ensure_numba_cache_dir  # noqa: E402

ensure_numba_cache_dir()

import numpy as np  # noqa: E402
import probe_oms_sequentiel as seq  # noqa: E402

DD = 0.05


def exact_stop(machine, thick, i, real, h, poem):
    """Exact POEM (or absolute level) stop of layer i on the real stack below, noise-free, on the fine grid."""
    wl = machine.layer_wl[i]
    pl = machine.plan(i, h)
    j0 = max(int(machine.block_start[i]), i - 4)
    start_is_tp = i == 0 and j0 == 0
    vals = [machine.T_curve(real, j0, wl, np.array([0.0]))[0]]
    for j in range(j0, i):
        vals.extend(machine.T_curve(real, j, wl, machine.layer_grid(real[j])))
    det = seq.Detector(vals[0], h, start_is_tp, machine.start_direction(wl) if start_is_tp else 0)
    for v in vals[1:]:
        det.push(v)
    ds = DD * np.arange(1, int(np.ceil(3.0 * thick[i] / DD)) + 1)
    T = machine.T_curve(real, i, wl, ds)
    t0 = machine.T_curve(real, i, wl, np.array([0.0]))[0]
    armed, level = False, None
    for k in range(len(ds)):
        det.push(T[k])
        if not armed and len(det.extrema) >= pl.n_exp:
            armed = True
            target = pl.target_abs
            if poem and pl.poem_ok and pl.n_exp >= 2:
                a, b = det.extrema[pl.n_exp - 2][1], det.extrema[pl.n_exp - 1][1]
                if abs(b - a) > seq.SWING_MIN:
                    target = a + pl.p_frac * (b - a)
            level = target
        if armed:
            prev = T[k - 1] if k > 0 else t0
            x, y = prev - level, T[k] - level
            if x * pl.direction < 0.0 <= y * pl.direction:
                lo, hi = (ds[k - 1] if k > 0 else 0.0), ds[k]
                for _ in range(40):  # the crossing, refined by bisection on the oracle
                    mid = 0.5 * (lo + hi)
                    if (machine.T_curve(real, i, wl, np.array([mid]))[0] - level) * pl.direction < 0.0:
                        lo = mid
                    else:
                        hi = mid
                return 0.5 * (lo + hi)
    return np.nan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("plans")
    ap.add_argument("--rank", type=int, default=0)
    ap.add_argument("--sigma", type=float, default=0.3, help="upstream error per layer, nm")
    ap.add_argument("--realisations", type=int, default=3)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--exact-inversion", action="store_true", help="the kernel's exact stop (D97)")
    ap.add_argument("--exact-anchors", action="store_true", help="the kernel's anchors at the extremum (D96)")
    ap.add_argument("--no-poem", action="store_true", help="both stop on the absolute level")
    args = ap.parse_args()

    from certus.physics.certus_strat_growth import simulate_growth_kernel
    from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio

    params = seq.load_params(Path(args.config))
    thick = seq.nominal_thicknesses(params)
    plan = json.load(open(args.plans))[args.rank]
    A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    hf = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    h = hf * A
    poem = not args.no_poem
    machine = seq.Machine(params, thick, plan["blocks"], DD, hf, 4, A, 1)
    probe = compute_probe_offset_nm_from_ratio(params)
    rng = np.random.default_rng(args.seed)
    diffs = []
    for r in range(args.realisations):
        real = thick + rng.normal(0.0, args.sigma, len(thick))
        row = []
        for i in range(len(thick)):
            wl = machine.layer_wl[i]
            nH, nL, nS = machine.indices(wl)
            got = simulate_growth_kernel(
                thick, i, real[:i].copy(), wl, nH, nL, nS, probe, 0.0, 2.0, 0, int(machine.block_start[i]),
                0.0, 0, 0, h, 1.0, 0.0, 0.0, poem, 1, -1.0, -1.0, False, None, 0, 0.0, None,
                args.exact_inversion, args.exact_anchors,
            )[0]
            row.append(got - exact_stop(machine, thick, i, real, h, poem))
        diffs.append(row)
        print(f"realisation {r}: |kernel - exact| median {np.nanmedian(np.abs(row)):.3g} nm, max {np.nanmax(np.abs(row)):.3g} nm",
              flush=True)
    d = np.array(diffs)
    print(f"config={Path(args.config).name} rank={args.rank} upstream sigma={args.sigma} nm, {args.realisations} realisations x "
          f"{len(thick)} layers, exact_inversion={args.exact_inversion} exact_anchors={args.exact_anchors} poem={poem}")
    print(f"kernel - exact stop, all layers: median |d| {np.nanmedian(np.abs(d)):.3g} nm, RMS {np.sqrt(np.nanmean(d * d)):.3g} nm, "
          f"P95 |d| {np.nanpercentile(np.abs(d), 95):.3g} nm, max {np.nanmax(np.abs(d)):.3g} nm")
    print("per-layer RMS (nm):", [float(f"{x:.3g}") for x in np.sqrt(np.nanmean(d * d, axis=0))])


if __name__ == "__main__":
    main()
