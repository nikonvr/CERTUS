"""The final statistical spectral error, broken down by band.

A global RMSE on a dichroic says nothing: it is dominated by the steep front, or a
displacement of a few nanometers produces an enormous variation of T. What counts for a
fabricant est different selon la bande :

  400-540 nm  bande passante  ~95 % de T   -> un ecart de 1 point est negligeable
  544-552 nm  front raide                  -> l'ecart mesure un DECALAGE du front
  555-700 nm  bande bloquee   < 0,1 % de T -> un ecart de 0,1 point est DEJA hors spec

We therefore capture the thicknesses actually simulated (thicknesses_all), we recalculate the spectrum
de chaque tirage, et on rend la distribution de l'ecart PAR BANDE — plus le decalage du front,
qui est la vraie grandeur physique sur un dichroique.

    .venv/Scripts/python.exe scripts/probe_spectral_error.py

Does not write anything except reports/. Do not touch any production codes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402

OUT = ROOT / "reports" / "probe_spectral_error.json"
OPTICS: dict = {}

#: SEEL calibration, captured from the headless path. Kept apart from OPTICS on
#: purpose -- see the comment on the hook that fills it.
SEEL_DATA: dict = {}
CAPTURED: list[dict] = []
MAX_STRAT = 12

#: Lightweight record of EVERY strategy the pipeline scored -- id, blocks, score,
#: crash rate, runs. A few dozen bytes each, so there is no reason to cap it.
#:
#: 🔴 WHY THIS EXISTS. `CAPTURED` keeps the first MAX_STRAT strategies **in iteration
#: order**, not the best ones. It is an arbitrary PREFIX. Reading a ranking out of it
#: -- "which strategy wins", "does the winner change with N", "does Phase A discard
#: what Phase B would crown" -- measures the capture order and nothing else, and it
#: does so while producing a perfectly readable curve. The winner of 10 is a 2-block
#: strategy that appears in no report for exactly this reason.
#:
#: So: RANKING keeps everything and is the only thing a ranking question may be asked
#: of; CAPTURED keeps the heavy per-run thickness matrices for a bounded few, which is
#: all the spectral band analysis needs.
RANKING: list[dict] = []

#: Which call of `run_final_simulation_block` we are in. Screening and deep evaluation
#: both go through it, at different Monte-Carlo depths.
STAGE: list[int] = [0]


def _has_crash(profile: dict | None) -> bool:
    """True when at least one layer crashed at least once."""
    return bool(profile) and any(sum(v or []) for v in profile.values())


def _nonzero_layers(profile: dict | None) -> dict:
    """Keep only the layers that actually failed, as {cause: {layer: count}}.

    A dense 48-long list of zeros per cause per strategy is pure weight. Storing the
    sparse form keeps the report readable AND makes the absence of a key meaningful:
    a cause that never fired simply is not there.
    """
    out: dict[str, dict[str, int]] = {}
    for cause, counts in (profile or {}).items():
        hits = {str(i): int(c) for i, c in enumerate(counts or []) if c}
        if hits:
            out[cause] = hits
    return out


def install_probe() -> None:
    import numpy as np

    import certus.core.certus_strat_robustness as R
    import certus.workers.certus_strat_workers as W

    orig_opt = R._prepare_robustness_nominal_optics

    def patched_opt(*a, **kw):
        out = orig_opt(*a, **kw)
        if not OPTICS:
            wl, nH, nL, nSub, T_nom = out
            OPTICS.update(
                wl=np.asarray(wl, dtype=np.float64), nH=np.asarray(nH), nL=np.asarray(nL),
                nSub=np.asarray(nSub), T_nom=np.asarray(T_nom, dtype=np.float64),
                p_thick=np.asarray(a[1] if len(a) > 1 else kw["p_thick_nominal"], dtype=np.float64),
            )
            B.emit(f"optiques : {OPTICS['wl'].size} lambda de {OPTICS['wl'][0]:.0f} a {OPTICS['wl'][-1]:.0f} nm")
        return out

    R._prepare_robustness_nominal_optics = patched_opt

    # SEEL is already computed in the headless path, so capture it rather than
    # recompute it: the calibration is not free (900 spectra) and recomputing would
    # also risk drawing a different one.
    # 🔴 SEEL goes in its OWN dict, never in OPTICS. `patched_opt` above is guarded by
    # `if not OPTICS`, and the two callbacks fire in an order nothing guarantees: on
    # 2026-08-10 SEEL landed first, OPTICS stopped being empty, the optics were never
    # recorded, and `analyse()` died on KeyError 'wl' AFTER the run had completed. A
    # 22-run campaign would have produced twenty-two failures and no report.
    try:
        import certus.utils.certus_strat_service as S

        orig_seel = S.calculate_seel_analysis

        def patched_seel(*a, **kw):
            data = orig_seel(*a, **kw)
            if isinstance(data, dict) and not SEEL_DATA:
                SEEL_DATA.update(data)
                B.emit(f"SEEL capture : fit_k={data.get('fit_k')} alpha={data.get('fit_alpha')}")
            return data

        S.calculate_seel_analysis = patched_seel
    except Exception as exc:  # noqa: BLE001 -- the readout must never break the run
        B.emit(f"PROBE_SEEL_HOOK_FAILED={exc!r}")

    orig_blk = W.run_final_simulation_block

    def patched_blk(*a, **kw):
        out = orig_blk(*a, **kw)
        STAGE[0] += 1
        try:
            items = (out or {}).get("all_strategies_results") if isinstance(out, dict) else None
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                st = it.get("strategy") or {}
                per = it.get("results_per_noise") or []

                # Heavy part: the per-run thickness matrices the band analysis needs.
                # Bounded, and explicitly a SAMPLE -- never a ranking.
                if len(CAPTURED) >= MAX_STRAT or not per:
                    continue
                lv = sorted(per, key=lambda r: float(r.get("noise_level", 0.0)))
                r = lv[len(lv) // 2]           # niveau de bruit NOMINAL
                th = r.get("thicknesses_all")
                if not th or len(th) < 10:
                    continue
                CAPTURED.append({
                    "id": st.get("strategy_id"), "n_blocks": st.get("n_blocks"),
                    "score": it.get("robustness_score"), "crash": it.get("crash_rate"),
                    "noise": r.get("noise_level"), "thick": np.asarray(th, dtype=np.float64),
                })
        except Exception as exc:  # noqa: BLE001
            B.emit(f"PROBE_CAPTURE_FAILED={exc!r}")
        return out

    W.run_final_simulation_block = patched_blk

    # The RANKING is taken where the bench itself takes it: `dump_strat_ranking`
    # receives `final_results["all_strategies_results"]`, the same list
    # `extract_best_rmse` reads RESULT from.
    #
    # 🔴 Why not hook `run_final_simulation_block` for this. It fires 28 times in one
    # run -- screening, deep evaluation, consensus -- at different Monte-Carlo depths.
    # Collecting them all and sorting by score lets a 10-run screening entry outrank a
    # 150-run one on a quarter of the evidence, and the resulting "winner" is simply
    # not the pipeline's. Measured 2026-08-10: 1690 rows over 28 stages, and a winner
    # that disagreed with RESULT.
    orig_dump = B.dump_strat_ranking

    def patched_dump(strategies, *a, **kw):
        try:
            from certus.utils.certus_strat_service import select_best_strat_result

            RANKING.clear()
            best = select_best_strat_result(strategies) or {}
            best_id = ((best.get("strategy") or {}).get("strategy_id"))
            for it in strategies or []:
                if not isinstance(it, dict):
                    continue
                st = it.get("strategy") or {}
                RANKING.append({
                    "id": st.get("strategy_id"),
                    "origin": st.get("origin"),
                    "n_blocks": len(st.get("blocks") or []),
                    "score": it.get("robustness_score"),
                    "crash": it.get("crash_rate"),
                    # 🔴 A rescued strategy's `robustness_score` is no longer a
                    # robustness score but the worst finite RMSE. Not the same
                    # quantity: flagged so it is never averaged with the others.
                    "crash_eliminated": bool(it.get("crash_eliminated", False)),
                    "wavelengths": [float(b.get("wavelength", 0.0)) for b in (st.get("blocks") or [])],
                    "is_winner": st.get("strategy_id") == best_id,
                    # A23 stage 0. WHERE it fails and WHAT is the poorest signal --
                    # both were already computed and both were averaged away.
                    # `crash_by_layer` is kept only when it is non-empty: a profile of
                    # zeros on 48 layers, times 250 strategies, would triple the report
                    # for no information. Its ABSENCE means "no crash anywhere", which
                    # is the normal case here and is exactly why the margin is needed.
                    **({"crash_by_layer": _nonzero_layers(it.get("crash_by_layer"))}
                       if _has_crash(it.get("crash_by_layer")) else {}),
                    "worst_swing": (it.get("worst_layer_swing") or {}).get("swing"),
                    "worst_swing_layer": (it.get("worst_layer_swing") or {}).get("layer"),
                    "n_below_swing_min": (it.get("worst_layer_swing") or {}).get("n_below_swing_min"),
                    # 17-37: how many layers had NO admissible wavelength and were
                    # forced onto the least-bad one. Run-level, but carried per row so
                    # a score can never be read without it.
                    "n_forced_layers": (it.get("phase_a_forced") or {}).get("n_forced"),
                })
            B.emit(f"RANKING capture : {len(RANKING)} strategies, gagnante id={best_id}")
        except Exception as exc:  # noqa: BLE001
            B.emit(f"PROBE_RANKING_FAILED={exc!r}")
        return orig_dump(strategies, *a, **kw)

    B.dump_strat_ranking = patched_dump
    B.emit("sonde installee")


def analyse() -> dict:
    import numpy as np
    from certus_physics import calculate_RT_batch_kernel

    wl = OPTICS["wl"]
    nH, nL, nSub = OPTICS["nH"], OPTICS["nL"], OPTICS["nSub"]
    d0 = OPTICS["p_thick"]
    _, T_nom = calculate_RT_batch_kernel(wl, nH, nL, nSub, d0.reshape(1, -1))
    T_nom = np.asarray(T_nom, dtype=np.float64)[0]

    #dichroic bands, read on the nominal spectrum itself
    pass_m = (wl >= 400) & (wl <= 540)
    edge_m = (wl > 540) & (wl < 560)
    stop_m = (wl >= 560)
    B.emit(f"bandes : passante {pass_m.sum()} pts | front {edge_m.sum()} | bloquee {stop_m.sum()}")
    B.emit(f"T nominal : passante {T_nom[pass_m].mean()*100:.2f} % | bloquee max {T_nom[stop_m].max()*100:.4f} %")

    def q(a, p):
        return float(np.percentile(a, p))

    def subpackets(rmse_per_run, orig_idx, n_total, n_crash_by_run):
        """Dispersion of the estimate over ALIGNED sub-packets of the Sobol sequence.

        👤 2026-08-10: "with 500 runs you have plenty of packets of 100 -- and that
        gives the dispersion of the sub-sets". Exactly right, and it answers a question
        separate runs cannot: not *does* the answer change with N, but by *how much* it
        would wobble at that N. One deep run replaces a sweep, and says more.

        🔴 Packets are powers of two ALIGNED on powers of two, and that is not
        housekeeping. Sobol is not random: an arbitrary contiguous slice has none of
        the equidistribution of the whole, so it would show an inflated spread and we
        would conclude far more runs are needed than really are. Sobol is a (t,s)
        sequence, so a block of 2^m aligned on a 2^m boundary IS a proper net.

        🔴 Packets are cut on the ORIGINAL run index, not on the filtered array.
        Crashed runs are dropped before this point; slicing the filtered array would
        shift every packet off its Sobol boundary and silently destroy the alignment
        the paragraph above depends on.
        """
        out = {}
        size = 2
        while size * 2 <= n_total:
            n_pk = n_total // size
            vals, crashes = [], []
            for p in range(n_pk):
                lo, hi = p * size, (p + 1) * size
                sel = np.flatnonzero((orig_idx >= lo) & (orig_idx < hi))
                if sel.size < max(2, size // 4):     # packet gutted by crashes
                    continue
                vals.append(float(np.percentile(rmse_per_run[sel], 95)))
                crashes.append(float(n_crash_by_run[lo:hi].sum()) / size)
            if len(vals) >= 2:
                arr = np.asarray(vals)
                out[str(size)] = {
                    "n_packets": len(vals),
                    "rmse_p95_min": float(arr.min()),
                    "rmse_p95_median": float(np.median(arr)),
                    "rmse_p95_max": float(arr.max()),
                    # The number that answers "is this N enough?": how wide the
                    # estimate wobbles, relative to itself.
                    "spread_relative": float((arr.max() - arr.min()) / np.median(arr))
                    if np.median(arr) > 0 else None,
                    "crash_min": min(crashes) if crashes else None,
                    "crash_max": max(crashes) if crashes else None,
                }
            size *= 2
        return out

    rows = []
    for c in CAPTURED:
        D = c["thick"]
        keep = ~np.any(np.abs(D) > 1e4, axis=1)     # ecarte les runs plantes (sentinelle 1e6)
        if keep.sum() < 8:
            continue
        orig_idx = np.flatnonzero(keep)              # Sobol index of each surviving run
        crashed = (~keep).astype(np.float64)
        _, T = calculate_RT_batch_kernel(wl, nH, nL, nSub, D[keep])
        T = np.asarray(T, dtype=np.float64)          # (n_runs, n_wl)
        E = T - T_nom[None, :]

        def band(mask):
            rmse = np.sqrt(np.mean(E[:, mask] ** 2, axis=1))
            return {"rmse_median": q(rmse, 50), "rmse_p95": q(rmse, 95),
                    "max_abs_median": q(np.max(np.abs(E[:, mask]), axis=1), 50),
                    "max_abs_p95": q(np.max(np.abs(E[:, mask]), axis=1), 95)}

        # decalage du front : lambda ou T croise 50 % du saut, par run
        lo, hi = T_nom[stop_m].mean(), T_nom[pass_m].mean()
        half = 0.5 * (lo + hi)
        idx_nom = int(np.argmin(np.abs(T_nom - half) + 1e6 * (~edge_m)))
        wl_nom = float(wl[idx_nom])
        shifts = []
        for k in range(T.shape[0]):
            i = int(np.argmin(np.abs(T[k] - half) + 1e6 * (~edge_m)))
            shifts.append(float(wl[i]) - wl_nom)
        shifts = np.asarray(shifts)

        rmse_global = np.sqrt(np.mean(E**2, axis=1))
        rows.append({
            "id": c["id"], "n_blocks": c["n_blocks"], "score": c["score"], "crash": c["crash"],
            "n_runs_ok": int(keep.sum()), "n_runs_total": int(D.shape[0]),
            "subpackets": subpackets(rmse_global, orig_idx, int(D.shape[0]), crashed),
            "global": band(np.ones_like(wl, dtype=bool)),
            "passante": band(pass_m), "front": band(edge_m), "bloquee": band(stop_m),
            "front_wl_nominal": wl_nom,
            "front_shift_nm": {"median": q(shifts, 50), "p05": q(shifts, 5), "p95": q(shifts, 95),
                               "abs_p95": q(np.abs(shifts), 95)},
        })
    # The pipeline's own final ranking, captured whole from `dump_strat_ranking`.
    # `winner` is the one `select_best_strat_result` designated -- the very strategy
    # whose `robustness_score` becomes RESULT -- and NOT the first row after a sort of
    # our own. Only `ranking` / `winner` may answer a ranking question; `strategies`
    # below is a bounded sample kept in capture order.
    ranked = sorted(
        (r for r in RANKING if r.get("score") is not None),
        key=lambda r: float(r["score"]),
    )
    return {
        "n": len(rows),
        "strategies": rows,
        "n_ranked": len(ranked),
        "n_rescued": sum(1 for r in ranked if r.get("crash_eliminated")),
        "ranking": ranked,
        "winner": next((r for r in RANKING if r.get("is_winner")), None),
        # 17-37. Run-level. Loud on purpose: a run where Phase A had no admissible
        # wavelength on a third of the layers still returns a winner, a score and a
        # SEEL that look exactly like a healthy run's. That silence is what let a
        # 100 %-crash strategy be reported as a result.
        "phase_a_forced": _forced_summary(),
    }


def _forced_summary() -> dict:
    """Layers on which Phase A had to keep the least-bad wavelength, run-wide."""
    vals = [r.get("n_forced_layers") for r in RANKING if r.get("n_forced_layers") is not None]
    if not vals:
        return {}
    n = max(vals)
    if n:
        # 🔴 sys.stdout DIRECTLY, and ASCII ONLY. Routed through `B.emit` with an emoji
        # prefix this line was swallowed in silence on a real run -- verified: the JSON
        # carried n_forced=18 while the transcript showed nothing. A warning that can
        # vanish is not a warning, and the console here is cp1252 (same lesson as the
        # analyser, which died outright on its first emoji).
        sys.stdout.write(
            f"PHASE_A_FORCED={n} couches sans aucune lambda admissible "
            f"-- la strategie est SUBIE, pas choisie (voir 17-37)\n"
        )
        sys.stdout.flush()
    return {"n_forced": n}


def main() -> None:
    B.qapp()
    B.autoanswer_dialogs(True)
    from certus_physics import calculate_RT_batch_kernel  # noqa: F401  echec immediat si absent
    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")
    if not CAPTURED or not OPTICS:
        B.emit(f"PROBE_INCOMPLETE captured={len(CAPTURED)} optics={bool(OPTICS)}")
        sys.stdout.flush(); os._exit(0)

    r = analyse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={OUT}  strategies={r['n']}")
    B.emit("")
    B.emit("  ERREUR SPECTRALE, en POINTS DE TRANSMISSION (x100 = %)")
    B.emit("  id        nb  crash | RMSE global med/p95 | passante p95 | FRONT p95 | BLOQUEE p95 max|E| | decalage front p95")
    for s in r["strategies"][:8]:
        g, pa, fr, st = s["global"], s["passante"], s["front"], s["bloquee"]
        B.emit(
            f"  {str(s['id'])[:9]:>9} {s['n_blocks']:>2} {s['crash']:.3f} | "
            f"{g['rmse_median']*100:6.3f}/{g['rmse_p95']*100:6.3f} | "
            f"{pa['rmse_p95']*100:7.3f} | {fr['rmse_p95']*100:8.3f} | "
            f"{st['rmse_p95']*100:7.4f} {st['max_abs_p95']*100:7.4f} | "
            f"{s['front_shift_nm']['abs_p95']:6.2f} nm"
        )
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
