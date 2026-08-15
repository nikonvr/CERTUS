"""MULTIPLE-TESTGLASS -- batch sweep of the cut positions on the 99-layer 5-cavity filter.

    .venv\\Scripts\\python.exe scripts\\sweep_testglass_99c.py --cuts none      # baseline FIRST
    .venv\\Scripts\\python.exe scripts\\sweep_testglass_99c.py --preset single
    .venv\\Scripts\\python.exe scripts\\sweep_testglass_99c.py --preset double --mode deep
    .venv\\Scripts\\python.exe scripts\\sweep_testglass_99c.py --preset control \\
        --config example/example_strat/JSON-strat-example.json --layers 48

Presets, all expressed as FRACTIONS of the stack so they transfer to any component:
  single   one cut swept from a third to two thirds -- the primary map
  double   two cuts at a third and two thirds, plus neighbours
  triple   three cuts
  wide     outside the prior, to check the window is not self-fulfilling
  control  🔴 the negative control, on a stack where monitoring already works

WHY THIS SCRIPT EXISTS, in 👤's words: *"ce sont les essais-erreur avec de nombreux batchs
qui permettront une comprehension a posteriori"*. So it does one thing well -- run the same
component many times, changing ONLY the cut plan, and write every trial down.

🔴 THE RECORD IS THE POINT, not the individual run. A trial that is not written down is
noise; written down, it is a map. Every batch appends one line to
`reports/testglass_sweep_99c.tsv` with the cut plan, the SEEL of the PART, the block count,
the crash rate and the wall-clock -- and the file is the deliverable.

WHAT IS HELD FIXED, so two lines differ by the cut and nothing else:
  * slit frozen at 2 nm and `search_resolution` OFF -- 👤 2026-08-14, "on va figer les
    fentes a 2 nm pour gagner du temps". The 99c had already selected 2.0 nm anyway, and
    dropping the search is most of the cost.
  * one seed, one mode, one configuration file.

🔴 READ BEFORE INTERPRETING A RESULT:
  * The number reported is the SEEL of the PART -- the whole 99 layers, which is what is
    sold. It is NOT the average of per-campaign SEELs and cannot be composed from them
    (CLAUDE.md 25.4).
  * A cut is a free degree of freedom: adding one can only improve an IN-SAMPLE result.
    Before believing a winner, replay it on another seed.
  * Baseline first. `--cuts none` runs the uncut reference, and every other line is
    meaningless without it in the same file.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402
from CERTUS_STRAT import CertusStratApp  # noqa: E402

CONFIG = "example/example_strat/JSON-strat-bandpass-5cav-99c.json"
OUT_TSV = ROOT / "reports" / "testglass_sweep_99c.tsv"
OUT_DIR = ROOT / "reports"

#: 👤 2026-08-14 -- frozen for the whole exploration, and the search is off with it.
SLIT_NM = 2.0

# 🔑 A CUT ALWAYS FALLS AT THE END OF AN L LAYER -- 👤, 2026-08-14. Layer parity in this
# codebase is fixed: even index = H, odd index = L (`n_H if j % 2 == 0 else n_L`). So the
# last layer of a campaign is odd, and the CUT INDEX -- the first layer of the new campaign
# -- IS ALWAYS EVEN. A new witness therefore always starts with an H layer.
#
# And the physics says why, on this very design: L is SiO2 at n = 1.4832 and the substrate
# is SiO2 at n = 1.4832. They are INDEX-MATCHED. An L layer growing on a bare witness
# produces no reflection, hence no signal at all -- a campaign opening on an L would be
# blind from its first layer. Starting on H is not a convention, it is the only option.
#
# ⚠️ 👤: "mais on ne sait pas laquelle". WHICH even layer is exactly the open question.
CUT_MUST_BE_EVEN = True

# 🔴 THE SWEEP IS BLIND TO THE DESIGN, AND THAT IS THE WHOLE POINT.
#
# 👤: "on se fout du fait que cela soit un multicavité, je cherche une stratégie
# générale". A rule that needs to know where the cavities are is not a rule -- it is this
# one filter's answer, and it will not survive the next component. So no preset below
# encodes anything about resonators, spacers or mirrors: the positions are a regular sweep
# over the admissible (even) layers, nothing more.
#
# 🔑 Design structure is not an INPUT, it is a CANDIDATE EXPLANATION. Once the sweep has
# run, ask whether the winners happen to land near structural boundaries -- and if they do,
# THAT is a finding, discovered rather than assumed. Assume it up front and the measurement
# can only agree with you. This is the "comprehension a posteriori" 👤 keeps asking for.
#
# The quantities a general rule may legitimately use are stack-agnostic: how many layers
# since the last cut, how much optical swing is left, how much a frozen error would cost
# the final spectrum. Never "the third cavity".

#: 🔑 EVERY POSITION IS A FRACTION OF THE STACK, NEVER AN ABSOLUTE LAYER INDEX.
#: That is what makes a result transferable: "cut at 0.45 of the stack" means something on
#: a 48-layer dichroic and on a 150-layer filter, "cut at layer 44" does not. Run the same
#: preset on another component with --config and the fractions follow.
def at(frac: float, n_layers: int) -> int:
    """Layer index at a fraction of the stack, snapped DOWN to an admissible (even) cut."""
    p = int(round(frac * n_layers))
    p -= p % 2                      # even: a campaign must open on H, see CUT_MUST_BE_EVEN
    return max(2, min(p, n_layers - 2))


def build_presets(n: int) -> dict[str, list[list[int]]]:
    """Cut plans for a stack of `n` layers. 👤's priors, expressed as fractions.

    👤 2026-08-14: *"il faudra tester une coupure entre 1/3 et 2/3 du design si une seule
    coupure"* and *"1/3 2/3 si deux coupures"*. Those are the priors under test -- they are
    swept, not assumed, and `wide` exists precisely to check that the prior is not
    self-fulfilling.
    """
    F = lambda *fr: [at(f, n) for f in fr]  # noqa: E731
    return {
        # PRIMARY EXPERIMENT -- one cut, swept across 👤's window, a third to two thirds.
        # This is the map: it says whether a best position exists, and whether the optimum
        # is sharp or flat.
        "single": [[]] + [[at(f, n)] for f in
                          (0.33, 0.37, 0.41, 0.45, 0.50, 0.54, 0.58, 0.62, 0.66)],
        # TWO CUTS at a third and two thirds -- 👤's prior -- plus near neighbours, so the
        # answer is not just "the prior scored something" but "the prior is a local best".
        "double": [[], F(0.33, 0.66), F(0.30, 0.60), F(0.36, 0.72),
                   F(0.28, 0.66), F(0.33, 0.72)],
        # THREE CUTS, quarters and thirds-of-thirds. 👤's target shape is 2 or 3 witnesses.
        "triple": [[], F(0.25, 0.50, 0.75), F(0.28, 0.50, 0.72),
                   F(0.22, 0.44, 0.68), F(0.33, 0.55, 0.77)],
        # 🔴 OUTSIDE THE PRIOR, and it is not decoration. If a cut at 0.15 or 0.85 beats
        # everything in `single`, then the "between a third and two thirds" window is
        # wrong -- and that is worth far more than confirming it.
        "wide": [[]] + [[at(f, n)] for f in (0.10, 0.15, 0.20, 0.25, 0.75, 0.80, 0.85, 0.90)],
        # 🔴 NEGATIVE CONTROL, not optional. On a stack where monitoring already works a cut
        # can only lose. Run with --config on the 48-layer dichroic: if a cut IMPROVES it,
        # the model is wrong and nothing else in this file means anything.
        "control": [[], F(0.50), F(0.33, 0.66)],
    }


def score_to_seel_nm(score: float | None, quantize: bool = True) -> float:
    if score is None or score < 0 or math.isnan(score):
        return float("nan")
    seel = 2.0 * math.sqrt(score)
    return round(seel * 100.0) / 100.0 if quantize else seel


def _tag(cuts: list[int]) -> str:
    return "nocut" if not cuts else "cut" + "-".join(str(c) for c in cuts)


def validate_cuts(cuts: list[int], n_layers: int = 99) -> list[int]:
    """Reject a cut plan the machine could not run, LOUDLY.

    An odd cut index would open a campaign on an L layer, which is index-matched to the
    silica witness and therefore invisible. The run would still produce a score -- a
    plausible one -- for a strategy nobody can deposit. That is the failure mode this
    project exists to avoid, so it is an error and not a warning.
    """
    for c in cuts:
        if not 0 < c < n_layers:
            raise SystemExit(f"cut {c} outside 1..{n_layers - 1}")
        if CUT_MUST_BE_EVEN and c % 2 != 0:
            raise SystemExit(
                f"cut {c} is ODD, so the campaign would open on an L layer. L is SiO2 and "
                f"so is the witness: index-matched, no signal. Use {c - 1} or {c + 1}."
            )
    if len(set(cuts)) != len(cuts):
        raise SystemExit(f"duplicate cut in {cuts}")
    return sorted(cuts)


def run_one(cuts: list[int], mode: str, config_rel: str, seed: int) -> dict:
    """One batch. Returns the row that will be appended to the TSV."""
    B.qapp()
    B.autoanswer_dialogs(True)

    app = CertusStratApp()
    app.load_configuration(str(ROOT / config_rel))
    B.attach_console_logging(app)

    # 🔴 THE MODE MUST BE SET ON THE WIDGET, BEFORE collect_params. That method reads the
    # combo box and expands it into the budget (N, dp_top_k, n_screen_runs, ...), so
    # writing `params["execution_mode"]` afterwards changes the label and NOTHING else.
    # This exact bug shipped here on 2026-08-15: `--mode fast` ran a full PREMIUM, and the
    # only reason it was caught is that the applied config is written down. Hence the
    # check below covers the budget, not just the mode string.
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText(mode)

    # 🔴 MUTATING THE DICT RETURNED BY collect_params() DOES NOTHING. `run_workflow` calls
    # `self.collect_params()` AGAIN, internally, and uses that fresh dict -- the one built
    # from the widgets. Anything written on the returned copy is thrown away.
    #
    # This shipped here on 2026-08-15 and produced two batches, "no cut" and "cut at 32",
    # with BIT-IDENTICAL scores: no cut had ever been applied, and neither had the frozen
    # slit. Worse, the check below read the values back from that same discarded dict, so
    # it was circular and confirmed nothing.
    #
    # The fix is to override at the ONE place collection happens, so every internal call
    # receives the same overrides.
    overrides = {
        "show_plots": False,
        "witness_reset_layers": list(cuts),
        "monochromator_resolution_nm": SLIT_NM,   # held fixed -- see module docstring
        "search_resolution": False,
        "robustness_seed": seed,
    }
    seen: dict[str, int] = {"calls": 0}
    _collect = app.collect_params

    def collect_with_overrides(*a, **kw):
        p = _collect(*a, **kw)
        p.update(overrides)
        seen["calls"] += 1
        return p

    app.collect_params = collect_with_overrides
    params = app.collect_params()

    # 🔴 Consign the configuration that was APPLIED, not the one that was asked for. The
    # gate campaign of 2026-08-14 lost all six of its runs to exactly this: a key applied
    # to the run and never written down. Read it back from `params` after setting it.
    applied = {
        "cuts": list(params.get("witness_reset_layers") or []),
        "mode": params.get("execution_mode"),
        "slit_nm": params.get("monochromator_resolution_nm"),
        "search_resolution": params.get("search_resolution"),
        "seed": params.get("robustness_seed"),
        "robustness_num_runs": params.get("robustness_num_runs"),
        "dp_top_k": params.get("dp_top_k"),
        "n_screen_runs": params.get("n_screen_runs"),
        "allow_rate": params.get("allow_rate"),
    }
    if applied["cuts"] != list(cuts):
        raise SystemExit(f"cut plan not applied: asked {cuts}, applied {applied['cuts']}")
    if abs(float(applied["slit_nm"] or 0.0) - SLIT_NM) > 1e-9:
        raise SystemExit(f"slit not applied: asked {SLIT_NM}, applied {applied['slit_nm']}")
    if str(applied["mode"]).lower() != mode.lower():
        raise SystemExit(f"mode not applied: asked {mode}, applied {applied['mode']}")
    # And the budget, not just the label: the mode is only real if it moved the numbers.
    expected_runs = {"fast": 50, "premium": 150, "deep": 300}[mode.lower()]
    if int(applied["robustness_num_runs"] or 0) != expected_runs:
        raise SystemExit(
            f"mode {mode} did not take: robustness_num_runs = "
            f"{applied['robustness_num_runs']}, expected {expected_runs}"
        )

    sys.stderr.write(f"\n{'=' * 78}\n  {_tag(cuts)}  |  {json.dumps(applied)}\n{'=' * 78}\n")

    t0 = time.perf_counter()
    calls_before = seen["calls"]
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None
    elapsed = time.perf_counter() - t0

    # 🔴 THE ONLY NON-CIRCULAR CHECK IN THIS SCRIPT. Reading the overrides back out of the
    # dict we just wrote them into proves nothing -- that is how the 2026-08-15 batches
    # passed their own verification while running no cut at all. What has to be true is
    # that `run_workflow` went THROUGH our injection point. If it collected its parameters
    # some other way, the run used the widgets and our cut plan never existed.
    if seen["calls"] <= calls_before:
        raise SystemExit(
            "run_workflow never called collect_params: the overrides (cut plan, frozen "
            "slit) did NOT reach the solver. Do not trust anything this run produced."
        )

    row = {
        "tag": _tag(cuts),
        "cuts": ",".join(str(c) for c in cuts) if cuts else "-",
        "n_cuts": len(cuts),
        "seel_nm": float("nan"),
        "rmse_p95": float("nan"),
        "n_blocks": -1,
        "crash_pct": float("nan"),
        "n_strats": 0,
        "run_s": round(elapsed, 1),
        "config": json.dumps(applied, sort_keys=True),
    }

    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    row["n_strats"] = len(strats)
    if strats:
        best = strats[0]
        st = best.get("strategy", {}) or {}
        row["rmse_p95"] = best.get("robustness_score")
        row["seel_nm"] = score_to_seel_nm(row["rmse_p95"])
        row["n_blocks"] = st.get("n_blocks", len(st.get("blocks", []) or []))
        row["crash_pct"] = round(float(best.get("crash_rate", 0.0)) * 100.0, 2)

        # 🔴 THE CHECK THAT SAVES THE WHOLE SWEEP FROM BEING MEANINGLESS.
        #
        # A strategy whose crash rate exceeds the 5 % tolerance is scored `inf` and taken
        # out of the ranking. When NOTHING survives, the solver falls back: it re-ranks the
        # eliminated candidates by increasing risk and hands back the least bad with a
        # finite number -- and that number is the WORST FINITE RMSE, not a robustness score.
        #
        # The run still looks perfect. It prints a score, a block count, a SEEL. On the
        # 99-layer filter on 2026-08-15 that fallback produced "SEEL = 0.86 nm" for a
        # strategy that fails in 100 % of draws, and it had been quoted as a manufacturing
        # figure. Comparing two cut positions on fallback scores compares two ways of
        # failing.
        if row["crash_pct"] >= 5.0:
            row["verdict"] = "FALLBACK"
            sys.stderr.write(
                f"  🔴 crash_rate = {row['crash_pct']} % >= 5 %: this is the NO-SURVIVOR "
                f"FALLBACK.\n     SEEL {row['seel_nm']} nm is the worst finite RMSE of a "
                f"strategy that FAILS, not a robustness score.\n     The question here is "
                f"not 'how low is the SEEL' but 'does anything survive at all'.\n"
            )
        else:
            row["verdict"] = "OK"
    else:
        # A run that returns nothing is NOT a run that found nothing. Say which.
        row["verdict"] = "RESULT_NONE"
        sys.stderr.write("  ⚠️ RESULT=None -- no strategy came back. Do not read this as a score.\n")
    return row


def append_row(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    cols = ["stamp", "tag", "cuts", "n_cuts", "verdict", "seel_nm", "rmse_p95",
            "n_blocks", "crash_pct", "n_strats", "run_s", "config"]
    new = not OUT_TSV.exists()
    with open(OUT_TSV, "a", encoding="utf-8", newline="") as f:
        if new:
            f.write("\t".join(cols) + "\n")
        row = {"stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **row}
        f.write("\t".join(str(row.get(c, "")) for c in cols) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cuts", help='e.g. "34,66" for one batch, or "none" for the baseline')
    ap.add_argument("--preset", choices=sorted(build_presets(99)),
                    help="a whole series of batches; positions are FRACTIONS of the stack")
    ap.add_argument("--mode", default="premium", choices=["fast", "premium", "deep"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--layers", type=int, default=99,
                    help="stack size the fractions are resolved against")
    args = ap.parse_args()

    presets = build_presets(args.layers)
    if args.preset:
        plans = presets[args.preset]
    elif args.cuts:
        plans = [[] if args.cuts.strip().lower() in ("none", "-", "") else
                 [int(x) for x in args.cuts.split(",") if x.strip()]]
    else:
        ap.error("give --cuts or --preset")

    plans = [validate_cuts(p, args.layers) for p in plans]

    if not any(len(p) == 0 for p in plans):
        sys.stderr.write(
            "\n⚠️ No uncut baseline in this series. Every SEEL below is uninterpretable\n"
            "   unless reports/testglass_sweep_99c.tsv already holds one for this mode,\n"
            "   seed and configuration. Run `--cuts none` first if it does not.\n"
        )

    sys.stderr.write(f"\n{len(plans)} batch(es) | mode={args.mode} | seed={args.seed} | "
                     f"slit={SLIT_NM} nm frozen | config={args.config}\n")

    for i, cuts in enumerate(plans, 1):
        sys.stderr.write(f"\n--- batch {i}/{len(plans)} : {_tag(cuts)} ---\n")
        try:
            row = run_one(cuts, args.mode, args.config, args.seed)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 -- one failed batch must not lose the others
            sys.stderr.write(f"  ⚠️ batch {_tag(cuts)} FAILED: {exc!r}\n")
            row = {"tag": _tag(cuts), "cuts": ",".join(map(str, cuts)) or "-",
                   "n_cuts": len(cuts), "seel_nm": float("nan"), "rmse_p95": float("nan"),
                   "n_blocks": -1, "crash_pct": float("nan"), "n_strats": 0,
                   "verdict": "CRASHED", "run_s": 0.0, "config": f"FAILED {exc!r}"}
        append_row(row)
        sys.stderr.write(
            f"  -> [{row.get('verdict')}] SEEL={row['seel_nm']} nm | blocks={row['n_blocks']} | "
            f"crash={row['crash_pct']} % | {row['n_strats']} strats | {row['run_s']} s\n"
        )

    sys.stderr.write(f"\nAll batches written to {OUT_TSV}\n")
    sys.stderr.write(
        "🔴 Read the baseline line first. And before believing any winner, replay it on\n"
        "   another seed: a cut is a free degree of freedom and can only help in-sample.\n"
    )


if __name__ == "__main__":
    main()
