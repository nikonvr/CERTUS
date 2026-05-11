# =============================================================================


# Helpers testables pour workers design (sans Qt) - même conventions que le GUI.


# =============================================================================


from __future__ import annotations


import logging


from typing import Any


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
