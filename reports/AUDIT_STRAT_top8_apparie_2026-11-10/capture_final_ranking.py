"""Capture, for STRAT's FINAL ranking, the per-draw RMSE and the per-draw stop flag of every plan that still carries them.

Read-only on CERTUS: it runs the bench's own `run_strat()` and listens on `bench_examples.dump_strat_ranking`, which
receives the final `all_strategies_results` in the main process. Patching `run_final_simulation_block` in
`certus.workers.certus_strat_workers`, as `scripts/probe_functional_stability.py` does, misses the calls made by the
local-search and Rate workers, which import the function from `certus.core.certus_strat_robustness`.

Only the plans kept with their full Monte Carlo (`keep_full_mc_top_k`) carry draws; the others are listed with their
score and crash rate only.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/capture_final_ranking.py

Writes final_ranking_draws.npz and final_ranking_meta.json next to this file. Changes no behaviour.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CAPTURED: dict = {}
SCALARS = (bool, int, float, str)


def _scalars(d: dict) -> dict:
    """The scalar fields of a dict, JSON-ready (numpy scalars included)."""
    out = {}
    for k, v in (d or {}).items():
        if hasattr(v, "item") and getattr(v, "ndim", 1) == 0:
            v = v.item()
        if v is None or isinstance(v, SCALARS):
            out[str(k)] = v
    return out


def extract(strategies, crash_sentinel_min: float) -> list[dict]:
    """One record per ranked plan, in ranking order; the draws are copied out as arrays."""
    import numpy as np

    items = []
    for rank, s in enumerate(strategies if isinstance(strategies, list) else []):
        if not isinstance(s, dict):
            continue
        strat = s.get("strategy") or {}
        levels = []
        for r in s.get("results_per_noise") or []:
            rmse = np.asarray(r.get("rmse_all") or [], dtype=np.float64).ravel()
            stopped = None
            try:
                th = np.asarray(r.get("thicknesses_all") or [], dtype=np.float64)
                if th.ndim == 2 and th.shape[0] == rmse.size and rmse.size > 0:
                    stopped = np.any(th > crash_sentinel_min, axis=1)
            except TypeError, ValueError:
                stopped = None
            levels.append({"scalars": _scalars(r), "rmse": rmse, "stopped": stopped})
        items.append(
            {
                "rank": rank,
                "result": _scalars(s),
                "strategy": _scalars(strat),
                "critical_layer": _scalars(s.get("critical_layer") or {}),
                "blocks": [_scalars(b) for b in (strat.get("blocks") or []) if isinstance(b, dict)],
                "levels": levels,
            }
        )
    return items


def save(items: list[dict], out_dir: Path, provenance=lambda d: d) -> tuple[Path, Path, int]:
    """Write the draws (npz, NaN-padded) and the metadata (json); return both paths and the number of plans with draws."""
    import numpy as np

    with_draws = [it for it in items if any(lv["rmse"].size for lv in it["levels"])]
    n_lv = max((len(it["levels"]) for it in with_draws), default=0)
    n_max = max((lv["rmse"].size for it in with_draws for lv in it["levels"]), default=0)
    rmse = np.full((len(with_draws), n_lv, n_max), np.nan)
    stopped = np.full((len(with_draws), n_lv, n_max), -1, dtype=np.int8)  # -1: unknown
    noise = np.full((len(with_draws), n_lv), np.nan)
    for i, it in enumerate(with_draws):
        for j, lv in enumerate(it["levels"]):
            n = lv["rmse"].size
            rmse[i, j, :n] = lv["rmse"]
            if lv["stopped"] is not None:
                stopped[i, j, :n] = lv["stopped"].astype(np.int8)
            noise[i, j] = float(lv["scalars"].get("noise_level", np.nan))
    draws, meta = out_dir / "final_ranking_draws.npz", out_dir / "final_ranking_meta.json"
    np.savez_compressed(
        draws,
        rmse=rmse,
        stopped=stopped,
        noise_level=noise,
        rank=np.asarray([it["rank"] for it in with_draws], dtype=np.int64),
    )
    listing = [
        {
            **{k: it[k] for k in ("rank", "result", "strategy", "critical_layer", "blocks")},
            "levels": [{**lv["scalars"], "n_draws": int(lv["rmse"].size)} for lv in it["levels"]],
        }
        for it in items
    ]
    payload = {"n_ranked": len(items), "n_with_draws": len(with_draws), "ranking": listing}
    meta.write_text(json.dumps(provenance(payload), indent=1), encoding="utf-8")
    return draws, meta, len(with_draws)


def main() -> None:
    import bench_examples as B
    from _artefact import avec_provenance

    B.qapp()
    B.autoanswer_dialogs(True)
    original = B.dump_strat_ranking

    def listening(strategies, *a, **kw):
        try:
            from certus_physics import CRASH_SENTINEL_MIN

            CAPTURED["items"] = extract(strategies, float(CRASH_SENTINEL_MIN))
        except Exception as exc:  # a probe never kills the run
            B.emit(f"CAPTURE_FAILED={exc!r}")
        return original(strategies, *a, **kw)

    B.dump_strat_ranking = listening
    B.emit("capture installed (final ranking, per-draw RMSE and stops)")

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")
    items = CAPTURED.get("items")
    if not items:
        B.emit("CAPTURE_EMPTY")
    else:
        draws, meta, n = save(items, HERE, avec_provenance)
        B.emit(f"CAPTURE_WRITTEN={draws.name} {meta.name} ranked={len(items)} with_draws={n}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
