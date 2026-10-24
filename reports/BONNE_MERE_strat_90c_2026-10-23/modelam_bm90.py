"""Joint local search over (mode, wavelength) per layer on the 90-layer Bonne Mere design (copy of the r75 tool modelam.py).

Changes from %TEMP%/r75/modelam.py: component bm90 registered here, work folder %TEMP%/bm90, wavelengths 430-900 nm
(owner's monitoring range), start plan read from WINNER (default winner_bm90.json). FORCE_OPTICAL="3,7" keeps those layers
(0-based) optical: a Rate one first gets its best wavelength, and Rate is never offered for them; the holdout still
compares with the WINNER plan.


python -X utf8 modelam.py COMP OUT_TAG OFFSET
Start: the STRAT winner val/winner_COMP.json. Two passes from the substrate up; for each layer the candidates are
  optical layer: its wavelength +-60 nm step 10, or monitored by Rate;
  Rate layer:    monitored optically at 450..750 nm step 10.
The best candidate is kept at once when, on the search seed (20261022001+OFFSET, 300 draws), it adds no stop over
the three noise levels and lowers the paired mean RMSE^2 at the nominal noise. The frozen plan is judged against the
winner on confirmation (20261022101+OFFSET..) and final holdout (20261022201+OFFSET..) seeds, 3 x 1000 draws each.
CAP_RUNS (smoke tests only) lowers the draws and keeps 6 layers.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import sys
import time
from pathlib import Path

COMP, OUT_TAG, OFF = sys.argv[1], sys.argv[2], int(sys.argv[3])
RUNS = int(os.environ.get("CAP_RUNS", "1000"))
SEARCH_RUNS = 300 if RUNS == 1000 else RUNS
REPO = Path(__file__).resolve().parents[2]
V = Path(os.environ["TEMP"]) / "bm90"
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
LOG = open(V / f"modelam_{OUT_TAG}.log", "a", encoding="utf-8")


def say(*a):
    m = " ".join(str(x) for x in a)
    print(m, flush=True)
    LOG.write(m + "\n")
    LOG.flush()


def main():
    import bench_examples as Bx
    import numpy as np
    import probe_blocs_vs_plantage as P
    from _composant import charger_configuration

    import certus.core.certus_strat_robustness_task as task
    from certus.core.certus_strat_config import precompute_clues_and_matrices
    from certus.core.certus_strat_robustness import _attach_slit_profiles, _prepare_robustness_nominal_optics
    from certus.core.certus_strat_robustness_noise import _resolve_robustness_noise_levels
    from certus.utils.certus_exclusions import filter_params_for_gui
    from certus_physics import CRASH_SENTINEL_MIN
    from CERTUS_STRAT import CertusStratApp

    P.COMPOSANTS["bm90"] = ("reports/BONNE_MERE_strat_90c_2026-10-23/config_strat_90c_corridor0.010.json", 90)
    cfg, n_layers = P.COMPOSANTS[COMP]
    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    app = CertusStratApp()
    charger_configuration(app, REPO / cfg)
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText("deep")
    base = app.collect_params()
    base.update({"show_plots": False, "monochromator_resolution_nm": 2.0, "search_resolution": False, "noise_layer_offset": 0,
                 "noise_total_layers": n_layers, "require_turning_point": 0, **P._leviers_rate(0), "execution_mode": "deep"})
    if os.environ.get("INDEX_CORRIDOR"):  # search under another index uncertainty (default: the configuration's)
        base["index_corridor"] = float(os.environ["INDEX_CORRIDOR"])
    logger = logging.getLogger("certus_strat")
    logger.setLevel(logging.WARNING)
    nominal = json.loads((V / f"nominal_{COMP}.json").read_text(encoding="utf-8"))
    base["p_thick_nominal"] = nominal
    clues, _, _ = precompute_clues_and_matrices(base, nominal, logger)
    optics = _prepare_robustness_nominal_optics(base, nominal, {"clues_at_wl": clues})
    levels = _resolve_robustness_noise_levels(base)

    def evaluate(plan, seed, runs):
        params = dict(base, robustness_seed=int(seed))
        p = copy.deepcopy(plan)
        _attach_slit_profiles([p], nominal, params, logger)
        res = task._test_strategy_robustness_task(p, 0, levels, runs, nominal, clues, filter_params_for_gui(params), *optics, {},
                                                  compute_layer_profile=False)
        return [(np.asarray(lv["rmse_all"], dtype=float), np.any(np.asarray(lv["thicknesses_all"], dtype=float) > CRASH_SENTINEL_MIN, axis=1))
                for lv in res["results_per_noise"]]

    def stops(ev):
        return sum(int(x[1].sum()) for x in ev)

    def dmean(a, b):
        both = ~a[1][1] & ~b[1][1]
        return float(np.mean(b[1][0][both] ** 2 - a[1][0][both] ** 2)) if both.any() else float("inf")

    def set_layer(p, k, lam):
        out = []
        for b in p["blocks"]:
            s, e, w = b["start"], b["end"], float(b["wavelength"])
            if s <= k < e:
                if s < k:
                    out.append(dict(start=s, end=k, wavelength=w))
                out.append(dict(start=k, end=k + 1, wavelength=float(lam)))
                if k + 1 < e:
                    out.append(dict(start=k + 1, end=e, wavelength=w))
            else:
                out.append(dict(start=s, end=e, wavelength=w))
        q = dict(p)
        q["blocks"] = out
        return q

    def wl_of(p, k):
        return next(float(b["wavelength"]) for b in p["blocks"] if b["start"] <= k < b["end"])

    def candidates(p, k):
        if k in p["rate_layers"]:
            for lam in range(430, 901, 10):
                q = set_layer(p, k, lam)
                q["rate_layers"] = [r for r in p["rate_layers"] if r != k]
                yield f"optical@{lam}", q
        else:
            lam0 = wl_of(p, k)
            for lam in range(int(max(430, lam0 - 60)), int(min(900, lam0 + 60)) + 1, 10):
                if float(lam) != lam0:
                    yield f"lambda {lam0:.0f}->{lam}", set_layer(p, k, lam)
            if k not in forced:
                q = dict(p)
                q["rate_layers"] = sorted(set(p["rate_layers"]) | {k})
                yield "Rate", q

    start = json.loads((V / os.environ.get("WINNER", f"winner_{COMP}.json")).read_text(encoding="utf-8"))
    SS = 20261022001 + OFF
    cur, cur_ev = start, evaluate(start, SS, SEARCH_RUNS)
    forced = {int(x) for x in os.environ.get("FORCE_OPTICAL", "").split(",") if x.strip()}
    for k in sorted(forced & set(start["rate_layers"])):
        trials = [(stops(ev), dmean(cur_ev, ev), label, q, ev) for label, q in candidates(cur, k) for ev in [evaluate(q, SS, SEARCH_RUNS)]]
        s_min = min(t[0] for t in trials)
        _, d, label, cur, cur_ev = min((t for t in trials if t[0] == s_min), key=lambda t: t[1])
        say(f"   forced optical L{k}: {label}, search stops {s_min}, dRMSE2 vs start {d:+.3e}")
    layers = list(range(n_layers)) if RUNS == 1000 else list(range(6))
    t0, n_eval, kept = time.monotonic(), 1, []
    say(f"== {COMP} {OUT_TAG}: index corridor {base.get('index_corridor')}, start {len(start['rate_layers'])} Rate, search stops {stops(cur_ev)}")
    for pss in (1, 2):
        for k in layers:
            best = None
            for label, q in candidates(cur, k):
                ev = evaluate(q, SS, SEARCH_RUNS)
                n_eval += 1
                s_try, d = stops(ev), dmean(cur_ev, ev)
                if s_try <= stops(cur_ev) and d < 0 and (best is None or d < best[0]):
                    best = (d, label, q, ev)
            if best is not None:
                cur, cur_ev = best[2], best[3]
                kept.append((pss, k, best[1]))
        m = float(np.mean(cur_ev[1][0][~cur_ev[1][1]] ** 2))
        say(f"   pass {pss}: {len(kept)} changes so far, Rate {len(cur['rate_layers'])}, search stops {stops(cur_ev)}, "
            f"mean RMSE2 {m:.4e}, {n_eval} evaluations, {time.monotonic() - t0:.0f} s")
    cur = dict(cur, origin=f"{start['origin']} + joint (mode, lambda) local search {OUT_TAG}")
    (V / f"modelam_{OUT_TAG}.json").write_text(json.dumps(dict(plan=cur, kept=kept), indent=1), encoding="utf-8")
    say(f"   frozen: {len(kept)} changes {kept}")
    final = {}
    for tag, first in (("conf", 20261022101), ("hold", 20261022201)):
        seeds = [first + OFF + i for i in range(3)]
        e_s = [evaluate(start, s, RUNS) for s in seeds]
        e_c = [evaluate(cur, s, RUNS) for s in seeds]
        d = np.concatenate([b[1][0][~a[1][1] & ~b[1][1]] ** 2 - a[1][0][~a[1][1] & ~b[1][1]] ** 2 for a, b in zip(e_s, e_c, strict=True)])
        r0 = np.mean(np.concatenate([a[1][0][~a[1][1]] ** 2 for a in e_s]))
        p95 = {nm: max(float(np.percentile(np.concatenate([e[i][0] for e in evs]), 95)) for i in range(3)) for nm, evs in (("start", e_s), ("new", e_c))}
        st = {nm: sum(stops(e) for e in evs) for nm, evs in (("start", e_s), ("new", e_c))}
        final[tag] = dict(rel=float(d.mean() / r0), se=float(d.std(ddof=1) / np.sqrt(len(d)) / r0), stops=st,
                          seel_start=2 * p95["start"] ** 0.5, seel_new=2 * p95["new"] ** 0.5)
        say(f"   {tag}: dRMSE2 {100 * final[tag]['rel']:+.1f} % (SE {100 * final[tag]['se']:.1f} %), stops {st['start']} -> {st['new']}, "
            f"SEEL_strat {final[tag]['seel_start']:.4f} -> {final[tag]['seel_new']:.4f} nm")
    (V / f"modelam_{OUT_TAG}_result.json").write_text(json.dumps(dict(comp=COMP, kept=kept, final=final), indent=1), encoding="utf-8")
    say("done")


if __name__ == "__main__":
    main()
