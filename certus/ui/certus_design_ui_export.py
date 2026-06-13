from certus.core.certus_core import __version__, APP_SUITE_VERSION
import os
from pathlib import Path
import multiprocessing
import sys
import functools
from certus.core.certus_core import create_module_environment
import logging
import time
import traceback
import copy
from threading import Event
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg
from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QThread,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CFG,
    ensure_numpy_array,
    get_complex_dtype,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)
from certus.utils.errors import safe_ui_action
from certus.workers.certus_design_worker_utils import (
    build_pglobal_optimizer,
    build_pglobal_config_from_cfg,
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_post_optim_time_budget_seconds,
    optim_prepare_stack_nk_back,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    prepare_pglobal_inputs_from_state,
    prepare_pglobal_optimizer_runtime,
    run_coord_descent_5cycles,
    run_pglobal_restart_loop,
)
from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)
from certus_physics import (  # Cache & Utils; Gradient Logic (Analytic); Numba Functions
    Layer,
    Material,
    ObliqueTarget,
    PGlobalConfig,
    PGlobalOptimizer,
    Target,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_gradient_contrib_analytic,
    cost_numba_fast,
    delta_e_2000,
    init_thickness,
    lab_to_rgb,
    needle_scan_cached,
    prepare_targets_vectorized,
    xyz_from_spectrum,
    xyz_to_lab,
)
from certus.utils.certus_index_utils import spectral_rmse_weights
from certus.ui.certus_ui import (
    CertusTheme,
    CertusBaseApp,
    CertusScientificPlot,
    CertusThemeToggle,
    CertusCard,
    CertusCollapsible,
    CertusStatusPill,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    EnhancedProgressWidget,
    FlashyCard,
    WelcomeGuideWidget,
    WorkerSignals,
    certus_get_save_file_name,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    create_flashy_grid,
    create_header_logo_widget,
    create_top_actions_bar,
    get_export_config,
    init_certus_app,
    open_documentation,
    plot_widget_plot_finite,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker
from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)
from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)
from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *
from certus.ui.mixins.certus_design_plot_mixin import CertusDesignUIPlotMixin

class CertusDesignExportMixin:
    @safe_ui_action
    def export_results(self) -> None:

        self.log("[DESIGN.export_results] entered export flow", "DEBUG")

        """Self-exports results to reports folder (Excel + HTML).

        This method generates comprehensive reports including:

        - Excel spreadsheet with design parameters and results

        - HTML report with visualization and analysis

        - Timestamped filenames with RMSE values

        - Automatic folder creation and organization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires last_result to be available

            - Creates reports folder if needed

            - Generates both Excel and HTML formats

            - Includes RMSE value in filename"""

        if not self.last_result:
            self.log("[DESIGN.export_results] export skipped: no results available", "WARNING")

            return

        try:
            self._sync_export_result_with_best_eval()

            rmse_val, base_name, excel_path, html_path = self._prepare_export_paths()

            self.log("[DESIGN.export_results] saving reports (Excel + HTML)", "INFO")

            manifest_dict = self._build_export_manifest()

            if not self._is_export_manifest_complete(manifest_dict):
                return

            # 1. EXCEL EXPORT

            self._export_results_excel(manifest_dict, rmse_val, excel_path)

            # 2.HTML EXPORT
            self._export_results_html(manifest_dict, rmse_val, html_path)

            self.status_label.setText(f"✓ Saved: {base_name}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("Export error: %s", e, exc_info=True)

    def _export_results_excel(self, manifest_dict: dict[str, Any], rmse_val: float, excel_path: str) -> None:
        """Write the Excel report workbook when openpyxl is available."""

        if not OPENPYXL_AVAILABLE:
            self.log("[DESIGN._export_results_excel] Excel export skipped: openpyxl not available", "WARNING")

            return

        import openpyxl

        wb = openpyxl.Workbook()

        ws = wb.active

        ws.title = "Summary"

        ws.append(["CERTUS-DESIGN Report"])

        ws.append([f"Generated: {certus_timestamp_display()}"])

        ws.append([f"Best RMSE: {rmse_val:.6f}"])

        t_exec = f"{self.last_result.get('execution_time', 0):.2f}" if "execution_time" in self.last_result else "N/A"

        ws.append([f"Execution Time: {t_exec} s"])

        ws.append([f"Global Cycles: {self.global_cycles_spin.value()}"])

        ws.append([f"Population: {self.max_clusters_spin.value()}"])

        ws.append([])

        ws.append(["STACK CONFIGURATION"])

        ws.append(["#", "Material", "QWOT", "Thickness (nm)", "Variable"])

        ep = self.ep_current if self.ep_current is not None else []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0

            ws.append([i + 1, layer.mat, layer.qwot, f"{d:.2f}", "Yes" if layer.var else "No"])

        if len(ep) > 0:
            ws.append([])

            ws.append(["Total Thickness (nm)", f"{np.sum(ep):.2f}"])

        if "vis" in self.last_result:
            ws2 = wb.create_sheet("Spectrum")

            ws2.append(["Wavelength (nm)", "Transmission"])

            vis = self.last_result["vis"]

            for i in range(len(vis["l"])):
                ws2.append([vis["l"][i], vis["Ts"][i]])

        ws_m = wb.create_sheet("Manifest")

        ws_m.append(["Key", "Value"])

        for k, v in manifest_dict.items():
            ws_m.append([str(k), str(v)])

        wb.save(excel_path)

        self.log(f"Excel saved: {Path(excel_path).name}", "SUCCESS")

    def _export_results_html(self, manifest_dict: dict[str, Any], rmse_val: float, html_path: str) -> None:
        """Write the HTML report for design optimization results."""

        ep = self.ep_current if self.ep_current is not None else []

        stack_data = []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0.0

            stack_data.append(
                {
                    "#": i + 1,
                    "Material": layer.mat,
                    "Thickness (nm)": f"{d:.2f}",
                    "QWOT": f"{layer.qwot:.3f}",
                    "Optimized": "Yes" if layer.var else "No",
                }
            )

        sections = [
            {
                "title": "Design Optimization Summary",
                "type": "kv",
                "content": {
                    "Best RMSE": f"{rmse_val:.5f}",
                    "Total Layers": str(self.front_table.rowCount()),
                    "Total Thickness": (f"{np.sum(ep):.2f} nm" if len(ep) > 0 else "N/A"),
                    "Reference L0": f"{self.l0_spin.value()} nm",
                    "Targets Count": str(len(self._get_tgts())),
                    "Global Cycles": str(self.global_cycles_spin.value()),
                    "Cluster Pop": str(self.max_clusters_spin.value()),
                    "Execution Time": (
                        f"{self.last_result.get('execution_time', 0):.2f} s"
                        if "execution_time" in self.last_result
                        else "N/A"
                    ),
                },
            },
            {"title": "Layer Structure", "type": "table", "content": stack_data},
            {
                "title": "Run Manifest",
                "type": "table",
                "headers": ["Key", "Value"],
                "rows": [[str(k), str(v)] for k, v in manifest_dict.items()],
            },
        ]

        methodology_sections = [
            {
                "title": "Optimization Methodology",
                "type": "kv",
                "content": {
                    "Topology Search": "Needle Algorithm (Automatic Layer Insertion)",
                    "Global Search": "PGlobal (Stochastic Differential Evolution)",
                    "Local Refinement": "L-BFGS-B (Analytic Gradient)",
                    "Gradient Mode": "Analytic (Exact Derivatives)",
                    "Convergence": "High (Gradient-Assisted)",
                },
            },
            {
                "title": "Algorithm Details",
                "type": "text",
                "content": (
                    "The design process uses the <strong>Needle Algorithm</strong> to automatically find the optimal layer structure "
                    "by inserting infinitely thin layers at positions of maximum gradient sensitivity. This is coupled with a "
                    "<strong>Global/Local Hybrid Optimization</strong> strategy to refine thicknesses. The local refinement uses "
                    "<strong>Analytic Gradients</strong> to compute exact derivatives of the Tauc-Lorentz-Urbach model and "
                    "Transfer Matrix Method interactions, providing high-precision convergence without numerical noise."
                ),
            },
        ]

        all_sections = methodology_sections + sections

        figures = [self.spectrum_plot, self.profile_plot]

        if generate_html_report(html_path, "CERTUS-DESIGN Report", all_sections, figures):
            self.log(f"HTML saved: {Path(html_path).name}", "SUCCESS")

    def _build_export_manifest(self) -> dict[str, Any]:
        """Build a run manifest for report export."""

        manifest_dict: dict[str, Any] = {}

        try:
            status_txt = str(getattr(self, "validation_status", "OK") or "OK")

            try:
                status_val = ValidationStatus(status_txt)

            except ValueError:
                status_val = ValidationStatus.OK

            seed_val = None

            for _seed_candidate in (
                getattr(self, "run_seed", None),
                getattr(self, "random_seed", None),
                getattr(self, "_loaded_config", {}).get("seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
                getattr(self, "_loaded_config", {}).get("random_seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
            ):
                if _seed_candidate is None:
                    continue

                try:
                    seed_val = int(_seed_candidate)

                    break

                except (TypeError, ValueError):
                    continue

            svc = IndexFitService(runner=lambda _cfg: self.last_result or {})

            req = IndexFitRequest(
                config={
                    "module": "CERTUS_DESIGN",
                    "export_kind": "full_results",
                    "l0_nm": float(self.l0_spin.value()),
                    "layers_count": int(self.front_table.rowCount()),
                },
                source_paths=[
                    p
                    for p in (
                        str(getattr(self, "filename", "") or "").strip(),
                        str(getattr(self, "_last_config_file", "") or "").strip(),
                    )
                    if p
                ],
                seed=seed_val,
                app_id="CERTUS_DESIGN",
                app_version=__version__,
                warnings=list(getattr(self, "validation_warnings", []) or []),
                status=status_val,
            )

            manifest_dict = svc.fit(req).manifest.to_dict()

        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            self.log(f"Manifest generation failed: {exc}", "WARNING")

            manifest_dict = {}

        return manifest_dict

    def _is_export_manifest_complete(self, manifest_dict: dict[str, Any]) -> bool:
        """Validate mandatory manifest fields before writing reports."""

        from certus.utils.certus_data import get_missing_manifest_fields

        missing_manifest_fields = get_missing_manifest_fields(manifest_dict)

        if not missing_manifest_fields:
            return True

        self.log(
            "Export blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
            "ERROR",
        )

        return False

    def _sync_export_result_with_best_eval(self) -> None:
        """Keep export payload aligned with the best evaluation spectrum and thickness table."""

        curr_rmse = self.last_result.get("rmse")

        curr_rmse_valid = self._is_valid_rmse_value(curr_rmse)

        if not (
            self._best_eval_result is not None
            and self._is_valid_rmse_value(self._best_eval_rmse)
            and (not curr_rmse_valid or self._best_eval_rmse <= curr_rmse + 1e-12)
        ):
            return

        self.last_result = copy.deepcopy(self._best_eval_result)

        try:
            ep_best = np.asarray(self.last_result.get("ep", []), dtype=float).flatten()

            if ep_best.size > 0:
                self._update_qwot_from_ep(ep_best)

                self._update_thickness_display()

                self.ep_current = ep_best.copy()

                self._use_exact_ep = True

        except NUMERICAL_FAULT_EXCEPTIONS as _e_export_sync:
            logging.debug(f"[EXPORT] Best spectrum/table sync skipped:{_e_export_sync}")

    def _prepare_export_paths(self) -> tuple[float, str, str, str]:
        """Prepare export paths and base metadata for report generation."""

        reports_dir = get_resource_path("reports")

        os.makedirs(reports_dir, exist_ok=True)

        rmse_val = getattr(self, "_workflow_best_rmse", None)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = self.last_result.get("rmse", 0.0)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = float("inf")

        ts = certus_timestamp_file()

        try:
            src_name = ""

            if hasattr(self, "_last_config_file") and self._last_config_file:
                src_name = "_" + Path(self._last_config_file).stem

            base_name = f"Report_DESIGN{src_name}_{ts}_RMSE_{rmse_val:.5f}"

        except NUMERICAL_FAULT_EXCEPTIONS:
            base_name = f"Report_DESIGN_{ts}_RMSE_{rmse_val:.5f}"

        excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")

        html_path = str(Path(reports_dir) / f"{base_name}.html")

        return rmse_val, base_name, excel_path, html_path

    def export_excel(self) -> None:
        """Exports design configuration and spectrum to Excel via build_standard_report."""
        import pandas as pd

        f = certus_get_save_file_name(self, "Export to Excel", "Excel (*.xlsx)")

        if not f:
            return

        try:
            # FINAL CLEANUP: Clean + Polish before export

            if self.front_table.rowCount() > 0:
                self.log("Final cleanup before export...", "INFO")

                removed = self.smart_cleanup()

                if removed > 0:
                    self.log(f"Final cleanup: removed {removed} layers.", "INFO")

                    self._is_internal_restart = True

                    self._schedule_eval(True)

            # --- Materials table ---

            mats = self._get_materials()

            df_mats = pd.DataFrame([{"Name": k, "n@400nm": m.n4, "n@700nm": m.n7} for k, m in mats.items()])

            # --- Front stack table ---

            ep = self.ep_current if self.ep_current is not None else []

            stack_rows = []

            for i, layer in enumerate(self._get_front_stack()):
                stack_rows.append(
                    {
                        "#": i + 1,
                        "Material": layer.mat,
                        "QWOT": layer.qwot,
                        "Thickness (nm)": ep[i] if i < len(ep) else 0,
                        "Variable": "Yes" if layer.var else "No",
                    }
                )

            df_stack = pd.DataFrame(stack_rows)

            if ep:
                df_stack = pd.concat(
                    [df_stack, pd.DataFrame([{"#": "TOTAL", "Thickness (nm)": float(np.sum(ep))}])],
                    ignore_index=True,
                )

            # --- Targets table ---

            df_targets = pd.DataFrame(
                [
                    {
                        "Active": "Yes" if t.on else "No",
                        "lambdamin (nm)": t.lmin,
                        "lambdamax (nm)": t.lmax,
                        "Tmin": t.tmin,
                        "Tmax": t.tmax,
                        "Weight": t.w,
                    }
                    for t in self._get_tgts()
                ]
            )

            # --- Summary kv ---

            summary_kv = {
                "Generated": certus_timestamp_display(),
                "CERTUS Suite": APP_SUITE_VERSION,
                "L0 (nm)": self.l0_spin.value(),
                "Total layers": len(stack_rows),
            }

            from certus.utils.certus_data import ReportSection, build_standard_report

            try:
                self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN validation status update skipped during export: %s", exc)
            run_manifest = None
            try:
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: self.last_result or {})
                seed_val = None
                seed_sources = [
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "cfg", {}).get("run_seed") if isinstance(getattr(self, "cfg", None), dict) else None,
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                ]
                for _seed_candidate in seed_sources:
                    if _seed_candidate is None:
                        continue
                    try:
                        seed_val = int(_seed_candidate)
                        break
                    except (TypeError, ValueError):
                        continue
                req = IndexFitRequest(
                    config={
                        "module": "CERTUS_DESIGN",
                        "l0_nm": float(self.l0_spin.value()),
                        "layers_count": int(len(stack_rows)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "filename", "") or "").strip(),
                            str(getattr(self, "_last_config_file", "") or "").strip(),
                        )
                        if p
                    ],
                    seed=seed_val,
                    app_id="CERTUS_DESIGN",
                    app_version=__version__,
                    warnings=list(getattr(self, "validation_warnings", []) or []),
                    status=status_val,
                )
                run_manifest = svc.fit(req).manifest
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN manifest generation failed: %s", exc)
                run_manifest = None

            sections = [
                ReportSection("Summary", kind="kv", content=summary_kv, sheet_name="Summary"),
                ReportSection("Materials", kind="table", content=df_mats, sheet_name="Materials"),
                ReportSection("Front Stack", kind="table", content=df_stack, sheet_name="Stack"),
                ReportSection("Spectral Targets", kind="table", content=df_targets, sheet_name="Targets"),
            ]

            if self.last_result:
                r = self.last_result["vis"]

                df_spectrum = pd.DataFrame({"Wavelength (nm)": r["l"], "Transmission": r["Ts"]})

                sections.append(ReportSection("Spectrum", kind="table", content=df_spectrum, sheet_name="Spectrum"))

            result = build_standard_report(
                sections,
                excel_path=f,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )

            if result.get("excel"):
                self.log(f"Exported to:  {f}", "SUCCESS")

            else:
                self.log("Export failed (build_standard_report error).", "ERROR")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Export error:{str(e)}", "ERROR")

