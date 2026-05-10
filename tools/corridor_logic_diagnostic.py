#!/usr/bin/env python3
"""Diagnostic hors-UI pour la **logique** du corridor d-profiling.

Objectif: produire un artefact lisible par machine (JSON) qui résume où la procédure
entre en tension (seuil RMSE vs échantillon, intervalle rapporté vs meilleur point,
dégénérescence latérale, seed-gate saturé). À utiliser pour guider une IA —
ou un humain — vers des réglages / évolutions du code dans ``spline_profile_corridors.py``
et ``spline_pipeline.py``.

Usage (depuis la racine du dépôt)::

    python tools/corridor_logic_diagnostic.py
    python tools/corridor_logic_diagnostic.py --json-out corridor_diag.json --verbose

Ce n'est pas un benchmark de temps; pour la perf CPU voir ``bench_corridor_*.py``.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
from spline_profile_corridors import ProfileCorridorConfig, compute_profiled_corridors_by_d


def _lam(lo: float, hi: float, n: int) -> np.ndarray:
    return np.linspace(lo, hi, int(n), dtype=np.float64)


def _synthetic_base(lam: np.ndarray) -> dict[str, Any]:
    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))
    k = int(sk.size)
    return {
        "sigma_knots": sk,
        "d_nm": 2000.0,
        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),
        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),
        "rmse": 0.01,
        "spectral_rmse_segments": 0.01,
        "n_lam": np.full(lam.size, 1.65, dtype=np.float64),
        "k_lam": np.full(lam.size, 1e-3, dtype=np.float64),
    }


def _cfg_default(lam: np.ndarray) -> SplineOptConfig:
    return SplineOptConfig(
        lam_nm=np.asarray(lam, dtype=np.float64),
        t_exp=0.6 * np.ones_like(lam, dtype=np.float64),
        r_exp=None,
        n_sub=np.full_like(lam, 1.52, dtype=np.float64),
        data_type=DataType.TRANSMISSION,
        n_seg=5,
        d_lo=500.0,
        d_hi=4000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="CorridorDiag",
        t_is_ratio=False,
        corridor_profile_d_enabled=True,
        polish_maxfun=300,
        corridor_profile_d_polish_maxfun=300,
        corridor_profile_d_parallel_walks=False,
    )


def _pconf_from_args(args: argparse.Namespace) -> ProfileCorridorConfig:
    return ProfileCorridorConfig(
        enabled=True,
        mode=str(args.mode),
        rmse_alpha=float(args.rmse_alpha),
        rmse_threshold_mode=str(args.rmse_threshold_mode),
        rmse_abs_tolerance=float(args.rmse_abs_tolerance),
        scientific_nominal_corridor=bool(args.scientific_nominal),
        step_nm=float(args.step_nm),
        step_nm_initial=float(args.step_nm_initial),
        max_span_nm=float(args.max_span_nm),
        max_steps_each_side=int(args.max_steps_each_side),
        refine_boundary=bool(args.refine_boundary),
        min_valid_points=int(args.min_valid_points),
        min_valid_each_side=int(args.min_valid_each_side),
        n_starts=int(args.n_starts),
        rng_seed=int(args.rng_seed),
        lr_conf_level=float(args.lr_conf_level),
    )


def _build_report(
    *,
    base: dict[str, Any],
    extra: dict[str, Any],
    promotion_fields: dict[str, Any],
) -> dict[str, Any]:
    d0 = float(base.get("d_nm", float("nan")))
    d_arr = np.asarray(extra.get("profile_d_values_nm", []), dtype=np.float64).ravel()
    rm_arr = np.asarray(extra.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
    status = str(extra.get("profile_d_status", "") or "")
    interval = extra.get("profile_d_interval_nm")
    rmse_ref = float(extra.get("profile_d_rmse_opt", float("nan")))
    rmse_thresh = float(extra.get("profile_d_rmse_thresh", float("nan")))

    report: dict[str, Any] = {
        "profile_d_status": status,
        "sample_count": int(d_arr.size),
        "d0_nm": d0,
        "rmse_ref_reported": rmse_ref,
        "rmse_thresh_active_reported": rmse_thresh,
        "pos_valid_side": int(extra.get("profile_d_valid_side_pos", -1)),
        "neg_valid_side": int(extra.get("profile_d_valid_side_neg", -1)),
        "seed_gate_eval_count": extra.get("profile_d_seed_gate_eval_count"),
        "seed_gate_kept_count": extra.get("profile_d_seed_gate_kept_count"),
        "seed_gate_kept_rate": extra.get("profile_d_seed_gate_kept_rate"),
        "seed_gate_saturated": extra.get("profile_d_seed_gate_saturated"),
        "parabola_ok": extra.get("profile_d_parabola_ok"),
        "interval_reported_nm": list(interval) if isinstance(interval, (tuple, list)) else None,
        "promotion_simulation": promotion_fields,
    }

    if d_arr.size > 0 and rm_arr.size == d_arr.size and np.any(np.isfinite(rm_arr)):
        m = np.isfinite(d_arr) & np.isfinite(rm_arr)
        if np.any(m):
            i_best = int(np.argmin(np.where(m, rm_arr, np.inf)))
            best_d = float(d_arr[i_best])
            best_rm = float(rm_arr[i_best])
            report["argmin_rmse_index"] = i_best
            report["best_d_nm"] = best_d
            report["best_rmse"] = best_rm
            report["gain_vs_rmse_ref"] = float(rmse_ref - best_rm) if np.isfinite(rmse_ref) else None

            interval_outside = False
            if isinstance(interval, (tuple, list)) and len(interval) == 2:
                try:
                    lo, hi = float(interval[0]), float(interval[1])
                    mn, mx = min(lo, hi), max(lo, hi)
                    interval_outside = best_d < mn - 1e-9 or best_d > mx + 1e-9
                except (TypeError, ValueError):
                    pass
            report["best_d_outside_symmetric_reported_interval"] = bool(interval_outside)

            if np.isfinite(rmse_thresh) and np.isfinite(best_rm):
                report["rmse_thresh_minus_best_rmse"] = float(rmse_thresh - best_rm)

    hints: list[str] = []
    if status.lower() == "degenerate":
        hints.append(
            "Corridor marqué dégénéré: vérifier min_valid_each_side, span de d, ou si un seul côté produit des refits admissibles."
        )
    if extra.get("profile_d_seed_gate_saturated"):
        hints.append(
            "Seed-gate saturé: beaucoup de refits gardent la graine — augmenter polish_maxfun, vérifier refit_pure_spectral, ou jitter n_starts."
        )
    if report.get("best_d_outside_symmetric_reported_interval"):
        hints.append(
            "Le meilleur RMSE tombe hors de l’intervalle d symétrisé rapporté — normal si asymétrie forte; à corréler avec force_symmetric_interval."
        )
    thr_m = float(report.get("rmse_thresh_minus_best_rmse", float("nan")))
    if math.isfinite(thr_m) and thr_m < 0:
        hints.append(
            "Meilleur RMSE au-dessus du seuil actif: soit pas de famille admissible cohérente, soit seulement points nominaux / dégénérés."
        )

    report["coaching_hypotheses"] = hints
    return report


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnostic logique du corridor d-profiling (sortie JSON).")
    ap.add_argument("--n-lam", type=int, default=24, help="Nombre de points spectraux (synthèse).")
    ap.add_argument("--json-out", type=Path, default=None, help="Écrire le rapport JSON sur disque.")
    ap.add_argument("--verbose", action="store_true", help="Logs INFO du module corridor.")
    ap.add_argument("--mode", default="alpha", choices=["alpha", "lr"], help="Mode walk ProfileCorridorConfig.")
    ap.add_argument("--rmse-threshold-mode", default="alpha", dest="rmse_threshold_mode")
    ap.add_argument("--rmse-alpha", type=float, default=1.15)
    ap.add_argument("--rmse-abs-tolerance", type=float, default=2.5e-4)
    ap.add_argument("--scientific-nominal", action="store_true", help="Activer scientific_nominal_corridor sur le pconf.")
    ap.add_argument("--step-nm", type=float, default=12.0)
    ap.add_argument("--step-nm-initial", type=float, default=12.0)
    ap.add_argument("--max-span-nm", type=float, default=48.0)
    ap.add_argument("--max-steps-each-side", type=int, default=4)
    ap.add_argument("--refine-boundary", action="store_true")
    ap.add_argument("--min-valid-points", type=int, default=1)
    ap.add_argument("--min-valid-each-side", type=int, default=1)
    ap.add_argument("--n-starts", type=int, default=1)
    ap.add_argument("--rng-seed", type=int, default=0)
    ap.add_argument("--lr-conf-level", type=float, default=0.95)
    ap.add_argument("--profile-polish-maxfun", type=int, default=300)
    ap.add_argument("--simulate-promotion", action="store_true", help="Simuler _maybe_promote_best_corridor_refit (spline_pipeline).")
    args = ap.parse_args()

    log = logging.getLogger("CERTUS")
    log.setLevel(logging.INFO if args.verbose else logging.WARNING)

    lam = _lam(400.0, 800.0, args.n_lam)
    base = _synthetic_base(lam)
    cfg = _cfg_default(lam)
    pconf = _pconf_from_args(args)

    # Cas scientifique nominal: enrichir la base comme le ferait le pipeline (minimal).
    if args.scientific_nominal:
        sk = np.asarray(base["sigma_knots"], dtype=np.float64).ravel()
        k = int(sk.size)
        x_seg = np.concatenate(
            (
                np.asarray([float(base["d_nm"])], dtype=np.float64),
                np.full(k, 1.65, dtype=np.float64),
                np.full(k, np.log(1e-3), dtype=np.float64),
            )
        )
        base["spectral_rmse_best_value"] = float(base["spectral_rmse_segments"])
        base["spectral_rmse_best_label"] = "diag_synthetic"
        base["spectral_rmse_seg_spline_sigma"] = float(base["spectral_rmse_segments"])
        base["n_lam_seg_spline_sigma"] = np.asarray(base["n_lam"], dtype=np.float64).copy()
        base["k_lam_seg_spline_sigma"] = np.asarray(base["k_lam"], dtype=np.float64).copy()
        base["d_nm_seg_spline_sigma"] = float(base["d_nm"])
        base["x_seg_spline_sigma"] = x_seg

    extra = compute_profiled_corridors_by_d(
        cfg,
        base,
        pconf=pconf,
        profile_polish_maxfun=int(args.profile_polish_maxfun),
        log_coaching=False,
    )
    if not extra:
        print(json.dumps({"error": "compute_profiled_corridors_by_d returned empty"}, indent=2))
        return 1

    promotion_fields: dict[str, Any] = {"simulated": False}
    if args.simulate_promotion:
        from spline_pipeline import _maybe_promote_best_corridor_refit

        out = dict(base)
        out.update(extra)
        _maybe_promote_best_corridor_refit(cfg, out, extra, log)
        promotion_fields = {
            "simulated": True,
            "profile_d_promoted": bool(out.get("profile_d_promoted", False)),
            "profile_d_promoted_from_rmse": out.get("profile_d_promoted_from_rmse"),
            "profile_d_promoted_to_rmse": out.get("profile_d_promoted_to_rmse"),
            "profile_d_promoted_from_d_nm": out.get("profile_d_promoted_from_d_nm"),
            "profile_d_promoted_to_d_nm": out.get("profile_d_promoted_to_d_nm"),
            "profile_d_promoted_from_status": out.get("profile_d_promoted_from_status"),
            "profile_d_promoted_seed_state": out.get("profile_d_promoted_seed_state"),
        }

    report = _build_report(base=base, extra=extra, promotion_fields=promotion_fields)
    report["pconf_summary"] = {
        "mode": args.mode,
        "rmse_threshold_mode": args.rmse_threshold_mode,
        "rmse_alpha": args.rmse_alpha,
        "scientific_nominal": bool(args.scientific_nominal),
        "step_nm": args.step_nm,
        "max_span_nm": args.max_span_nm,
        "min_valid_each_side": args.min_valid_each_side,
        "n_starts": args.n_starts,
    }

    safe = _json_safe(report)
    text = json.dumps(safe, indent=2, ensure_ascii=False)
    print(text)
    if args.json_out is not None:
        args.json_out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
