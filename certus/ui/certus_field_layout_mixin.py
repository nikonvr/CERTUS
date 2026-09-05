from __future__ import annotations
from certus.ui.certus_field_common import *


class CertusFieldLayoutMixin:
    """CertusFieldLayoutMixin."""

    def _build_left_panel(self) -> QWidget:
        left_panel = QWidget()
        left_panel.setMinimumWidth(380)
        # left_panel.setMaximumWidth(420)  # Removed to free the splitter
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. Header (Logo)
        header_widget = create_header_logo_widget("FIELD", self.APP_TITLE, logo_width=160, module_name="CERTUS_FIELD")
        self.btn_theme = CertusThemeToggle(header_widget)
        header_widget.layout().addWidget(self.btn_theme)
        left_layout.addWidget(header_widget)

        # 2. Action Bar with log toggle
        self.toggle_details_btn = QPushButton("Show Details")
        self.toggle_details_btn.setCheckable(True)
        self.toggle_details_btn.setMinimumHeight(28)  # click-target floor
        self.toggle_details_btn.setToolTip("Toggle the visibility of the application logs panel")
        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        self.btn_screenshot = create_styled_button("📸 Capture", variant="secondary")
        self.btn_screenshot.setToolTip("Save a screenshot of the electric field profile (PNG)")
        self.btn_screenshot.clicked.connect(self.export_png)

        self.btn_copy_log = create_styled_button("Copy Log", variant="secondary", icon=certus_icon("copy"))
        self.btn_copy_log.setToolTip("Copy the application logs to the clipboard")
        self.btn_copy_log.clicked.connect(self.copy_logs_to_clipboard)

        action_bar = create_top_actions_bar(self, self.save_config, self.load_config, self.export_data, self.open_help)
        left_layout.addWidget(action_bar)

        # Secondary actions on their own row. Appended to the main bar they made
        # seven buttons share one line, which alone forced the control panel to
        # 846 px - wider than the splitter ever grants it (measured 2026-09-03).
        secondary_bar = QWidget()
        secondary_layout = QHBoxLayout(secondary_bar)
        secondary_layout.setContentsMargins(6, 0, 6, 0)
        secondary_layout.setSpacing(6)
        secondary_layout.addWidget(self.btn_screenshot)
        secondary_layout.addWidget(self.toggle_details_btn)
        secondary_layout.addWidget(self.btn_copy_log)
        left_layout.addWidget(secondary_bar)

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self, use_app_reset=True)
        left_layout.addWidget(self.clear_btn)

        # 3. Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 8, 4, 0)
        scroll_layout.setSpacing(8)

        # -- Card: Optics
        card_optics = CertusCard("🔭 Optical Parameters", "Materials & Wavelengths")
        self.optics_panel = OpticsPanelWidget(self.material_list)

        # Connect to main app
        self.optics_panel.thickness_update_requested.connect(self._update_thicknesses)
        self.optics_panel.mat_h_changed.connect(self._on_mat_h_changed)
        self.optics_panel.mat_l_changed.connect(self._on_mat_l_changed)

        # Aliases for convenience during refactoring
        self.combo_mat_H = self.optics_panel.combo_mat_H
        self.combo_mat_L = self.optics_panel.combo_mat_L
        self.combo_mat_Sub = self.optics_panel.combo_mat_Sub
        self.combo_mat_Sup = self.optics_panel.combo_mat_Sup
        self.edit_l0 = self.optics_panel.edit_l0
        self.edit_lcalc = self.optics_panel.edit_lcalc
        self.edit_angle = self.optics_panel.edit_angle
        self.combo_pol = self.optics_panel.combo_pol

        card_optics.body.addWidget(self.optics_panel)
        scroll_layout.addWidget(CertusCollapsible("1  Materials Config", card_optics, expanded=True))

        # -- Card: Structure
        self.card_stack = CertusCard("🥞 Stack Structure", "Layers & Thicknesses")
        self.stack_panel = StackPanelWidget()

        self.stack_panel.table_item_changed.connect(self._on_table_item_changed)
        self.stack_panel.structure_changed.connect(self._update_thicknesses)
        self.stack_panel.import_requested.connect(self.on_import_design)
        self.stack_panel.pareto_requested.connect(self._show_pareto_window)

        btn_load_layout = QHBoxLayout()
        self.btn_detach_stack = create_styled_button("⬡ Detach Stack", variant="secondary")
        self.btn_detach_stack.setToolTip("Open the stack editor in a floating panel")
        self.btn_detach_stack.clicked.connect(self.toggle_detach_stack)
        btn_load_layout.addWidget(self.btn_detach_stack)

        self.table_layers = self.stack_panel.table_layers

        self.card_stack.body.addWidget(self.stack_panel)
        self.card_stack.body.addLayout(btn_load_layout)
        scroll_layout.addWidget(CertusCollapsible("2  Stack", self.card_stack, expanded=True))

        # -- Card: Optimisation
        card_opt = CertusCard("⚡ Optimization", "Weights & Controls")
        self.opt_panel = OptimizationPanelWidget()

        self.opt_panel.calc_requested.connect(self.on_calc_clicked)
        self.opt_panel.opt_requested.connect(self.on_opt_clicked)
        self.opt_panel.mc_requested.connect(self.on_mc_clicked)

        self.edit_seuil1 = self.opt_panel.edit_seuil1
        self.edit_seuil2 = self.opt_panel.edit_seuil2
        self.edit_alpha = self.opt_panel.edit_alpha
        self.edit_mc_error = self.opt_panel.edit_mc_error
        self.edit_mc_iter = self.opt_panel.edit_mc_iter
        self.edit_rmin = self.opt_panel.edit_rmin
        self.edit_rmax = self.opt_panel.edit_rmax
        self.chk_min_field = self.opt_panel.chk_min_field
        self.chk_global_opt = self.opt_panel.chk_global_opt
        self.chk_allow_growth = self.opt_panel.chk_allow_growth
        self.btn_calc = self.opt_panel.btn_calc
        self.btn_opt = self.opt_panel.btn_opt
        self.btn_mc = self.opt_panel.btn_mc

        card_opt.body.addWidget(self.opt_panel)
        scroll_layout.addWidget(CertusCollapsible("3  Action", card_opt, expanded=True))

        # -- Card: Metrics
        self.card_metrics = CertusCard("📊 Analytical Metrics", "Latest calculation results")
        metrics_layout_w = QWidget()
        metrics_layout = QVBoxLayout(metrics_layout_w)
        self.lbl_max_e2 = QLabel("Peak |E|² : N/A")
        self.lbl_r = QLabel("R : N/A")
        self.lbl_max_e2.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {CertusTheme.SUCCESS};")
        metrics_layout.addWidget(self.lbl_max_e2)
        metrics_layout.addWidget(self.lbl_r)
        self.card_metrics.body.addWidget(metrics_layout_w)
        scroll_layout.addWidget(self.card_metrics)

        # -- Card: Reports & Data
        card_reports = CertusCard("📁 Reports & Data", "Export history")
        rep_layout_w = QWidget()
        rep_layout = QVBoxLayout(rep_layout_w)
        self.btn_open_reports = create_styled_button("📂 Open Reports Folder", variant="secondary")
        self.btn_open_reports.setToolTip("Open the folder containing exported reports in File Explorer")
        self.btn_open_reports.clicked.connect(self.on_open_reports_clicked)
        rep_layout.addWidget(self.btn_open_reports)

        card_reports.body.addWidget(rep_layout_w)
        scroll_layout.addWidget(card_reports)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        return left_panel

    def _build_right_panel(self) -> QWidget:
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)

        # Tab 1: Overview (field + spectral + index simultaneously)
        overview_container = QWidget()
        overview_layout = QVBoxLayout(overview_container)
        overview_layout.setContentsMargins(4, 4, 4, 4)
        overview_layout.setSpacing(6)

        overview_hint = QLabel("Overview — field, spectral response and index profile visible together")
        overview_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        overview_layout.addWidget(overview_hint)

        overview_grid = QGridLayout()
        overview_grid.setHorizontalSpacing(8)
        overview_grid.setVerticalSpacing(8)

        field_panel = QWidget()
        field_layout = QVBoxLayout(field_panel)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_title = QLabel("Electric field")
        field_title.setStyleSheet("font-weight: 600;")
        field_layout.addWidget(field_title)
        self.plot_widget_ov = CertusFieldPlotWidget()
        field_layout.addWidget(self.plot_widget_ov)

        spectral_panel = QWidget()
        spectral_layout = QVBoxLayout(spectral_panel)
        spectral_layout.setContentsMargins(0, 0, 0, 0)
        spectral_layout.setSpacing(4)
        spectral_title = QLabel("Spectral response")
        spectral_title.setStyleSheet("font-weight: 600;")
        spectral_layout.addWidget(spectral_title)
        self.spectral_plot_widget_ov = CertusSpectralPlotWidget()
        spectral_layout.addWidget(self.spectral_plot_widget_ov)

        profile_panel = QWidget()
        profile_layout = QVBoxLayout(profile_panel)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(4)
        profile_title = QLabel("Index profile")
        profile_title.setStyleSheet("font-weight: 600;")
        profile_layout.addWidget(profile_title)
        self.profile_plot_widget_ov = CertusIndexProfilePlotWidget()
        profile_layout.addWidget(self.profile_plot_widget_ov)

        overview_grid.addWidget(field_panel, 0, 0)
        overview_grid.addWidget(spectral_panel, 0, 1)
        overview_grid.addWidget(profile_panel, 1, 0, 1, 2)
        overview_layout.addLayout(overview_grid)
        self.tab_widget.addTab(overview_container, "Overview")

        # Focus tabs for dedicated inspection
        field_container = QWidget()
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(4, 4, 4, 4)
        self.plot_widget = CertusFieldPlotWidget()
        field_layout.addWidget(self.plot_widget)
        self.tab_widget.addTab(field_container, "Field")

        spectral_container = QWidget()
        spectral_layout = QVBoxLayout(spectral_container)
        spectral_layout.setContentsMargins(4, 4, 4, 4)
        self.spectral_plot_widget = CertusSpectralPlotWidget()
        spectral_layout.addWidget(self.spectral_plot_widget)
        self.tab_widget.addTab(spectral_container, "Spectrum")

        profile_container = QWidget()
        profile_layout = QVBoxLayout(profile_container)
        profile_layout.setContentsMargins(4, 4, 4, 4)
        self.profile_plot_widget = CertusIndexProfilePlotWidget()
        profile_layout.addWidget(self.profile_plot_widget)
        self.tab_widget.addTab(profile_container, "Index")

        # Field Result Tab
        field_res_container = QWidget()
        field_res_layout = QVBoxLayout(field_res_container)
        field_res_layout.setContentsMargins(4, 4, 4, 4)
        field_res_tb = QHBoxLayout()
        self.btn_copy_field_res = create_styled_button("Copy Field Data", "secondary")
        self.btn_copy_field_res.clicked.connect(self._copy_field_res_to_clipboard)
        field_res_tb.addWidget(self.btn_copy_field_res)
        field_res_tb.addStretch(1)
        field_res_layout.addLayout(field_res_tb)
        self.table_field_res = ExcelTableWidget()
        self.table_field_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        field_res_layout.addWidget(self.table_field_res, 1)
        self.tab_widget.addTab(field_res_container, "Field Result")

        # Spectral Result Tab
        spectral_res_container = QWidget()
        spectral_res_layout = QVBoxLayout(spectral_res_container)
        spectral_res_layout.setContentsMargins(4, 4, 4, 4)
        spectral_res_tb = QHBoxLayout()
        self.btn_copy_spectral_res = create_styled_button("Copy Spectral Data", "secondary")
        self.btn_copy_spectral_res.clicked.connect(self._copy_spectral_res_to_clipboard)
        spectral_res_tb.addWidget(self.btn_copy_spectral_res)
        spectral_res_tb.addStretch(1)
        spectral_res_layout.addLayout(spectral_res_tb)
        self.table_spectral_res = ExcelTableWidget()
        self.table_spectral_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        spectral_res_layout.addWidget(self.table_spectral_res, 1)
        self.tab_widget.addTab(spectral_res_container, "Spectral Result")

        # Design Result Tab
        design_res_container = QWidget()
        design_res_layout = QVBoxLayout(design_res_container)
        design_res_layout.setContentsMargins(4, 4, 4, 4)
        design_res_tb = QHBoxLayout()
        self.btn_copy_design_res = create_styled_button("Copy Design Data", "secondary")
        self.btn_copy_design_res.clicked.connect(self._copy_design_res_to_clipboard)
        design_res_tb.addWidget(self.btn_copy_design_res)
        design_res_tb.addStretch(1)
        design_res_layout.addLayout(design_res_tb)
        self.table_design_res = ExcelTableWidget()
        # Row order IS the stack: certus_field_plot_mixin fills it with
        # "0 (Superstrate)", the layers in deposition order, then the substrate.
        # A text sort reads 0, 1, 10 (Substrate), 2, 3 ... and puts the substrate
        # between layer 1 and layer 2.
        self.table_design_res.certus_lock_row_order()
        self.table_design_res.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        design_res_layout.addWidget(self.table_design_res, 1)
        self.tab_widget.addTab(design_res_container, "Design Result")

        right_top_widget = QWidget()
        right_top_layout = QVBoxLayout(right_top_widget)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 0)
        header_label = QLabel("Results")
        header_label.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.btn_detach = create_styled_button("⬡ Detach active tab", "secondary")
        self.btn_detach.setFixedHeight(24)
        self.btn_detach.setToolTip("Open the current tab in a separate window.")
        self.btn_detach.clicked.connect(self.detach_current_plot)
        header_layout.addWidget(self.btn_detach)

        right_top_layout.addLayout(header_layout)
        right_top_layout.addWidget(self.tab_widget)

        self.right_splitter.addWidget(right_top_widget)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setVisible(False)
        self.right_splitter.addWidget(self.log_text)

        self.right_splitter.setSizes([1000, 0])
        self.tab_widget.setCurrentIndex(0)
        return self.right_splitter

    def _build_plot_export_frames(self, plot_data: dict) -> dict[str, pd.DataFrame]:
        return FieldExportService.build_plot_export_frames(plot_data)

    def _build_summary_frame(self, params: FieldParamsDTO) -> pd.DataFrame:
        return FieldExportService.build_summary_frame(
            params,
            self.combo_mat_H,
            self.combo_mat_L,
            self.combo_mat_Sub,
            self.combo_mat_Sup,
            self.edit_angle,
            self.combo_pol,
        )

    def _build_plot_data(self, result) -> FieldPlotData:
        return FieldPlotData.from_any(result)
