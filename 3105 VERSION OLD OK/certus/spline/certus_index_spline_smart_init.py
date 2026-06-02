#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Smart Initialization Module.
Contains Payload, State, PreviewManager and Dialog Mixin for Smart Init.
"""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pydantic import BaseModel, ConfigDict
from scipy.optimize import minimize_scalar

from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QEvent
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton, QSlider, QSpinBox, QSplitter,
    QTableWidgetItem, QVBoxLayout, QWidget, QCheckBox, QApplication, QComboBox
)

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog
from certus.ui.certus_smart_init_curve_editor import SmartInitNKCurveEditorDialog
from certus.ui.certus_ui import (
    CertusScientificPlot,
    CertusTheme,
    attach_excel_clipboard_context_menu,
    create_header_logo_widget,
    create_styled_button,
    get_certus_last_dir,
    set_certus_last_dir,
    wrap_scientific_plot_with_toolbar,
    show_toast,
    CertusActionBar,
    CertusCard,
    CertusStepper,
    CertusCollapsible,
    CertusStatusPill,
    safe_ui_action,
)

from certus.spline.certus_index_spline_core import (
    bridge_sigma_knots_preserve_manual,
    log_rmse_mesh_bridge_diagnosis,
    rmse_at_spline_stage_x0_init,
    SplineOptConfig,
    _to_fraction_T,
    SPLINE_PWL_K_NODES,
)

from certus.spline.spline_smart_init import (
    build_smart_manual_sigma_knots_from_preview_grid,
    interp_n_L_pwlnk_to_sigmas,
    pick_best_manual_material_preset,
    recalc_smart_init_spectral_preview,
    smart_init_sweep_node_thickness_rmse,
)

from certus.spline.spline_objective import (
    physical_nodes_to_x_slice_n,
)

from certus.spline.spline_pipeline import enforce_local_optimization_policy

from certus.spline.spline_presets import _project_nb2o5_preset_to_sigma_knots, project_manual_material_preset

from certus.spline.spline_visual_utils import (
    snap_spline_visual_dict as _snap_spline_visual_dict,
)

logger = logging.getLogger("CERTUS_INDEX_SPLINE.smart_init")

_QS_SPLINE_ORG = "CERTUS"
_QS_SPLINE_APP = "INDEX_SPLINE"
_QS_SMART_INIT_DEEP = "smart_init_deep_pglobal_after_manual"
_QS_SMART_INIT_TWO_PHASE = "smart_init_deep_two_phase_enabled"


class SmartInitPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    cfg: Any
    sigma_knots: np.ndarray
    preview_grids: dict[str, Any]
    n_nodes_physical: np.ndarray
    L_nodes: np.ndarray
    d_best_nm: float
    t_exp: np.ndarray
    t_theo: np.ndarray
    t_is_ratio: bool
    lam_nm: np.ndarray | None

    @classmethod
    def from_dict(cls: type["SmartInitPayload"], d: dict[str, Any]) -> "SmartInitPayload":
        clean_d = {}
        clean_d["cfg"] = d.get("cfg")
        clean_d["sigma_knots"] = np.asarray(d.get("sigma_knots", []), dtype=np.float64).ravel()
        clean_d["preview_grids"] = d.get("preview_grids", {})
        clean_d["n_nodes_physical"] = np.asarray(d.get("n_nodes_physical", []), dtype=np.float64).ravel().copy()
        clean_d["L_nodes"] = np.asarray(d.get("L_nodes", []), dtype=np.float64).ravel().copy()
        clean_d["d_best_nm"] = float(d.get("d_best_nm", 0.0))
        clean_d["t_exp"] = np.asarray(d.get("t_exp", []), dtype=np.float64)
        clean_d["t_theo"] = np.asarray(d.get("t_theo", []), dtype=np.float64)
        clean_d["t_is_ratio"] = bool(d.get("t_is_ratio", False))
        clean_d["lam_nm"] = (
            np.asarray(d.get("lam_nm"), dtype=np.float64).ravel() if d.get("lam_nm") is not None else None
        )
        return cls(**clean_d)


@dataclass
class _SmartInitState:
    """State object to hold mutable UI references and mathematical parameters of the Smart Init dialog."""
    sk: np.ndarray
    n_phys: np.ndarray
    L_nodes: np.ndarray
    preview_d_nm: float
    best_rmse: float
    best_n: np.ndarray
    best_L: np.ndarray
    current_rmse: float
    current_t_th: np.ndarray
    k_n: int = 0
    best_live: dict | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.k_n == 0:
            self.k_n = int(np.asarray(self.sk).size)

    def update(
        self,
        sk: np.ndarray,
        n_phys: np.ndarray,
        L_nodes: np.ndarray,
        preview_d_nm: float,
        best_rmse: float,
        best_n: np.ndarray,
        best_L: np.ndarray,
        current_rmse: float,
        current_t_th: np.ndarray,
    ) -> None:
        self.sk = sk
        self.n_phys = n_phys
        self.L_nodes = L_nodes
        self.preview_d_nm = preview_d_nm
        self.best_rmse = best_rmse
        self.best_n = best_n
        self.best_L = best_L
        self.current_rmse = current_rmse
        self.current_t_th = current_t_th


@dataclass
class SmartInitState:
    sk: np.ndarray
    k_n: int
    n_phys: np.ndarray
    L_nodes: np.ndarray
    preview_d_nm: float
    best_rmse: float
    best_n: np.ndarray
    best_L: np.ndarray
    current_rmse: float
    current_t_th: Any
    best_live: Any


class SmartInitPreviewManager:
    def __init__(self, parent_worker, payload):
        self.parent_worker = parent_worker
        self.payload = payload
        self.cfg = payload.cfg
        self.sk = payload.sigma_knots
        self.grids = payload.preview_grids

        logger.info(
            "Smart Init dialog enter | parent=%s | cfg_present=%s | grids_present=%s | payload_K=%d | payload_d=%.6f",
            type(self.parent_worker).__name__,
            bool(self.cfg is not None),
            bool(self.grids is not None),
            int(np.asarray(self.sk, dtype=np.float64).size),
            float(getattr(payload, "d_best_nm", float("nan"))),
        )

        if self.cfg is None or self.grids is None or self.sk.size < 2:
            logger.warning(
                "Smart Init dialog early return | cfg_present=%s | grids_present=%s | payload_K=%d | payload_d=%.6f",
                bool(self.cfg is not None),
                bool(self.grids is not None),
                int(np.asarray(self.sk, dtype=np.float64).size),
                float(getattr(payload, "d_best_nm", float("nan"))),
            )

            QMessageBox.warning(
                self.parent_worker,
                "Smart Init",
                "Incomplete preview data (cfg or grids). Aborting preview safely.",
            )

            raise ValueError("Incomplete preview data (cfg or grids)")

        self.k_n = int(self.sk.size)
        self.n_phys = payload.n_nodes_physical.copy()
        self.L_nodes = payload.L_nodes.copy()

        logger.info(
            "Smart Init dialog payload vectors | len(n)=%d | len(L)=%d | K=%d | d_best=%.6f",
            int(np.asarray(self.n_phys, dtype=np.float64).size),
            int(np.asarray(self.L_nodes, dtype=np.float64).size),
            int(self.k_n),
            float(getattr(payload, "d_best_nm", float("nan"))),
        )

        if self.n_phys.size != self.k_n or self.L_nodes.size != self.k_n:
            logger.warning(
                "Smart Init dialog early return | inconsistent vectors len(n)=%d len(L)=%d K=%d",
                int(np.asarray(self.n_phys, dtype=np.float64).size),
                int(np.asarray(self.L_nodes, dtype=np.float64).size),
                int(self.k_n),
            )

            QMessageBox.warning(self.parent_worker, "Smart Init", "n / L sizes are inconsistent with sigma knots.")
            raise ValueError("n / L sizes are inconsistent with sigma knots")

        self.rel_step = 0.005  # +/-0,5 % sur n et sur L = ln k
        self.L_lo_g = float(self.grids["L_lo"])
        self.L_hi_g = float(self.grids["L_hi"])
        self._relax_si_mono = self.cfg.n_mono_band_nm is not None

        if self.sk.size == SPLINE_PWL_K_NODES:
            self.sk, self.n_phys, self.L_nodes, d_total = _project_nb2o5_preset_to_sigma_knots(self.sk)
            self.effective_d_best_nm = float(d_total)
            self.open_preset_name = "nb2o5"
        else:
            self.effective_d_best_nm = float(payload.d_best_nm)
            self.open_preset_name = "none"

        if getattr(self.cfg, "rmse_fit_lambda_nm", None) is not None:
            sig_f_g = np.asarray(self.grids["sig_f"], dtype=np.float64).ravel()
            if int(sig_f_g.size) >= 2:
                self.sk_win = build_smart_manual_sigma_knots_from_preview_grid(sig_f_g, n_uniform_in_sigma2=11)
                self.n_phys, self.L_nodes = interp_n_L_pwlnk_to_sigmas(self.sk, self.n_phys, self.L_nodes, self.sk_win)
                self.sk = self.sk_win
                self.k_n = int(self.sk.size)

        self.parent_worker.smart_preview_sk_arr = np.asarray(self.sk, dtype=np.float64).ravel().copy()
        self.parent_worker.smart_preview_n_phys = np.asarray(self.n_phys, dtype=np.float64).ravel().copy()
        self.parent_worker.smart_preview_L_nodes = np.asarray(self.L_nodes, dtype=np.float64).ravel().copy()
        self.parent_worker._si_mesh_sk_snap = self.parent_worker.smart_preview_sk_arr.copy()
        self._d0 = self.effective_d_best_nm

        if self._d0 is None or not np.isfinite(float(self._d0)):
            self.preview_d_nm = float(0.5 * (float(self.cfg.d_lo) + float(self.cfg.d_hi)))
        else:
            self.preview_d_nm = float(self._d0)

        logger.info(
            "Smart Init dialog mesh prepared | sigma_knots_count=%d | rmse_fit_window_nm=%s | preset_applied_on_open=%s | preview_d=%.6f",
            int(np.asarray(self.parent_worker.smart_preview_sk_arr, dtype=np.float64).size),
            str(getattr(self.cfg, "rmse_fit_lambda_nm", None)),
            str(self.open_preset_name),
            float(self.preview_d_nm),
        )

        if str(self.open_preset_name) == "nb2o5":
            logger.info(
                "Smart Init dialog seed transformation | incoming_payload_d_best_nm=%.6f | nb2o5_preset_d_total_nm=%.6f | "
                "preset_replaces_incoming_d_for_dialog_preview",
                float(payload.d_best_nm),
                float(self.preview_d_nm),
            )
        else:
            logger.info(
                "Smart Init dialog initial seed | incoming_d_best_nm=%.6f | effective_preview_d_nm=%.6f | preset=%s",
                float(payload.d_best_nm),
                float(self.preview_d_nm),
                str(self.open_preset_name),
            )

        _, rm0 = rmse_at_spline_stage_x0_init(
            self.cfg,
            self.sk,
            self.n_phys,
            self.L_nodes,
            self.preview_d_nm,
            relax_n_mono=self._relax_si_mono,
        )

        best_rmse = float(rm0)
        best_n = self.n_phys.copy()
        best_L = self.L_nodes.copy()
        current_rmse = float(rm0)

        logger.info(
            "Smart Init dialog RMSE-at-seed | dialog_d_nm=%.6f | initial_rmse=%.8f",
            float(self.preview_d_nm),
            float(current_rmse),
        )

        self.dlg = QDialog(self.parent_worker)
        logger.info("Smart Init dialog QDialog created")

        self.dlg.setWindowTitle(f"Smart Init  PWL n and ln k ({self.k_n} sigma knots — presets Nb2O5 | SiO2 | Ta2O5)")
        self.dlg.setMinimumWidth(1180)
        self.dlg.setMinimumHeight(620)

        aux_dlg, curve_n, curve_pk, main_vb, p_extra = self.parent_worker._build_smart_init_aux_dialog(self.dlg)
        logger.info("Smart Init dialog auxiliary window created")

        lay = QVBoxLayout(self.dlg)
        h_x_main = QHBoxLayout()
        h_x_main.addWidget(QLabel("X axis (spectrum):"))
        self.cb_x_main = QComboBox()
        self.cb_x_main.addItems(["Lambda (nm)", "Sigma (nm⁻¹)", "Sigma² (nm⁻²)"])
        h_x_main.addWidget(self.cb_x_main)
        h_x_main.addStretch()
        lay.addLayout(h_x_main)

        if self._relax_si_mono:
            lbl_mono_relax = QLabel(
                "<b>Manual tuning</b>: <i>n</i> may be <b>non-monotone</b> in sigma between knots here "
                "(sliders / editor). <b>After Continue</b>: optimization uses the "
                "<b>— reparametrization</b> - <i>n</i> non-decreasing in sigma on the run's lambda band "
                "(so in practice <i>n</i> <b>decreasing or quasi-flat</b> as lambda increases on these segments), "
                "plus a penalty (UV-VIS band) if <i>n</i> rises too much with lambda "
                "(small slack on this penalty is configurable)."
            )
            lbl_mono_relax.setWordWrap(True)
            lbl_mono_relax.setStyleSheet(f"color: {CertusTheme.WARNING}; font-size: 11px; padding: 2px 0;")
            lay.addWidget(lbl_mono_relax)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(splitter)

        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        y_lab = "Transmittance"
        if payload.t_is_ratio:
            y_lab = "Ratio T/T_sub"
        pw, curve_exp, curve_theo, knot_markers = self.parent_worker._build_smart_init_main_plot(y_lab)
        left_lay.addWidget(wrap_scientific_plot_with_toolbar(self.dlg, pw))

        self.lbl_rmse = QLabel()
        self.lbl_rmse.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {CertusTheme.PRIMARY}; padding: 4px 0;"
        )
        left_lay.addWidget(self.lbl_rmse)

        btn_show_profiles = create_styled_button("Show n(λ) / k(λ) profiles window", CertusTheme.SECONDARY)
        btn_show_profiles.clicked.connect(aux_dlg.show)
        left_lay.addWidget(btn_show_profiles)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        card_sliders = CertusCard("Sigma Knots n and ln k Sliders")
        right_lay.addWidget(card_sliders)

        grid_lay = QGridLayout()
        grid_lay.setSpacing(6)
        card_sliders.body.addLayout(grid_lay)

        self.sliders_n = []
        self.sliders_L = []
        self.lbls_n = []
        self.lbls_L = []

        headers = ["#", "Knot λ (nm)", "n (ref. slider)", "ln k (ref. slider)", "k (preview)"]
        for col_idx, h in enumerate(headers):
            grid_lay.addWidget(QLabel(f"<b>{h}</b>"), 0, col_idx)

        # Scale slider integers to floats
        self.scale_n = 1000.0  # 1.0 -> 3.0
        self.scale_L = 1000.0  # L_lo -> L_hi

        for i in range(self.k_n):
            s_val = float(self.sk[i])
            wl = 1.0 / max(s_val, 1e-30)

            grid_lay.addWidget(QLabel(f"#{i+1}"), i + 1, 0)
            grid_lay.addWidget(QLabel(f"{wl:.1f} nm"), i + 1, 1)

            # n slider
            sl_n = QSlider(Qt.Orientation.Horizontal)
            sl_n.setRange(int(1.0 * self.scale_n), int(3.3 * self.scale_n))
            sl_n.setValue(int(round(float(self.n_phys[i]) * self.scale_n)))
            self.sliders_n.append(sl_n)
            grid_lay.addWidget(sl_n, i + 1, 2)

            lbl_n = QLabel(f"{float(self.n_phys[i]):.4f}")
            lbl_n.setFixedWidth(55)
            self.lbls_n.append(lbl_n)
            grid_lay.addWidget(lbl_n, i + 1, 3)

            # ln k slider
            sl_L = QSlider(Qt.Orientation.Horizontal)
            sl_L.setRange(int(self.L_lo_g * self.scale_L), int(self.L_hi_g * self.scale_L))
            sl_L.setValue(int(round(float(self.L_nodes[i]) * self.scale_L)))
            self.sliders_L.append(sl_L)
            grid_lay.addWidget(sl_L, i + 1, 4)

            lbl_L = QLabel(f"{float(self.L_nodes[i]):.2f}")
            lbl_L.setFixedWidth(50)
            self.lbls_L.append(lbl_L)
            grid_lay.addWidget(lbl_L, i + 1, 5)

            # k (preview value)
            lbl_k_preview = QLabel(f"{np.exp(float(self.L_nodes[i])):.2e}")
            lbl_k_preview.setFixedWidth(65)
            grid_lay.addWidget(lbl_k_preview, i + 1, 6)

            # Setup slider connections
            def _make_n_changed(idx=i, sl=sl_n, lbl=lbl_n) -> Callable[[], None]:
                def _fn() -> None:
                    val = float(sl.value()) / self.scale_n
                    self.n_phys[idx] = val
                    lbl.setText(f"{val:.4f}")
                    self.recalculate()
                return _fn

            def _make_L_changed(idx=i, sl=sl_L, lbl=lbl_L, lbl_kp=lbl_k_preview) -> Callable[[], None]:
                def _fn() -> None:
                    val = float(sl.value()) / self.scale_L
                    self.L_nodes[idx] = val
                    lbl.setText(f"{val:.2f}")
                    lbl_kp.setText(f"{np.exp(val):.2e}")
                    self.recalculate()
                return _fn

            sl_n.valueChanged.connect(_make_n_changed())
            sl_L.valueChanged.connect(_make_L_changed())

        # Thickness slider card
        card_d = CertusCard("Layer Thickness Slider")
        right_lay.addWidget(card_d)

        h_d = QHBoxLayout()
        h_d.addWidget(QLabel("d (nm):"))
        self.sl_d = QSlider(Qt.Orientation.Horizontal)
        self.scale_d = 100.0
        self.sl_d.setRange(int(float(self.cfg.d_lo) * self.scale_d), int(float(self.cfg.d_hi) * self.scale_d))
        self.sl_d.setValue(int(round(self.preview_d_nm * self.scale_d)))
        h_d.addWidget(self.sl_d)

        self.lbl_d = QLabel(f"{self.preview_d_nm:.2f} nm")
        self.lbl_d.setFixedWidth(65)
        h_d.addWidget(self.lbl_d)

        def _d_changed() -> None:
            val = float(self.sl_d.value()) / self.scale_d
            self.preview_d_nm = val
            self.lbl_d.setText(f"{val:.2f} nm")
            self.recalculate()

        self.sl_d.valueChanged.connect(_d_changed)
        card_d.body.addLayout(h_d)

        # Advanced tools card
        card_tools = CertusCard("Advanced Initialization Tools")
        right_lay.addWidget(card_tools)

        grid_tools = QGridLayout()
        grid_tools.setSpacing(6)
        card_tools.body.addLayout(grid_tools)

        # presets
        btn_preset_nb2o5 = create_styled_button("Apply Nb2O5 preset", CertusTheme.SECONDARY)
        btn_preset_nb2o5.clicked.connect(lambda: self.apply_preset("nb2o5"))
        grid_tools.addWidget(btn_preset_nb2o5, 0, 0)

        btn_preset_sio2 = create_styled_button("Apply SiO2 preset", CertusTheme.SECONDARY)
        btn_preset_sio2.clicked.connect(lambda: self.apply_preset("sio2"))
        grid_tools.addWidget(btn_preset_sio2, 0, 1)

        btn_preset_ta2o5 = create_styled_button("Apply Ta2O5 preset", CertusTheme.SECONDARY)
        btn_preset_ta2o5.clicked.connect(lambda: self.apply_preset("ta2o5"))
        grid_tools.addWidget(btn_preset_ta2o5, 0, 2)

        # Load / Save buttons
        self.btn_load_cfg = create_styled_button("Load config from file", CertusTheme.SECONDARY)
        self.btn_load_cfg.clicked.connect(
            lambda: self.parent_worker._load_smart_init_index_config(
                self.state,
                self.dlg,
                self.L_lo_g,
                self.L_hi_g,
                float(self.cfg.d_lo),
                float(self.cfg.d_hi),
                self.refresh_knot_lines_and_ui,
                self.btn_load_cfg,
            )
        )
        grid_tools.addWidget(self.btn_load_cfg, 1, 0)

        btn_save_cfg = create_styled_button("Save current config", CertusTheme.SECONDARY)
        btn_save_cfg.clicked.connect(self.save_config)
        grid_tools.addWidget(btn_save_cfg, 1, 1)

        # Curve editor integration
        btn_open_curve_editor = create_styled_button("Open Interactive NK Curve Editor...", CertusTheme.SECONDARY)
        btn_open_curve_editor.clicked.connect(self.open_curve_editor)
        grid_tools.addWidget(btn_open_curve_editor, 1, 2)

        # Row optimization (local sweep)
        h_opt_row = QHBoxLayout()
        h_opt_row.addWidget(QLabel("Optimize single knot indices (local search):"))
        self.sp_opt_row = QSpinBox()
        self.sp_opt_row.setRange(1, self.k_n)
        h_opt_row.addWidget(self.sp_opt_row)

        btn_opt_n = create_styled_button("Optimize n", CertusTheme.SECONDARY)
        btn_opt_n.clicked.connect(lambda: self.run_auto_opt(is_ln_k=False))
        h_opt_row.addWidget(btn_opt_n)

        btn_opt_k = create_styled_button("Optimize ln k", CertusTheme.SECONDARY)
        btn_opt_k.clicked.connect(lambda: self.run_auto_opt(is_ln_k=True))
        h_opt_row.addWidget(btn_opt_k)
        card_tools.body.addLayout(h_opt_row)

        # Autofind best presets
        h_af = QHBoxLayout()
        btn_auto_preset = create_styled_button("Auto-select best preset & optimize d", CertusTheme.SECONDARY)
        btn_auto_preset.clicked.connect(self.auto_find_best_preset)
        h_af.addWidget(btn_auto_preset)

        btn_auto_local = create_styled_button("Polish d & indices (fast local search)", CertusTheme.SECONDARY)
        btn_auto_local.clicked.connect(self.run_fast_local_search)
        h_af.addWidget(btn_auto_local)
        card_tools.body.addLayout(h_af)

        # Recall best
        h_recall = QHBoxLayout()
        self.btn_recall = create_styled_button("Recall best session state (RMSE=n/a)", CertusTheme.SECONDARY)
        self.btn_recall.setEnabled(False)
        self.btn_recall.clicked.connect(self.recall_best)
        h_recall.addWidget(self.btn_recall)
        card_tools.body.addLayout(h_recall)

        splitter.addWidget(right_widget)

        # Actions Card
        card_actions = CertusCard("Execution Actions")
        right_lay.addWidget(card_actions)
        h_actions = QHBoxLayout()

        self.chk_si_deep = QCheckBox("Run pglobal deep search after Continue")
        # Load default
        self.chk_si_deep.setChecked(
            bool(QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).value(_QS_SMART_INIT_DEEP, True, type=bool))
        )
        h_actions.addWidget(self.chk_si_deep)

        self.chk_si_two_phase = QCheckBox("Enable two-phase pglobal (re-grid K=14)")
        self.chk_si_two_phase.setChecked(
            bool(QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).value(_QS_SMART_INIT_TWO_PHASE, False, type=bool))
        )
        h_actions.addWidget(self.chk_si_two_phase)

        h_actions.addStretch()

        self._on_keep_called = [False]
        btn_keep = create_styled_button("Continue (use these seed profiles)", CertusTheme.PRIMARY)
        btn_keep.clicked.connect(self.on_keep)
        h_actions.addWidget(btn_keep)

        btn_cancel = create_styled_button("Abort Preview", CertusTheme.DANGER)
        btn_cancel.clicked.connect(self.dlg.reject)
        h_actions.addWidget(btn_cancel)

        card_actions.body.addLayout(h_actions)

        # References to the GUI objects
        self.curve_exp = curve_exp
        self.curve_theo = curve_theo
        self.knot_markers = knot_markers
        self.pw = pw
        self.curve_n = curve_n
        self.curve_pk = curve_pk
        self.aux_dlg = aux_dlg
        self.main_vb = main_vb
        self.p_extra = p_extra

        # Main lambda grid
        self.lam_grid = np.asarray(payload.lam_nm, dtype=np.float64).ravel()
        self.t_exp = np.asarray(payload.t_exp, dtype=np.float64).ravel()
        self.t_is_ratio = payload.t_is_ratio

        self.state = _SmartInitState(
            sk=self.sk,
            n_phys=self.n_phys,
            L_nodes=self.L_nodes,
            preview_d_nm=self.preview_d_nm,
            best_rmse=best_rmse,
            best_n=best_n,
            best_L=best_L,
            current_rmse=current_rmse,
            current_t_th=payload.t_theo.copy(),
            k_n=self.k_n,
        )

        self.cb_x_main.currentIndexChanged.connect(self.replot_x_axis)

        # Plot EXP data initially
        self.plot_exp_data()

        # Update initial graphs
        self.recalculate(is_initial=True)

    def plot_exp_data(self) -> None:
        try:
            x_ax = str(self.cb_x_main.currentText())
            sig = 1.0 / np.maximum(self.lam_grid, 1e-9)
            if "Sigma²" in x_ax:
                x_vals = sig * sig
            elif "Sigma" in x_ax:
                x_vals = sig
            else:
                x_vals = self.lam_grid

            self.curve_exp.setData(x_vals, self.t_exp)
            self.pw.plotItem.getAxis("bottom").setLabel(x_ax)
        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Failed to plot experimental data in smart init", exc_info=True)

    def replot_x_axis(self) -> None:
        self.plot_exp_data()
        self.recalculate(is_initial=False)

    def update_btn_recall_text(self) -> None:
        if np.isfinite(self.state.best_rmse) and self.state.best_rmse < 1e90:
            self.btn_recall.setText(f"Recall best session state (RMSE={self.state.best_rmse:.6f})")
            self.btn_recall.setEnabled(True)
        else:
            self.btn_recall.setText("Recall best session state (RMSE=n/a)")
            self.btn_recall.setEnabled(False)

    @safe_ui_action
    def recalculate(self, is_initial: bool = False) -> None:
        try:
            out = self.parent_worker._execute_smart_init_recalc_logic(self.cfg, self.grids, self._relax_si_mono, self.state)
            if out is None:
                return

            self.update_btn_recall_text()
            self.lbl_rmse.setText(f"Current spectral RMSE: {self.state.current_rmse:.6f}")

            # Plot theoretical
            x_ax = str(self.cb_x_main.currentText())
            sig_f = np.asarray(out["lam_nm"], dtype=np.float64).ravel()
            sig_f = 1.0 / np.maximum(sig_f, 1e-9)
            if "Sigma²" in x_ax:
                x_theo = sig_f * sig_f
            elif "Sigma" in x_ax:
                x_theo = sig_f
            else:
                x_theo = out["lam_nm"]

            self.curve_theo.setData(x_theo, out["t_theo"])

            # Plot knot markers
            sk_curr = self.state.sk
            lam_knots = 1.0 / np.maximum(sk_curr, 1e-9)
            if "Sigma²" in x_ax:
                x_knots = sk_curr * sk_curr
            elif "Sigma" in x_ax:
                x_knots = sk_curr
            else:
                x_knots = lam_knots

            # T theoretical values evaluated at knots
            t_knots = np.interp(lam_knots, out["lam_nm"], out["t_theo"])
            self.knot_markers.setData(x_knots, t_knots)

            # Plot n(lambda) and log k(lambda) in auxiliary window
            lam_f_eval = out["lam_nm"]
            self.curve_n.setData(lam_f_eval, out["n_lam"])

            k_lam_full = out["k_lam"]
            lnk_lam_full = np.log(np.maximum(k_lam_full, 1e-30))
            self.curve_pk.setData(lam_f_eval, lnk_lam_full)

            # Auto scale ViewBox for right axis (ln k)
            self.p_extra.setYRange(float(np.min(lnk_lam_full) - 0.2), float(np.max(lnk_lam_full) + 0.2))

            # Auto fit view on initial render
            if is_initial:
                pad_x = (np.max(x_theo) - np.min(x_theo)) * 0.05
                self.pw.setXRange(float(np.min(x_theo) - pad_x), float(np.max(x_theo) + pad_x), padding=0)
                pad_y = (np.max(out["t_theo"]) - np.min(out["t_theo"])) * 0.05
                self.pw.setYRange(float(np.min(out["t_theo"]) - pad_y), float(np.max(out["t_theo"]) + pad_y), padding=0)

        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            logger.error("Failed to recalculate Smart Init preview", exc_info=True)
            self.lbl_rmse.setText(f"Error: {exc}")

    def refresh_knot_lines_and_ui(self) -> None:
        self.sk = self.state.sk
        self.n_phys = self.state.n_phys
        self.L_nodes = self.state.L_nodes
        self.preview_d_nm = self.state.preview_d_nm

        # Block slider signals to update them without triggers
        for sl in self.sliders_n:
            sl.blockSignals(True)
        for sl in self.sliders_L:
            sl.blockSignals(True)
        self.sl_d.blockSignals(True)

        for i in range(self.k_n):
            if i < len(self.sliders_n):
                self.sliders_n[i].setValue(int(round(float(self.n_phys[i]) * self.scale_n)))
                self.lbls_n[i].setText(f"{float(self.n_phys[i]):.4f}")
            if i < len(self.sliders_L):
                self.sliders_L[i].setValue(int(round(float(self.L_nodes[i]) * self.scale_L)))
                self.lbls_L[i].setText(f"{float(self.L_nodes[i]):.2f}")

        self.sl_d.setValue(int(round(self.preview_d_nm * self.scale_d)))
        self.lbl_d.setText(f"{self.preview_d_nm:.2f} nm")

        for sl in self.sliders_n:
            sl.blockSignals(False)
        for sl in self.sliders_L:
            sl.blockSignals(False)
        self.sl_d.blockSignals(False)

        self.recalculate()

    @safe_ui_action
    def apply_preset(self, preset_name: str) -> None:
        try:
            target_sk = np.asarray(self.state.sk, dtype=np.float64).ravel()
            projector = lambda sk: project_manual_material_preset(
                self.cfg, preset_name, sk, d_nm_hint=self.state.preview_d_nm
            )
            self.parent_worker._execute_smart_init_preset_logic(self.cfg, projector, self._relax_si_mono, self.state)
            self.refresh_knot_lines_and_ui()
            logger.info("Smart Init Preset Applied: %s", preset_name)
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            QMessageBox.warning(self.dlg, "Apply Preset", f"Preset failed: {exc}")

    @safe_ui_action
    def auto_find_best_preset(self) -> None:
        try:
            target_sk = np.asarray(self.state.sk, dtype=np.float64).ravel()
            picked = self.parent_worker._pick_best_smart_init_material_preset(
                self.cfg, target_sk, self.state.preview_d_nm, self._relax_si_mono
            )
            if picked is None:
                QMessageBox.information(
                    self.dlg,
                    "Auto preset selection",
                    "No material preset produced a lower RMSE score than the current profile.",
                )
                return

            winner, rm_w, d_w = picked
            self.apply_preset(winner)
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            QMessageBox.warning(self.dlg, "Auto Select Preset", f"Preset failed: {exc}")

    @safe_ui_action
    def save_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self.dlg, "Save current config (Smart Init)", "", "JSON Files (*.json);;All Files (*.*)"
        )
        if not path:
            return
        try:
            out_d = {
                "sigma_knots": np.asarray(self.state.sk, dtype=float).ravel().tolist(),
                "n_nodes_physical": np.asarray(self.state.n_phys, dtype=float).ravel().tolist(),
                "L_nodes": np.asarray(self.state.L_nodes, dtype=float).ravel().tolist(),
                "d_nm": float(self.state.preview_d_nm),
                "rmse": float(self.state.current_rmse),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out_d, f, indent=2)
            show_toast(self.dlg, "Config saved successfully", level="success")
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self.dlg, "Save Config", f"Save failed: {exc}")

    @safe_ui_action
    def run_auto_opt(self, is_ln_k: bool = False) -> None:
        try:
            row = int(self.sp_opt_row.value() - 1)
            err = self.parent_worker._execute_smart_init_run_auto(
                self.cfg,
                row,
                is_ln_k,
                self.L_lo_g,
                self.L_hi_g,
                self._relax_si_mono,
                self.state,
            )
            if err:
                QMessageBox.warning(self.dlg, "Optimize knot", err)
                return

            self.refresh_knot_lines_and_ui()
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            QMessageBox.warning(self.dlg, "Optimize knot", f"Optimization failed: {exc}")

    @safe_ui_action
    def run_fast_local_search(self) -> None:
        # Launch QDialog for auto-fit wait feedback
        progress = QMessageBox(self.dlg)
        progress.setWindowTitle("Autofind")
        progress.setText("Executing fast local search on thickness & indices...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        QApplication.processEvents()

        try:
            cur_sk = np.asarray(self.state.sk, dtype=np.float64).ravel()
            n_loc = np.asarray(self.state.n_phys, dtype=np.float64).ravel()
            L_loc = np.asarray(self.state.L_nodes, dtype=np.float64).ravel()

            auto_cfg, sk_canon, k_loc = self.parent_worker._prepare_smart_init_autofind_config(
                self.cfg, cur_sk, n_loc, L_loc, self.state.preview_d_nm
            )

            from certus.spline.spline_workers import _run_single_spline_stage
            best = _run_single_spline_stage(auto_cfg, sk_canon, "regridding")

            progress.close()

            if not isinstance(best, dict) or best.get("success") is False:
                QMessageBox.warning(
                    self.dlg,
                    "Local Search",
                    f"Local search failed: {best.get('message') if isinstance(best, dict) else 'Unknown error'}",
                )
                return

            size_match = self.parent_worker._apply_smart_init_autofind_result(best, k_loc, sk_canon, self.state)
            if not size_match:
                QMessageBox.warning(
                    self.dlg,
                    "Local Search",
                    "Autofind succeeded but returned inconsistent size vectors. Discarding result.",
                )
                return

            self.refresh_knot_lines_and_ui()
            show_toast(self.dlg, "Autofind local search succeeded!", level="success")

        except Exception as exc:
            progress.close()
            logger.exception("Autofind failed")
            QMessageBox.warning(self.dlg, "Local Search", f"Search aborted: {exc}")

    @safe_ui_action
    def recall_best(self) -> None:
        try:
            err = self.parent_worker._execute_smart_init_recall_best(self.state)
            if err:
                QMessageBox.warning(self.dlg, "Recall Best", err)
                return
            self.refresh_knot_lines_and_ui()
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            QMessageBox.warning(self.dlg, "Recall Best", f"Recall failed: {exc}")

    @safe_ui_action
    def open_curve_editor(self) -> None:
        # Build n/k points from current state
        try:
            lam_knots = np.sort(1.0 / np.maximum(self.state.sk, 1e-9))
            k_knots = np.exp(np.maximum(self.state.L_nodes, -300.0))
            
            # Open the visual curve editor dialog
            editor = SmartInitNKCurveEditorDialog(
                self.dlg,
                lam_knots,
                self.state.n_phys.copy(),
                k_knots,
                d_nm=self.state.preview_d_nm,
            )
            
            if editor.exec() == QDialog.DialogCode.Accepted:
                n_new, k_new, d_new = editor.get_curves()
                
                # Regrid the manual nodes onto current sigma knots
                self.state.n_phys = np.asarray(n_new, dtype=np.float64).ravel()
                self.state.L_nodes = np.log(np.maximum(k_new, 1e-300))
                self.state.preview_d_nm = float(d_new)
                
                self.refresh_knot_lines_and_ui()
                show_toast(self.dlg, "Curves imported from visual editor!", level="success")
        except Exception as exc:
            logger.exception("NK curve editor failed")
            QMessageBox.warning(self.dlg, "NK Curve Editor", f"Failed to edit curves: {exc}")

    def on_keep(self) -> None:
        if self._on_keep_called[0]:
            return
        self._on_keep_called[0] = True
        try:
            self.parent_worker._on_smart_init_keep(self.dlg, self.cfg, self.state, {
                "chk_si_deep": self.chk_si_deep,
                "chk_si_two_phase": self.chk_si_two_phase,
                "relax_si_mono": self._relax_si_mono,
            })
        except Exception:
            logger.exception("Error in Smart Init Keep dispatch")
            self._on_keep_called[0] = False


def _smart_init_pw_nk_clipboard_df(curve_n: Any, curve_pk: Any) -> pd.DataFrame | None:
    """Build a DataFrame for Excel export from n(lambda) and ln k(lambda) plot items (k = exp(ln k), capped)."""
    xn, yn = curve_n.getData()
    xk, yk_ln = curve_pk.getData()

    xn = np.asarray(xn if xn is not None else [], dtype=float).ravel()
    yn = np.asarray(yn if yn is not None else [], dtype=float).ravel()
    xk = np.asarray(xk if xk is not None else [], dtype=float).ravel()
    yk_ln = np.asarray(yk_ln if yk_ln is not None else [], dtype=float).ravel()

    yk_k = np.full(yk_ln.shape, np.nan, dtype=float)
    m_ln = np.isfinite(yk_ln)
    yk_k[m_ln] = np.exp(np.minimum(yk_ln[m_ln], 700.0))

    n = int(max(xn.size, yn.size, xk.size, yk_k.size))
    if n == 0:
        return None

    def _pad(a: np.ndarray) -> np.ndarray:
        a = np.asarray(a, dtype=float).ravel()
        if a.size >= n:
            return a[:n].copy()
        return np.pad(a, (0, n - a.size), constant_values=np.nan)

    if xn.size == xk.size and xn.size > 0 and np.allclose(xn, xk, equal_nan=True):
        return pd.DataFrame({"lambda_nm": _pad(xn), "n": _pad(yn), "k": _pad(yk_k)})

    return pd.DataFrame(
        {
            "lambda_nm_n": _pad(xn),
            "n": _pad(yn),
            "lambda_nm_k": _pad(xk),
            "k": _pad(yk_k),
        }
    )
