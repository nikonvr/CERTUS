from __future__ import annotations
from certus.ui.certus_index_spline_common import *
from certus.spline.certus_index_spline_core import SPLINE_PERF_PRESETS

class Step4MeshOptimizerBuilder:
    def __init__(self, app: "CertusIndexSplineApp", parent_layout: "QVBoxLayout", style: str):
        self.app = app
        self.parent_layout = parent_layout
        self.style = style

    def build(self) -> None:
        app = self.app
        parent_layout = self.parent_layout
        style = self.style
        box4 = CertusCard("Advanced settings")

        box4.setStyleSheet(style)
        box4.body.setContentsMargins(6, 4, 6, 4)
        box4.body.setSpacing(4)

        box4.setToolTip("Advanced optimization budgets and uncertainty/corridor controls.")

        g4 = QGridLayout()
        g4.setContentsMargins(0, 0, 0, 0)
        g4.setHorizontalSpacing(6)
        g4.setVerticalSpacing(4)

        box4.body.addLayout(g4)

        r4 = 0

        # --- Local budget + uncertainty: full panel (hidden in simplified interface) ---

        app._w_full_adv = QWidget()

        v_adv = QVBoxLayout(app._w_full_adv)

        v_adv.setContentsMargins(0, 0, 0, 0)

        v_adv.setSpacing(4)

        lb_pg = QLabel("Local iterations hint (max):")

        lb_pg.setToolTip("Legacy control kept for compatibility; inactive in local-only INDEX-SPLINE mode.")

        app.sp_pg_iter = QSpinBox()

        app.sp_pg_iter.setRange(5, 120)

        app.sp_pg_iter.setValue(int(SPLINE_PERF_PRESETS.get("fast", {}).get("pglobal_max_iter", 35)))

        app.sp_pg_iter.setToolTip("Inactive in local-only mode; kept only for preset/config compatibility.")

        app.sp_pg_iter.setEnabled(False)

        row_pg = QHBoxLayout()

        row_pg.addWidget(lb_pg)

        row_pg.addWidget(app.sp_pg_iter, 1)

        v_adv.addLayout(row_pg)

        lb_pr = QLabel("Performance profile:")

        lb_pr.setToolTip(
            'Budget preset: polish budget and local searches. "Maximal" gives best quality at the expense of runtime.'
        )

        app.cb_profilee = QComboBox()

        for lab, key in [
            ("Fast", "fast"),
            ("Standard", "standard"),
            ("Quality", "quality"),
            ("Maximal", "max"),
        ]:
            app.cb_profilee.addItem(lab, key)

        app.cb_profilee.setCurrentIndex(0)

        app.cb_profilee.setToolTip(
            "When the profile changes, a recommended local budget may be applied automatically to the spin."
        )

        app.cb_profilee.currentIndexChanged.connect(app._on_profilee_changed)

        row_pf = QHBoxLayout()

        row_pf.addWidget(lb_pr)

        row_pf.addWidget(app.cb_profilee, 1)

        v_adv.addLayout(row_pf)

        lb_mesh_dlam = QLabel("Min. Deltalambda/lambda step (sigma mesh) :")

        lb_mesh_dlam.setToolTip(
            "Canonical mesh constraint: min(delta-lambda between nodes) / lambda >= this value, "
            "with lambda? = (lambda_min + lambda_max) / 2 from file. Number of segments is reduced if needed; "
            "IR extension (+2 knots) is omitted if it violates threshold.\n"
            "0 = disabled (nominal behavior without this constraint)."
        )

        app.sp_mesh_min_dlam = QDoubleSpinBox()

        app.sp_mesh_min_dlam.setRange(0.0, 0.5)

        app.sp_mesh_min_dlam.setDecimals(4)

        app.sp_mesh_min_dlam.setSingleStep(0.0025)

        app.sp_mesh_min_dlam.setValue(0.02)

        app.sp_mesh_min_dlam.setSpecialValueText("disabled")

        app.sp_mesh_min_dlam.setToolTip(lb_mesh_dlam.toolTip())

        row_mesh_dlam = QHBoxLayout()

        row_mesh_dlam.addWidget(lb_mesh_dlam)

        row_mesh_dlam.addWidget(app.sp_mesh_min_dlam, 1)

        v_adv.addLayout(row_mesh_dlam)

        lb_auto_clean_v2 = QLabel("Auto-clean V2 (neighbor pull):")
        lb_auto_clean_v2.setToolTip(
            "After removing an internal knot, optionally adjusts the two local neighboring knots\n"
            "(extremes never moved), then re-optimizes RMSE.\n\n"
            "V2 explores symmetric/asymmetric pulls and a small local 2D refinement."
        )
        app.chk_auto_clean_neighbor_pull = QCheckBox("Enable local neighbor pull")
        app.chk_auto_clean_neighbor_pull.setChecked(bool(getattr(app, "_auto_clean_neighbor_pull_enabled", True)))
        app.chk_auto_clean_neighbor_pull.setToolTip(lb_auto_clean_v2.toolTip())
        row_ac0 = QHBoxLayout()
        row_ac0.addWidget(lb_auto_clean_v2)
        row_ac0.addWidget(app.chk_auto_clean_neighbor_pull)
        row_ac0.addStretch(1)
        v_adv.addLayout(row_ac0)

        row_ac1 = QHBoxLayout()
        row_ac1.addWidget(QLabel("pull ratios"))
        app.sp_auto_clean_pull_r1 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r1.setDecimals(3)
        app.sp_auto_clean_pull_r1.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r1.setSingleStep(0.01)
        app.sp_auto_clean_pull_r1.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r1", 0.10)))
        app.sp_auto_clean_pull_r1.setToolTip("First inward pull ratio (recommended: 0.10).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r1)
        app.sp_auto_clean_pull_r2 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r2.setDecimals(3)
        app.sp_auto_clean_pull_r2.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r2.setSingleStep(0.01)
        app.sp_auto_clean_pull_r2.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r2", 0.20)))
        app.sp_auto_clean_pull_r2.setToolTip("Second inward pull ratio (recommended: 0.20).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r2)
        app.sp_auto_clean_pull_r3 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r3.setDecimals(3)
        app.sp_auto_clean_pull_r3.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r3.setSingleStep(0.01)
        app.sp_auto_clean_pull_r3.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r3", 0.30)))
        app.sp_auto_clean_pull_r3.setToolTip("Third inward pull ratio (recommended: 0.30).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r3)
        row_ac1.addStretch(1)
        v_adv.addLayout(row_ac1)

        row_ac2 = QHBoxLayout()
        app.chk_auto_clean_neighbor_pull_local_refine = QCheckBox("Enable local 2D refine")
        app.chk_auto_clean_neighbor_pull_local_refine.setChecked(
            bool(getattr(app, "_auto_clean_neighbor_pull_local_refine_enabled", False))
        )
        app.chk_auto_clean_neighbor_pull_local_refine.setToolTip(
            "After selecting the best pull variant for one removed knot, run a tiny 2D local\n"
            "search on the two adjacent knots to further reduce RMSE."
        )
        row_ac2.addWidget(app.chk_auto_clean_neighbor_pull_local_refine)
        row_ac2.addWidget(QLabel("refine rel. step"))
        app.sp_auto_clean_neighbor_pull_local_refine_step = QDoubleSpinBox()
        app.sp_auto_clean_neighbor_pull_local_refine_step.setDecimals(3)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setRange(0.005, 0.20)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setSingleStep(0.005)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setValue(
            float(getattr(app, "_auto_clean_neighbor_pull_local_refine_rel_step", 0.05))
        )
        app.sp_auto_clean_neighbor_pull_local_refine_step.setToolTip(
            "Relative step used by the local 2D refine around neighboring knots (recommended: 0.05)."
        )
        row_ac2.addWidget(app.sp_auto_clean_neighbor_pull_local_refine_step)
        row_ac2.addStretch(1)
        v_adv.addLayout(row_ac2)

        # --- Search depth (LOT E) ---
        row_ac3 = QHBoxLayout()
        row_ac3.addWidget(QLabel("Top-N candidates (auto-clean):"))
        app.sp_auto_clean_top_n = QSpinBox()
        app.sp_auto_clean_top_n.setRange(1, 12)
        app.sp_auto_clean_top_n.setValue(int(getattr(app, "_auto_clean_top_n_sensitivity", 4)))
        app.sp_auto_clean_top_n.setToolTip(
            "Number of removal candidates per step passed to the full polish "
            "(higher values = deeper but slower search). Recommended: 4."
        )
        row_ac3.addWidget(app.sp_auto_clean_top_n)

        row_ac3.addWidget(QLabel("Polish maxfun candidat:"))
        app.sp_auto_clean_cand_maxfun = QSpinBox()
        app.sp_auto_clean_cand_maxfun.setRange(120, 4000)
        app.sp_auto_clean_cand_maxfun.setSingleStep(100)
        app.sp_auto_clean_cand_maxfun.setValue(int(getattr(app, "_auto_clean_candidate_polish_maxfun", 700)))
        app.sp_auto_clean_cand_maxfun.setToolTip("L-BFGS-B budget per removal candidate (recommended: 700-1500).")
        row_ac3.addWidget(app.sp_auto_clean_cand_maxfun)

        row_ac3.addWidget(QLabel("Tolerance RMSE:"))
        app.sp_auto_clean_tol = QDoubleSpinBox()
        app.sp_auto_clean_tol.setDecimals(6)
        app.sp_auto_clean_tol.setRange(0.0, 1.0e-2)
        app.sp_auto_clean_tol.setSingleStep(1.0e-5)
        app.sp_auto_clean_tol.setValue(float(getattr(app, "_auto_clean_ui_tolerance", 5.0e-5)))
        app.sp_auto_clean_tol.setToolTip("Absolute RMSE regression tolerated per removal. 0 = strict mode.")
        row_ac3.addWidget(app.sp_auto_clean_tol)
        row_ac3.addStretch(1)
        v_adv.addLayout(row_ac3)

        lb_cor = QLabel("Corridors n/k (d profiling):")

        lb_cor.setToolTip(
            "Calculate a plausible thickness interval and n(lambda), k(lambda) corridors by fixing d, then re-optimizing\n"
            "the n and ln k nodes with the same penalties and masked RMSE as the fit.\n\n"
            "RMSE_ref+Delta mode (default): accepted RMSE <= best polished spectral RMSE + Delta; the nominal 'best' curve\n"
            "is a native member of the envelope (not a pseudo-confidence interval centered on a heuristic refit).\n"
            "Alpha mode: RMSE(d) <= alpha * RMSE_opt (heuristic).\n\n"
            "Enabled by default at the end of optimization; results appear in the 'Corridors n/k' tab."
        )

        app.chk_corridor_d = QCheckBox("Enable")

        app.chk_corridor_d.setChecked(True)

        app.chk_corridor_d.setToolTip(lb_cor.toolTip())

        row_cd = QHBoxLayout()

        row_cd.addWidget(lb_cor)

        row_cd.addWidget(app.chk_corridor_d)

        app.lbl_corridors_state_adv = QLabel()

        app.lbl_corridors_state_adv.setTextFormat(Qt.TextFormat.RichText)

        app.lbl_corridors_state_adv.setToolTip(
            "Read-only: same state as the 'Corridors' button under Run (Yes = computation at the end of optimization)."
        )

        row_cd.addWidget(app.lbl_corridors_state_adv)

        row_cd.addStretch(1)

        v_adv.addLayout(row_cd)

        row_cor = QHBoxLayout()

        app.cb_corr_mode = QComboBox()

        app.cb_corr_mode.addItem("Heuristic (alpha?RMSE_opt)", "alpha")

        app.cb_corr_mode.addItem("RMSE_ref + Delta (absolute)", "abs_delta")

        app.cb_corr_mode.addItem("RMSE_ref + Delta adaptive (local)", "abs_delta_adaptive")

        app.cb_corr_mode.addItem("Likelihood ratio (Delta^2) - constant sigma or residual", "lr")

        _iad = app.cb_corr_mode.findData("abs_delta_adaptive")

        app.cb_corr_mode.setCurrentIndex(int(_iad) if _iad >= 0 else 0)

        app.cb_corr_mode.setToolTip(
            "Alpha mode: RMSE(d) <= alpha * RMSE_opt (heuristic).\n"
            "RMSE_ref + Delta: RMSE(d) <= RMSE_ref + Delta (same spectral mask). With 'best RMSE' checked, RMSE_ref = "
            "spectral_rmse_best_value (best polish); otherwise base curves from the dict.\n"
            "RMSE_ref + Delta adaptive: Delta is estimated locally from the profiled RMSE(d) parabola and local roughness.\n"
            "LR: Delta^2 <= chi^2(1, conf); constant sigma or sigma_i(lambda) ~ |residual| when residual sigma is enabled."
        )

        row_cor.addWidget(QLabel("mode"))

        row_cor.addWidget(app.cb_corr_mode)

        app.cb_corr_mode.currentIndexChanged.connect(app._on_corr_mode_changed)

        app.sp_corr_alpha = QDoubleSpinBox()

        app.sp_corr_alpha.setDecimals(3)

        app.sp_corr_alpha.setRange(1.000, 2.000)

        app.sp_corr_alpha.setSingleStep(0.005)

        app.sp_corr_alpha.setValue(1.05)

        app.sp_corr_alpha.setToolTip("Alpha threshold: RMSE threshold = alpha * RMSE_opt (e.g. 1.05 = +5%).")

        app.lbl_corr_alpha = QLabel("alpha")

        row_cor.addWidget(app.lbl_corr_alpha)

        row_cor.addWidget(app.sp_corr_alpha)

        app.lbl_corr_rmse_delta = QLabel("Delta RMSE abs.")

        app.sp_corr_rmse_delta = QDoubleSpinBox()

        app.sp_corr_rmse_delta.setDecimals(5)

        app.sp_corr_rmse_delta.setRange(0.00005, 0.05)

        app.sp_corr_rmse_delta.setSingleStep(0.00005)

        from certus.ui.certus_index_spline_common import _DEFAULT_CORRIDOR_RMSE_DELTA as default_delta
        app.sp_corr_rmse_delta.setValue(float(default_delta))

        app.sp_corr_rmse_delta.setToolTip(
            "Absolute margin on masked spectral RMSE: a refit at fixed d is accepted if "
            "RMSE <= RMSE_ref + Delta (default 2.5e-4; adaptive Delta_eff floor 2.5e-5). "
            "With best polished RMSE, RMSE_ref is the one of the exported model."
        )

        row_cor.addWidget(app.lbl_corr_rmse_delta)

        row_cor.addWidget(app.sp_corr_rmse_delta)

        app.chk_corr_scientific_nominal = QCheckBox("best RMSE")

        app.chk_corr_scientific_nominal.setChecked(True)

        app.chk_corr_scientific_nominal.setToolTip(
            "Scientific corridor mode (only if mode = RMSE_ref + Delta): RMSE_ref = spectral_rmse_best_value; "
            "nominal curves and nodes are aligned on the best polished model; no envelope widening toward the "
            "main solver curve. Uncheck to use legacy abs_delta behavior on base curves only."
        )

        row_cor.addWidget(app.chk_corr_scientific_nominal)

        app.btn_corr_preset_auto_robust = create_styled_button("Auto robust", "secondary", parent=app)

        app.btn_corr_preset_auto_robust.setToolTip(
            "Recommended settings for the d corridor: adaptive RMSE_ref + Delta mode (local), "
            "expanded parabolic window, thickness interval symmetrized around the parabola peak, "
            "side probes, and a reinforced Delta floor. Default behavior after migration."
        )

        app.btn_corr_preset_auto_robust.clicked.connect(app._apply_corridor_preset_auto_robust)

        row_cor.addWidget(app.btn_corr_preset_auto_robust)

        app.sp_corr_conf = QDoubleSpinBox()

        app.sp_corr_conf.setDecimals(3)

        app.sp_corr_conf.setRange(0.50, 0.999)

        app.sp_corr_conf.setSingleStep(0.01)

        app.sp_corr_conf.setValue(0.95)

        app.sp_corr_conf.setToolTip("LR confidence level (df=1): e.g. 0.95 -> Delta^2 ~ 3.84.")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("conf"))

        row_cor.addWidget(app.sp_corr_conf)

        app.sp_corr_sigma = QDoubleSpinBox()

        app.sp_corr_sigma.setDecimals(6)

        app.sp_corr_sigma.setRange(0.0, 1.0)

        app.sp_corr_sigma.setSingleStep(0.001)

        app.sp_corr_sigma.setValue(0.0)

        app.sp_corr_sigma.setToolTip(
            "Constant sigma (T and R) in fraction units (not %). 0 = auto (sigma := RMSE_opt)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("sigma"))

        row_cor.addWidget(app.sp_corr_sigma)

        app.sp_corr_step = QDoubleSpinBox()

        app.sp_corr_step.setDecimals(2)

        app.sp_corr_step.setRange(0.1, 50.0)

        app.sp_corr_step.setSingleStep(0.5)

        app.sp_corr_step.setValue(1.0)

        app.sp_corr_step.setToolTip("d continuation step size (nm).")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("step (nm)"))

        row_cor.addWidget(app.sp_corr_step)

        app.sp_corr_span = QDoubleSpinBox()

        app.sp_corr_span.setDecimals(1)

        app.sp_corr_span.setRange(1.0, 2000.0)

        app.sp_corr_span.setSingleStep(1.0)

        app.sp_corr_span.setValue(15.0)

        app.sp_corr_span.setToolTip(
            "Maximum offset |d - d_opt| explored in each direction (+d and -d), in nm (not the sum). "
            "Default 15 nm ~ local neighborhood around the optimal thickness."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("span (nm)"))

        row_cor.addWidget(app.sp_corr_span)

        # Multi-start (V2.2): robustness to local minima during fixed-d refit.

        app.sp_corr_starts = QSpinBox()

        app.sp_corr_starts.setRange(1, 25)

        app.sp_corr_starts.setValue(1)

        app.sp_corr_starts.setToolTip(
            "Number of initializations (multi-start) per d value. 1 = continuation only (fast). "
            ">1 increases robustness (best solution kept), at the cost of computation time."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(QLabel("starts"))

        row_cor.addWidget(app.sp_corr_starts)

        app.sp_corr_jn = QDoubleSpinBox()

        app.sp_corr_jn.setDecimals(3)

        app.sp_corr_jn.setRange(0.0, 1.0)

        app.sp_corr_jn.setSingleStep(0.01)

        app.sp_corr_jn.setValue(0.02)

        app.sp_corr_jn.setToolTip("Gaussian jitter sigma on n (or ? if monotonicity active) for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_n"))

        row_cor.addWidget(app.sp_corr_jn)

        app.sp_corr_jL = QDoubleSpinBox()

        app.sp_corr_jL.setDecimals(3)

        app.sp_corr_jL.setRange(0.0, 5.0)

        app.sp_corr_jL.setSingleStep(0.05)

        app.sp_corr_jL.setValue(0.15)

        app.sp_corr_jL.setToolTip("Gaussian jitter sigma on L=ln k for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_L"))

        row_cor.addWidget(app.sp_corr_jL)

        app.sp_corr_seed = QSpinBox()

        app.sp_corr_seed.setRange(-(2**31), 2**31 - 1)

        app.sp_corr_seed.setValue(0)

        app.sp_corr_seed.setToolTip("RNG seed for multi-start reproducibility (jitter).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seed"))

        row_cor.addWidget(app.sp_corr_seed)

        # V2.3: ln(k) regularization sensitivity scan (d2(L)^2 weight).

        app.chk_corr_reg_sens = QCheckBox("scan reg")

        app.chk_corr_reg_sens.setChecked(False)

        app.chk_corr_reg_sens.setToolTip(
            "Runs a scan (log grid) of the ln(k) regularization weight and re-launches d profiling for each value.\n"
            "Goal: verify the robustness of the d interval and the n/k corridors to regularization choices."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(app.chk_corr_reg_sens)

        app.sp_corr_reg_pts = QSpinBox()

        app.sp_corr_reg_pts.setRange(2, 15)

        app.sp_corr_reg_pts.setValue(5)

        app.sp_corr_reg_pts.setToolTip("Number of points in the regularization scan log grid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("pts"))

        row_cor.addWidget(app.sp_corr_reg_pts)

        app.sp_corr_reg_dec = QSpinBox()

        app.sp_corr_reg_dec.setRange(0, 6)

        app.sp_corr_reg_dec.setValue(2)

        app.sp_corr_reg_dec.setToolTip("Number of decades on each side of the base weight (lnk_spline_reg_weight).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("dec"))

        row_cor.addWidget(app.sp_corr_reg_dec)

        # V2.4: parametric bootstrap for publication-level bands

        app.chk_corr_boot = QCheckBox("bootstrap")

        app.chk_corr_boot.setChecked(False)

        app.chk_corr_boot.setToolTip(
            "Parametric bootstrap: generates B T/R datasets by adding Gaussian noise (sigma_T, sigma_R),\n"
            "re-launches d profiling for each replication, then computes percentile bands on n(lambda), k(lambda)\n"
            "and a distribution of the d interval."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(app.chk_corr_boot)

        app.sp_corr_boot_n = QSpinBox()

        app.sp_corr_boot_n.setRange(5, 500)

        app.sp_corr_boot_n.setValue(40)

        app.sp_corr_boot_n.setToolTip("Number of bootstrap replications (B). Larger = more robust, but slower.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("B"))

        row_cor.addWidget(app.sp_corr_boot_n)

        app.sp_corr_boot_p = QDoubleSpinBox()

        app.sp_corr_boot_p.setDecimals(3)

        app.sp_corr_boot_p.setRange(0.50, 0.999)

        app.sp_corr_boot_p.setSingleStep(0.01)

        app.sp_corr_boot_p.setValue(0.95)

        app.sp_corr_boot_p.setToolTip("Central percentile (e.g. 0.95 => bounds 2.5% / 97.5%).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("p"))

        row_cor.addWidget(app.sp_corr_boot_p)

        app.sp_corr_boot_seed = QSpinBox()

        app.sp_corr_boot_seed.setRange(-(2**31), 2**31 - 1)

        app.sp_corr_boot_seed.setValue(0)

        app.sp_corr_boot_seed.setToolTip("Seed RNG bootstrap.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seedB"))

        row_cor.addWidget(app.sp_corr_boot_seed)

        app.cb_corr_boot_mode = QComboBox()

        app.cb_corr_boot_mode.addItem("parametric (T/R + N(0,sigma))", "parametric")

        app.cb_corr_boot_mode.addItem("residual (T_th + residuals*)", "residual")

        app.cb_corr_boot_mode.setCurrentIndex(0)

        app.cb_corr_boot_mode.setToolTip(
            "parametric: adds Gaussian noise to measurements.\n"
            "residual: non-parametric bootstrap on residuals (more realistic if noise is non-Gaussian / correlated)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(app.cb_corr_boot_mode)

        app.sp_corr_boot_block = QSpinBox()

        app.sp_corr_boot_block.setRange(1, 5000)

        app.sp_corr_boot_block.setValue(1)

        app.sp_corr_boot_block.setToolTip("Block length (in lambda points) for residual bootstrap. 1 = iid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("blk"))

        row_cor.addWidget(app.sp_corr_boot_block)

        app._on_corr_mode_changed()

        w_cor = QWidget()

        w_cor.setLayout(row_cor)

        v_adv.addWidget(w_cor)

        row_cor_prof = QHBoxLayout()

        app.sp_corr_prof_maxfun = QSpinBox()

        app.sp_corr_prof_maxfun.setRange(0, 200000)

        app.sp_corr_prof_maxfun.setSingleStep(500)

        app.sp_corr_prof_maxfun.setValue(2500)

        app.sp_corr_prof_maxfun.setToolTip(
            "L-BFGS-B budget (maxfun) for each refit of n, ln k nodes at fixed d during corridor profiling.\n"
            "0 = reuse the main run polish_maxfun (often 8000+, very slow per step).\n"
            "Typ. 1500-4000 for a local scan; increase if 'EXCEEDS LIMIT' messages or poor refits."
        )

        row_cor_prof.addWidget(QLabel("d profiling: maxfun / refit"))

        row_cor_prof.addWidget(app.sp_corr_prof_maxfun)

        row_cor_prof.addStretch(1)

        w_cor_prof = QWidget()

        w_cor_prof.setLayout(row_cor_prof)

        v_adv.addWidget(w_cor_prof)

        row_cor_v25 = QHBoxLayout()

        app.chk_corr_sigma_hetero = QCheckBox("sigma(lambda) residual")
        app.chk_corr_sigma_hetero.setToolTip(
            "Heteroscedastic residual model: local regression plus parametric bootstrap."
        )

        app.chk_corr_sigma_hetero.setChecked(False)

        app.chk_corr_sigma_hetero.setToolTip(
            "In LR mode: ?^2 with sigma_i = max(floor, scale?|y_exp-y_th|) on the objective grid.\n"
            "Parametric bootstrap: same sigma_i for Gaussian noise on T/R (objective points only)."
        )

        row_cor_v25.addWidget(app.chk_corr_sigma_hetero)

        app.sp_corr_hetero_scale = QDoubleSpinBox()

        app.sp_corr_hetero_scale.setDecimals(3)

        app.sp_corr_hetero_scale.setRange(0.0, 20.0)

        app.sp_corr_hetero_scale.setSingleStep(0.05)

        app.sp_corr_hetero_scale.setValue(1.0)

        app.sp_corr_hetero_scale.setToolTip("Scale factor on |residual| for sigma_i(lambda) (0 = floor only).")

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("scale sigma(lambda)"))

        row_cor_v25.addWidget(app.sp_corr_hetero_scale)

        app.chk_corr_boot_refit = QCheckBox("Fast bootstrap refit")
        app.chk_corr_boot_refit.setToolTip("Parametric bootstrap: refit each resample instead of reusing the fit.")

        app.chk_corr_boot_refit.setChecked(False)

        app.chk_corr_boot_refit.setToolTip(
            "After each bootstrap trial: a short L-BFGS-B on (d + nodes) using noisy T/R, "
            "same spectral objective as main run (n,L interp. in sigma = cubic spline), "
            "then profiling in d from this refit (often more consistent than freezing initial mesh)."
        )

        row_cor_v25.addSpacing(12)

        row_cor_v25.addWidget(app.chk_corr_boot_refit)

        app.sp_corr_boot_maxfun = QSpinBox()

        app.sp_corr_boot_maxfun.setRange(0, 200000)

        app.sp_corr_boot_maxfun.setValue(4000)

        app.sp_corr_boot_maxfun.setToolTip(
            "L-BFGS-B maxfun budget per bootstrap refit (0 = disabled even if box is checked)."
        )

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("maxfun"))

        row_cor_v25.addWidget(app.sp_corr_boot_maxfun)

        app.sp_corr_boot_workers = QSpinBox()

        app.sp_corr_boot_workers.setRange(1, 64)

        app.sp_corr_boot_workers.setValue(1)

        app.sp_corr_boot_workers.setToolTip(
            "Number of parallel processes for bootstrap replications (1 = sequential). "
            f"Typ. 2-{max(2, multiprocessing.cpu_count() or 4)} on this machine "
            f"({multiprocessing.cpu_count() or '?'} cores). "
            "Pickle or worker failure -> automatic fallback to sequential."
        )

        row_cor_v25.addSpacing(10)

        row_cor_v25.addWidget(QLabel("proc."))

        row_cor_v25.addWidget(app.sp_corr_boot_workers)

        row_cor_v25.addStretch(1)

        w_cor2 = QWidget()

        w_cor2.setLayout(row_cor_v25)

        v_adv.addWidget(w_cor2)

        page_full_adv = QWidget()

        app._box4_full_adv_layout = QVBoxLayout(page_full_adv)

        app._box4_full_adv_layout.setContentsMargins(0, 0, 0, 0)

        app._box4_full_adv_layout.addWidget(app._w_full_adv)

        page_epure = QWidget()

        lay_ep = QVBoxLayout(page_epure)

        lay_ep.setContentsMargins(0, 0, 0, 0)

        btn_open_adv = create_styled_button("Advanced settings...", "secondary")

        btn_open_adv.setToolTip("Optimization budgets and detailed uncertainty/corridor options.")

        btn_open_adv.clicked.connect(app._open_advanced_settings_dialog)

        lay_ep.addWidget(btn_open_adv)

        app._stack_box4_adv = QStackedWidget()

        app._stack_box4_adv.addWidget(page_epure)

        app._stack_box4_adv.addWidget(page_full_adv)

        def _sync_adv_stack_height(_index: int = -1) -> None:
            try:
                current = app._stack_box4_adv.currentWidget()
                if current is None:
                    return
                h = max(1, int(current.sizeHint().height()))
                app._stack_box4_adv.setMinimumHeight(h)
                app._stack_box4_adv.setMaximumHeight(h)
            except (RuntimeError, ValueError):
                app.logger.debug("advanced_settings_stack_height_sync_failed", exc_info=True)

        app._stack_box4_adv.currentChanged.connect(_sync_adv_stack_height)
        QTimer.singleShot(0, _sync_adv_stack_height)

        g4.addWidget(app._stack_box4_adv, r4, 0, 1, 2)

        r4 += 1

        g4.setColumnStretch(1, 1)

        parent_layout.addWidget(box4)

