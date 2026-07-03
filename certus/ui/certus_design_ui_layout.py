from __future__ import annotations
from certus.ui.certus_design_common import *
from certus.utils.certus_ux import OBJ

class LayoutManager:
    def __init__(self, ui):
        self.ui = ui
    def _build_left_panel(self) -> QWidget:
        """Constructs left control panel"""

        left_panel = QWidget()

        left_panel.setMinimumWidth(280)

        # Removed setFixedWidth to allow resizing via splitter

        left_panel.setObjectName("LeftPanel")

        left_layout = QVBoxLayout(left_panel)

        left_layout.setSpacing(0)

        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Standard Header

        header_widget = create_header_logo_widget(
            "DESIGN",
            self.ui.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_DESIGN",
        )

        self.ui.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.ui.btn_theme)

        left_layout.addWidget(header_widget)

        # 2. Action Bar (Shared)

        action_bar = create_top_actions_bar(self.ui, self.ui.save_config, self.ui.load_config, self.ui.export_excel, self.ui.open_help)

        left_layout.addWidget(action_bar)

        # Scrollable area

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()

        scroll_layout = QVBoxLayout(scroll_content)

        scroll_layout.setContentsMargins(0, 0, 4, 0)

        scroll_layout.setSpacing(12)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Configure materials  2 Define stack  3 Set optimizer  4 Evaluate / Run")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(CertusTheme.get_hint_text_style())

        workflow_card.body.addWidget(workflow_hint)

        scroll_layout.addWidget(workflow_card)

        self.ui.back_group = self._build_back_group()

        materials_widget = self._build_materials_group()

        params_widget = self._build_params_group()

        optim_widget = self._build_optim_group()

        scroll_layout.addWidget(CertusCollapsible("1  Materials", materials_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("2  Back-side structure", self.ui.back_group, expanded=False))

        scroll_layout.addWidget(CertusCollapsible("3  Parameters", params_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("4  Optimization", optim_widget, expanded=True))

        # Action buttons (inside scroll to prevent vertical squeezing on small heights)
        action_layout = self._build_action_buttons()

        bottom_actions_widget = CertusCard("Actions")
        bottom_actions_widget.body.setContentsMargins(10, 8, 10, 10)
        bottom_actions_widget.body.addLayout(action_layout)

        scroll_layout.addWidget(bottom_actions_widget)

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        left_layout.addWidget(scroll)

        self.ui.back_group.setVisible(self.ui.back_coat_check.isChecked())

        return left_panel

    def _apply_theme(self) -> None:
        """Apply Certus theme dynamically"""

        self.ui._apply_certus_compact_theme(
            plots=[
                getattr(self, "spectrum_plot", None),
                getattr(self, "profile_plot", None),
                getattr(self, "nk_plot", None),
                getattr(self, "color_plot", None),
                getattr(self, "plot_convergence", None),
            ]
        )

    def _build_materials_group(self) -> CertusCard:
        """Constructs materials group"""

        mat_group = CertusCard("Materials")

        mat_grid = QGridLayout()

        mat_group.body.addLayout(mat_grid)

        headers = ["Material", "Preset", "n@400", "n@700"]

        for col, header in enumerate(headers):
            mat_grid.addWidget(QLabel(f"<b>{header}</b>"), 0, col)

        materials = list(CFG.MATERIALS)

        for i, mat_name in enumerate(materials):
            row = i + 1

            mat_grid.addWidget(QLabel(f"<b>{mat_name}</b>"), row, 0)

            combo = QComboBox()

            combo.setToolTip("Select the material preset or 'Custom'.")

            combo.addItems(["Custom"])

            combo.setCurrentText("Custom")

            n4_spin = self.ui._create_spin(1.5, dec=3)

            n7_spin = self.ui._create_spin(1.5, dec=3)

            for spin in [n4_spin, n7_spin]:
                spin.setRange(1.0, 4.0)

                spin.valueChanged.connect(self.ui._on_schedule_eval_signal)

                spin.valueChanged.connect(self.ui._on_tikhonravov_points_changed)

            combo.currentTextChanged.connect(lambda t, s4=n4_spin, s7=n7_spin: self.ui._apply_preset(t, s4, s7))

            mat_grid.addWidget(combo, row, 1)

            mat_grid.addWidget(n4_spin, row, 2)

            mat_grid.addWidget(n7_spin, row, 3)

            self.ui.mat_widgets[mat_name] = {"preset": combo, "n4": n4_spin, "n7": n7_spin}

            # Initialize spinbox states based on default preset

            self.ui._apply_preset(combo.currentText(), n4_spin, n7_spin)

        return mat_group

    def _build_params_group(self) -> CertusCard:
        """Constructs parameters group"""

        param_group = CertusCard("Parameters")

        param_layout = param_group.body

        # Reference Lambda

        l0_lay = QHBoxLayout()

        self.ui.l0_spin = QDoubleSpinBox()

        self.ui.l0_spin.setRange(200, 20000)

        self.ui.l0_spin.setValue(CFG.DEFAULT_L0)

        self.ui.l0_spin.setDecimals(1)

        self.ui.l0_spin.setSuffix(" nm")

        self.ui.l0_spin.valueChanged.connect(self.ui._on_schedule_eval_signal)

        self.ui.l0_spin.valueChanged.connect(self.ui._on_tikhonravov_points_changed)

        self.ui.l0_spin.setToolTip("Reference wavelength lambda₀ (nm) for converting QWOT to physical thickness.")

        l0_lay.addWidget(QLabel("lambda₀ ref.:"))

        l0_lay.addWidget(self.ui.l0_spin)

        param_layout.addLayout(l0_lay)

        # Backside options

        self.ui.back_check = QCheckBox("substrate back face (Fresnel)")

        self.ui.back_check.setToolTip("Include reflection from the untreated back face of the substrate.")

        self.ui.back_check.stateChanged.connect(self.ui._on_schedule_eval_instant_signal)

        param_layout.addWidget(self.ui.back_check)

        self.ui.back_coat_check = QCheckBox("Back-side stack")

        self.ui.back_coat_check.setToolTip(
            "Show the back-side layer editor and include those layers in the calculation when checked."
        )

        self.ui.back_coat_check.stateChanged.connect(self.ui._toggle_back_stack)

        param_layout.addWidget(self.ui.back_coat_check)

        # Oblique Mode

        self.ui.oblique_check = QCheckBox("Oblique incidence mode")

        self.ui.oblique_check.setToolTip("R/T targets with angle and s / p / average polarization per row.")

        self.ui.oblique_check.stateChanged.connect(self.ui._toggle_oblique_mode)

        param_layout.addWidget(self.ui.oblique_check)

        # Auto Y Scale or Fixed (0-1)

        self.ui.auto_scale_y_check = QCheckBox("Auto Y scale")

        self.ui.auto_scale_y_check.setChecked(True)

        self.ui.auto_scale_y_check.setToolTip("Fit the Y axis to the spectrum data on display.")

        self.ui.auto_scale_y_check.stateChanged.connect(self.ui._on_update_spectrum_y_scale_signal)

        param_layout.addWidget(self.ui.auto_scale_y_check)

        # Deep Needle / Layer Growth

        self.ui.allow_growth_check = QCheckBox("Topology growth (deep Needle)")

        self.ui.allow_growth_check.setChecked(True)

        self.ui.allow_growth_check.setToolTip("Allow thin-layer insertion during optimization (Needle mode).")

        param_layout.addWidget(self.ui.allow_growth_check)

        # Pre-Polish

        self.ui.pre_polish_check = QCheckBox("Local polish before PGLOBAL")

        self.ui.pre_polish_check.setChecked(False)

        self.ui.pre_polish_check.setToolTip("Run a local gradient polish before the multi-minima global phase.")

        param_layout.addWidget(self.ui.pre_polish_check)

        return param_group

    def _build_back_group(self) -> CertusCard:
        """Constructs backside group"""

        back_group = CertusCard("Back-side structure")

        back_layout = back_group.body

        self.ui.back_table = QTableWidget(0, 3)

        self.ui.back_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)"])

        self.ui.back_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.ui.back_table.setAlternatingRowColors(True)

        self.ui.back_table.setMaximumHeight(150)

        back_layout.addWidget(self.ui.back_table)

        back_btns = QHBoxLayout()
        back_btns.setSpacing(12)

        b_add = QPushButton("Add")

        b_add.setToolTip("Add a layer to the back-side stack.")

        b_add.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        b_add.clicked.connect(self.ui.add_back_layer)

        b_del = QPushButton("Remove")

        b_del.setToolTip("Remove a layer from the back-side stack.")

        b_del.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        b_del.clicked.connect(self.ui.del_back_layer)

        back_btns.addWidget(b_add)

        back_btns.addWidget(b_del)

        back_btns.addStretch()

        back_layout.addLayout(back_btns)

        return back_group

    def _build_optim_group(self) -> CertusCard:
        """Constructs optimization group"""

        opt_group = CertusCard("Optimization (PGLOBAL)")

        opt_grid = QGridLayout()

        opt_group.body.addLayout(opt_grid)

        opt_grid.setSpacing(12)

        row = 0

        # Samples per iteration

        self.ui.n100_spin = QSpinBox()

        self.ui.n100_spin.setRange(50, 500000)

        self.ui.n100_spin.setValue(6000)

        self.ui.n100_spin.setSingleStep(50)

        self.ui.n100_spin.setToolTip(
            "Number of random starting points evaluated per global iteration.\n"
            "Higher values improve exploration but increase computation time."
        )

        opt_grid.addWidget(QLabel("Samples / Iter:"), row, 0)

        opt_grid.addWidget(self.ui.n100_spin, row, 1)

        row += 1

        # Max clusters

        self.ui.max_clusters_spin = QSpinBox()

        self.ui.max_clusters_spin.setRange(5, 2500)

        self.ui.max_clusters_spin.setValue(40)

        self.ui.max_clusters_spin.setToolTip(
            "Maximum number of local minima (clusters) tracked simultaneously.\n"
            "Limits memory usage and ensures the best basins are retained."
        )

        opt_grid.addWidget(QLabel("Max Clusters:"), row, 0)

        opt_grid.addWidget(self.ui.max_clusters_spin, row, 1)

        row += 1

        # Max iterations

        self.ui.global_cycles_spin = QSpinBox()

        self.ui.global_cycles_spin.setRange(1, 2500)

        self.ui.global_cycles_spin.setValue(50)

        self.ui.global_cycles_spin.setToolTip("Maximum number of global optimization cycles before auto-stopping.")

        opt_grid.addWidget(QLabel("Max Iterations:"), row, 0)

        opt_grid.addWidget(self.ui.global_cycles_spin, row, 1)

        row += 1

        # Points per target

        self.ui.points_per_target_spin = QSpinBox()

        self.ui.points_per_target_spin.setRange(1, 5000)

        self.ui.points_per_target_spin.setValue(50)

        self.ui.points_per_target_spin.setToolTip(
            "Number of spectral evaluation points per target region.\n"
            "Higher values increase spectral accuracy but slow down evaluation."
        )

        self.ui.points_per_target_spin.valueChanged.connect(self.ui._update_optim_point_count)

        opt_grid.addWidget(QLabel("Points / Target:"), row, 0)

        opt_grid.addWidget(self.ui.points_per_target_spin, row, 1)

        row += 1

        # Spectrum points (readonly)

        self.ui.npts_spin = QSpinBox()

        self.ui.npts_spin.setToolTip("Total number of spectrum points evaluated (read-only).")

        self.ui.npts_spin.setRange(0, 50000)

        self.ui.npts_spin.setReadOnly(True)

        self.ui.npts_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        opt_grid.addWidget(QLabel("Spectrum Points:"), row, 0)

        opt_grid.addWidget(self.ui.npts_spin, row, 1)

        row += 1

        # Monte Carlo section

        opt_grid.addWidget(QLabel("<b>MC ANALYSIS: </b>"), row, 0, 1, 2)

        row += 1

        self.ui.mc_n_spin = QSpinBox()

        self.ui.mc_n_spin.setToolTip("Number of Monte Carlo samples.")

        self.ui.mc_n_spin.setRange(10, 5000)

        self.ui.mc_n_spin.setValue(200)

        opt_grid.addWidget(QLabel("Samples:"), row, 0)

        opt_grid.addWidget(self.ui.mc_n_spin, row, 1)

        row += 1

        self.ui.mc_sigma_spin = QDoubleSpinBox()

        self.ui.mc_sigma_spin.setRange(0.1, 20)

        self.ui.mc_sigma_spin.setValue(2.0)

        self.ui.mc_sigma_spin.setToolTip(
            "Standard deviation of the Gaussian thickness perturbation for Monte Carlo\n"
            "sensitivity analysis (nm). Simulates manufacturing thickness errors."
        )

        opt_grid.addWidget(QLabel("Sigma (nm):"), row, 0)

        opt_grid.addWidget(self.ui.mc_sigma_spin, row, 1)

        return opt_group

    def _build_action_buttons(self) -> QVBoxLayout:
        """Constructs action buttons"""

        action_layout = QVBoxLayout()
        action_layout.setSpacing(12)

        logger = getattr(self, "logger", None)
        if logger:
            logger.info("DESIGN UI: building action buttons | has_functools=%s", bool(getattr(functools, "partial", None)))

        # Evaluate

        primary_obj = OBJ.PRIMARY_BUTTON

        self.ui.eval_btn = QPushButton("Evaluate (Ctrl+E)")

        self.ui.eval_btn.setObjectName(primary_obj)
        self.ui.eval_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.ui.eval_btn.setMinimumHeight(32)
        self.ui.eval_btn.setToolTip("Compute the spectrum for the current stack (instant).")

        self.ui.eval_btn.clicked.connect(functools.partial(self.ui._schedule_eval, True))
        if logger:
            logger.info("DESIGN UI: connected eval button -> _schedule_eval(True)")

        action_layout.addWidget(self.ui.eval_btn)

        # Local/Global optimization

        h_act = QHBoxLayout()
        h_act.setSpacing(12)

        self.ui.local_btn = QPushButton("Polish local (+/-2 nm)")

        self.ui.local_btn.setObjectName(primary_obj)
        self.ui.local_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.ui.local_btn.setMinimumHeight(32)
        self.ui.local_btn.setToolTip(
            "Run a local gradient polish (L-BFGS) on the current design.\n"
            "Perturbs each layer by +/-2 nm and refines thickness values."
        )

        self.ui.local_btn.clicked.connect(functools.partial(self.ui.run_optim, "local"))

        self.ui.global_btn = QPushButton("PGLOBAL (global)")

        self.ui.global_btn.setObjectName(primary_obj)
        self.ui.global_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))
        self.ui.global_btn.setMinimumHeight(32)
        self.ui.global_btn.setToolTip(
            "Run the full global PGLOBAL optimization:\n"
            "multi-start random sampling, single-linkage clustering, and local polish."
        )

        self.ui.global_btn.clicked.connect(functools.partial(self.ui.run_optim, "global"))

        h_act.addWidget(self.ui.local_btn)

        h_act.addWidget(self.ui.global_btn)

        action_layout.addLayout(h_act)

        # Remove thinnest layer + merge adjacents + local polish

        self.ui.drop_thin_btn = QPushButton("▼ Drop thinnest layer")

        self.ui.drop_thin_btn.setObjectName(primary_obj)
        self.ui.drop_thin_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.ui.drop_thin_btn.setMinimumHeight(32)
        self.ui.drop_thin_btn.setToolTip(
            "Removes the thinnest layer, merges adjacent layers (except 1 and N), "
            "and runs a local polish to optimize the resulting design."
        )

        self.ui.drop_thin_btn.clicked.connect(self.ui._drop_thinnest_and_polish)

        action_layout.addWidget(self.ui.drop_thin_btn)

        # Stop

        self.ui.stop_btn = QPushButton("Stop")
        self.ui.stop_btn.setObjectName(OBJ.DANGER_BUTTON)
        self.ui.stop_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.ui.stop_btn.setMinimumHeight(32)
        self.ui.stop_btn.setToolTip("Stop the running optimization and keep the best design found so far.")

        self.ui.stop_btn.clicked.connect(self.ui.stop_optim)

        self.ui.stop_btn.setEnabled(False)

        action_layout.addWidget(self.ui.stop_btn)

        # Colorimetry

        self.ui.color_btn = QPushButton("Colorimetric analysis")
        self.ui.color_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.ui.color_btn.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_CommandLink))
        self.ui.color_btn.setMinimumHeight(32)
        self.ui.color_btn.setToolTip(
            "Run a Monte Carlo colorimetric analysis on the current design.\n"
            "Shows CIE Lab a*b* distribution and DeltaE stability."
        )

        self.ui.color_btn.clicked.connect(self.ui.run_colorimetry)

        action_layout.addWidget(self.ui.color_btn)

        # Stack Info Button

        self.ui.substrate_info_btn = QPushButton("🔬 Stack info")
        self.ui.substrate_info_btn.setObjectName(OBJ.PRIMARY_BUTTON)

        self.ui.substrate_info_btn.setToolTip(
            "substrate summary and stack structure in QWOT (best design if optimization is running)."
        )

        self.ui.substrate_info_btn.clicked.connect(self.ui._show_substrate_info_window)

        action_layout.addWidget(self.ui.substrate_info_btn)

        # Update stack info when optimization completes

        self.ui.optimization_finished_signal.connect(self.ui._update_substrate_info)

        # Clear / Reset (use app's full reset: tables, state, plots, then _load_defaults)

        from certus.utils.certus_reset_framework import create_reset_button

        self.ui.clear_btn = create_reset_button(self, use_app_reset=True)

        action_layout.addWidget(self.ui.clear_btn)

        return action_layout

    def _build_right_panel(self) -> Any:
        """Constructs right panel with visualization and tables"""

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)

        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Visualization Area

        self.ui.viz_stack = QStackedWidget()

        self.ui.viz_stack.addWidget(WelcomeGuideWidget("CERTUS-DESIGN"))

        viz_container = QWidget()

        v_lay = QVBoxLayout(viz_container)

        self.ui.plot_tabs = QTabWidget()

        # Y Label dynamically updated

        self.ui.spectrum_plot = CertusScientificPlot(self.ui, "Spectrum", "Transmission", "lambda (nm)")

        # Init X scale (def: 380-780nm)

        self.ui.spectrum_plot.setXRange(200, 3000, 0)

        self.ui.spectrum_plot.plotItem.enableAutoRange(y=True)

        self.ui.profile_plot = CertusScientificPlot(self.ui, "Refractive Index Profile", "n", "z (nm)")

        self.ui.nk_plot = CertusScientificPlot(self.ui, "Dispersion n(lambda)", "n", "lambda (nm)")

        self.ui.color_plot = CertusScientificPlot(self.ui, "CIE a*b* Diagram", "b*", "a*")

        # Buttons to detach plots

        plot_header = QWidget()

        plot_header.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(6, 2, 6, 2)

        detach_btn = QPushButton("🔗 Detach plot")

        detach_btn.setToolTip("Open the current plot tab in a separate window.")

        detach_btn.clicked.connect(self.ui.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_header_layout.addStretch()

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.ui.plot_tabs)

        self.ui.plot_tabs.addTab(self.ui.spectrum_plot, "Spectrum (T)")

        self.ui.plot_tabs.addTab(self.ui.profile_plot, "Profile")

        self.ui.plot_tabs.addTab(self.ui.nk_plot, "n(lambda)")

        self.ui.plot_tabs.addTab(self.ui.color_plot, "Color")

        # Convergence plot (like INDEX/METAL)

        self.ui.plot_convergence = CertusScientificPlot(self.ui, "Optimization Convergence", "RMSE", "Iteration")

        self.ui.plot_convergence.showGrid(x=True, y=True)

        self.ui.plot_convergence.setLogMode(y=True)

        self.ui.convergence_curve = self.ui.plot_convergence.plot([], [], pen=pg.mkPen(CertusTheme.ERROR, width=2))

        self.ui.plot_tabs.addTab(self.ui.plot_convergence, "Convergence")

        # Why CERTUS? tab (matching INDEX/METAL style)

        c1 = FlashyCard(
            "Global Optimization PGLOBAL",
            "Multi-start + real-time callback\nKeeps the best RMSE over the entire workflow",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Solution Topology",
            "Single-linkage clustering of minima\nAvoids missing design valleys",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Automatic Needle + Healing",
            "Variational layer insertion\nLocal refinement to converge cleanly",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Optical Performance + Color",
            "Spectrum, n(lambda) profile, CIE Lab\nDeltaE tracking for visual stability",
            icon="🔮",
        )

        self.ui.perf_tab = create_flashy_grid([c1, c2, c3, c4])

        self.ui.plot_tabs.addTab(self.ui.perf_tab, "Why CERTUS?")

        v_lay.addWidget(plot_container)

        self.ui.viz_stack.addWidget(viz_container)

        right_splitter.addWidget(self.ui.viz_stack)

        # Table Area

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        bottom_splitter.addWidget(self._build_front_table_widget())

        bottom_splitter.addWidget(self._build_target_table_widget())

        right_splitter.addWidget(bottom_splitter)

        right_splitter.setSizes([600, 300])

        right_layout.addWidget(right_splitter)

        # Log Container

        self.ui.log_container = self.ui._build_log_container()

        self.ui.log_container.setVisible(False)  # Start hidden

        right_layout.addWidget(self.ui.log_container)

        return right_panel

    def _build_front_table_widget(self) -> QWidget:
        """Constructs front layer table widget (Now a TabWidget with Pareto History)"""

        self.ui.front_tabs = QTabWidget()

        self.ui.front_tabs.setMaximumWidth(460)

        # Tab 1: Front Structure

        self.ui.front_container = QWidget()

        f_lay = QVBoxLayout(self.ui.front_container)

        f_head = QHBoxLayout()

        f_head.addWidget(QLabel("<b>FRONT STRUCTURE</b>"))

        self.ui.layer_count_label = QLabel("0 layers")

        f_head.addStretch()

        self.ui.detach_btn = QPushButton("Detach")
        self.ui.detach_btn.setObjectName(OBJ.PRIMARY_BUTTON)

        self.ui.detach_btn.setToolTip("Open the front layer table in a separate floating window.")

        self.ui.detach_btn.clicked.connect(self.ui.detach_front_table)

        f_head.addWidget(self.ui.detach_btn)

        f_head.addWidget(self.ui.layer_count_label)

        f_lay.addLayout(f_head)

        self.ui.front_table = QTableWidget(0, 5)

        self.ui.front_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)", "Var", "Del"])

        header = self.ui.front_table.horizontalHeader()

        self.ui.front_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.ui.front_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        for idx, width in enumerate((55, 70, 80, 40, 40)):
            header.resizeSection(idx, width)

        self.ui.front_table.verticalHeader().setVisible(False)

        self.ui.front_table.setAlternatingRowColors(True)

        table_font = self.ui.front_table.font()

        if table_font.pointSize() > 0:
            table_font.setPointSize(max(8, table_font.pointSize() - 1))

            self.ui.front_table.setFont(table_font)

        f_lay.addWidget(self.ui.front_table)

        # Install event filter for Excel copy/paste

        self.ui.front_table.installEventFilter(self.ui)

        # Manipulation Buttons

        f_btns = QHBoxLayout()

        btn_defs = [
            ("Add", self.ui.add_front_layer, QStyle.StandardPixmap.SP_FileDialogNewFolder),
            ("Remove", self.ui.del_front_layer, QStyle.StandardPixmap.SP_TrashIcon),
            ("Undo", self.ui._undo, QStyle.StandardPixmap.SP_ArrowBack),
            ("Thin", self.ui.remove_thinnest, QStyle.StandardPixmap.SP_ArrowDown),
            ("Reset", self.ui.reset_qwot, QStyle.StandardPixmap.SP_BrowserReload),
        ]

        _btn_tooltips = {
            "Add": "Add a new layer below the current selection.",
            "Remove": "Remove the selected layer from the stack.",
            "Undo": "Undo the last change to the layer table.",
            "Thin": "Remove the thinnest layer (useful for topology simplification).",
            "Reset": "Reset all QWOT values to 1.0 (quarter-wave optical thickness).",
        }

        for txt, func, icon in btn_defs:
            b = QPushButton(txt)

            b.setIcon(self.ui.style().standardIcon(icon))

            b.clicked.connect(func)

            b.setToolTip(_btn_tooltips.get(txt, ""))

            f_btns.addWidget(b)

        self.ui.undo_btn = f_btns.itemAt(2).widget()

        self.ui.undo_btn.setEnabled(False)

        f_lay.addLayout(f_btns)

        self.ui.pareto_btn = QPushButton("🏆 Open Pareto Front")
        self.ui.pareto_btn.setObjectName(OBJ.PRIMARY_BUTTON)

        self.ui.pareto_btn.setToolTip(
            "Open the Pareto Front window: trade-off between RMSE and number of layers N.\n"
            "Double-click a row to load the corresponding design."
        )



        self.ui.pareto_btn.clicked.connect(self.ui._show_pareto_window)

        f_lay.addWidget(self.ui.pareto_btn)

        self.ui.front_tabs.addTab(self.ui.front_container, "Structure")

        # Pareto chart will be created in a separate window

        self.ui.pareto_table = QTableWidget(0, 8)

        self.ui.pareto_table.setHorizontalHeaderLabels(
            ["N", "Best RMSE", "dₘᵢₙ(nm)", "Best MC +/-0.3nm", "dₘᵢₙ(nm)", "Best Fab", "dₘᵢₙ Fab", "RMSE/N"]
        )

        self.ui.pareto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.ui.pareto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.ui.pareto_table.verticalHeader().setVisible(False)

        self.ui.pareto_table.setAlternatingRowColors(True)

        font = self.ui.pareto_table.font()

        font.setPointSize(max(8, font.pointSize() - 1))

        self.ui.pareto_table.setFont(font)
        self.ui.pareto_table.cellDoubleClicked.connect(self.ui._load_pareto_design)
        self.ui.pareto_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.pareto_table.customContextMenuRequested.connect(self.ui._show_pareto_context_menu)

        # Pareto window will be created on demand

        self.ui.pareto_window = None
        self.ui._pareto_initialized = False

        return self.ui.front_tabs

    def _build_target_table_widget(self) -> QWidget:
        """Constructs spectral targets table widget"""

        tgt_widget = QWidget()

        t_lay = QVBoxLayout(tgt_widget)

        t_lay.addWidget(QLabel("<b>SPECTRAL TARGETS</b>"))

        # Table with adaptive columns by mode

        self.ui.target_table = QTableWidget(0, 6)

        self.ui._update_target_table_headers()

        self.ui.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.ui.target_table.setAlternatingRowColors(True)

        t_lay.addWidget(self.ui.target_table)

        t_btns = QHBoxLayout()

        bt_add = QPushButton("Add Target")

        bt_add.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        bt_add.setToolTip(
            "Add a new spectral target row (lambdamin, lambdamax, Tmin, Tmax, Weight).\n"
            "Double-click a cell to edit values directly."
        )

        bt_add.clicked.connect(self.ui.add_target)

        bt_del = QPushButton("Remove")

        bt_del.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        bt_del.setToolTip("Remove the selected spectral target row.")

        bt_del.clicked.connect(self.ui.del_target)

        t_btns.addWidget(bt_add)

        t_btns.addWidget(bt_del)

        t_lay.addLayout(t_btns)

        return tgt_widget

    def _build_status_bar(self) -> None:
        """Constructs status bar"""

        self.ui.status_bar = QStatusBar()

        self.ui.setStatusBar(self.ui.status_bar)

        self.ui.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.ui.best_rmse_label = QLabel("Best RMSE: N/A")

        self.ui.best_rmse_label.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-weight: bold; padding-left: 15px; padding-right: 15px;"
        )

        self.ui.status_label = CertusStatusPill("Ready", "ready")

        self.ui.stats_label = QLabel("♟️ 0 minima  | 🎲 0 evals  | 🌈️ 0")

        self.ui.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.ui.zoom_label = QLabel("Zoom 100%")
        self.ui.zoom_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding: 0 8px; }}"
        )

        self.ui.progress_widget = EnhancedProgressWidget()

        self.ui.log_btn = QPushButton("Logs")
        self.ui.log_btn.setObjectName(OBJ.PRIMARY_BUTTON)

        self.ui.log_btn.setToolTip("Show or hide the log panel and optimization detail.")

        self.ui.log_btn.setCheckable(True)

        self.ui.log_btn.setChecked(False)

        self.ui.log_btn.clicked.connect(self.ui.toggle_logs)



        self.ui.status_bar.addWidget(self.ui.log_btn)

        self.ui.status_bar.addWidget(self.ui.status_label)
        self.ui.status_bar.addPermanentWidget(self.ui.zoom_label)

        self.ui.status_bar.addPermanentWidget(self.ui.stats_label)

        self.ui.status_bar.addPermanentWidget(self.ui.best_rmse_label)

        self.ui.status_bar.addPermanentWidget(self.ui.progress_widget)

