from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_ui import WelcomeGuideWidget, EnhancedProgressWidget

class CertusStratLayoutMixin:
    def apply_default_layout(self) -> None:

        main_splitter = self.centralWidget()

        if isinstance(main_splitter, QSplitter):
            total_width = self.width()

            main_splitter.setSizes([int(total_width / 2), int(total_width / 2)])

    def _apply_theme(self) -> None:

        font = CertusTheme.get_font(9)

        QApplication.instance().setFont(font)

        QApplication.instance().setStyle("Fusion")

        # Propagate theme to auxiliary windows if open

        if hasattr(self, "live_monitor_window") and self.live_monitor_window and self.live_monitor_window.isVisible():
            # Force style refresh for live monitor

            self.live_monitor_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

            # If it has plots, ideally update them too - generic refresh

            self.live_monitor_window.style().unpolish(self.live_monitor_window)

            self.live_monitor_window.style().polish(self.live_monitor_window)

        if hasattr(self, "results_window") and self.results_window and self.results_window.isVisible():
            self.results_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

        # Apply theme with STRAT-specific overrides

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}

            /* Labels are slightly subtler in STRAT */
            QLabel {{ color: {CertusTheme.TEXT_SUB}; font-weight: 500; }}
            """,
        )

    def _build_log_container(self) -> QWidget:
        """Build log container with Copy button (uses shared CertusLogPanel)."""

        panel = CertusLogPanel(title="LOGS", visible=False)

        self.log_text = panel.log_text

        self._log_panel = panel

        return panel

    def _build_gui(self) -> None:

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_split = main_splitter

        self.setCentralWidget(main_splitter)

        left_panel_widget = QWidget()

        left_panel_layout = QVBoxLayout(left_panel_widget)

        left_panel_widget.setMinimumWidth(280)

        # Removed MaximumWidth to allow resizing via splitter

        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        left_panel_layout.setSpacing(0)

        # 1. Standard Header (Pinned)

        header_widget = create_header_logo_widget(
            "STRAT",
            self.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_STRAT",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_panel_layout.addWidget(header_widget)

        # 2. Action Bar (Pinned)

        # Note: No export function passed as it's not standard in STRAT top bar yet.

        action_bar = create_top_actions_bar(
            self,
            self.save_configuration,
            self.load_configuration,
            export_func=None,
            help_func=lambda: open_documentation("CERTUS_STRAT"),
        )

        left_panel_layout.addWidget(action_bar)

        # 3. Scroll Area

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        left_panel_layout.addWidget(scroll_area)

        main_splitter.addWidget(left_panel_widget)

        controls_widget = QWidget()

        scroll_area.setWidget(controls_widget)

        controls_layout = QVBoxLayout(controls_widget)

        controls_layout.setSpacing(12)

        controls_layout.setContentsMargins(0, 0, 4, 0)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Build stack · 2 Configure optimization · 3 Run workflow · 4 Inspect strategies")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; line-height: 1.4; padding: 2px 0 4px 0;"
        )

        workflow_card.body.addWidget(workflow_hint)

        controls_layout.addWidget(workflow_card)

        self.tabs = QTabWidget()

        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tabs_card = CertusCard("Controls")

        tabs_card.body.setContentsMargins(0, 0, 0, 0)

        tabs_card.body.addWidget(self.tabs)

        controls_layout.addWidget(tabs_card)

        self._create_design_tab()

        self._create_optimization_tab()

        self._create_advanced_tab()

        self._create_why_certus_tab()

        controls_layout.addStretch()

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        main_splitter.addWidget(right_splitter)

        self.plot_stack = QStackedWidget()

        self.welcome_widget = WelcomeGuideWidget()

        self.plot_stack.addWidget(self.welcome_widget)

        self.main_plot_widget = QLabel()

        self.main_plot_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_plot_widget.setScaledContents(True)

        self.main_plot_widget.setStyleSheet(f"background-color: {CertusTheme.SURFACE};")

        self.plot_stack.addWidget(self.main_plot_widget)

        right_splitter.addWidget(self.plot_stack)

        log_widget = self._build_log_container()

        right_splitter.addWidget(log_widget)

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.status_bar.setSizeGripEnabled(False)

        self.zoom_label = QLabel("Zoom 100%")
        self.zoom_label.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding: 0 8px;"
        )

        self.toggle_details_btn = QPushButton("Show Details")

        self.toggle_details_btn.setCheckable(True)

        self.toggle_details_btn.setFixedWidth(118)

        self.toggle_details_btn.setToolTip("Show/hide the computation log panel below the plot area.")

        self.toggle_details_btn.setObjectName(OBJ.PRIMARY_BUTTON)

        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        self.status_bar.addWidget(self.toggle_details_btn)
        self.status_bar.addPermanentWidget(self.zoom_label)

        self.status_label = CertusStatusPill("Ready.", "ready")

        self.status_bar.addWidget(self.status_label, 1)

        self.stats_label = QLabel("♟️ 0  | 🎲 0  |  🌈️ 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: 700; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.stats_label.setToolTip(
            "♟️ Mining Strategies evaluated  |  🎲 Monte Carlo Simulations run  |  🌈 Spectral points processed"
        )

        self.status_bar.addPermanentWidget(self.stats_label)

        self.progress_bar = EnhancedProgressWidget(main_label="STRAT Execution")
        self.status_bar.addPermanentWidget(self.progress_bar)

        if getattr(self, "_log_panel", None):
            self._log_panel.copied.connect(lambda: self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"]))

    def _create_design_tab(self) -> None:

        design_tab = QWidget()

        self.tabs.addTab(design_tab, "Design")

        self.design_layout = QVBoxLayout(design_tab)

        self.design_layout.setSpacing(12)

        self.design_layout.setContentsMargins(5, 8, 5, 5)

        materials_container = CertusCard("Material Refractive Indices")

        materials_layout = QHBoxLayout()

        materials_layout.setSpacing(10)

        materials_layout.setContentsMargins(5, 12, 5, 5)

        materials_container.body.addLayout(materials_layout)

        layout_h = QVBoxLayout()

        self._create_material_group(layout_h, "High-Index (H)", "h", "H", _is_compact=True)

        layout_l = QVBoxLayout()

        self._create_material_group(layout_l, "Low-Index (L)", "l", "L", _is_compact=True)

        materials_layout.addLayout(layout_h, 1)

        materials_layout.addLayout(layout_l, 1)

        self.design_layout.addWidget(materials_container)

        top_settings_widget = QWidget()

        top_settings_layout = QHBoxLayout(top_settings_widget)

        top_settings_layout.setContentsMargins(0, 5, 0, 5)

        top_settings_layout.setSpacing(10)

        gb_sub = CertusCard("substrate_Base Wavelength")

        gb_sub_layout = QHBoxLayout()

        gb_sub_layout.setContentsMargins(10, 15, 10, 8)

        gb_sub.body.addLayout(gb_sub_layout)

        gb_sub_layout.setSpacing(10)

        lbl_sub = QLabel("substrate:")

        self.widgets["substrate_choice"] = QComboBox()

        self.widgets["substrate_choice"].addItems(["Custom"] + list(SUBSTRATE_MAPPING.keys()))

        self.widgets["substrate_choice"].setMinimumWidth(100)

        self.widgets["substrate_choice"].setToolTip(
            "substrate material. 'Custom' lets you enter a fixed real index below.\n"
            "Predefined substrates fill the index field automatically."
        )

        self.widgets["substrate_choice"].currentTextChanged.connect(self._on_substrate_choice_changed)

        lbl_idx = QLabel("Index:")

        self.widgets["nSub_custom"] = QLineEdit()

        self.widgets["nSub_custom"].setPlaceholderText("1.73")

        self.widgets["nSub_custom"].setFixedWidth(50)

        self.widgets["nSub_custom"].setToolTip(
            "Real part of the substrate refractive index (used when substrate = Custom)."
        )

        gb_sub_layout.addWidget(lbl_sub)

        gb_sub_layout.addWidget(self.widgets["substrate_choice"])

        gb_sub_layout.addWidget(lbl_idx)

        gb_sub_layout.addWidget(self.widgets["nSub_custom"])

        gb_lam = CertusCard("Reference")

        gb_lam_layout = QHBoxLayout()

        gb_lam_layout.setContentsMargins(10, 15, 10, 8)

        gb_lam.body.addLayout(gb_lam_layout)

        lbl_l0 = QLabel("Center lambda₀ (nm):")

        lbl_l0.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {CertusTheme.INFO_TEXT};")

        self.widgets["l0"] = QLineEdit()

        self.widgets["l0"].setFixedWidth(70)

        self.widgets["l0"].setStyleSheet(
            f"font-weight: bold; background-color: {CertusTheme.WARNING_BG}; border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; color: {CertusTheme.TEXT_MAIN};"
        )

        self.widgets["l0"].setToolTip(
            "Reference (center) wavelength lambda₀ in nanometres.\n"
            "Used as the nucleation anchor and to convert optical thicknesses (QWOT = lambda₀/4n).\n"
            "Also used as the nucleation wavelength for the first monochromatic monitoring block."
        )

        gb_lam_layout.addWidget(lbl_l0)

        gb_lam_layout.addWidget(self.widgets["l0"])

        top_settings_layout.addWidget(gb_sub)

        top_settings_layout.addWidget(gb_lam)

        self.design_layout.addWidget(top_settings_widget)

        self.stack_group = CertusCard("Stack Control & Workflow")

        cockpit_layout = QHBoxLayout()

        self.stack_group.body.addLayout(cockpit_layout)

        cockpit_layout.setContentsMargins(5, 15, 5, 5)

        cockpit_layout.setSpacing(80)

        tools_widget = QWidget()

        tools_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tools_grid = QGridLayout(tools_widget)

        tools_grid.setContentsMargins(0, 0, 0, 0)

        tools_grid.setSpacing(12)

        tools_grid.setColumnStretch(0, 1)

        tools_grid.setColumnStretch(1, 1)

        def set_std_icon(btn, pixmap_enum) -> None:

            btn.setIcon(self.style().standardIcon(pixmap_enum))

        self.add_btn = QPushButton("Add Layer")
        self.add_btn.setObjectName(OBJ.SUCCESS_BUTTON)

        self.add_btn.setFixedHeight(32)

        set_std_icon(self.add_btn, QStyle.StandardPixmap.SP_FileDialogNewFolder)

        self.add_btn.setToolTip("Add a new layer at the bottom of the stack table.")

        self.add_btn.clicked.connect(self.add_layer)

        self.remove_btn = QPushButton("Remove Layer")
        self.remove_btn.setObjectName(OBJ.DANGER_BUTTON)

        self.remove_btn.setFixedHeight(32)

        set_std_icon(self.remove_btn, QStyle.StandardPixmap.SP_TrashIcon)

        self.remove_btn.setToolTip("Remove the last (bottom) layer from the stack table.")

        self.remove_btn.clicked.connect(self.remove_layer)

        tools_grid.addWidget(self.add_btn, 0, 0)

        tools_grid.addWidget(self.remove_btn, 0, 1)

        btn_save = QPushButton("Save Config")

        btn_save.setFixedHeight(30)

        set_std_icon(btn_save, QStyle.StandardPixmap.SP_DialogSaveButton)

        btn_save.setToolTip("Save the current stack & all parameters to a JSON config file (Ctrl+S).")

        btn_save.clicked.connect(self.save_configuration)

        btn_load = QPushButton("Load Config")

        btn_load.setFixedHeight(30)

        set_std_icon(btn_load, QStyle.StandardPixmap.SP_DialogOpenButton)

        btn_load.setToolTip("Load a previously saved JSON config file, restoring stack & parameters (Ctrl+O).")

        btn_load.clicked.connect(self.load_configuration)

        tools_grid.addWidget(btn_save, 1, 0)

        tools_grid.addWidget(btn_load, 1, 1)

        self.load_strat_btn = QPushButton("Import Strat.")

        self.load_strat_btn.setFixedHeight(30)

        set_std_icon(self.load_strat_btn, QStyle.StandardPixmap.SP_ArrowDown)

        self.load_strat_btn.setToolTip(
            "Import an external strategies JSON file generated by a previous CERTUS-STRAT run.\n"
            "Allows direct comparison of strategies without re-running the full workflow."
        )

        self.load_strat_btn.clicked.connect(self.load_external_strategies)

        self.detach_btn = QPushButton("Pop-Out")

        self.detach_btn.setFixedHeight(30)

        set_std_icon(self.detach_btn, QStyle.StandardPixmap.SP_TitleBarNormalButton)

        self.detach_btn.setToolTip("Detach the Stack Definition table into its own floating window for easier editing.")

        self.detach_btn.clicked.connect(self.detach_stack_window)

        tools_grid.addWidget(self.load_strat_btn, 2, 0)

        tools_grid.addWidget(self.detach_btn, 2, 1)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.HLine)

        line.setStyleSheet(f"color:{CertusTheme.BORDER};")

        tools_grid.addWidget(line, 3, 0, 1, 2)

        self.run_step0_btn = QPushButton("Step 1 (Nominal)")
        self.run_step0_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step0_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step0_btn, QStyle.StandardPixmap.SP_ComputerIcon)

        self.run_step0_btn.setToolTip(
            "Step 0: Computes the basic optical response of the nominal layer stack without exploration."
        )

        self.run_step0_btn.clicked.connect(functools.partial(self.run_workflow, 0))

        tools_grid.addWidget(self.run_step0_btn, 4, 0)

        self.run_step2_btn = QPushButton("Step 2 (Opti)")
        self.run_step2_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step2_btn, QStyle.StandardPixmap.SP_BrowserReload)

        self.run_step2_btn.setToolTip(
            "Step 2: Launches the primary DP Optimization kernel based on the Target Spectrum."
        )

        self.run_step2_btn.clicked.connect(functools.partial(self.run_workflow, 2))

        tools_grid.addWidget(self.run_step2_btn, 4, 1)

        self.run_step3_btn = QPushButton("Step 3 (Rob)")
        self.run_step3_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step3_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step3_btn, QStyle.StandardPixmap.SP_DialogApplyButton)

        self.run_step3_btn.setEnabled(False)

        self.run_step3_btn.setToolTip(
            "Step 3: Simulates thousands of robust Monte-Carlo growth scenarios for yield estimation."
        )

        self.run_step3_btn.clicked.connect(functools.partial(self.run_workflow, 3))

        tools_grid.addWidget(self.run_step3_btn, 5, 0)

        self.stop_step2_btn = QPushButton("STOP Calculation")
        self.stop_step2_btn.setObjectName(OBJ.DANGER_BUTTON)
        self.stop_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.stop_step2_btn, QStyle.StandardPixmap.SP_MediaStop)

        self.stop_step2_btn.setToolTip(
            "Gracefully interrupt the running optimization.\n"
            "The engine will finish its current block and then proceed directly to Step 3 (robustness test)."
        )

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.stop_step2_btn.clicked.connect(self.request_stop_optimization)

        tools_grid.addWidget(self.stop_step2_btn, 5, 1)

        self.run_full_btn = QPushButton(" RUN FULL WORKFLOW")
        self.run_full_btn.setObjectName(OBJ.FEATURED_BUTTON)
        self.run_full_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.run_full_btn.setFixedHeight(42)

        set_std_icon(self.run_full_btn, QStyle.StandardPixmap.SP_MediaPlay)

        self.run_full_btn.setToolTip(
            "Run the complete workflow in one click:\n"
            "Step 2 (DP Strategy Search) -> Step 3 (Monte Carlo Robustness Validation).\n"
            "Equivalent to pressing Step 2 then Step 3 sequentially."
        )

        self.run_full_btn.clicked.connect(functools.partial(self.run_workflow, 23))

        tools_grid.addWidget(self.run_full_btn, 6, 0, 1, 2)

        # Clear / Reset button

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)

        self.clear_btn.setFixedHeight(32)

        tools_grid.addWidget(self.clear_btn, 7, 0, 1, 2)

        tools_grid.setRowStretch(8, 1)

        cockpit_layout.addWidget(tools_widget)

        self.widgets["stack_table"] = ExcelTableWidget()

        self.widgets["stack_table"].setColumnCount(3)

        self.widgets["stack_table"].setHorizontalHeaderLabels(["#", "Mat.", "Mult."])

        self.widgets["stack_table"].setFixedWidth(200)

        # Column header tooltips

        _stack_col_tips = {
            0: "Layer index (1 = topmost). Read-only.",
            1: "Material type: H (high-index) or L (low-index).",
            2: "Thickness multiplier relative to QWOT (lambda₀/4n). E.g. 1.0 = 1 QWOT, 0.5 = half-wave.",
        }



        for _col, _tip in _stack_col_tips.items():
            _item = self.widgets["stack_table"].horizontalHeaderItem(_col)

            if _item:
                _item.setToolTip(_tip)

        self.widgets["stack_table"].verticalHeader().setDefaultSectionSize(22)

        h_header = self.widgets["stack_table"].horizontalHeader()

        h_header.resizeSection(0, 25)

        h_header.resizeSection(1, 35)

        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.widgets["stack_table"].setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.widgets["stack_table"].setMinimumHeight(200)

        # Connect cellChanged to save state before modification

        self.widgets["stack_table"].cellChanged.connect(self._on_stack_table_changed)

        cockpit_layout.addWidget(self.widgets["stack_table"])

        self.design_layout.addWidget(self.stack_group)

    def _create_optimization_tab(self) -> None:

        opt_tab = QWidget()

        self.tabs.addTab(opt_tab, "Strategy Loop")

        opt_layout = QVBoxLayout(opt_tab)

        opt_layout.setSpacing(10)

        opt_layout.setContentsMargins(5, 5, 5, 5)

        scan_group = CertusCard("Spectral Scanning Range")

        scan_layout = scan_group.body

        self._create_line_edits(
            scan_layout,
            [
                ("wl_range_start", "Spectral Range Start (nm):"),
                ("wl_range_end", "Spectral Range End (nm):"),
                (
                    "wl_step",
                    "Spectral Step (nm):",
                ),
                ("extrema_exclusion_ratio", "Extrema Exclusion Ratio (1:X):"),
            ],
        )

        opt_layout.addWidget(scan_group)

        # Spectral Scanning tooltips

        _tips_scan = {
            "wl_range_start": "Start of the optical simulation wavelength range (nm). Must be within the available dispersive data range for H and L materials.",
            "wl_range_end": "End of the optical simulation wavelength range (nm).",
            "wl_step": "Spectral step (nm) used to build the simulation grid. Smaller = more precise but slower.",
            "extrema_exclusion_ratio": "Ratio 1:X - exclude 1 in X extremum from monitoring candidates to avoid crowded regions near turning points.",
        }

        for _k, _tip in _tips_scan.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        filter_group = CertusCard("Candidate Filtering")

        filter_layout = filter_group.body

        self._create_line_edits(
            filter_layout,
            [
                ("scan_wl_min", "Candidate lambda Min (nm):"),
                ("scan_wl_max", "Candidate lambda Max (nm):"),
                ("scan_wl_step", "Candidate lambda Step (nm):"),
                ("dynamics_threshold", "Dynamics Threshold:"),
                ("min_transmission_floor", "Min Transmission Floor (0-1, e.g. 0.10):"),
                ("min_spectral_resolution", "Min Spectral Resolution (nm):"),
            ],
        )

        opt_layout.addWidget(filter_group)

        # Candidate Filtering tooltips

        _tips_filter = {
            "scan_wl_min": "Minimum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_max": "Maximum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_step": "Step (nm) between candidate monitoring wavelengths during the DP scan.",
            "dynamics_threshold": "Minimum peak-to-valley transmission dynamics required for a candidate wavelength to be retained (unitless, 0-1).",
            "min_transmission_floor": "Minimum absolute transmission T required at a candidate wavelength (0-1). Excludes opaque regions.",
            "min_spectral_resolution": "Minimum allowed spectral resolution (nm) at a candidate wavelength. Below this, the optical signal is too noisy to be usable.",
        }

        for _k, _tip in _tips_filter.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        loop_group = CertusCard("Iteration Parameters (Nb Layers / X)")

        loop_layout = loop_group.body

        self._create_line_edits(
            loop_layout,
            [
                ("iter_divider_start", "Start Divider (Low Complexity) [N / X]:"),
                ("iter_divider_end", "End Divider (High Complexity) [N / X]:"),
                ("screening_mc_runs", "Screening MC Runs (Pre-selection):"),
                ("screening_keep_top_k", "Keep Top K Strategies per Config:"),
                ("mc_runs_block", "MC Runs per layer test (Phase A):"),
                ("strategy_phase_timeout", "Max Time per Iteration (sec):"),
            ],
        )

        opt_layout.addWidget(loop_group)

        # Iteration Parameters tooltips

        _tips_loop = {
            "iter_divider_start": "Low-complexity limit: the search starts with stacks of N/X layers per block iteration (X = this value). Lower X = finer search.",
            "iter_divider_end": "High-complexity limit: as stacks grow large, divides the iteration count. Higher X = faster but coarser.",
            "screening_mc_runs": "Number of Monte Carlo runs for the pre-selection screening phase. More = better filtering but slower.",
            "screening_keep_top_k": "Number of top strategies retained per configuration after screening before deep evaluation.",
            "mc_runs_block": "Monte Carlo runs per candidate block test in Phase A. Drives early robustness estimation.",
            "strategy_phase_timeout": "Maximum wall-clock time (seconds) allowed per iteration. The engine cancels the current pass if exceeded.",
        }

        for _k, _tip in _tips_loop.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sim_group = CertusCard("Simulation Parameters")

        sim_layout = sim_group.body

        self._create_line_edits(
            sim_layout,
            [
                ("thickness_tolerance_nm", "Thickness Tolerance (+/- nm):"),
                (
                    "trigger_tolerance",
                    "Trigger Tolerance (noise) %:",
                ),  # Kept for backward compat / relative
                ("mse_tolerance_limit_pct", "MSE Filtering Tolerance (Best +/- %):"),
                ("non_monotonic_error_factor", "Non-Monotonic Error Gain Factor:"),
                (
                    "wavelength_change_penalty",
                    "Penalty on Wavelength Change (x factor):",
                ),
            ],
        )

        # Noise distribution selector

        noise_dist_layout = QHBoxLayout()

        noise_dist_layout.addWidget(QLabel("Noise Distribution:"))

        self.widgets["noise_distribution"] = QComboBox()

        self.widgets["noise_distribution"].addItems(["gaussian"])

        self.widgets["noise_distribution"].setCurrentText("gaussian")

        self.widgets["noise_distribution"].setEnabled(False)

        self.widgets["noise_distribution"].setToolTip("Gaussian-only policy enabled for STRAT.")

        noise_dist_layout.addWidget(self.widgets["noise_distribution"])

        noise_dist_layout.addStretch()

        sim_layout.addLayout(noise_dist_layout)

        # Non-monotonic mode selector

        nm_mode_layout = QHBoxLayout()

        nm_mode_layout.addWidget(QLabel("Non-Monotonic Mode:"))

        self.widgets["non_monotonic_mode"] = QComboBox()

        self.widgets["non_monotonic_mode"].addItems(["attenuate", "reject"])

        self.widgets["non_monotonic_mode"].setToolTip(
            "attenuate: Divide error by factor (legacy)\nreject: Penalize non-monotonic zones (stricter)"
        )

        nm_mode_layout.addWidget(self.widgets["non_monotonic_mode"])

        nm_mode_layout.addStretch()

        sim_layout.addLayout(nm_mode_layout)

        opt_layout.addWidget(sim_group)

        # Simulation Parameters tooltips

        _tips_sim = {
            "thickness_tolerance_nm": "Gaussian noise standard deviation (+/- nm) applied to each layer thickness during Monte Carlo simulations.",
            "trigger_tolerance": "Relative trigger tolerance (% of thickness) used to define the optical trigger acceptance window.",
            "mse_tolerance_limit_pct": "MSE filtering tolerance: retain candidates within Best MSE × (1 + this %). Filters out poor strategies early.",
            "non_monotonic_error_factor": "Penalty multiplier applied to the RMSE when the growth curve is non-monotonic in the monitoring window.",
            "wavelength_change_penalty": "Cost multiplier applied each time the monitoring wavelength changes between consecutive blocks. Rewards single-wavelength strategies.",
        }

        for _k, _tip in _tips_sim.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # Reports Group

        report_group = CertusCard("Reports & Data")

        report_layout = QHBoxLayout()

        report_group.body.addLayout(report_layout)

        self.btn_open_reports = QPushButton("📂 Open Reports Folder")

        self.btn_open_reports.setToolTip("Open the folder containing HTML/Excel reports")

        self.btn_open_reports.clicked.connect(lambda: open_file_explorer(get_resource_path("reports")))

        report_layout.addWidget(self.btn_open_reports)

        opt_layout.addWidget(report_group)

        opt_layout.addStretch()

    def _create_advanced_tab(self) -> None:

        adv_tab = QWidget()

        self.tabs.addTab(adv_tab, "Advanced")

        adv_layout = QVBoxLayout(adv_tab)

        adv_layout.setSpacing(10)

        adv_layout.setContentsMargins(5, 5, 5, 5)

        robust_group = CertusCard("Robustness Test (Step 3)")

        robust_layout = robust_group.body

        self._create_line_edits(
            robust_layout,
            [
                ("robustness_noise_factors", "Noise Factors (e.g., 0.5,1,2):"),
                ("robustness_num_runs", "Number of Runs (Validation):"),
            ],
        )

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("Execution Mode:"))

        self.widgets["execution_mode"] = QComboBox()

        # The `fast` mode was REMOVED (2026-08-05). It divided the Monte-Carlo budgets
        # by 4: at 6 screening draws, a P95 is the maximum of six and the crash rate
        # has a resolution of 17% for a threshold of 5%. See the full justification
        # in collect_params (certus_strat_ui_state.py).
        self.widgets["execution_mode"].addItems(["premium"])

        self.widgets["execution_mode"].setCurrentText("premium")

        self.widgets["execution_mode"].setToolTip(
            "premium : budget Monte-Carlo complet — le seul mode disponible.\n"
            "Le mode 'fast' a ete retire : il divisait les budgets par 4 et rendait "
            "l'elimination sur taux de plantage non significative."
        )

        mode_layout.addWidget(self.widgets["execution_mode"])

        mode_layout.addStretch()

        robust_layout.addLayout(mode_layout)

        adv_layout.addWidget(robust_group)

        # Robustness tooltips

        _tips_robust = {
            "robustness_noise_factors": "Comma-separated noise factor values (e.g. 0.5,1,2) applied as multipliers on the base thickness noise sigma during final validation runs.",
            "robustness_num_runs": "Number of Monte Carlo simulations in the final robustness validation (Step 3). More = more reliable RMSE/P95 statistics.",
        }

        for _k, _tip in _tips_robust.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # ── MODELE MACHINE : les sources d'erreur, et leur ETAT visible ────────
        #
        # 👤 2026-08-12 : "l'utilisateur doit visualiser tres facilement ce qui est
        # actif, ce qui ne l'est pas". Avant cette carte, les huit reglages du modele
        # n'existaient QUE dans le JSON: on lancait un run sans savoir quelle machine il
        # simulait, et un fichier sans la clef prenait un defaut invisible.
        #
        # 🔴 Le bandeau d'etat est le point, pas les champs. Il se relit d'un coup d'oeil
        # et il est recalcule a chaque frappe: c'est la seule facon de garantir que ce que
        # l'ecran affiche est ce que le run va faire.
        machine_group = CertusCard("Machine model — error sources")

        machine_layout = machine_group.body

        self._create_line_edits(
            machine_layout,
            [
                ("slit_bias_enabled", "Slit bias (0/1):"),
                ("monochromator_resolution_nm", "Slit width (nm):"),
                ("search_resolution", "Search the slit (0/1):"),
                ("index_corridor", "Index corridor (+/-):"),
                ("photometric_curvature_amp", "Photometric curvature:"),
                ("allow_rate", "Allow Rate mode (0/1):"),
                ("reading_smoothing_window", "Reading smoothing (k):"),
                ("machine_sampling_dd", "Machine grid (nm, 0=off):"),
            ],
        )

        self.machine_status = QLabel("")
        self.machine_status.setWordWrap(True)
        self.machine_status.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-family: monospace; "
            f"padding: 6px; border: 1px solid {CertusTheme.TEXT_SUB}; border-radius: 4px; }}"
        )
        machine_layout.addWidget(self.machine_status)

        _tips_machine = {
            "slit_bias_enabled": (
                "The machine EXPECTS T computed at perfect resolution but READS the average "
                "over the slit. The difference is a BIAS, not noise: it does not average out "
                "over draws. Leave on to be realistic."
            ),
            "monochromator_resolution_nm": (
                "2 nm is nominal, and the reading noise was measured there. 5 nm divides the "
                "noise by 1.5 but multiplies the bias by 6.25; 0.5 nm multiplies the noise by 5. "
                "Only 5 / 2 / 1 / 0.5 exist on the machine -- another value raises."
            ),
            "search_resolution": (
                "Put the four slit widths in competition instead of imposing one. A strategy "
                "then carries its own slit, which is what makes it executable in the chamber."
            ),
            "index_corridor": (
                "Half-width of the index uncertainty, in ABSOLUTE index units, drawn once per "
                "run and per material. 0.005 is the specified value; 0 means the materials are "
                "known exactly, which no chamber is."
            ),
            "photometric_curvature_amp": (
                "Detector non-linearity, maximal at T = 0.5 and ZERO at T = 0 and T = 1 -- those "
                "two are the anchors of the dark/void referencing. 0.00375 puts the true value "
                "within [0.4975, 0.5025] at 2 sigma."
            ),
            "allow_rate": (
                "Generate variants depositing one layer by turn counting instead of photometry. "
                "The general case on the machine, so on by default."
            ),
            "reading_smoothing_window": (
                "Running mean over k readings before detection. OFF (k=1) on purpose: the OMS "
                "filter chain is not known, and an unmeasured hypothesis is worse than none."
            ),
            "machine_sampling_dd": (
                "Sampling step of the deposition sweep, in nm. 0 keeps the fast grid. The real "
                "machine reads every 0.125 nm, which is 38x finer and far slower -- the model is "
                "therefore OPTIMISTIC on turning points fabricated by noise."
            ),
        }
        for _k, _tip in _tips_machine.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)
                self.widgets[_k].textChanged.connect(self._refresh_machine_status)

        adv_layout.addWidget(machine_group)

        engine_group = CertusCard("Deep Search Engine & Hybridization")

        engine_layout = engine_group.body

        self._create_line_edits(
            engine_layout,
            [
                ("nucleation_mc_runs", "Smart Nucleation MC Runs:"),
                ("mining_candidates_limit", "Mining DP Candidates Limit:"),
                ("n_screen_runs", "Screening Runs (Phase B):"),
                ("k_keep_survivors", "Keep K Survivors per Block:"),
                ("top_k_parents", "Hybridization: Top K Parents:"),
                ("max_fusions_per_parent", "Hybridization: Max Fusions/Parent:"),
            ],
        )

        adv_layout.addWidget(engine_group)

        # Deep Search Engine tooltips

        _tips_engine = {
            "nucleation_mc_runs": "MC runs used by the Smart Nucleation phase to evaluate the first-block quality before committing to a wavelength.",
            "mining_candidates_limit": "Maximum number of DP candidate strategies extracted from the cost map during Phase A mining.",
            "n_screen_runs": "MC runs per candidate in Phase B (screening). More = better pre-ranking but slower.",
            "k_keep_survivors": "Number of top-K candidates kept after each Phase B screening pass before deep evaluation.",
            "top_k_parents": "Hybridization: number of parent strategies combined to generate hybrid offspring.",
            "max_fusions_per_parent": "Hybridization: maximum number of hybrid offspring generated per parent pair.",
        }

        for _k, _tip in _tips_engine.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        limits_group = CertusCard("Physical Limits & Search Depth")

        limits_layout = limits_group.body

        self._create_line_edits(
            limits_layout,
            [
                ("phase_a_scan_limit", "Phase A: Scan Depth (Candidates):"),
                ("phase_a_keep_limit", "Phase A: Max Retained Candidates:"),
                ("nucleation_max_rmse", "Nucleation: Max RMSE (nm):"),
                ("nucleation_degradation", "Nucleation: Degradation Thresh. (Ratio):"),
                ("step0_sigma", "Step 1: Preview Noise Sigma (nm):"),
            ],
        )

        adv_layout.addWidget(limits_group)

        # Physical Limits tooltips

        _tips_limits = {
            "phase_a_scan_limit": "Phase A: maximum number of candidate wavelengths evaluated per block iteration.",
            "phase_a_keep_limit": "Phase A: maximum number of candidates retained after scanning before Phase B screening.",
            "nucleation_max_rmse": "Nucleation: maximum acceptable RMSE (nm) for a nucleation wavelength to be accepted.",
            "nucleation_degradation": "Nucleation: if the RMSE degrades by more than this ratio vs. the reference, the nucleation attempt is rejected.",
            "step0_sigma": "Step 1 (Nominal preview): Gaussian sigma (nm) applied to simulate a quick noise preview without full Monte Carlo.",
        }

        for _k, _tip in _tips_limits.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sym_group = CertusCard("SYM Strategy Controls")

        sym_layout = sym_group.body

        self._create_line_edits(
            sym_layout,
            [
                ("sym_enable", "Enable SYM (0/1):"),
                ("sym_weight", "SYM Weight:"),
                ("sym_same_wl_bonus", "SYM Same-WL Bonus:"),
                ("sym_extrema_window", "SYM Extrema Window (OT nm):"),
                ("sym_continuity_weight", "SYM Continuity Weight:"),
                ("sym_adaptive_same_wl", "SYM Adaptive Same-WL (0/1):"),
                ("sym_allow_hybrid", "SYM Allow Hybrid Double-Score (0/1):"),
                ("sym_prefer_on_tie", "SYM Prefer on Tie (0/1):"),
                ("sym_tie_epsilon", "SYM Tie Epsilon Abs:"),
                ("sym_tie_epsilon_rel", "SYM Tie Epsilon Rel:"),
            ],
        )

        # SYM advanced field tooltips

        _tips_sym = {
            "sym_weight": "Global weight applied to the SYM score when combining it with the RMSE score. Higher = more symmetric strategies favored.",
            "sym_same_wl_bonus": "Bonus awarded when two consecutive blocks use the same monitoring wavelength.",
            "sym_extrema_window": "Optical thickness window (nm) around extrema within which candidate points qualify for SYM scoring.",
            "sym_continuity_weight": "Weight applied to reward monotonically continuous growth curves in the SYM metric.",
            "sym_adaptive_same_wl": "Enable (1) adaptive same-wavelength bonus that scales with observability quality.",
            "sym_allow_hybrid": "Allow (1) the same strategy to accumulate both a SYM score and an RMSE score simultaneously (double-score mode).",
            "sym_prefer_on_tie": "On tied RMSE score (within epsilon), prefer (1) the strategy with the better SYM score.",
            "sym_tie_epsilon": "Absolute RMSE tolerance below which two strategies are considered tied (to trigger SYM tie-break).",
            "sym_tie_epsilon_rel": "Relative RMSE tolerance (fraction of the best RMSE) for tie-breaking.",
        }

        for _k, _tip in _tips_sym.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # SYM is a mandatory supplementary strategy: always active.

        if "sym_enable" in self.widgets:
            self.widgets["sym_enable"].setText("1")

            self.widgets["sym_enable"].setReadOnly(True)

            self.widgets["sym_enable"].setToolTip("Always active (supplementary strategy)")

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("SYM Scoring Mode:"))

        self.widgets["sym_scoring_mode"] = QComboBox()

        self.widgets["sym_scoring_mode"].addItems(["post", "pre", "hybrid"])

        self.widgets["sym_scoring_mode"].setCurrentText(SYM_DEFAULT_SCORING_MODE)

        self.widgets["sym_scoring_mode"].setToolTip(
            "post: SYM score is applied after ranking by RMSE (default).\n"
            "pre: SYM score influences block selection during DP search.\n"
            "hybrid: SYM score applied both during and after search."
        )

        mode_layout.addWidget(self.widgets["sym_scoring_mode"])

        mode_layout.addStretch()

        sym_layout.addLayout(mode_layout)

        adv_layout.addWidget(sym_group)

        adv_layout.addStretch()

    def _create_why_certus_tab(self) -> None:
        """Creates Why CERTUS? tab with FlashyCards matching INDEX/METAL/DESIGN style"""

        perf_tab = QWidget()

        self.tabs.addTab(perf_tab, "Why CERTUS?")

        perf_layout = QGridLayout(perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "High-Rate Monte Carlo",
            "Simulation of deposition dispersions\nRapid evaluation of real-world robustness",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Error Compensation",
            "Auto-compensated wavelengths\nMaintains performance under perturbations",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Dynamic Programming",
            "Block selection by global cost\nStructured, scalable, and traceable search",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Robust Statistical Validation",
            "Multi-noise stress tests + RMSE scoring\nReliable ranking of manufacturable strategies",
            icon="🔮",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

    def _create_material_group(self, parent_layout, title, prefix, label, _is_compact=False) -> None:

        group = CertusCard(title)

        layout = group.body

        layout.setSpacing(8)

        layout.setContentsMargins(4, 12, 4, 4)

        radio_layout = QHBoxLayout()

        self.widgets[f"{prefix}_type_custom"] = QRadioButton("Custom (Constant)")

        self.widgets[f"{prefix}_type_custom"].setChecked(True)  # Default to Custom mode

        self.widgets[f"{prefix}_type_file"] = QRadioButton("Dispersive (File)")

        grp = QButtonGroup(self)

        grp.addButton(self.widgets[f"{prefix}_type_custom"])

        grp.addButton(self.widgets[f"{prefix}_type_file"])

        grp.setExclusive(True)

        radio_layout.addWidget(self.widgets[f"{prefix}_type_custom"])

        radio_layout.addWidget(self.widgets[f"{prefix}_type_file"])

        radio_layout.addStretch()

        layout.addLayout(radio_layout)

        combined_layout = QHBoxLayout()

        self.widgets[f"n{label}_r"] = QLineEdit()

        self.widgets[f"n{label}_r"].setPlaceholderText("e.g. 2.3")

        self.widgets[f"n{label}_r"].setFixedWidth(50)

        self.widgets[f"n{label}_r"].setToolTip(
            "Fixed real part of the refractive index n (constant, wavelength-independent).\n"
            "Active only in 'Custom' mode."
        )

        combined_layout.addWidget(QLabel("n (real):"))

        combined_layout.addWidget(self.widgets[f"n{label}_r"])

        combined_layout.addSpacing(10)

        self.widgets[f"{prefix}_material_file"] = QComboBox()

        self.widgets[f"{prefix}_material_file"].addItems(self.material_list)

        self.widgets[f"{prefix}_material_file"].setToolTip(
            "Dispersive material file from the clues database (wavelength-dependent n & k).\n"
            "Active only in 'Dispersive (File)' mode."
        )

        combined_layout.addWidget(QLabel("Material File:"))

        combined_layout.addWidget(self.widgets[f"{prefix}_material_file"], 1)

        layout.addLayout(combined_layout)

        # Connect toggle signals to enable/disable widgets

        self.widgets[f"{prefix}_type_custom"].toggled.connect(
            lambda checked, p=prefix, l=label: self._on_material_mode_changed(p, l)
        )

        parent_layout.addWidget(group)

    #: Les huit sources d'erreur, dans l'ordre ou elles se lisent: clef, libelle court,
    #: et la valeur qui signifie INACTIF. `None` = c'est un reglage, pas un interrupteur.
    _MACHINE_SOURCES = (
        ("slit_bias_enabled", "biais de fente", 0.0),
        ("search_resolution", "recherche de fente", 0.0),
        ("index_corridor", "corridor d'indice", 0.0),
        ("photometric_curvature_amp", "courbure photometrique", 0.0),
        ("allow_rate", "mode Rate", 0.0),
        ("reading_smoothing_window", "lissage de lecture", 1.0),
        ("machine_sampling_dd", "grille machine", 0.0),
    )

    def _refresh_machine_status(self, *_a) -> None:
        """Bandeau d'etat : ce qui est ACTIF, ce qui ne l'est pas, d'un coup d'oeil.

        👤 2026-08-12 : *"l'utilisateur doit visualiser tres facilement ce qui est actif,
        ce qui ne l'est pas"*. Recalcule a chaque frappe, donc il ne peut pas mentir --
        un bandeau rafraichi seulement au chargement afficherait la configuration
        precedente pendant qu'on en edite une autre.

        ⚠️ Un champ illisible s'affiche `?` et JAMAIS "inactif". Les deux ne veulent pas
        dire la meme chose, et confondre "je ne sais pas" avec "c'est eteint" est
        exactement ce que ce projet paie depuis le debut.
        """
        if not hasattr(self, "machine_status"):
            return
        on, off, bad = [], [], []
        for key, label, neutral in self._MACHINE_SOURCES:
            w = self.widgets.get(key)
            raw = (w.text() if w is not None else "").strip()
            if not raw:
                bad.append(label); continue
            try:
                val = float(raw)
            except ValueError:
                bad.append(label); continue
            (off if val == neutral else on).append(label)
        slit = self.widgets.get("monochromator_resolution_nm")
        slit_txt = (slit.text().strip() if slit is not None else "") or "?"
        parts = [f"FENTE {slit_txt} nm"]
        if on:
            parts.append("ACTIF : " + ", ".join(on))
        if off:
            parts.append("inactif : " + ", ".join(off))
        if bad:
            parts.append("ILLISIBLE : " + ", ".join(bad))
        self.machine_status.setText("   |   ".join(parts))
        colour = CertusTheme.DANGER if bad else (
            CertusTheme.SUCCESS if len(on) >= 5 else CertusTheme.WARNING)
        self.machine_status.setStyleSheet(
            f"QLabel {{ color: {colour}; font-family: monospace; padding: 6px; "
            f"border: 1px solid {colour}; border-radius: 4px; }}"
        )

    def _create_line_edits(self, layout, items, columns=2) -> None:

        grid = QGridLayout()

        grid.setHorizontalSpacing(5)

        grid.setVerticalSpacing(2)

        rows = (len(items) + columns - 1) // columns

        for idx, (key, label_text) in enumerate(items):
            col_block = idx // rows

            row = idx % rows

            lbl = QLabel(label_text)

            edit = QLineEdit()

            self.widgets[key] = edit

            grid.addWidget(lbl, row, col_block * 2)

            grid.addWidget(edit, row, col_block * 2 + 1)

        for c in range(columns):
            grid.setColumnStretch(c * 2 + 1, 1)

        layout.addLayout(grid)

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

