# =============================================================================


# Helpers testables pour workers design (sans Qt) - même conventions que le GUI.


# =============================================================================


from __future__ import annotations


import logging
import time

from typing import Any

from certus_core import CFG, NUMERICAL_FAULT_EXCEPTIONS, get_float_dtype
from certus_physics import PGlobalConfig, PGlobalOptimizer

import numpy as np


def optim_calc_oblique_selected(
    wls_arr: np.ndarray,
    n_front_T: np.ndarray,
    d_front_arr: np.ndarray,
    n_sub_arr: np.ndarray,
    angle: float,
    pol: str,
    *,
    has_back_calc: bool,
    has_back_stack: bool,
    d_back: np.ndarray,
    n_back_T: np.ndarray,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
):
    """Sélectionne le noyau oblique (front-only, backside nu, backside avec coating)."""

    if has_back_calc and has_back_stack:
        return calc_spectrum_full_oblique_exact(
            wls_arr,
            d_front_arr,
            n_front_T,
            d_back,
            n_back_T,
            n_sub_arr,
            float(angle),
            str(pol).lower() == "s",
        )

    if has_back_calc and (not has_back_stack):
        return calc_spectrum_oblique_backside_vectorized(wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol)

    return calc_spectrum_oblique_vectorized(wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol)


def optim_post_optim_time_budget_seconds(n_layers: int) -> float:
    """

    Budget (s) pour la chaîne post-optim (cleanup / healing / needle) selon le

    nombre de couches - même loi que ``CertusDesign._on_optim_done``.

    """

    n = max(int(n_layers), 0)

    if n <= 10:
        return 30.0

    if n <= 26:
        return 30.0 + (n - 10) * (180.0 - 30.0) / (26 - 10)

    return 180.0 + (n - 26) * (600.0 - 180.0) / (40 - 26)


def optim_backside_flags_from_cfg(
    cfg: dict[str, Any],
) -> tuple[bool, bool, list]:
    """

    Drapeaux backside comme dans OptimWorker.run :

    ``has_back_stack`` = coating arrière activé et pile non vide ;

    ``has_back_calc`` = calcul face arrière (Fresnel / pile) selon ``cfg['back']``.

    Retourne aussi ``stack_back`` (liste telle que dans la config).

    """

    back_enabled = bool(cfg.get("back", False))

    use_back = bool(cfg.get("use_back_coat", False))

    stack_back = cfg.get("stack_back", []) or []

    has_back_stack = use_back and len(stack_back) > 0

    has_back_calc = back_enabled

    return has_back_stack, has_back_calc, stack_back


def optim_oblique_unique_display_keys(valid_targets: list) -> list[tuple[Any, Any]]:
    """

    Clés (angle, pol) uniques pour tracés live, ordre de première apparition

    (même logique que OptimWorker.run).

    """

    display_keys: list[tuple[Any, Any]] = []

    seen: set[tuple[Any, Any]] = set()

    for tgt in valid_targets:
        key = (tgt.angle, tgt.pol)

        if key not in seen:
            seen.add(key)

            display_keys.append(key)

    return display_keys


def optim_oblique_group_targets_on_wavelengths(
    wls: np.ndarray,
    valid_targets: list,
) -> dict[tuple[Any, Any], dict[str, Any]]:
    """

    Regroupe les cibles obliques par (angle, pol) : indices ``clues``, valeurs cibles

    interpolées en lambda, types et poids (étape 1 avant assemblage ``oblique_configs``).

    """

    config_groups: dict[tuple[Any, Any], dict[str, Any]] = {}

    for tgt in valid_targets:
        mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)

        if not np.any(mask):
            continue

        key = (tgt.angle, tgt.pol)

        clues = np.where(mask)[0]

        if key not in config_groups:
            config_groups[key] = {"clues_set": set(), "targets": []}

        config_groups[key]["clues_set"].update(clues.tolist())

        wls_tgt = wls[clues]

        denom = max(tgt.lmax - tgt.lmin, 1e-9)

        slope = (tgt.tmax - tgt.tmin) / denom

        tgt_vals = tgt.tmin + slope * (wls_tgt - tgt.lmin)

        config_groups[key]["targets"].append(
            {
                "clues": clues,
                "tgt_vals": tgt_vals,
                "target_type": tgt.target_type,
                "weight": tgt.w,
            }
        )

    return config_groups


def optim_oblique_configs_from_groups(
    config_groups: dict[tuple[Any, Any], dict[str, Any]],
    wls: np.ndarray,
    n_sub: np.ndarray,
    n_layers_T: np.ndarray,
) -> list[dict[str, Any]]:
    """

    Pour chaque (angle, pol) : indices globaux triés, vues lambda / nk / épaisseurs,

    table idx->local (étape 2 dans OptimWorker.run).

    """

    oblique_configs: list[dict[str, Any]] = []

    for (angle, pol), group in config_groups.items():
        all_clues = np.array(sorted(group["clues_set"]), dtype=np.int64)

        idx_to_local = {idx: i for i, idx in enumerate(all_clues)}

        oblique_configs.append(
            {
                "angle": angle,
                "pol": pol,
                "is_s_pol": str(pol).lower() == "s",
                "all_clues": all_clues,
                "wls_config": wls[all_clues],
                "n_sub_config": n_sub[all_clues],
                "n_layers_T_config": n_layers_T[all_clues, :],
                "idx_to_local": idx_to_local,
                "targets": group["targets"],
            }
        )

    return oblique_configs


def optim_oblique_attach_local_positions(oblique_configs: list[dict[str, Any]]) -> None:
    """Remplit ``local_positions`` pour chaque entrée de ``targets`` (étape 3)."""

    for config in oblique_configs:
        idx_to_local = config["idx_to_local"]

        for tgt_data in config["targets"]:
            tgt_data["local_positions"] = np.array(
                [idx_to_local[i] for i in tgt_data["clues"]],
                dtype=np.int64,
            )


def optim_prepare_stack_nk_back(
    mats: dict[str, Any],
    stack: list,
    wls: np.ndarray,
    *,
    stack_back: list,
    ep_back: np.ndarray,
    has_back_stack: bool,
    complex_dtype,
    float_dtype,
    substrate_key: str = "Substrate",
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Indices nk(lambda) pour la pile avant, substrat (clé *substrate* en design),

    et piles / épaisseurs arrière si ``has_back_stack``.

    Aligné sur OptimWorker.run (préparation avant noyaux obliques).

    """

    mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

    # Robust substrate lookup: try provided key, then case-insensitive 'substrate'
    if substrate_key not in mats_nk:
        lower_mats = {k.lower(): k for k in mats_nk.keys()}
        fallback = lower_mats.get("substrate")
        if fallback:
            substrate_key = fallback

    n_sub = np.ascontiguousarray(mats_nk[substrate_key])

    n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

    n_layers_T = np.ascontiguousarray(n_layers.T)

    if has_back_stack:
        n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)

        n_back_T = np.ascontiguousarray(n_back.T)

        d_back = np.ascontiguousarray(ep_back, dtype=float_dtype)

    else:
        n_back_T = np.zeros((len(wls), 0), dtype=complex_dtype)

        d_back = np.zeros(0, dtype=float_dtype)

    return mats_nk, n_sub, n_layers_T, n_back_T, d_back


def optim_display_wavelength_grid(
    cfg: dict[str, Any],
    *,
    n_points: int = 300,
    margin_fraction: float = 0.20,
    wls_display_min_floor: float = 200.0,
    float_dtype=np.float64,
) -> np.ndarray:
    """

    Grille lambda pour tracés / rafraîchissement live : marge spectrale 20 % par défaut,

    plancher plausible 200 nm côté UV (aligné sur OptimWorker.__init__).

    """

    wls_min_cfg = float(cfg.get("wls_min", 380))

    wls_max_cfg = float(cfg.get("wls_max", 780))

    margin_min = wls_min_cfg * margin_fraction

    margin_max = wls_max_cfg * margin_fraction

    wls_min_display = max(wls_display_min_floor, wls_min_cfg - margin_min)

    wls_max_display = wls_max_cfg + margin_max

    return np.linspace(wls_min_display, wls_max_display, n_points).astype(float_dtype)


def optim_qwot_values_from_ep_stack(
    final_ep: np.ndarray,
    stack: list,
    mats: dict[str, Any],
    l0: float,
) -> list[float]:
    """

    Liste QWOT par couche : ``4 n d / lambda₀`` avec ``n`` depuis ``mats[layer.mat].n4``

    (ou dict ``n4``), aligné sur ``CertusDesign._on_optim_done`` (arrêt utilisateur).

    """

    ep = np.asarray(final_ep, dtype=np.float64).ravel()

    qw: list[float] = []

    for i, layer in enumerate(stack):
        d_val = float(ep[i]) if i < ep.size else 0.0

        mat_obj = mats.get(layer.mat)

        n_val = 1.45

        if mat_obj:
            if hasattr(mat_obj, "n4"):
                n_val = mat_obj.n4

            elif isinstance(mat_obj, dict):
                n_val = mat_obj.get("n4", 1.45)

        val = (4.0 * float(n_val) * d_val) / l0 if abs(l0) > 1e-9 else 0.0

        qw.append(val)

    return qw


def optim_var_indices_from_stack(stack: list) -> np.ndarray:
    """Indices des couches d’épaisseur optimisable (``layer.var``), comme dans OptimWorker.run."""

    return np.array([i for i, layer in enumerate(stack) if layer.var], dtype=np.int64)


def optim_bounds_thickness_local(
    ep0: np.ndarray,
    var_idx: np.ndarray,
    delta_nm: float,
    *,
    float_dtype=np.float64,
) -> np.ndarray:
    """Bornes +/-Deltanm autour des épaisseurs initiales (mode ``local`` OptimWorker)."""

    ep = np.asarray(ep0, dtype=float_dtype).ravel()

    rows = [(max(0.0, float(ep[int(i)]) - delta_nm), float(ep[int(i)]) + delta_nm) for i in var_idx]

    return np.array(rows, dtype=float_dtype)


def optim_bounds_thickness_healing(
    ep0: np.ndarray,
    var_idx: np.ndarray,
    stack: list,
    mats: dict[str, Any],
    l0: float,
    *,
    float_dtype=np.float64,
) -> np.ndarray:
    """

    Bornes healing : Deltad = lambda₀/(10·n(lambda₀)) (mode ``healing`` OptimWorker).

    """

    ep = np.asarray(ep0, dtype=float_dtype).ravel()

    wls_l0 = np.array([float(l0)], dtype=float_dtype)

    bounds_list: list[tuple[float, float]] = []

    for i in var_idx:
        ii = int(i)

        mat_obj = mats.get(stack[ii].mat)

        n_val = 1.45

        if mat_obj:
            try:
                n_val = float(mat_obj.get_nk(wls_l0)[0].real)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.warning(f"Could not get n for bounds (using 1.45): {e}")

        delta_d = float(l0) / (10.0 * max(n_val, 1.0))

        bounds_list.append(
            (
                max(0.0, float(ep[ii]) - delta_d),
                max(float(ep[ii]) + delta_d, delta_d),
            )
        )

    return np.array(bounds_list, dtype=float_dtype)


def optim_bounds_thickness_global(
    ep0: np.ndarray,
    var_idx: np.ndarray,
    stack: list,
    mats: dict[str, Any],
    l0: float,
    *,
    float_dtype=np.float64,
) -> np.ndarray:
    """Borne basse 0, haute max(limite physique, 1.2×ep₀) - mode global OptimWorker."""

    ep = np.asarray(ep0, dtype=float_dtype).ravel()

    rows = []

    lf = float(l0)

    for i in var_idx:
        ii = int(i)

        n4 = float(mats[stack[ii].mat].n4)

        upper = max(1.2 * lf / (4.0 * n4), float(ep[ii]) * 1.2)

        rows.append((0.0, upper))

    return np.array(rows, dtype=float_dtype)


def optim_rmse_is_valid_for_log(rmse: Any) -> bool:
    """True si la RMSE est définie, finie et >= 0 (affichage / logs design)."""

    return bool(rmse is not None and np.isfinite(rmse) and float(rmse) >= 0.0)


def optim_rmse_display_string(rmse: Any, *, ndigits: int = 6) -> str:
    """Format fixe pour logs ou la chaîne N/A - aligné ``CertusDesign._on_optim_done``."""

    if not optim_rmse_is_valid_for_log(rmse):
        return "N/A"

    return f"{float(rmse):.{ndigits}f}"


def build_pglobal_config_from_cfg(
    cfg: dict[str, Any],
    *,
    mode: str,
    dim: int,
    conv_tol: float,
) -> tuple[PGlobalConfig, int]:
    """Build PGlobal configuration and max iteration budget from mode and dimensions."""
    if mode == "local":
        pg_conf = PGlobalConfig.for_local(
            dim=dim,
            max_feval=cfg.get("max_feval", 10000),
            convergence_tol=conv_tol,
        )
        max_iter_run = 15
    elif mode == "healing":
        scale = max(1.0, dim / 10.0)
        pg_conf = PGlobalConfig(
            n_samples_per_iter=int(1000 * scale),
            alpha=0.02,
            reduction_ratio=0.3,
            local_search_budget=10000,
            max_active_clusters=min(20, max(5, dim)),
            max_feval=cfg.get("max_feval", 50000000),
            convergence_tol=conv_tol,
        )
        max_iter_run = cfg.get("max_iter", 10)
    else:
        pg_conf = PGlobalConfig.for_dimension(
            dim=dim,
            base_samples=cfg.get("n100", 6000),
            max_feval=cfg.get("max_feval", 50000000),
        )
        user_clusters = cfg.get("max_clusters")
        overrides = {}
        if user_clusters is not None:
            overrides["max_active_clusters"] = user_clusters
        if conv_tol != 1e-8:
            overrides["convergence_tol"] = conv_tol
        if "alpha" in cfg:
            overrides["alpha"] = cfg["alpha"]
        if "reduction_ratio" in cfg:
            overrides["reduction_ratio"] = cfg["reduction_ratio"]
        if "local_search_budget" in cfg:
            overrides["local_search_budget"] = cfg["local_search_budget"]
        if overrides:
            pg_conf = pg_conf.with_overrides(**overrides)
        max_iter_run = cfg.get("max_iter", 50)

    return pg_conf, int(max_iter_run)


def prepare_pglobal_inputs_from_state(
    *,
    var_idx: list[int],
    mode: str,
    cfg: dict[str, Any],
    signal_emit,
    gradient_func,
) -> tuple[int, Any, PGlobalConfig, int]:
    """Build PGlobal preamble objects and emit initial progress line."""
    dim = len(var_idx)
    conv_tol = 1e-8
    pg_conf, max_iter_run = build_pglobal_config_from_cfg(
        cfg=cfg,
        mode=mode,
        dim=dim,
        conv_tol=conv_tol,
    )
    signal_emit(0, f"Config:  dim={dim}, samples/iter={pg_conf.n_samples_per_iter}")
    return dim, gradient_func, pg_conf, max_iter_run


def build_pglobal_optimizer(
    *,
    objective_wrapper,
    bounds,
    stop_event,
    pg_conf,
    x0_start,
    gradient_func,
):
    """Instantiate a PGlobalOptimizer with the standard CERTUS wiring."""
    return PGlobalOptimizer(
        objective_wrapper,
        bounds,
        config=pg_conf,
        stop_event=stop_event,
        x0=x0_start,
        gradient_func=gradient_func,
    )


def prepare_pglobal_optimizer_runtime(
    *,
    optimizer,
    mode: str,
    max_iter_run: int,
    dim: int,
    progress_emit,
    best_rmse_seen: float,
    callback_counter: int,
) -> tuple[Any, float]:
    """Emit progress/log preamble and return optimizer + start timestamp."""
    if mode == "local":
        progress_emit(0, "Fast Local Polish (PGLOBAL)...")
    elif mode == "healing":
        progress_emit(0, "Healing: Restricted Global Search (+/-Deltad)...")
    else:
        progress_emit(0, "Starting PGLOBAL Global Optimization...")

    opt_start_time = time.time()
    logging.info(f"OptimWorker: Starting PGLOBAL optimization - mode={mode}, max_iter={max_iter_run}, dim={dim}")
    logging.info(
        f"OptimWorker: Initial state - best_rmse_seen={best_rmse_seen:.6e}, callback_counter={callback_counter}"
    )
    return optimizer, opt_start_time


def run_pglobal_restart_loop(
    *,
    mode: str,
    optimizer,
    objective_wrapper,
    bounds,
    pg_conf,
    gradient_func_to_use,
    max_iter_run: int,
    callback,
    opt_start_time: float,
    stop_event,
    progress_emit,
    cfg: dict[str, Any],
    callback_counter_getter,
    set_optimizer,
):
    """Run the auto-restart loop and return the best sample found."""
    best_sample_overall = None
    restarts = 3 if mode == "global" else 1
    restart_no_gain = 0
    restart_rel_gain_min = float(cfg.get("restart_rel_gain_min", 2e-4))
    restart_no_gain_patience = int(cfg.get("restart_no_gain_patience", 1))

    for restart_idx in range(restarts):
        if stop_event.is_set():
            break

        if restarts > 1:
            progress_emit(0, f"Starting PGLOBAL Auto-Restart {restart_idx + 1}/{restarts}...")

        if restart_idx > 0 and best_sample_overall is not None:
            optimizer = PGlobalOptimizer(
                objective_wrapper,
                bounds,
                config=pg_conf,
                stop_event=stop_event,
                x0=best_sample_overall.x.copy(),
                gradient_func=gradient_func_to_use,
            )
            set_optimizer(optimizer)

        try:
            prev_best_y = best_sample_overall.y if best_sample_overall is not None else float("inf")
            best_sample = optimizer.optimize(max_iter=max_iter_run, callback=callback)
            opt_time = time.time() - opt_start_time
            logging.info(
                f"OptimWorker [Restart {restart_idx + 1}]: optimizer.optimize() returned after {opt_time:.2f}s - best_sample={best_sample is not None}, callback_count={callback_counter_getter()}"
            )
            if best_sample:
                logging.info(
                    f"OptimWorker [Restart {restart_idx + 1}]: Best sample - rmse={np.sqrt(best_sample.y):.6e}, n_evals={optimizer.n_evals}"
                )
                if best_sample_overall is None or best_sample.y < best_sample_overall.y:
                    best_sample_overall = best_sample

            curr_best_y = best_sample_overall.y if best_sample_overall is not None else float("inf")
            if np.isfinite(prev_best_y) and np.isfinite(curr_best_y):
                rel_gain = (prev_best_y - curr_best_y) / max(abs(prev_best_y), 1e-12)
                if rel_gain < restart_rel_gain_min:
                    restart_no_gain += 1
                else:
                    restart_no_gain = 0
            else:
                restart_no_gain = 0

            if mode == "global" and restart_idx < restarts - 1 and restart_no_gain > restart_no_gain_patience:
                logging.info(
                    "OptimWorker: auto-restart stopped on stagnation "
                    f"({restart_no_gain} consecutive restart(s) below {restart_rel_gain_min * 100:.3f}% gain)."
                )
                break
        except NUMERICAL_FAULT_EXCEPTIONS as opt_err:
            opt_time = time.time() - opt_start_time
            logging.error(
                f"OptimWorker: Error during optimizer.optimize() after {opt_time:.2f}s: {opt_err}",
                exc_info=True,
            )
            raise

    return best_sample_overall


def run_coord_descent_5cycles(
    *,
    ep_current,
    best_cost,
    var_idx,
    oblique_mode,
    compute_oblique_error,
    compute_oblique_error_and_grad_analytic,
    n_layers_T,
    n_sub,
    wls,
    tgt_vals,
    tgt_weights,
    has_back_calc,
    n_back_T,
    d_back,
    cfg: dict[str, Any],
    evaluate_thicknesses,
    get_gradient_analytic,
    progress_emit,
    best_rmse_seen: float,
):
    """Run the final 5-cycle refinement and return updated state."""
    use_gradient = True
    cycle_no_gain = 0
    cycle_rel_gain_min = float(cfg.get("cycle_rel_gain_min", 2e-4))
    cycle_no_gain_patience = int(cfg.get("cycle_no_gain_patience", 1))

    for cycle in range(5):
        cycle_start_best = float(best_cost)
        ep_current.copy()
        float_dtype = get_float_dtype()
        n_vars = len(var_idx)
        steps = np.full(n_vars, 2.0, dtype=float_dtype)
        min_step_val = 1e-4
        min_steps = np.full(n_vars, min_step_val, dtype=float_dtype)

        if use_gradient:
            for _ in range(50):
                try:
                    cost_curr, grad = get_gradient_analytic(
                        ep_current,
                        oblique_mode=oblique_mode,
                        compute_oblique_error_and_grad_analytic=compute_oblique_error_and_grad_analytic,
                        n_layers_T=n_layers_T,
                        n_sub=n_sub,
                        wls=wls,
                        tgt_vals=tgt_vals,
                        tgt_weights=tgt_weights,
                        has_back_calc=has_back_calc,
                        n_back_T=n_back_T,
                        d_back=d_back,
                        var_idx=var_idx,
                    )
                    if cost_curr < best_cost:
                        best_cost = cost_curr
                    grad_norm = np.linalg.norm(grad)
                    if grad_norm < 1e-8:
                        break
                    direction = -grad / grad_norm
                    alpha = 2.0
                    improved_step = False
                    for _ in range(10):
                        ep_trial = ep_current.copy()
                        for i, v_idx in enumerate(var_idx):
                            ep_trial[v_idx] += alpha * direction[i]
                            ep_trial[v_idx] = max(CFG.MIN_THICKNESS, ep_trial[v_idx])
                        cost_trial = evaluate_thicknesses(
                            ep_trial,
                            oblique_mode=oblique_mode,
                            compute_oblique_error=compute_oblique_error,
                            n_layers_T=n_layers_T,
                            n_sub=n_sub,
                            wls=wls,
                            tgt_vals=tgt_vals,
                            tgt_weights=tgt_weights,
                            has_back_calc=has_back_calc,
                            n_back_T=n_back_T,
                            d_back=d_back,
                        )
                        if cost_trial < best_cost - 1e-8 * alpha * grad_norm:
                            ep_current = ep_trial
                            best_cost = cost_trial
                            improved_step = True
                            break
                        alpha *= 0.5
                    if not improved_step:
                        break
                except (ValueError, RuntimeError, np.linalg.LinAlgError) as e:
                    logging.debug(f"Gradient optimization failed, fallback to coordinate descent: {e}")
                    use_gradient = False
                    break

        if not use_gradient:
            for _ in range(200):
                improved = False
                for i, v_idx in enumerate(var_idx):
                    if steps[i] < min_steps[i]:
                        continue
                    original_val = ep_current[v_idx]
                    step = steps[i]
                    ep_current[v_idx] = max(CFG.MIN_THICKNESS, original_val + step)
                    cost_plus = evaluate_thicknesses(
                        ep_current,
                        oblique_mode=oblique_mode,
                        compute_oblique_error=compute_oblique_error,
                        n_layers_T=n_layers_T,
                        n_sub=n_sub,
                        wls=wls,
                        tgt_vals=tgt_vals,
                        tgt_weights=tgt_weights,
                        has_back_calc=has_back_calc,
                        n_back_T=n_back_T,
                        d_back=d_back,
                    )
                    if cost_plus < best_cost:
                        best_cost = cost_plus
                        steps[i] *= 1.2
                        improved = True
                        continue
                    ep_current[v_idx] = max(CFG.MIN_THICKNESS, original_val - step)
                    cost_minus = evaluate_thicknesses(
                        ep_current,
                        oblique_mode=oblique_mode,
                        compute_oblique_error=compute_oblique_error,
                        n_layers_T=n_layers_T,
                        n_sub=n_sub,
                        wls=wls,
                        tgt_vals=tgt_vals,
                        tgt_weights=tgt_weights,
                        has_back_calc=has_back_calc,
                        n_back_T=n_back_T,
                        d_back=d_back,
                    )
                    if cost_minus < best_cost:
                        best_cost = cost_minus
                        steps[i] *= 1.2
                        improved = True
                    else:
                        ep_current[v_idx] = original_val
                        steps[i] *= 0.5
                if not improved:
                    break

        current_rmse = np.sqrt(best_cost) if best_cost < 1e20 else 1e9
        if current_rmse < best_rmse_seen:
            best_rmse_seen = current_rmse
        progress_emit(95 + cycle, f"Refine cycle {cycle + 1}/5 - RMSE: {current_rmse:.6f}")
        if np.isfinite(cycle_start_best) and np.isfinite(best_cost):
            rel_gain_cycle = (cycle_start_best - best_cost) / max(abs(cycle_start_best), 1e-12)
            if rel_gain_cycle < cycle_rel_gain_min:
                cycle_no_gain += 1
            else:
                cycle_no_gain = 0
            if cycle_no_gain > cycle_no_gain_patience:
                logging.info(
                    "OptimWorker: final refinement stopped on stagnation "
                    f"({cycle_no_gain} cycle(s) below {cycle_rel_gain_min * 100:.3f}% gain)."
                )
                break

    return ep_current, best_cost, best_rmse_seen


def maybe_upgrade_grid_tikhonravov(
    *,
    ep_current,
    mats,
    stack,
    tgts,
    oblique_mode,
    oblique_tgts,
    wls,
    float_dtype,
    complex_dtype,
    has_back_stack,
    stack_back,
    ep_back,
    n_sub,
    n_layers_T,
    n_back_T,
    tgt_vals,
    tgt_weights,
):
    """Optionally densify the wavelength grid before final refinement."""
    try:
        lambda_min = min(t.lmin for t in tgts if t.valid()) if not oblique_mode else min(t.lmin for t in oblique_tgts if t.valid())
        lambda_max = max(t.lmax for t in tgts if t.valid()) if not oblique_mode else max(t.lmax for t in oblique_tgts if t.valid())
        wl_ref = (lambda_min + lambda_max) / 2.0
        L_total = 0.0
        for i, layer in enumerate(stack):
            if i >= len(ep_current):
                continue
            mat_obj = mats.get(layer.mat)
            if mat_obj:
                n_ref = mat_obj.get_nk(np.array([wl_ref]))[0].real
                L_total += n_ref * ep_current[i]
        if L_total > 1e-6 and lambda_max > lambda_min:
            nu_min = 1.0 / lambda_max
            nu_max = 1.0 / lambda_min
            delta_nu = nu_max - nu_min
            marge = 10.0
            N_tikhon = int(np.ceil(2.0 * L_total * delta_nu * marge))
            N_tikhon = max(10, min(5000, N_tikhon))
            current_n_points = len(wls)
            if N_tikhon > current_n_points * 1.15:
                logging.info(
                    f"Tikhonravov: Upgrading grid from {current_n_points} to {N_tikhon} points for final refinement"
                )
                active_tgts_for_grid = [t for t in (oblique_tgts if oblique_mode else tgts) if t.valid()]
                wls_list_new = []
                for t in active_tgts_for_grid:
                    start = max(t.lmin, 1e-3)
                    end = max(t.lmax, start + 1e-3)
                    sigma_min = 1.0 / end
                    sigma_max = 1.0 / start
                    sigma_grid = np.linspace(sigma_min, sigma_max, N_tikhon)
                    wls_list_new.append(1.0 / sigma_grid)
                wls = np.unique(np.concatenate(wls_list_new))
                wls = np.ascontiguousarray(wls.astype(float_dtype))
                mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
                _sub_key = "substrate" if "substrate" in mats_nk else "Substrate"
                n_sub = np.ascontiguousarray(mats_nk[_sub_key])
                n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)
                n_layers_T = np.ascontiguousarray(n_layers.T)
                if has_back_stack:
                    n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)
                    n_back_T = np.ascontiguousarray(n_back.T)
                if not oblique_mode:
                    tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
                else:
                    config_groups = optim_oblique_group_targets_on_wavelengths(wls, [t for t in oblique_tgts if t.valid()])
                    oblique_configs = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T)
                    optim_oblique_attach_local_positions(oblique_configs)
                logging.info(f"Tikhonravov: Grid upgraded successfully to {len(wls)} points")
    except NUMERICAL_FAULT_EXCEPTIONS as tikhon_err:
        logging.warning(f"Tikhonravov grid update failed, using original grid: {tikhon_err}")

    return wls, n_sub, n_layers_T, n_back_T, tgt_vals, tgt_weights


def build_needle_scan_mask(
    stack: list,
    mats_nk: dict,
    *,
    excluded_layers: list | set | tuple | None = None,
) -> tuple[list[str], np.ndarray]:
    """Build per-layer candidate needle material names and scan mask."""
    N = len(stack)
    excluded = set(excluded_layers or [])
    needle_mat_names = [""] * N
    scan_mask = np.zeros(N, dtype=np.int64)
    for i, layer in enumerate(stack):
        if i in excluded:
            continue
        nm = "L" if layer.mat == "H" else "H"
        if nm in mats_nk:
            needle_mat_names[i] = nm
            scan_mask[i] = 1
    return needle_mat_names, scan_mask
