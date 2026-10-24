"""Index share of the error of Bonne Mere 90-layer plans: the same holdout draws with the index corridor at 0 and at +-0.010.

python -X utf8 index_share_bm90.py PLAN.json [PLAN.json ...] (files in %TEMP%/bm90); CORRIDORS="0,0.005,0.010" sets the corridors. Built from modelam_bm90.py.

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

COMP, OUT_TAG, OFF = "bm90", "index_share", 0
PLANS = sys.argv[1:]
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

    def corridor(c):
        base["index_corridor"] = c
        return levels

    out = {}
    for name in PLANS:
        plan = json.loads((V / name).read_text(encoding="utf-8"))
        row = {}
        for c in [float(x) for x in os.environ.get("CORRIDORS", "0,0.010").split(",")]:
            corridor(c)
            evs = [evaluate(plan, 20261022201 + i, RUNS) for i in range(3)]
            p95 = max(float(np.percentile(np.concatenate([e[i][0] for e in evs]), 95)) for i in range(3))
            m = float(np.mean(np.concatenate([e[1][0][~e[1][1]] ** 2 for e in evs])))
            row[str(c)] = dict(seel=2 * p95 ** 0.5, mean_rmse2=m, stops=sum(int(x[1].sum()) for e in evs for x in e))
        if "0.0" in row and "0.01" in row:
            row["index_share_of_mean_rmse2"] = 1.0 - row["0.0"]["mean_rmse2"] / row["0.01"]["mean_rmse2"]
        out[name] = row
        for c, v in row.items():
            if isinstance(v, dict):
                say(f"{name}: corridor {c}: SEEL {v['seel']:.4f} nm, mean RMSE {v['mean_rmse2'] ** 0.5:.5f}, stops {v['stops']}")
    (V / os.environ.get("OUT_JSON", "index_share_result.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    say("done")


if __name__ == "__main__":
    main()
