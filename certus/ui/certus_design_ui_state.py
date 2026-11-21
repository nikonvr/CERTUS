from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from certus.core.certus_core import APP_SUITE_VERSION, CFG
from certus.core.certus_design_workers_dto import DESIGN_OPTIONAL_STEPS
from certus.ui.certus_config_table import ConfigField, apply_table, collect_table
from certus.ui.certus_qt_widgets import QCheckBox
from certus.ui.certus_ui import show_toast
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus_physics import init_thickness

# The settings a DESIGN configuration saves and loads back at its top level; the materials, stacks and targets are
# rows of tables, saved and loaded by `_collect_config` and `_apply_config` themselves.
DESIGN_CONFIG_TABLE = (
    ConfigField("l0", "l0_spin", "float", 500.0),
    ConfigField("back_en", "back_check", "bool", False),
    ConfigField("back_coat", "back_coat_check", "bool", False),
    # Substrate thickness, mm: a file without it is a file at 1 mm, the thickness every kernel assumed before the field.
    ConfigField("substrate_thickness_mm", "sub_thickness_mm_spin", "float", 1.0, missing=1.0),
)

# The settings of the "optimization" block (the files of example/example_design name it "optim").
DESIGN_OPTIMIZATION_TABLE = (
    ConfigField("points_per_target", "points_per_target_spin", "int"),
    ConfigField("n100", "n100_spin", "int"),
    ConfigField("max_clusters", "max_clusters_spin", "int"),
    ConfigField("max_iter", "global_cycles_spin", "int"),
    ConfigField("mc_n", "mc_n_spin", "int"),
    ConfigField("mc_sigma", "mc_sigma_spin", "float"),
    ConfigField("mc_sigma_rel", "mc_sigma_rel_spin", "float"),
    ConfigField("mc_sigma_ot", "mc_sigma_ot_spin", "float"),
    ConfigField("mc_rmse_threshold", "mc_rmse_threshold_spin", "float"),
    ConfigField("pre_polish", "pre_polish_check", "bool", False),
    ConfigField("allow_growth", "allow_growth_check", "bool", True),
    ConfigField("auto_scale_y", "auto_scale_y_check", "bool", True),
    # Least thickness of a final layer, in nm: a file without it is a file at 5 nm, the value before the field existed.
    ConfigField("min_layer_nm", "min_layer_spin", "float", missing=5.0),
    # Limits of the design, 0 = none: a file without them has none. `_collect_config` saves the exact values the
    # window holds (`_max_layers_cap`, `_max_total_qwot`), which a file may give with more decimals than the field.
    ConfigField("max_layers", "max_layers_spin", "int", missing=0),
    ConfigField("max_total_qwot", "max_total_qwot_spin", "float", missing=0.0),
)

# The editable widgets the two tables do not carry, with the reason.
DESIGN_CONFIG_OUTSIDE_TABLE = {
    "oblique_check": "saved as oblique_mode with the targets, whose columns it sets",
    "auto_grid_check": "saved among the optional steps of the optimization block (auto_wavelength_grid)",
    # The Compare tab measures the barrier between two designs of this session (the current one, the Pareto records),
    # which a configuration does not hold: its choices and its path settings belong to that analysis.
    "compare_a_combo": "Compare tab: a design of this session",
    "compare_b_combo": "Compare tab: a design of this session",
    "compare_free_spin": "Compare tab: setting of the barrier analysis",
    "compare_iter_spin": "Compare tab: setting of the barrier analysis",
    "compare_images_spin": "Compare tab: setting of the barrier analysis",
}


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

            if hasattr(self.ui, "sub_thickness_mm_spin"):
                self.ui.sub_thickness_mm_spin.setValue(1.0)

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
        """Nothing: saving writes the design as it is.

        It removed the layers under 1 nm and merged neighbours, so saving changed the operator's design (audit
        2026-11-15, L5-m1). Cleaning stays an explicit action; the owner decided that saving never cleans.
        """

    def _post_save_config(self, filename: str) -> None:
        """UX feedback after a successful save."""

        self.ui.log(f"Configuration saved:  {filename}", "SUCCESS")

        show_toast(self.ui, f"Saved: {Path(filename).name}", "success")

    def _collect_config(self) -> dict:
        """Build the JSON-serialisable config dict from current UI state.

        Pure: it reads the window and changes nothing. The pre-save cleanup is an explicit step of the save flow
        (`save_config` runs `_pre_save_smart_cleanup` itself); this function also feeds the unsaved-changes comparison
        at opening and closing, which must not rewrite the operator's stack.
        """

        cfg = {
            "version": APP_SUITE_VERSION,
            **collect_table(self.ui, DESIGN_CONFIG_TABLE),
            "materials": {
                n: {
                    "n4": w["n4"].value(),
                    "n7": w["n7"].value(),
                    "preset": w["preset"].currentText(),
                }
                for n, w in self.ui.mat_widgets.items()
            },
            "front": [{"mat": layer.mat, "qw": layer.qwot, "var": layer.var} for layer in self.ui._get_front_stack()],
            "back": [{"mat": layer.mat, "qw": layer.qwot} for layer in self.ui._get_back_stack()],
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
            "optimization": collect_table(self.ui, DESIGN_OPTIMIZATION_TABLE),
        }
        for key, attr in (("max_layers", "_max_layers_cap"), ("max_total_qwot", "_max_total_qwot"),
                          ("min_layer_ot_nm", "_min_layer_ot_nm"), ("floor_at_end", "_floor_at_end")):
            if getattr(self.ui, attr, None):
                cfg["optimization"][key] = getattr(self.ui, attr)
        cfg["optimization"].update(getattr(self.ui, "_design_optional_steps", None) or {})

        return cfg

    def _apply_config(self, c: dict) -> None:
        """Apply a parsed configuration dict to the UI (Lot C)."""

        cfg_filename = getattr(self.ui, "_last_config_file", None) or "<unknown>"
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
        cfg_version = c.get("version", "Unknown")
        self.ui.log(
            f"[LOAD] start | file={cfg_filename} | version={cfg_version} | l0={float(c.get('l0', 500)):.2f} | "
            f"materials={len(materials):d} | front={len(front_rows):d} | back_en={back_enabled} | "
            f"back_coat={back_coat_enabled} | back={len(back_rows):d} | targets={len(target_rows):d} | "
            f"oblique={oblique_mode} | ep_before_len={ep_before_len} | front_table_rows={front_before_len}",
            "INFO",
        )

        self.ui.log(f"Format Version: {c.get('version', 'Unknown')}", "INFO")

        # The new configuration has no source file until _post_load_config records it.
        self.ui._last_config_file = None
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
        
        apply_table(self.ui, DESIGN_CONFIG_TABLE, c)

        self._apply_material_config(materials)
        self.ui.log(f"[LOAD] Materials applied | count={len(materials)} | keys={list(materials.keys())}", "INFO")

        self._apply_stack_rows(front_rows, back=False)
        self.ui.log(
            f"[LOAD] Front stack applied | rows={len(front_rows)} | table_rows={self.ui.front_table.rowCount()} | rebuilt_stack_len={len(self.ui._get_front_stack())}",
            "INFO",
        )

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

        # The window saves "optimization"; the files of example/example_design name the block "optim".
        self._apply_optimization_config(c.get("optimization", c.get("optim", {})))
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

        apply_table(self.ui, DESIGN_OPTIMIZATION_TABLE, opt)

        # Limits of the design, absent from most files: the most layers the workflow may grow to, and the most
        # total optical thickness (QWOT at l0, n4 convention) of the global stage. A file without them clears them.
        # Their fields were set by the table; the values kept are the file's own, whatever the decimals of a field.
        self.ui._max_layers_cap = int(opt["max_layers"]) if opt.get("max_layers") else None
        self.ui._max_total_qwot = float(opt["max_total_qwot"]) if opt.get("max_total_qwot") else None
        # Least optical thickness n4 * d of a final layer, in nm; without it every final layer keeps 5 nm.
        self.ui._min_layer_ot_nm = float(opt["min_layer_ot_nm"]) if opt.get("min_layer_ot_nm") else None
        # Apply the thickness floor only at the end of the workflow (owner's practice); off unless the file asks.
        self.ui._floor_at_end = bool(opt.get("floor_at_end", False))
        # Optional steps of 2026-10-26, off unless the file names them (DESIGN_OPTIONAL_STEPS).
        self.ui._design_optional_steps = {k: opt[k] for k in DESIGN_OPTIONAL_STEPS if k in opt}
        if hasattr(self.ui, "auto_grid_check") and hasattr(self.ui, "layout_manager"):
            self.ui.layout_manager.sync_auto_grid()

    def config_load_problems(self, c: dict) -> list[str]:
        """What `c` names that this window cannot reproduce (D88): loading it would compute with something else.

        A layer naming a material slot the window does not have would become the first slot. A material slot whose
        preset no list offers is loaded from the indices the file saved with it (`_apply_material_config`); only a
        slot that saved none cannot be.
        """
        problems = []
        for name, d in (c.get("materials") or {}).items():
            widgets = self.ui.mat_widgets.get(name)
            preset = d.get("preset", "Custom") if isinstance(d, dict) else "Custom"
            offered = widgets is None or preset == "Custom" or widgets["preset"].findText(str(preset)) >= 0
            if not offered and not ("n4" in d and "n7" in d):
                problems.append(f'Material {name}: the preset "{preset}" is not offered and the file saved no indices for it.')
        slots = [m for m in CFG.MATERIALS if m.lower() != "substrate"]
        for side in ("front", "back"):
            for k, row in enumerate(c.get(side) or [], start=1):
                mat = row.get("mat") if isinstance(row, dict) else None
                if mat is not None and str(mat) not in slots:
                    problems.append(f'{side.capitalize()} layer {k}: "{mat}" is not one of {", ".join(slots)}.')
        return problems

    def _apply_material_config(self, materials: dict) -> None:
        """Apply saved material presets and custom n values.

        The preset lists offer only "Custom": a file saved with a named preset (the shipped example has `TiO2 (H)`)
        carries the indices that preset stood for, and those are applied. They used to be skipped, so the slot kept the
        indices it had before the load, whatever the file said.
        """

        for n, d in materials.items():
            if n not in self.ui.mat_widgets:
                continue
            preset_name = d.get("preset", "Custom")
            if preset_name != "Custom" and self.ui.mat_widgets[n]["preset"].findText(str(preset_name)) < 0:
                self.ui.log(f"Material {n}: preset {preset_name!r} is not offered; the indices the file saved are used.", "INFO")
                preset_name = "Custom"
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
                        if w.findText(str(value)) < 0:
                            # A combo box ignores a text it does not offer, and keeps its first choice:
                            # a configuration saved with `Avg` used to load as s without a word.
                            self.ui.log(
                                f"Target row {r + 1}: {value!r} is not one of the choices of this column;"
                                f" {w.itemText(0)!r} is kept.",
                                "WARNING",
                            )
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

        self._apply_optimization_config(config.get("optimization", config.get("optim", {})))
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

        self.ui.log(f"Config loaded from {Path(filename).name}", "SUCCESS")

        show_toast(self.ui, f"Loaded: {Path(filename).name}", "success")

    def reset_to_defaults(self) -> Any:
        """Resets the entire application to factory defaults (clean slate)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self.ui)


