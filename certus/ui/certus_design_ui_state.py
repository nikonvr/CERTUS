from __future__ import annotations
from certus.ui.certus_design_common import *

class StateManager:
    def __init__(self, ui):
        self.ui = ui
    def _load_defaults(self) -> None:
        """Loads default values"""

        # Block signals to avoid massive re-evaluations during reset

        self.ui.blockSignals(True)

        try:
            defaults = {
                "H": (2.35, 2.30),
                "L": (1.46, 1.46),
                "A": (2.05, 2.00),
                "B": (1.75, 1.73),
                "C": (1.60, 1.58),
                "Substrate": (1.52, 1.51),
            }

            for name, (n4, n7) in defaults.items():
                if name in self.ui.mat_widgets:
                    self.ui.mat_widgets[name]["n4"].setValue(n4)

                    self.ui.mat_widgets[name]["n7"].setValue(n7)

                    self.ui.mat_widgets[name]["preset"].setCurrentText("Custom")

            # Reset Global Parameters

            if hasattr(self.ui, "l0_spin"):
                self.ui.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self.ui, "back_check"):
                self.ui.back_check.setChecked(False)

            if hasattr(self.ui, "back_coat_check"):
                self.ui.back_coat_check.setChecked(False)

            if hasattr(self.ui, "oblique_check"):
                self.ui.oblique_check.setChecked(False)

            if hasattr(self.ui, "auto_scale_y_check"):
                self.ui.auto_scale_y_check.setChecked(True)

            if hasattr(self.ui, "allow_growth_check"):
                self.ui.allow_growth_check.setChecked(True)

            if hasattr(self.ui, "pre_polish_check"):
                self.ui.pre_polish_check.setChecked(False)

            # Add default layers

            for _ in range(4):
                self.ui.add_front_layer()

            # Add default target

            self.ui.add_target()

            # Default optimization parameters

            self.ui.n100_spin.setValue(6000)

            self.ui.max_clusters_spin.setValue(40)

            self.ui.global_cycles_spin.setValue(50)

            if hasattr(self.ui, "points_per_target_spin"):
                self.ui.points_per_target_spin.setValue(50)

            # Default MC parameters

            if hasattr(self.ui, "mc_n_spin"):
                self.ui.mc_n_spin.setValue(200)

            if hasattr(self.ui, "mc_sigma_spin"):
                self.ui.mc_sigma_spin.setValue(2.0)

            # Update Tikhonravov points after loading defaults

            self.ui.orchestrator.schedule_update_tikhonravov_points(500)

            self.ui.log("Default configuration loaded with optimized PGLOBAL settings.", "INFO")

        finally:
            self.ui.blockSignals(False)

            # Force one final evaluation to show the default design

            self.ui._schedule_eval(instant=True)

    def _pre_save_smart_cleanup(self) -> None:
        """Run the pre-save cleanup + heal step (idempotent)."""

        if self.ui.front_table.rowCount() > 0:
            self.ui.log("Final cleanup before save...", "INFO")

            removed = self.ui.smart_cleanup()

            if removed > 0:
                self.ui.log(
                    f"Final cleanup: removed {removed} layers. Optimizing...",
                    "INFO",
                )

                # Run fast local optimization to heal

                self.ui._is_internal_restart = True

                # Note: Cannot wait for optimization here (async)

                self.ui._schedule_eval(True)  # Update display

    def _post_save_config(self, filename: str) -> None:
        """UX feedback after a successful save."""

        self.ui.log(f"Configuration saved:  {filename}", "SUCCESS")

        show_toast(self.ui, f"Saved: {Path(filename).name}", "success")

    def _collect_config(self) -> dict:
        """Build the JSON-serialisable config dict from current UI state."""

        self._pre_save_smart_cleanup()

        cfg = {
            "version": APP_SUITE_VERSION,
            "l0": self.ui.l0_spin.value(),
            "materials": {
                n: {
                    "n4": w["n4"].value(),
                    "n7": w["n7"].value(),
                    "preset": w["preset"].currentText(),
                }
                for n, w in self.ui.mat_widgets.items()
            },
            "front": [{"mat": l.mat, "qw": l.qwot, "var": l.var} for l in self.ui._get_front_stack()],
            "back_en": self.ui.back_check.isChecked(),
            "back_coat": self.ui.back_coat_check.isChecked(),
            "back": [{"mat": l.mat, "qw": l.qwot} for l in self.ui._get_back_stack()],
            "targets": (
                [
                    {
                        "on": t.on,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "tmin": t.tmin,
                        "tmax": t.tmax,
                        "w": t.w,
                    }
                    for t in self.ui._get_tgts()
                ]
                if not self.ui.oblique_mode
                else [
                    {
                        "active": t.on,
                        "angle": t.angle,
                        "polarization": t.pol,
                        "target_type": t.target_type,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "val_min": t.tmin,
                        "val_max": t.tmax,
                        "weight": t.w,
                    }
                    for t in self.ui._get_oblique_tgts()
                ]
            ),
            "oblique_mode": self.ui.oblique_mode,
            "optimization": {
                "points_per_target": self.ui.points_per_target_spin.value(),
                "n100": self.ui.n100_spin.value(),
                "max_clusters": self.ui.max_clusters_spin.value(),
                "max_iter": self.ui.global_cycles_spin.value(),
                "mc_n": self.ui.mc_n_spin.value(),
                "mc_sigma": self.ui.mc_sigma_spin.value(),
                # Extra params
                "pre_polish": (self.ui.pre_polish_check.isChecked() if hasattr(self.ui, "pre_polish_check") else False),
                "allow_growth": (self.ui.allow_growth_check.isChecked() if hasattr(self.ui, "allow_growth_check") else True),
                "auto_scale_y": (self.ui.auto_scale_y_check.isChecked() if hasattr(self.ui, "auto_scale_y_check") else True),
            },
        }

        return cfg

    def _apply_config(self, c: dict) -> None:
        """Apply a parsed configuration dict to the UI (Lot C)."""

        cfg_filename = getattr(self.ui, "_last_config_file", None) or getattr(self, "_last_config_file", None) or "<unknown>"
        front_rows = c.get("front", [])
        back_rows = c.get("back", [])
        target_rows = c.get("targets", [])
        materials = c.get("materials", {})
        oblique_mode = bool(c.get("oblique_mode", False))
        back_enabled = bool(c.get("back_en", False))
        back_coat_enabled = bool(c.get("back_coat", False))

        ep_before = getattr(self.ui, "ep_current", None)
        ep_before_len = len(ep_before) if ep_before is not None else None
        front_before_len = self.ui.front_table.rowCount() if hasattr(self.ui, "front_table") else None
        self.ui.log(
            (
                "[LOAD] start | file=%s | version=%s | l0=%.2f | materials=%d | front=%d | back_en=%s | "
                "back_coat=%s | back=%d | targets=%d | oblique=%s | ep_before_len=%s | front_table_rows=%s"
            )
            % (
                cfg_filename,
                c.get("version", "Unknown"),
                float(c.get("l0", 500)),
                len(materials),
                len(front_rows),
                back_enabled,
                back_coat_enabled,
                len(back_rows),
                len(target_rows),
                oblique_mode,
                ep_before_len,
                front_before_len,
            ),
            "INFO",
        )

        self.ui.log("Format Version: %s" % c.get("version", "Unknown"), "INFO")

        self.ui._last_config_file = getattr(self, "_last_config_file", None)
        self.ui._loading_config = True
        
        # Reset current optimization state so new config is evaluated fresh
        self.ui.ep_current = None
        self.ui._use_exact_ep = False
        self.ui._best_eval_result = None
        self.ui._best_eval_rmse = float("inf")
        self.ui._workflow_best_rmse = float("inf")
        self.ui._stack_info_best_ep = None
        self.ui._stack_info_best_rmse = None
        if hasattr(self.ui, "mse_data"):
            self.ui.mse_data = {"iterations": [], "errors": []}
        
        self.ui.l0_spin.setValue(c.get("l0", 500))

        self._apply_material_config(materials)
        self.ui.log(f"[LOAD] Materials applied | count={len(materials)} | keys={list(materials.keys())}", "INFO")

        self._apply_stack_rows(front_rows, back=False)
        self.ui.log(
            f"[LOAD] Front stack applied | rows={len(front_rows)} | table_rows={self.ui.front_table.rowCount()} | rebuilt_stack_len={len(self.ui._get_front_stack())}",
            "INFO",
        )

        self.ui.back_check.setChecked(back_enabled)
        self.ui.back_coat_check.setChecked(back_coat_enabled)
        self._apply_stack_rows(back_rows, back=True)
        self.ui.log(
            f"[LOAD] Back stack applied | rows={len(back_rows)} | table_rows={self.ui.back_table.rowCount()} | rebuilt_stack_len={len(self.ui._get_back_stack())}",
            "INFO",
        )

        self.ui.log(f"[LOAD] Oblique mode: {oblique_mode}", "INFO")
        self.ui.oblique_targets = []
        if hasattr(self.ui, "oblique_check"):
            self.ui.oblique_check.setChecked(oblique_mode)
        self.ui.oblique_mode = oblique_mode

        self.ui.log(f"[LOAD] Loading {len(target_rows)} targets...", "INFO")
        self.ui._update_target_table_headers()
        self.ui.target_table.setRowCount(0)
        self._apply_target_config(target_rows, oblique_mode)
        self.ui.log(
            f"[LOAD] Targets applied | count={len(target_rows)} | target_table_rows={self.ui.target_table.rowCount()}",
            "INFO",
        )

        self._apply_optimization_config(c.get("optimization", {}))
        self.ui._update_optim_point_count()
        self.ui._update_layer_count()

        try:
            stack = self.ui._get_front_stack()
            mats = self.ui._get_materials()
            self.ui.log(
                f"[LOAD] ep_current rebuild start | stack_len={len(stack)} | mats_len={len(mats)} | l0={self.ui.l0_spin.value():.2f}",
                "INFO",
            )
            if stack and mats:
                loaded_ep = init_thickness(stack, self.ui.l0_spin.value(), mats)
                loaded_ep_len = len(loaded_ep) if loaded_ep is not None else None
                self.ui.log(
                    f"[LOAD] ep_current rebuild result | loaded_ep_len={loaded_ep_len} | stack_len={len(stack)}",
                    "INFO",
                )
                if loaded_ep is not None and len(loaded_ep) == len(stack):
                    self.ui.ep_current = np.asarray(loaded_ep, dtype=float).copy()
                    self.ui._use_exact_ep = True
                    self.ui.log(f"[LOAD] ep_current rebuilt from loaded stack | ep_len={len(self.ui.ep_current)}", "INFO")
                else:
                    self.ui.log(
                        f"[LOAD] ep_current rebuild skipped | ep_len={loaded_ep_len} | stack_len={len(stack)}",
                        "WARNING",
                    )
        except Exception as rebuild_err:
            self.ui.log(f"[LOAD] ep_current rebuild failed: {rebuild_err}", "WARNING")

        final_stack = self.ui._get_front_stack()
        final_ep = getattr(self.ui, "ep_current", None)
        self.ui.log(
            f"[LOAD] pre-refresh snapshot | ep_current_len={len(final_ep) if final_ep is not None else None} | front_stack_len={len(final_stack)} | targets={len(self.ui._get_tgts())} | oblique={self.ui.oblique_mode}",
            "INFO",
        )
        self.ui.log("[LOAD] Scheduling immediate spectrum/profile refresh", "INFO")
        try:
            self.ui._schedule_eval(True)
        finally:
            self.ui._loading_config = False
            self.ui.log("[LOAD] config load lock released", "INFO")

    def _apply_optimization_config(self, opt: dict) -> None:
        """Apply optimization controls from a config dict."""

        self.ui.points_per_target_spin.setValue(opt.get("points_per_target", self.ui.points_per_target_spin.value()))
        self.ui.n100_spin.setValue(opt.get("n100", self.ui.n100_spin.value()))
        self.ui.max_clusters_spin.setValue(opt.get("max_clusters", self.ui.max_clusters_spin.value()))
        self.ui.global_cycles_spin.setValue(opt.get("max_iter", self.ui.global_cycles_spin.value()))
        self.ui.mc_n_spin.setValue(opt.get("mc_n", self.ui.mc_n_spin.value()))
        self.ui.mc_sigma_spin.setValue(opt.get("mc_sigma", self.ui.mc_sigma_spin.value()))

        if hasattr(self.ui, "pre_polish_check"):
            self.ui.pre_polish_check.setChecked(opt.get("pre_polish", self.ui.pre_polish_check.isChecked()))

        if hasattr(self.ui, "allow_growth_check"):
            self.ui.allow_growth_check.setChecked(opt.get("allow_growth", self.ui.allow_growth_check.isChecked()))

        if hasattr(self.ui, "auto_scale_y_check"):
            self.ui.auto_scale_y_check.setChecked(opt.get("auto_scale_y", self.ui.auto_scale_y_check.isChecked()))

    def _apply_material_config(self, materials: dict) -> None:
        """Apply saved material presets and custom n values."""

        for n, d in materials.items():
            if n not in self.ui.mat_widgets:
                continue
            preset_name = d.get("preset", "Custom")
            self.ui.mat_widgets[n]["preset"].setCurrentText(preset_name)
            if preset_name == "Custom":
                self.ui.mat_widgets[n]["n4"].setValue(d.get("n4", 1.5))
                self.ui.mat_widgets[n]["n7"].setValue(d.get("n7", 1.5))

    def _apply_target_config(self, targets: list[dict], oblique_mode: bool) -> None:
        """Apply target rows from a config dict."""

        for t in targets:
            self.ui.add_target()
            r = self.ui.target_table.rowCount() - 1
            active_cb = self.ui.target_table.cellWidget(r, 0)
            if active_cb:
                active_cb.findChild(QCheckBox).setChecked(t.get("active", t.get("on", True)))

            if oblique_mode:
                widget_updates = [
                    (1, t.get("angle", 0.0)),
                    (2, t.get("polarization", "s")),
                    (3, t.get("target_type", "T")),
                    (4, t.get("lmin", 400)),
                    (5, t.get("lmax", 700)),
                    (6, t.get("val_min", t.get("tmin", 0.0))),
                    (7, t.get("val_max", t.get("tmax", 1.0))),
                    (8, t.get("weight", t.get("w", 1.0))),
                ]
                for idx, value in widget_updates:
                    w = self.ui.target_table.cellWidget(r, idx)
                    if w is None:
                        continue
                    if hasattr(w, "setCurrentText"):
                        w.setCurrentText(value)
                    else:
                        w.setValue(value)
            else:
                for idx, value in enumerate([t.get("lmin", 400), t.get("lmax", 700), t.get("tmin", 0), t.get("tmax", 1), t.get("w", 1)], start=1):
                    w = self.ui.target_table.cellWidget(r, idx)
                    if w:
                        w.setValue(value)

    def _apply_stack_rows(self, rows: list[dict], *, back: bool) -> None:
        """Apply front or back stack rows from a config dict."""

        add_row = self.ui._add_back_row if back else self.ui._add_front_row
        table = self.ui.back_table if back else self.ui.front_table
        table.blockSignals(True)
        table.setRowCount(0)
        for row in rows:
            if back:
                add_row(row["mat"], row["qw"])
            else:
                add_row(row["mat"], row["qw"], row["var"])
        table.blockSignals(False)

    def _post_load_config(self, filename: str, config: dict) -> None:
        """UX side-effects after a successful load (summary dialog, toast, ...)."""

        self.ui._last_config_file = filename

        self.ui.log(f"Configuration loaded:  {filename}", "SUCCESS")

        oblique_mode = bool(config.get("oblique_mode", False))

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            mats_cfg = config.get("materials", {})

            front_cfg = config.get("front", [])

            back_cfg = config.get("back", [])

            tgts_cfg = config.get("targets", [])

            l0_val = float(config.get("l0", self.ui.l0_spin.value()))

            summary = build_summary_plain_text(
                "CERTUS DESIGN - Load Summary",
                [
                    f"File: {Path(filename).resolve()}",
                    "",
                    "General",
                    f"Version: {config.get('version', 'unknown')}",
                    (f"Reference wavelength l0: {l0_val:.2f} nm", not (100.0 <= l0_val <= 10000.0)),
                    "",
                    "Stack",
                    f"Materials declared: {len(mats_cfg)}",
                    (f"Front layers: {len(front_cfg)}", len(front_cfg) <= 0),
                    f"Back enabled: {'yes' if bool(config.get('back_en', False)) else 'no'}",
                    f"Back coating enabled: {'yes' if bool(config.get('back_coat', False)) else 'no'}",
                    (
                        f"Back layers: {len(back_cfg)}",
                        bool(config.get("back_coat", False)) and len(back_cfg) <= 0,
                    ),
                    f"Oblique mode: {'yes' if oblique_mode else 'no'}",
                    "",
                    "Targets",
                    (f"Targets loaded: {len(tgts_cfg)}", len(tgts_cfg) <= 0),
                ],
            )

            show_load_summary_dialog(self.ui, "DESIGN Load Summary", summary)

        logging.info("[LOAD] Calling _schedule_eval (final)...")

        self._apply_optimization_config(config.get("optimization", {}))
        self.ui._update_optim_point_count()
        self.ui._update_layer_count()

        # Force a fresh recomputation after the full load payload has been applied.
        # Using the instant path avoids stale detached plots when the profile/nk
        # views still reflect the previous design for a short time window.
        self.ui._schedule_eval(True)

        try:
            self.ui._plot_profile(
                self.ui.ep_current,
                self.ui._get_front_stack(),
                getattr(self.ui, "ep_back_current", None),
                self.ui._get_back_stack(),
            )
            self.ui._plot_nk()
        except Exception as plot_err:
            logging.debug("[LOAD] immediate plot refresh failed: %s", plot_err)

        _load_start = getattr(self, '_load_config_start_time', None)
        if _load_start is not None:
            self.ui.log(f"[LOAD] === load_config complete in {(time.time() - _load_start) * 1000:.1f}ms ===", "INFO")

        self.ui.log(f"Config loaded from {Path(filename).name}", "SUCCESS")

        show_toast(self.ui, f"Loaded: {Path(filename).name}", "success")

    def reset_to_defaults(self) -> Any:
        """Resets the entire application to factory defaults (clean slate)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

