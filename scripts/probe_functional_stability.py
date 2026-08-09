"""P95 versus CVaR95: which gives the most reproducible classification?

Le classement des strategies repose sur une fonctionnelle de la distribution des RMSE
Monte-Carlo. `rmse_p95` est un QUANTILE — la fonctionnelle la moins efficace d'un
echantillon, determinee par la seule queue haute :

    N =   6  ->  un seul point decide (le maximum)
    N =  25  ->  un a deux
    N = 150  ->  environ sept

`rmse_cvar95` est la MOYENNE des 5 % pires (expected shortfall). Meme semantique de risque,
mais elle moyenne la queue au lieu d'en piocher un point.

PROTOCOL — fair, and without a single additional simulation.
The RMSEs per draw are already stored (`results_per_noise[i]["rmse_all"]`). We capture them,
puis hors ligne :

  1. HALF SAMPLES. We cut the N draws into two halves (the SAME indices for
     all strategies — random numbers are common, so the comparison remains
     appariee). On calcule chaque fonctionnelle sur chaque moitie, et on mesure le rho de
     Spearman between the classification of the A half and that of the B half.
     The functional whose classification reproduces the best is the most reliable, at a budget
     Strictly identical. Each is judged on ITS own ranking, never on that
     de l'autre : le test ne favorise ni l'une ni l'autre par construction.
  2. BOOTSTRAP. Coefficient de variation de chaque estimateur, strategie par strategie.

    .venv/Scripts/python.exe scripts/probe_functional_stability.py

Does not write anything except reports/. Does not modify any behavior.
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

OUT = ROOT / "reports" / "probe_functional_stability.json"
RAW = ROOT / "reports" / "probe_functional_raw.npz"
CAPTURED: list[dict] = []


def _p95(a, axis=-1):
    import numpy as np

    return np.percentile(a, 95, axis=axis)


def _cvar95(a, axis=-1):
    """Average of the worst 5% — at least one point."""
    import numpy as np

    a = np.sort(a, axis=axis)
    n = a.shape[axis]
    k = max(1, int(np.ceil(0.05 * n)))
    return np.mean(np.take(a, range(n - k, n), axis=axis), axis=axis)


def install_probe() -> None:
    import certus.workers.certus_strat_workers as W

    original = W.run_final_simulation_block

    def patched(*a, **kw):
        out = original(*a, **kw)
        try:
            items = out.get("all_strategies_results") if isinstance(out, dict) else None
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                for r in it.get("results_per_noise") or []:
                    allr = r.get("rmse_all")
                    if not allr or len(allr) < 8:
                        continue
                    CAPTURED.append(
                        {
                            "strategy_id": (it.get("strategy") or {}).get("strategy_id"),
                            "n_blocks": (it.get("strategy") or {}).get("n_blocks"),
                            "noise_level": r.get("noise_level"),
                            "rmse_all": [float(x) for x in allr],
                        }
                    )
        except Exception as exc:  # noqa: BLE001 - une sonde ne tue jamais le calcul
            B.emit(f"PROBE_CAPTURE_FAILED={exc!r}")
        return out

    W.run_final_simulation_block = patched
    B.emit("sonde installee (capture de rmse_all)")


def analyse() -> dict:
    import numpy as np
    from scipy import stats

    #we group by (noise level, sample length): we need a matrix
    groups: dict = {}
    for c in CAPTURED:
        key = (round(float(c["noise_level"]), 6), len(c["rmse_all"]))
        groups.setdefault(key, {})[c["strategy_id"]] = c["rmse_all"]

    rng = np.random.default_rng(12345)
    results = []

    for (noise, n_runs), by_id in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(by_id) < 8:
            continue
        ids = sorted(by_id)
        M = np.asarray([by_id[i] for i in ids], dtype=np.float64)  # (n_strat, n_runs)

        #--- 1. half samples, same indices for all strategies ---------
        R = 200
        rho_p95, rho_cvar = [], []
        for _ in range(R):
            perm = rng.permutation(n_runs)
            ia, ib = perm[: n_runs // 2], perm[n_runs // 2 :]
            for fn, acc in ((_p95, rho_p95), (_cvar95, rho_cvar)):
                va, vb = fn(M[:, ia]), fn(M[:, ib])
                if np.std(va) == 0 or np.std(vb) == 0:
                    continue
                acc.append(stats.spearmanr(va, vb).statistic)

        # --- 2. bootstrap : dispersion de chaque estimateur -------------------------
        Bn = 200
        cv_p95, cv_cvar = [], []
        for s in range(min(len(ids), 40)):
            row = M[s]
            idx = rng.integers(0, n_runs, size=(Bn, n_runs))
            samp = row[idx]
            for fn, acc in ((_p95, cv_p95), (_cvar95, cv_cvar)):
                v = fn(samp, axis=1)
                m = float(np.mean(v))
                if m > 0:
                    acc.append(float(np.std(v) / m))

        results.append(
            {
                "noise_level": noise,
                "n_runs": int(n_runs),
                "n_strategies": len(ids),
                "demi_ech_rho_p95": float(np.mean(rho_p95)) if rho_p95 else None,
                "demi_ech_rho_cvar95": float(np.mean(rho_cvar)) if rho_cvar else None,
                "bootstrap_cv_p95": float(np.mean(cv_p95)) if cv_p95 else None,
                "bootstrap_cv_cvar95": float(np.mean(cv_cvar)) if cv_cvar else None,
            }
        )

    return {"n_captures": len(CAPTURED), "groupes": results}


def main() -> None:
    import numpy as np

    B.qapp()
    B.autoanswer_dialogs(True)
    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")

    if not CAPTURED:
        B.emit("PROBE_JAMAIS_APPELEE")
        sys.stdout.flush()
        os._exit(0)

    r = analyse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    np.savez_compressed(
        RAW,
        rmse_all=np.asarray([c["rmse_all"] for c in CAPTURED], dtype=object),
        meta=np.asarray(
            [[c["strategy_id"], c["n_blocks"], c["noise_level"]] for c in CAPTURED], dtype=object
        ),
    )
    B.emit(f"PROBE_WRITTEN={OUT}")
    B.emit(f"CAPTURES={r['n_captures']}")
    B.emit("")
    B.emit("  reproductibilite du classement (rho entre deux moities du MEME echantillon)")
    B.emit("  et dispersion de l'estimateur (bootstrap, plus petit = mieux)")
    for g in r["groupes"]:
        rp, rc = g["demi_ech_rho_p95"], g["demi_ech_rho_cvar95"]
        cp, cc = g["bootstrap_cv_p95"], g["bootstrap_cv_cvar95"]
        if rp is None or rc is None:
            continue
        verdict = "CVaR" if rc > rp else ("P95" if rp > rc else "egalite")
        B.emit(
            f"  bruit={g['noise_level']:.4f} N={g['n_runs']:>3} strat={g['n_strategies']:>3} | "
            f"rho_p95={rp:+.3f} rho_cvar={rc:+.3f} -> {verdict} | "
            f"cv_p95={cp:.3f} cv_cvar={cc:.3f}"
            if cp is not None and cc is not None
            else f"  bruit={g['noise_level']:.4f} N={g['n_runs']} rho_p95={rp:+.3f} rho_cvar={rc:+.3f} -> {verdict}"
        )

    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
