"""ARMING PROBE: is the last turning point before each stop DECLARED before the stop?

For every layer of given strategies, on the NOMINAL signal (noise-free, as planned offline):
the gap in transmission between the stop level and the last extremum before it, compared with
the hysteresis threshold h = factor * noise_level * A. A causal controller only knows an
extremum once the signal has retraced by h from it; if the stop level lies closer than h to
that extremum, the level is crossed before the controller has counted the extremum.

T(d) comes from the independent oracle (tests/oracle/tmm_reference.py), never from certus.

The kernel counts a turning point by the POSITION of the extremum (`detect_turning_points` returns the index of
the extremum itself); the stop it then solves for may precede the moment a causal controller could know that
extremum. The window is the kernel's: the layers of the block, `MAX_LOOKBACK_VAL` (4) at most, then three
nominal thicknesses of the layer being grown.

    python scripts/probe_armement.py <config.json> <plans.json> [top] [lookback] [out.json]
    PROBE_QUIET=1 prints the summary only.
"""
import json
import os
import sys
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


def load_params(config_path):
    from PyQt6.QtWidgets import QApplication

    app_qt = QApplication.instance() or QApplication([])
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app._post_load_config = lambda *a: None
    app.load_configuration(str(config_path))
    params = app.collect_params()
    return app_qt, app, params


def nominal_thicknesses(params):
    from certus.core._certus_physics_impl import get_refractive_index

    l0 = float(params["l0"])
    mults = [float(e) for e in params["stack_string"].split(",") if e.strip()]
    db = params.get("materials_db_instance") or params.get("materials_db")
    nH = get_refractive_index(params["nH_id"], l0, db)
    nL = get_refractive_index(params["nL_id"], l0, db)
    return [(m * l0) / (4.0 * np.real(nH if i % 2 == 0 else nL)) for i, m in enumerate(mults)]


def indices_at(params, wl):
    from certus.core._certus_physics_impl import get_refractive_index

    db = params.get("materials_db_instance") or params.get("materials_db")
    return (complex(get_refractive_index(params["nH_id"], wl, db)),
            complex(get_refractive_index(params["nL_id"], wl, db)),
            complex(get_refractive_index(params["nSub_id"], wl, db)))


def window_signal(thick, i_layer, j0, wl, nH, nL, nS, dd=0.05, d_scan=3.0):
    """Nominal T over layers j0..i_layer-1 (whole layers) then the current layer to d_scan*d_nom."""
    n_of = lambda j: nH if j % 2 == 0 else nL  # noqa: E731
    M = ref.stack_matrix([n_of(j) for j in range(j0)], thick[:j0], wl) if j0 > 0 else np.eye(2, dtype=complex)
    Ts, layer_of = [], []
    for j in range(j0, i_layer + 1):
        d_end = thick[j] if j < i_layer else d_scan * thick[j]
        ds = np.arange(0.0, d_end + 1e-12, dd)
        if j > j0:
            ds = ds[1:]  # depth 0 is the end of the layer below
        for d in ds:
            _, T = ref.rt_from_assembly(ref.characteristic_matrix(n_of(j), d, wl) @ M, 1.0 + 0j, nS)
            Ts.append(T)
            layer_of.append(j)
        M = ref.characteristic_matrix(n_of(j), thick[j], wl) @ M
    return np.array(Ts), np.array(layer_of)


def declared_extrema(Ts, h, start_is_tp):
    """Online hysteresis detector: list of (extremum index, extremum value, declaration index)."""
    out = []
    if start_is_tp:
        out.append((0, Ts[0], 0))
    maxv = minv = Ts[0]
    maxi = mini = 0
    dirn = 0
    for k in range(1, len(Ts)):
        v = Ts[k]
        if v > maxv:
            maxv, maxi = v, k
        if v < minv:
            minv, mini = v, k
        if dirn >= 0 and maxv - v > h:
            if not (start_is_tp and maxi == 0):
                out.append((maxi, Ts[maxi], k))
            dirn, minv, mini = -1, v, k
        elif dirn <= 0 and v - minv > h:
            if not (start_is_tp and mini == 0):
                out.append((mini, Ts[mini], k))
            dirn, maxv, maxi = 1, v, k
    return out


def main():
    config = Path(sys.argv[1])
    plans_json = Path(sys.argv[2])
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    lookback = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    out_json = sys.argv[5] if len(sys.argv) > 5 else None
    factors = (0.5, 1.0, 2.0)
    _qt, _app, params = load_params(config)
    thick = nominal_thicknesses(params)
    A = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    hyst = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    margin_f = float(params.get("phase_a_level_margin_factor", 0.0) or 0.0)
    print(f"config={config.name} layers={len(thick)} A={A:g} tp_hysteresis_factor={hyst} "
          f"phase_a_level_margin_factor={margin_f} lookback={lookback}")
    plans = json.load(open(plans_json))[:top]
    cache = {}
    summary = []
    detail = []
    quiet = os.environ.get("PROBE_QUIET") == "1"
    for rank, plan in enumerate(plans):
        blocks = plan["blocks"]
        layer_wl, layer_b0 = {}, {}
        for b0, b1, wl in blocks:
            for i in range(b0, b1):
                layer_wl[i], layer_b0[i] = float(wl), b0
        late = {f: [] for f in factors}
        nopoem_tp = []
        rows = []
        for i in range(len(thick)):
            wl, b0 = layer_wl[i], layer_b0[i]
            j0 = max(b0, i - lookback)
            key = (i, j0, wl)
            if key not in cache:
                nH, nL, nS = indices_at(params, wl)
                cache[key] = window_signal(thick, i, j0, wl, nH, nL, nS)
            Ts, layer_of = cache[key]
            cur0 = int(np.argmax(layer_of == i))
            i_stop = cur0 + round(float(thick[i]) / 0.05)
            T_stop = Ts[i_stop]
            start_is_tp = i == 0 and j0 == 0
            for f in factors:
                h = hyst * f * A
                ext = declared_extrema(Ts, h, start_is_tp)
                before = [e for e in ext if e[0] <= i_stop]
                if before:
                    _e_idx, e_val, e_decl = before[-1]
                    gap = abs(T_stop - e_val)
                    if e_decl > i_stop:
                        late[f].append((i, gap / A))
                if f == 1.0:
                    n_before = len(before)
                    poem = (len(before) >= 2 and abs(before[-1][1] - before[-2][1]) > 0.04)
                    in_cur = [e for e in before if e[0] >= cur0]
                    if not poem and len(in_cur) >= 1:
                        nopoem_tp.append((i, len(in_cur)))
                    gap_a = abs(T_stop - before[-1][1]) / A if before else float("inf")
                    rows.append((i, wl, n_before, poem, gap_a))
        summary.append((rank, plan.get("id"), {f: len(late[f]) for f in factors}, len(nopoem_tp),
                        min((r[4] for r in rows), default=float("inf"))))
        detail.append({"rank": rank, "id": plan.get("id"), "score": plan.get("score"),
                       "late": {str(f): [[int(i), float(g)] for i, g in late[f]] for f in factors},
                       "nopoem_tp": [[int(i), int(c)] for i, c in nopoem_tp],
                       "min_gap_A": float(min((r[4] for r in rows), default=float("inf")))})
        if quiet:
            continue
        print(f"\nRANK{rank:02d} id={plan.get('id')} score={plan.get('score'):.6f} blocks="
              f"{[(b[0], b[1], b[2]) for b in blocks]}")
        for f in factors:
            print(f"  h={hyst * f:.2f} A (noise x{f}): stop crossed before the last extremum is declared on "
                  f"{len(late[f])} layer(s): {[(i, round(g, 2)) for i, g in late[f]]}")
        print(f"  layers without POEM but with >=1 turning point in the layer before the stop: {nopoem_tp}")
        if rank == 0:
            print("  per layer (i, wl, n_tp_before_stop, poem_ok, gap_to_last_extremum_in_A):")
            for r in rows:
                print("   ", r[0], r[1], r[2], r[3], f"{r[4]:.2f}")
    print(f"\nSUMMARY over {len(summary)} plans")
    for f in factors:
        n_pl = sum(1 for s_ in summary if s_[2][f] > 0)
        n_ly = sum(s_[2][f] for s_ in summary)
        print(f"  noise x{f}: {n_pl} plan(s) with >=1 late-armed layer, {n_ly} layer(s) in total")
    print(f"  plans with a non-POEM layer counting >=1 turning point before its stop: "
          f"{sum(1 for s_ in summary if s_[3] > 0)}")
    gaps = sorted(s_[4] for s_ in summary)
    print(f"  smallest gap (A) per plan: min {gaps[0]:.2f}, median {gaps[len(gaps) // 2]:.2f}")
    for s_ in summary[:20]:
        print("   ", s_)
    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump({"config": config.name, "plans": plans_json.name, "A": A, "tp_hysteresis_factor": hyst,
                       "phase_a_level_margin_factor": margin_f, "lookback": lookback, "plans_detail": detail}, fh,
                      indent=1)


if __name__ == "__main__":
    main()
