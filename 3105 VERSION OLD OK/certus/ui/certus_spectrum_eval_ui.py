# =============================================================================

# UI d'evaluation spectrale partagee  CERTUS_DESIGN + CERTUS_RE

# =============================================================================

from __future__ import annotations


import copy

import logging

import time

from typing import Any, Dict, Literal


import numpy as np

import pyqtgraph as pg


from certus.ui.certus_ui import CertusTheme


SpectrumEvalVariant = Literal["design", "re"]


def spectrum_eval_feedback(app: Any, message: str, level: str = "info") -> None:
    """Best-effort premium feedback for spectrum evaluation workflows."""
    try:
        from certus.ui.certus_ui import show_status_feedback

        show_status_feedback(app, message, level, duration_ms=1200)
    except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
        try:
            if hasattr(app, "status_label"):
                app.status_label.setText(message)
            if hasattr(app, "lbl_status"):
                app.lbl_status.setText(message)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            pass


def spectrum_eval_substrate_key(variant: SpectrumEvalVariant) -> str:

    return "Substrate"


def spectrum_eval_n_vis_points(app: Any, variant: SpectrumEvalVariant) -> int:

    if variant == "re" and getattr(app, "_re_loaded", False) and app.oblique_mode:
        return 1000

    return 2000


def spectrum_eval_on_finished_prepare_display(
    app: Any,
    data: Dict[str, Any],
    generation_id: int | None,
) -> Dict[str, Any] | None:
    """

    Controle de generation (stale), snapshot RMSE, politique d'affichage monotone.

    Retourne ``None`` si le callback est obsolete (``_set_busy(False)`` deja appele).

    Sinon retourne ``data_for_display`` pour la suite de ``_on_eval_finished``.

    """

    logging.info(
        "[SPECTRUM_EVAL._on_eval_finished] callback received | oblique=%s | generation_id=%s | current_generation=%s",
        data.get('oblique_mode', False),
        generation_id,
        getattr(app, '_current_eval_generation', None),
    )

    result_generation = data.get("eval_generation_id", generation_id)

    if result_generation != app._current_eval_generation:
        logging.debug(
            "[SPECTRUM_EVAL._on_eval_finished] ignored stale callback | result_gen=%s | current_gen=%s",
            result_generation,
            app._current_eval_generation,
        )

        app._set_busy(False)

        return None

    incoming_rmse = data.get("rmse")

    incoming_rmse_valid = app._is_valid_rmse_value(incoming_rmse)

    if incoming_rmse_valid:
        app._store_best_eval_snapshot(data)

    data_for_display = data

    if (
        app._monotonic_visual_mode_enabled()
        and incoming_rmse_valid
        and app._best_eval_result is not None
        and incoming_rmse > app._best_eval_rmse + 1e-12
    ):
        data_for_display = copy.deepcopy(app._best_eval_result)

        data_for_display["eval_generation_id"] = result_generation

        logging.info(
            "[SPECTRUM_EVAL._on_eval_finished] keeping best visual spectrum | incoming_rmse=%.6f | best_rmse=%.6f",
            incoming_rmse,
            app._best_eval_rmse,
        )

        try:
            ep_best = np.asarray(data_for_display.get("ep", []), dtype=float).flatten()

            if ep_best.size > 0:
                app._update_qwot_from_ep(ep_best)

                app._update_thickness_display()

                app.ep_current = ep_best.copy()

                app._use_exact_ep = True

        except (
            ValueError,
            TypeError,
            RuntimeError,
            AttributeError,
            KeyError,
            IndexError,
            FileNotFoundError,
        ) as _e_best_sync:
            logging.debug(
                "[SPECTRUM_EVAL._on_eval_finished] best spectrum/table sync skipped | error=%s",
                _e_best_sync,
            )

    return data_for_display


def spectrum_eval_run_preamble(app: Any, run_eval_cb: Any) -> bool:
    """

    Warmup gate + viz_stack. Returns False if caller must return (possibly rescheduled).

    """

    if not app._warmup_done:
        # Evite un double message si plusieurs eval sont planifies avant fin warmup.

        if not getattr(app, "_spectrum_eval_jit_wait_logged", False):
            app.log("Waiting for JIT compilation...", "WARNING")

            app._spectrum_eval_jit_wait_logged = True

        from PyQt6.QtCore import QTimer

        QTimer.singleShot(500, run_eval_cb)

        return False

    if app.viz_stack.currentIndex() == 0:
        app.viz_stack.setCurrentIndex(1)

    return True


def spectrum_eval_build_worker_cfg(
    app: Any,
    variant: SpectrumEvalVariant,
) -> Dict[str, Any] | None:
    """

    Prepare le dict cfg pour EvalWorker. Retourne None si abandon (materiaux / cibles).

    """

    from certus_physics import init_thickness

    mats = app._get_materials()

    sk = spectrum_eval_substrate_key(variant)

    if not mats:
        return None

    if sk not in mats:
        sk = "Substrate" if sk == "substrate" else "substrate"

    if sk not in mats:
        return None

    stack = app._get_front_stack()

    if app.oblique_mode:
        tgts = app._get_oblique_tgts()

    else:
        tgts = app._get_tgts()

    active = [t for t in tgts if t.valid()]

    if not active:
        return None

    if getattr(app, "_use_exact_ep", False) and app.ep_current is not None and len(app.ep_current) == len(stack):
        ep = app.ep_current

        app._use_exact_ep = False

    else:
        ep = init_thickness(stack, app.l0_spin.value(), mats)

    lmin_display = app._calculate_wls_min_with_margin(active)

    lmax_display = app._calculate_wls_max_with_margin(active)

    n_vis = spectrum_eval_n_vis_points(app, variant)

    wls_vis = np.linspace(lmin_display, lmax_display, n_vis)

    wls_optim = app._get_optim_wls()

    app.log(
        (
            "[SPECTRUM_EVAL.build_worker_cfg] spectral evaluation prepared | "
            "display_pts=%d | display_range_nm=[%.0f,%.0f] | optim_pts=%d | active_targets=%d | variant=%s"
        )
        % (n_vis, lmin_display, lmax_display, len(wls_optim), len(active), variant),
        "INFO",
    )
    spectrum_eval_feedback(
        app,
        f"[{variant.upper()}] evaluation prepared: {len(active)} active target(s)",
        "info",
    )

    cfg: Dict[str, Any] = {
        "variant": variant,
        "mats": mats,
        "stack": stack,
        "ep": ep,
        "tgts": tgts if not app.oblique_mode else [],
        "oblique_mode": app.oblique_mode,
        "oblique_tgts": tgts if app.oblique_mode else [],
        "wls_vis": wls_vis,
        "wls_optim": wls_optim,
        "back": app.back_check.isChecked(),
        "l0": app.l0_spin.value(),
    }

    if variant == "design":
        from certus_physics import calc_spectrum_oblique_vectorized

        sb = app._get_back_stack()

        epb = init_thickness(sb, app.l0_spin.value(), mats) if sb else np.array([])

        cfg["stack_back"] = sb

        cfg["ep_back"] = epb

        cfg["use_back_coat"] = app.back_coat_check.isChecked()

        cfg["calc_oblique_func"] = calc_spectrum_oblique_vectorized if app.oblique_mode else None

    else:
        cfg["re_loaded"] = getattr(app, "_re_loaded", False)

        cfg["a_pct"] = getattr(app, "_re_opt_a_pct", 0.0)

        cfg["b_pct"] = getattr(app, "_re_opt_b_pct", 0.0)

        cfg["f_pct"] = getattr(app, "_re_opt_f_pct", 0.0)

        cfg["spline_dH"] = getattr(app, "_re_spline_dH", None)

        cfg["spline_dL"] = getattr(app, "_re_spline_dL", None)

        cfg["spline_lam2"] = getattr(app, "_re_spline_lam2_nm", None)

        cfg["re_envelope_scale"] = app._re_envelope_scale_from_gui()

        cfg["re_sub_cauchy_a0"] = getattr(app, "_re_sub_cauchy_a0", None)

        cfg["re_sub_cauchy_a1"] = getattr(app, "_re_sub_cauchy_a1", None)

        cfg["re_sub_cauchy_a2"] = getattr(app, "_re_sub_cauchy_a2", None)

        if getattr(app, "_re_p4_display_beam_active", False):
            ak = getattr(app, "_re_p4_display_ap_knots_deg", None)

            al = getattr(app, "_re_p4_display_ap_knots_nm", None)

            if ak is not None and al is not None:
                cfg["re_p4_display_beam"] = True

                cfg["re_p4_ap_knots_deg"] = np.asarray(ak, dtype=np.float64)

                cfg["re_p4_ap_knots_lam_nm"] = np.asarray(al, dtype=np.float64)

                cfg["re_beam_aperture_deg"] = float(app.cfg.get("re_beam_aperture_deg", 1.0))

    return cfg


def spectrum_eval_start_worker(app: Any, cfg: Dict[str, Any], eval_start: float) -> None:

    from certus.workers.certus_spectral_workers import EvalWorker

    app._current_eval_generation += 1

    eval_generation_id = app._current_eval_generation

    cfg["eval_generation_id"] = eval_generation_id
    variant = cfg.get("variant", "design")

    logging.info(
        "[SPECTRUM_EVAL.start_worker] creating EvalWorker | setup_ms=%.1f | variant=%s | generation_id=%s",
        (time.time() - eval_start) * 1000,
        variant,
        eval_generation_id,
    )

    app._set_busy(True)

    app.eval_worker = EvalWorker(cfg)

    app.eval_worker.signals.finished.connect(lambda data, gen=eval_generation_id: app._on_eval_finished(data, gen))
    spectrum_eval_feedback(app, f"Evaluation running ({variant})…", "info")

    app.eval_worker.signals.error.connect(lambda e, gen=eval_generation_id: app._on_error(e, gen))

    logging.info(
        "[SPECTRUM_EVAL.start_worker] starting EvalWorker thread | variant=%s | generation_id=%s",
        variant,
        eval_generation_id,
    )

    app.eval_worker.start()

    logging.info(
        "[SPECTRUM_EVAL.start_worker] EvalWorker started | variant=%s | generation_id=%s",
        variant,
        eval_generation_id,
    )


def spectrum_eval_plot_curves(
    app: Any,
    *,
    data_for_display: Dict[str, Any],
    plot_targets: list,
    res_vis: dict,
    res_optim: dict,
    oblique_mode: bool,
) -> None:
    """Nettoie les widgets spectrum et trace courbes oblique ou transmission + points d'optimization."""

    for plot_widget in plot_targets:
        items_to_keep = [
            getattr(plot_widget, attr) for attr in ["vLine", "hLine", "info_label"] if hasattr(plot_widget, attr)
        ]

        for item in plot_widget.plotItem.items[:]:
            if item not in items_to_keep:
                plot_widget.removeItem(item)

    if oblique_mode:
        spectra_vis = data_for_display.get("spectra_vis", {})

        oblique_tgts = app._get_oblique_tgts()

        if not hasattr(app, "_oblique_spectrum_colors"):
            app._oblique_spectrum_colors = {}

        else:
            app._oblique_spectrum_colors.clear()

        _seen_spec = set()

        _tgts_for_curves = []

        for _t in oblique_tgts:
            if not _t.valid():
                continue

            _k = (round(_t.angle, 3), _t.pol, _t.target_type)

            if _k not in _seen_spec:
                _seen_spec.add(_k)

                _tgts_for_curves.append(_t)

        for tgt in _tgts_for_curves:
            if not tgt.valid():
                continue

            spec_key = (tgt.angle, tgt.pol, bool(getattr(tgt, "include_backside", True)))

            if spec_key in spectra_vis:
                if tgt.target_type not in spectra_vis[spec_key]:
                    app.log(
                        f"Error: Target type {tgt.target_type} not found in spectrum for angle={tgt.angle}, pol={tgt.pol}",
                        "ERROR",
                    )

                    continue

                spectrum = spectra_vis[spec_key][tgt.target_type]

                if tgt.target_type == "R":
                    color = "#dc2626"

                else:
                    color = "#2563eb"

                tgt_id = (tgt.angle, tgt.pol, tgt.target_type, tgt.lmin, tgt.lmax)

                app._oblique_spectrum_colors[tgt_id] = color

                label = f"{tgt.target_type}{tgt.pol} ({tgt.angle})"

                assert tgt.target_type in ("R", "T"), f"Invalid target type: {tgt.target_type}"

                assert tgt.pol in ("s", "p"), f"Invalid polarization: {tgt.pol}"

                assert 0 <= tgt.angle <= 90, f"Invalid angle: {tgt.angle}"

                for plot_widget in plot_targets:
                    plot_widget.plot(
                        res_vis["l"],
                        spectrum,
                        pen=pg.mkPen(color, width=2.5),
                        name=label,
                    )

            else:
                app.log(
                    f"Error: No spectrum calculated for angle={tgt.angle}, pol={tgt.pol}. Target: {tgt.target_type}{tgt.pol}. Cannot display.",
                    "ERROR",
                )

    else:
        for plot_widget in plot_targets:
            plot_widget.plot(
                res_vis["l"],
                res_vis["Ts"],
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
                name="Transmission",
            )

        if len(res_optim["l"]) > 0 and not oblique_mode:
            wls_optim = res_optim["l"]

            Ts_optim = res_optim["Ts"]

            active_tgts = [t for t in app._get_tgts() if t.valid()]

            if active_tgts:
                mask = np.zeros(len(wls_optim), dtype=bool)

                for t in active_tgts:
                    mask |= (wls_optim >= t.lmin) & (wls_optim <= t.lmax)

                wls_filtered = wls_optim[mask]

                Ts_filtered = Ts_optim[mask]

                if len(wls_filtered) > 0:
                    for plot_widget in plot_targets:
                        plot_widget.plot(
                            wls_filtered,
                            Ts_filtered,
                            pen=None,
                            symbol="o",
                            symbolSize=5,
                            symbolBrush=CertusTheme.ERROR,
                            name="Optim Points",
                        )

    wls_for_targets = res_optim["l"] if len(res_optim["l"]) > 0 else res_vis["l"]

    app._rebuild_target_scatter(wls_for_targets, oblique_mode)


def spectrum_eval_apply_axes_legend_scale(
    app: Any,
    *,
    res_vis: dict,
    oblique_mode: bool,
) -> None:
    """Legende, echelles Y/X du plot spectrum principal."""

    if oblique_mode:
        app.spectrum_plot.plotItem.setLabel("left", "R / T", color="black", size="12pt")

    else:
        app.spectrum_plot.plotItem.setLabel("left", "Transmission", color="black", size="12pt")

    if not hasattr(app.spectrum_plot.plotItem, "_legend"):
        app.spectrum_plot.plotItem.addLegend(offset=(10, 10))

    elif not app.spectrum_plot.plotItem._legend.isVisible():
        app.spectrum_plot.plotItem._legend.setVisible(True)

    app._update_spectrum_y_scale()

    if len(res_vis.get("l", [])) == 0:
        app.spectrum_plot.setXRange(200, 3000, 0)
