#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS HUB - Unified entry point for the CERTUS suite


=====================================================


Visually aligned with CERTUS-STRAT and certus_core/certus_ui standards.


Fixed: Header generation and Config loading robustness.


"""

from typing import Any
import logging

import functools


import multiprocessing


from pathlib import Path


import sys


from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    __version__,
    create_module_environment,
    setup_module_logging,
    certus_timestamp_display,
)


# =============================================================================


# LOGGING SETUP


# =============================================================================


logger = setup_module_logging("CERTUS_HUB")


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


bootstrap_env = create_module_environment(__file__, "CERTUS_HUB")


script_dir = bootstrap_env["script_dir"]


from certus_qt_widgets import (
    QApplication,
    QCheckBox,
    QColor,
    QFont,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProcess,
    QPushButton,
    QShortcut,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
)


# Conditional SVG import for logo


from certus_core import SVG_AVAILABLE


if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


else:
    QSvgWidget = None


# =============================================================================


# MODULAR IMPORTS (Post-Refactoring 2026)


# =============================================================================


from certus_core import get_export_config, get_resource_path, save_export_config


from certus_ui import (
    SVG_AVAILABLE,
    CertusTheme,
    CertusThemeToggle,
    create_colored_label,
    create_header_logo_widget,
    create_styled_label,
    init_certus_app,
    open_documentation,
    set_certus_window_icon,
)


# Styled buttons/labels - Now imported from certus_ui


# (create_styled_label & create_colored_label removed for DRY)


# get_base_path rm (use get_resource_path)


# =============================================================================


# UI COMPONENTS


# =============================================================================


class ModuleBadge(QLabel):
    """Professional Badge (CERTUS 2026)"""

    def __init__(self, text, color, parent=None) -> None:

        super().__init__(text, parent)

        self.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 2))

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setContentsMargins(
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_XS,
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_XS,
        )

        self.setStyleSheet(f"""

            background-color: {color}15;

            color: {color};

            border: 1px solid {color}60;

            border-radius: {CertusTheme.RADIUS_MD}px;

            letter-spacing: 0.5px;

            font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};

        """)

        self.setFixedHeight(26)


class ApplicationCard(QFrame):
    """

    Professional Application Card (CERTUS 2026).

    Modern design with hover effects.

    """

    def __init__(
        self,
        title: str,
        subtitle: str,
        description: str,
        script_name: str,
        icon_text: str,
        accent_color: str,
        badge_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(parent)

        self.script_name = script_name

        self.accent_color = accent_color

        self._is_hovered = False

        self.setFixedWidth(280)

        self.setFixedHeight(360)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setObjectName("AppCard")

        bg = CertusTheme.SURFACE

        border = CertusTheme.BORDER

        text_main = CertusTheme.TEXT_MAIN

        text_sub = CertusTheme.TEXT_SUB

        self._normal_style = f"""

            #AppCard {{

                background-color: {bg};

                border-radius: {CertusTheme.RADIUS_LG}px;

                border: 1px solid {border};

            }}

            QLabel {{ 

                border: none; 

                background: transparent; 

            }}

        """

        self._hover_style = f"""

            #AppCard {{

                background-color: {bg};

                border-radius: {CertusTheme.RADIUS_LG}px;

                border: 2px solid {accent_color};

            }}

            QLabel {{ 

                border: none; 

                background: transparent; 

            }}

        """

        self.setStyleSheet(self._normal_style)

        self._shadow = QGraphicsDropShadowEffect(self)

        self._shadow.setBlurRadius(CertusTheme.get_shadow().blurRadius())

        self._shadow.setColor(CertusTheme.get_shadow().color())

        self._shadow.setOffset(0, CertusTheme.get_shadow().offset().y())

        self.setGraphicsEffect(self._shadow)

        self._normal_blur = CertusTheme.get_shadow().blurRadius()

        self._normal_opacity = CertusTheme.get_shadow().color().alpha()

        self._normal_offset = CertusTheme.get_shadow().offset().y()

        self._hover_blur = 30

        self._hover_opacity = 40

        self._hover_offset = 4

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        # 1. Colored Header

        header_frame = QFrame()

        header_frame.setFixedHeight(5)

        header_frame.setStyleSheet(f"""

            background-color: {accent_color}; 

            border-top-left-radius: {CertusTheme.RADIUS_LG}px; 

            border-top-right-radius: {CertusTheme.RADIUS_LG}px;

        """)

        layout.addWidget(header_frame)

        content = QWidget()

        c_layout = QVBoxLayout(content)

        c_layout.setContentsMargins(
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
        )

        c_layout.setSpacing(CertusTheme.SPACING_MD)

        top_row = QHBoxLayout()

        top_row.setSpacing(CertusTheme.SPACING_MD)

        icon_lbl = QLabel(icon_text)

        icon_lbl.setFont(CertusTheme.get_font(36))

        icon_lbl.setStyleSheet(f"color: {accent_color};")

        top_row.addWidget(icon_lbl)

        top_row.addStretch()

        if badge_text:
            badge = ModuleBadge(badge_text.upper(), accent_color)

            top_row.addWidget(badge)

        c_layout.addLayout(top_row)

        c_layout.addSpacing(CertusTheme.SPACING_SM)

        title_lbl = create_styled_label(title, style="bold", color=text_main)

        title_lbl.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 8))

        title_lbl.setStyleSheet(f"color: {text_main}; letter-spacing: -0.3px;")

        c_layout.addWidget(title_lbl)

        sub_lbl = create_styled_label(subtitle, style="subtitle", color=accent_color)

        sub_lbl.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

        sub_lbl.setStyleSheet(f"""

            color: {accent_color}; 

            text-transform: uppercase; 

            letter-spacing: 1.2px; 

            margin-top: 2px;

        """)

        c_layout.addWidget(sub_lbl)

        c_layout.addSpacing(CertusTheme.SPACING_MD)

        desc_lbl = create_styled_label(description, style="normal", color=text_sub)

        desc_lbl.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

        desc_lbl.setStyleSheet(f"""

            color: {text_sub}; 

            line-height: 1.6; 

            font-weight: {CertusTheme.FONT_WEIGHT_NORMAL};

        """)

        desc_lbl.setWordWrap(True)

        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        c_layout.addWidget(desc_lbl)

        c_layout.addStretch()

        btn_row = QHBoxLayout()

        btn_row.setSpacing(CertusTheme.SPACING_SM)

        btn_lbl = create_styled_label("LAUNCH MODULE ->", style="bold", color=accent_color)

        btn_lbl.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

        btn_lbl.setStyleSheet(f"""

            color: {accent_color};

            padding: {CertusTheme.SPACING_SM}px 0px;

            border-bottom: 2px solid transparent;

        """)

        btn_row.addWidget(btn_lbl)

        btn_row.addStretch()

        c_layout.addLayout(btn_row)

        self.content_container = content

        layout.addWidget(content)

    def enterEvent(self, event) -> None:
        """Hover effect improvement with micro-animation"""

        if not hasattr(self, "_anim"):
            from PyQt6.QtCore import QVariantAnimation

            self._anim = QVariantAnimation(self)

            self._anim.setDuration(150)

            self._anim.valueChanged.connect(self._animate_hover)

            self._current_progress = 0.0

        self._anim.stop()

        self._anim.setStartValue(self._current_progress)

        self._anim.setEndValue(1.0)

        self._anim.start()

        if hasattr(self, "_hover_style"):
            self.setStyleSheet(self._hover_style)

        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Return to normal state with micro-animation"""

        if hasattr(self, "_anim"):
            self._anim.stop()

            self._anim.setStartValue(self._current_progress)

            self._anim.setEndValue(0.0)

            self._anim.start()

        if hasattr(self, "_normal_style"):
            self.setStyleSheet(self._normal_style)

        super().leaveEvent(event)

    def _animate_hover(self, progress: float) -> None:

        self._current_progress = progress

        if hasattr(self, "_shadow") and self._shadow:
            try:
                blur = self._normal_blur + (self._hover_blur - self._normal_blur) * progress

                opac = self._normal_opacity + (self._hover_opacity - self._normal_opacity) * progress

                off_y = self._normal_offset + (self._hover_offset - self._normal_offset) * progress

                from certus_qt_widgets import QColor

                self._shadow.setBlurRadius(blur)

                self._shadow.setColor(QColor(0, 0, 0, int(opac)))

                self._shadow.setOffset(0, off_y)

            except RuntimeError:
                # Shadow might have been deleted on C++ side (e.g. by effect replacement)

                pass


# =============================================================================


# UI COMPONENTS (Helper Classes)


# =============================================================================


class GroupedApplicationCard(ApplicationCard):
    """

    Card containing multiple sub-modules (Stacked vertically).

    """

    def __init__(
        self,
        title: str,
        icon_text: str,
        accent_color: str,
        sub_apps: list[dict[str, str]],
        badge_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:

        # Explicit call to QFrame init to skip ApplicationCard setup but keep inheritance if needed

        # Actually simplest is to just call QFrame init

        QFrame.__init__(self, parent)

        self.accent_color = accent_color

        self._is_hovered = False

        # Dimensions (taller to accommodate variants)

        self.setFixedWidth(280)

        self.setFixedHeight(380)  # Slightly taller

        self.setObjectName("AppCard")

        # Styling (Same as ApplicationCard)

        bg = CertusTheme.SURFACE

        border = CertusTheme.BORDER

        self._normal_style = f"""

            #AppCard {{

                background-color: {bg};

                border-radius: {CertusTheme.RADIUS_LG}px;

                border: 1px solid {border};

            }}

            QLabel {{ border: none; background: transparent; }}

        """

        self._hover_style = f"""

            #AppCard {{

                background-color: {bg};

                border-radius: {CertusTheme.RADIUS_LG}px;

                border: 2px solid {accent_color};

            }}

            QLabel {{ border: none; background: transparent; }}

        """

        self.setStyleSheet(self._normal_style)

        # Shadow

        self._shadow = QGraphicsDropShadowEffect(self)

        self._shadow.setBlurRadius(CertusTheme.get_shadow().blurRadius())

        self._shadow.setColor(CertusTheme.get_shadow().color())

        self._shadow.setOffset(0, CertusTheme.get_shadow().offset().y())

        self.setGraphicsEffect(self._shadow)

        # Shadow Props

        self._normal_blur = CertusTheme.get_shadow().blurRadius()

        self._normal_opacity = CertusTheme.get_shadow().color().alpha()

        self._normal_offset = CertusTheme.get_shadow().offset().y()

        self._hover_blur = 30

        self._hover_opacity = 40

        self._hover_offset = 4

        # Layout

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        # 1. Header

        header_frame = QFrame()

        header_frame.setFixedHeight(5)

        header_frame.setStyleSheet(f"""

            background-color: {accent_color}; 

            border-top-left-radius: {CertusTheme.RADIUS_LG}px; 

            border-top-right-radius: {CertusTheme.RADIUS_LG}px;

        """)

        layout.addWidget(header_frame)

        # 2. Content

        content = QWidget()

        c_layout = QVBoxLayout(content)

        c_layout.setContentsMargins(
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
        )

        c_layout.setSpacing(CertusTheme.SPACING_SM)

        # Top: Icon + Main Title

        top_row = QHBoxLayout()

        icon_lbl = QLabel(icon_text)

        icon_lbl.setFont(CertusTheme.get_font(24))

        icon_lbl.setStyleSheet(f"color: {accent_color};")

        top_row.addWidget(icon_lbl)

        title_lbl = create_styled_label(title, style="bold", color=CertusTheme.TEXT_MAIN)

        title_lbl.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 6))

        top_row.addWidget(title_lbl)

        top_row.addStretch()

        if badge_text:
            badge = ModuleBadge(badge_text.upper(), accent_color)

            top_row.addWidget(badge)

        c_layout.addLayout(top_row)

        # Separator

        line = QFrame()

        line.setFrameShape(QFrame.Shape.HLine)

        line.setStyleSheet(f"color: {CertusTheme.BORDER};")

        c_layout.addWidget(line)

        # Sub-Apps using shared click handler logic usually, but here we have specific buttons

        # We need to access 'launch_module' from parent. We can't easily.

        # Using signal or callback?

        # We'll assign a callback property to the instance.

        self.launch_callback = None  # Set after init

        for i, app in enumerate(sub_apps):
            # Sub-App Block

            sa_layout = QVBoxLayout()

            sa_layout.setSpacing(2)

            # Title Row

            sa_header = QHBoxLayout()

            sa_title = create_styled_label(app["title"], style="subtitle", color=accent_color)

            sa_title.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

            sa_header.addWidget(sa_title)

            if app.get("badge"):
                b = create_colored_label(app["badge"], CertusTheme.SUCCESS, 9, QFont.Weight.Bold)

                # b.setStyleSheet(f"background: {CertusTheme.SUCCESS_BG}; padding: 2px 4px; border-radius: 4px;")

                sa_header.addWidget(b)

            sa_header.addStretch()

            sa_layout.addLayout(sa_header)

            # Description

            sa_desc = create_styled_label(app["desc"], style="normal", color=CertusTheme.TEXT_SUB)

            sa_desc.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 1))

            sa_desc.setWordWrap(True)

            sa_layout.addWidget(sa_desc)

            # Launch Button

            btn = QPushButton("Launch")

            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            btn.setToolTip(f"Launch {app['title']} ({app['script']})")

            btn.setStyleSheet(f"""

                QPushButton {{

                    text-align: left;

                    color: {accent_color};

                    font-weight: bold;

                    border: none;

                    background: transparent;

                    padding: 4px 0px;

                }}

                QPushButton:hover {{

                    text-decoration: underline;

                }}

            """)

            # Capture script in lambda

            btn.clicked.connect(functools.partial(self._on_launch_button_clicked, app["script"]))

            sa_layout.addWidget(btn)

            c_layout.addLayout(sa_layout)

            # Divider between apps

            if i < len(sub_apps) - 1:
                div = QFrame()

                div.setFixedHeight(1)

                div.setStyleSheet(f"background-color: {CertusTheme.BORDER}; margin: 5px 0px;")

                c_layout.addWidget(div)

        c_layout.addStretch()

        self.content_container = content

        layout.addWidget(content)

    def _on_launch(self, script) -> None:

        if self.launch_callback:
            self.launch_callback(script)

    def _on_launch_button_clicked(self, script, *_args) -> None:

        self._on_launch(script)


# =============================================================================


# MAIN WINDOW


# =============================================================================


class CertusHub(QMainWindow):
    @staticmethod
    def _build_hub_apps_catalog() -> list[dict[str, str]]:
        """Return HUB application cards configuration."""
        return [
            {
                "title": "DESIGN",
                "sub": "Synthesis",
                "desc": "Stochastic Global Optimization. PGLOBAL algorithm with Single-Linkage Clustering.",
                "script": "CERTUS_DESIGN.py",
                "icon": "🧩",
                "color": CertusTheme.BRAND_DESIGN,
                "badge": "Concept",
                "type": "single",
            },
            {
                "title": "RE",
                "sub": "Reverse Engineering",
                "desc": "Extraction of refractive clues from experimental curves using spline networks.",
                "script": "CERTUS_RE.py",
                "icon": "🕵️",
                "color": CertusTheme.BRAND_STRAT,
                "badge": "Analysis",
                "type": "single",
            },
            {
                "title": "STRAT",
                "sub": "Manufacturing",
                "desc": "Predictive Monitoring Strategy. Error self-compensation analysis.",
                "script": "CERTUS_STRAT.py",
                "icon": "🏭",
                "color": CertusTheme.BRAND_STRAT,
                "badge": "Production",
                "type": "single",
            },
            {
                "title": "INDEX",
                "sub": "Dielectrics",
                "desc": "Advanced Tauc-Lorentz Characterization. Kramers-Kronig consistent extraction.",
                "script": "CERTUS_INDEX.py",
                "icon": "🧪",
                "color": CertusTheme.BRAND_INDEX,
                "badge": "Material",
                "type": "single",
            },
            {
                "title": "INDEX SPLINE",
                "sub": "Spline Model",
                "desc": "Non-parametric n,k extraction using PWL splines. Ideal for complex IR absorption.",
                "script": "CERTUS_INDEX_SPLINE.py",
                "icon": "〰️",
                "color": CertusTheme.BRAND_INDEX,
                "badge": "Material",
                "type": "single",
            },
            {
                "title": "SMOOTHER",
                "sub": "Processing",
                "desc": "Parametric smoothing of spectral measurement data.",
                "script": "certus_curve_smoother.py",
                "icon": "🫧",
                "color": CertusTheme.SUCCESS,
                "badge": "Utility",
                "type": "single",
            },
            {
                "title": "SUBSTRATE INDEX",
                "sub": "Characterization",
                "desc": "Substrate refractive index determination from spectral measurements.",
                "script": "certus_substrate_index.py",
                "icon": "📏",
                "color": CertusTheme.BRAND_INDEX,
                "badge": "Material",
                "type": "single",
            },
            {
                "title": "METAL BILAYER",
                "sub": "Opaque Substrate",
                "desc": "Opaque substrate strategy (Legacy).",
                "script": "CERTUS_METAL_BILAYER.py",
                "icon": "🛡️",
                "color": CertusTheme.BRAND_METAL,
                "badge": "Std",
                "type": "single",
            },
            {
                "title": "METAL SINGLE",
                "sub": "Transparent Substrate",
                "desc": "Transparent substrate strategy (R/T/Rb).",
                "script": "CERTUS_METAL_SINGLE.py",
                "icon": "🛡️",
                "color": CertusTheme.BRAND_METAL,
                "badge": "New",
                "type": "single",
            },
        ]

    @staticmethod
    def _hub_export_checkbox_stylesheet() -> str:
        """Return shared style for HUB export toggle."""
        return f"""
            QCheckBox {{ 
                color: {CertusTheme.TEXT_MAIN}; 
                spacing: {CertusTheme.SPACING_MD}px; 
                font-weight: {CertusTheme.FONT_WEIGHT_MEDIUM};
                font-family: {CertusTheme.FONT_FAMILY};
            }}
            QCheckBox::indicator {{ 
                width: 18px; 
                height: 18px; 
                border-radius: {CertusTheme.RADIUS_SM}px; 
                border: 1.5px solid {CertusTheme.BORDER}; 
                background: {CertusTheme.BACKGROUND}; 
            }}
            QCheckBox::indicator:checked {{ 
                background-color: {CertusTheme.PRIMARY}; 
                border-color: {CertusTheme.PRIMARY}; 
            }}
            QCheckBox::indicator:hover {{
                border-color: {CertusTheme.PRIMARY};
            }}
        """

    def __init__(self) -> None:
        """

        Initialize the CERTUS Hub main window.

        This method sets up the main application window including:

        - Window properties (title, size, minimum size)

        - UI components and layout

        - Module connections and integrations

        - Event handlers and signals

        Args:

            self: CertusHub instance

        Returns:

            None

        Notes:

            - Main entry point for the CERTUS Suite

            - Integrates all CERTUS modules

            - Provides unified interface for all tools

        """

        super().__init__()

        self.setWindowTitle("CERTUS-HUB - Calculated Error Reduction Through Unbiased Simulation")

        self.resize(1280, 720)

        self.setMinimumSize(1100, 600)

        self.active_processes = []

        # Global Background Style 2026

        bg_color = CertusTheme.BACKGROUND

        try:
            from certus_ux import build_premium_overrides

            premium_css = build_premium_overrides()
        except ImportError:
            premium_css = ""

        self.setStyleSheet(f"QMainWindow {{ background-color: {bg_color}; }}\n{premium_css}")

        set_certus_window_icon(self)

        # Keyboard shortcuts for quick module launch

        self._setup_shortcuts()

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        # Main layout

        main_layout = QVBoxLayout(central_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        # --- 1. HEADER (Style 2026) ---

        # Use create_header_logo_widget for consistency

        header_widget = create_header_logo_widget(
            "CERTUS HUB", "Unified Optical Suite", logo_width=200, module_name="HUB"
        )

        # Theme toggle injected into the header (right side) for consistency across CERTUS suite

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        main_layout.addWidget(header_widget)

        # --- 2. CONTENT AREA (Style 2026) ---

        content_area = QWidget()

        content_layout = QVBoxLayout(content_area)

        # Spacing Style 2026

        content_layout.setContentsMargins(
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
        )

        grid_layout = QGridLayout()

        grid_layout.setSpacing(CertusTheme.SPACING_XL)

        grid_wrapper = QHBoxLayout()

        grid_wrapper.addStretch()

        grid_wrapper.addLayout(grid_layout)

        grid_wrapper.addStretch()

        # Module definitions
        self.apps = self._build_hub_apps_catalog()

        MAX_COLS = 3  # 3x3 Grid (9 modules)

        for idx, app in enumerate(self.apps):
            if app.get("type") == "group":
                card = GroupedApplicationCard(
                    app["title"],
                    app["icon"],
                    app["color"],
                    app["sub_apps"],
                    app["badge"],
                )

                card.launch_callback = self.launch_module

            else:
                card = ApplicationCard(
                    app["title"],
                    app["sub"],
                    app["desc"],
                    app["script"],
                    app["icon"],
                    app["color"],
                    app["badge"],
                )

                card.mousePressEvent = lambda e, s=app["script"]: self.launch_module(s)

            # P1.4 - apply hover-lift + fade-in micro-animations on each card.
            self._apply_card_animations(card, index=idx)

            row = idx // MAX_COLS

            col = idx % MAX_COLS

            grid_layout.addWidget(card, row, col)

        content_layout.addLayout(grid_wrapper)

        content_layout.addStretch()

        # --- 3. BOTTOM BAR (Style 2026) ---

        bottom_bar = QWidget()

        bottom_bar.setStyleSheet(f"""

            border-top: 1px solid {CertusTheme.BORDER}; 

            background-color: {CertusTheme.SURFACE};

        """)

        bb_layout = QHBoxLayout(bottom_bar)

        bb_layout.setContentsMargins(
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_LG,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_LG,
        )

        # Config Group

        config_group = QWidget()

        cg_layout = QHBoxLayout(config_group)

        cg_layout.setContentsMargins(0, 0, 0, 0)

        # --- Auto Export Toggle ---

        _chk_style = self._hub_export_checkbox_stylesheet()

        auto_export_val = get_export_config()

        self.chk_export = QCheckBox("Auto Export Reports")

        self.chk_export.setChecked(auto_export_val)

        self.chk_export.setToolTip("Automatically generate Excel/HTML reports after calculationation.")

        self.chk_export.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

        self.chk_export.setStyleSheet(_chk_style)

        self.chk_export.stateChanged.connect(self.on_export_changed)

        cg_layout.addWidget(self.chk_export)

        bb_layout.addWidget(config_group)

        bb_layout.addStretch()

        # Documentation Button style 2026

        self.btn_docs = QPushButton(" Scientific Documentation")
        try:
            from certus_ux import OBJ

            self.btn_docs.setObjectName(OBJ.PRIMARY_BUTTON)
        except ImportError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.btn_docs.setToolTip("Open the full scientific documentation for the CERTUS suite (HTML reference).")

        # Try loading icon

        icon_path = get_resource_path("icons/book.svg")

        if Path(icon_path).exists():
            self.btn_docs.setIcon(QIcon(icon_path))

        self.btn_docs.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_docs.setFixedHeight(40)

        self.btn_docs.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 1))

        self.btn_docs.clicked.connect(self.open_documentation)

        bb_layout.addWidget(self.btn_docs)

        main_layout.addWidget(content_area)

        # P0.4 - Recent configs strip (opt-in wired here)
        self.attach_recent_files_strip(parent_layout=main_layout, limit=6)

        main_layout.addWidget(bottom_bar)

        # P0.4 / P2.3 - install a Help menu bar (consistent with sub-apps)
        self._install_help_menu()

        # Log Container (toggleable)

        self.log_container = QWidget()

        self.log_container.setVisible(False)

        self.log_container.setFixedHeight(150)

        log_layout = QVBoxLayout(self.log_container)

        log_layout.setContentsMargins(10, 0, 10, 10)

        self.log_text = QTextEdit()

        self.log_text.setReadOnly(True)

        self.log_text.setStyleSheet(CertusTheme.get_log_stylesheet())

        log_layout.addWidget(self.log_text)

        main_layout.addWidget(self.log_container)

        # Show Details Button (add to bottom bar)

        self.btn_details = QPushButton("Show Details")

        self.btn_details.setCheckable(True)

        self.btn_details.setStyleSheet(f"""

            QPushButton {{ background: transparent; color: {CertusTheme.TEXT_SUB}; border: 1px solid {CertusTheme.BORDER}; padding: 5px 10px; border-radius: 4px; }}

            QPushButton:checked {{ background: {CertusTheme.SURFACE_HOVER}; color: {CertusTheme.PRIMARY}; border-color: {CertusTheme.PRIMARY}; }}

            QPushButton:hover {{ background: {CertusTheme.SURFACE_HOVER}; }}

        """)

        self.btn_details.setToolTip("Show or hide the process launch log panel.")

        self.btn_details.clicked.connect(self.on_toggle_details)

        bb_layout.insertWidget(bb_layout.count() - 2, self.btn_details)  # Insert before stretch/docs

        # Active modules indicator

        self.lbl_active = create_styled_label("", style="normal", color=CertusTheme.SUCCESS)

        self.lbl_active.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 1))

        self.lbl_active.setVisible(False)

        bb_layout.insertWidget(0, self.lbl_active)

        # Theme toggle now lives in the header (see above) for UX consistency.

        # Footer Style 2026

        import platform

        from PyQt6.QtCore import QT_VERSION_STR

        footer_text = f"© 2024-2026 CERTUS Scientific Suite v{__version__} • Python {sys.version.split()[0]} ({platform.architecture()[0]}) • Qt {QT_VERSION_STR}"

        footer = create_styled_label(footer_text, style="caption")

        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 1))

        footer.setObjectName("HubFooter")

        main_layout.addWidget(footer)

        # Apply initial theme

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply global theme styles"""

        self.setStyleSheet(f"""

            QMainWindow {{ background-color: {CertusTheme.BACKGROUND}; }}

            QWidget {{ font-family: {CertusTheme.FONT_FAMILY}; }}

            /* Header components from COMMON */

            #CertusHeader {{ background-color: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER}; }}

            #CertusLogoFallback {{ color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 16px; }}

            #CertusHeaderTitle {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; }}

            #CertusHeaderSubtitle {{ color: {CertusTheme.TEXT_SUB}; border: none; }}

            /* Footer */

            #HubFooter {{ 

                color: {CertusTheme.TEXT_SUB}; 

                font-size: 9px; 

                padding: {CertusTheme.SPACING_MD}px; 

                background-color: {CertusTheme.BACKGROUND}; 

                border-top: 1px solid {CertusTheme.BORDER}; 

            }}

        """)

    def launch_module(self, app_name: str) -> None:

        # Use get_resource_path to get base dir

        base_dir = get_resource_path("")

        base_name = Path(app_name).stem

        if getattr(sys, "frozen", False):
            program = str(Path(base_dir) / (base_name + (".exe" if sys.platform == "win32" else "")))

            args = []

        else:
            program = sys.executable

            script_path = Path(base_dir) / app_name

            args = [str(script_path)]

            if not script_path.exists():
                QMessageBox.critical(self, "Error", f"Script not found: {script_path}")

                return

        process = QProcess(self)

        process.setProgram(program)

        process.setArguments(args)

        # Set working directory for relative paths (logs/configs)

        process.setWorkingDirectory(base_dir)

        process.finished.connect(lambda c, s, p=process, n=app_name: self.on_process_finished(p, n, c))

        # Log launch info

        module_name = Path(app_name).stem

        self._log_message(f"Launching {module_name}...")

        process.start()

        if not process.waitForStarted(3000):
            self._log_message(f"ERROR: Failed to start {module_name}")

            QMessageBox.warning(
                self,
                "Launch Error",
                f"Could not start {module_name}.\nPlease check that the module exists.",
            )

            return

        self.active_processes.append(process)

        self._update_active_indicator()

    def open_documentation(self) -> None:
        """Opens CERTUS_HUB documentation"""

        open_documentation("CERTUS_HUB")

    def on_export_changed(self, state) -> None:

        enabled = state == Qt.CheckState.Checked.value

        try:
            save_export_config(enabled)

        except (OSError, IOError, PermissionError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def on_process_finished(self, process, app_name, exit_code) -> None:

        module_name = Path(app_name).stem

        if process in self.active_processes:
            self.active_processes.remove(process)

        self._update_active_indicator()

        if exit_code == 0:
            self._log_message(f"{module_name} exited normally.")

        elif exit_code not in (1, 15, -1):  # Ignore common force-close codes
            err = process.readAllStandardError().data().decode("utf-8", errors="replace")

            self._log_message(f"{module_name} exited with code {exit_code}")

            if err:
                self._log_message(f"Error: {err[:200]}")

    def on_toggle_details(self, checked) -> None:

        self.log_container.setVisible(checked)

    def _update_active_indicator(self) -> None:
        """Update the active modules indicator in the status bar."""

        n = len(self.active_processes)

        if n > 0:
            self.lbl_active.setText(f"● {n} module{'s' if n > 1 else ''} running")

            self.lbl_active.setVisible(True)

        else:
            self.lbl_active.setVisible(False)

    def _log_message(self, msg) -> None:
        """Add a timestamped message to the log panel."""

        self.log_text.append(f"[{certus_timestamp_display()}] {msg}")

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for quick module launch."""

        shortcuts = [
            ("Ctrl+D", "CERTUS_DESIGN.py", "Launch DESIGN"),
            ("Ctrl+Shift+S", "CERTUS_STRAT.py", "Launch STRAT"),
            ("Ctrl+I", "CERTUS_INDEX.py", "Launch INDEX"),
            ("Ctrl+M", "CERTUS_METAL_SINGLE.py", "Launch METAL"),
            ("F1", None, "Open Documentation"),
        ]

        for key, script, desc in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)

            if script:
                shortcut.activated.connect(functools.partial(self.launch_module, script))

            else:
                shortcut.activated.connect(self.open_documentation)

            shortcut.setWhatsThis(desc)

    # =========================================================================

    # U5+ - Recent files strip (opt-in, additive; does not alter default UI)

    # =========================================================================

    def attach_recent_files_strip(self, parent_layout=None, *, limit: int = 5) -> Any:
        """Instantiate and return a recent-configs strip.

        This is an **opt-in** helper: calling code passes the layout where

        the strip should be inserted (e.g. the main dashboard layout, a

        sidebar, or the status bar). If ``parent_layout`` is ``None`` the

        widget is created, parented to the hub, and returned without

        being added anywhere, letting callers place it manually.

        Returns ``None`` if the recent-strip module is unavailable.

        """

        try:
            from certus_recent_strip import build_recent_files_strip

        except ImportError as e:  # pragma: no cover - defensive
            self._log_message(f"Recent strip unavailable: {e}")

            return None

        strip = build_recent_files_strip(
            self,
            limit=limit,
            on_open=self._on_recent_config_selected,
        )

        if strip is None:
            return None

        if parent_layout is not None:
            try:
                parent_layout.addWidget(strip)

            except (AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
                self._log_message(f"Recent strip insert failed: {e}")

        return strip

    def _on_recent_config_selected(self, path: str) -> None:
        """Callback when the user clicks a recent-file pill."""

        self._log_message(f"Recent file selected: {path}")

    # =========================================================================

    # P2.3 - Help menu (uniform entry points across the suite)

    # =========================================================================

    def _install_help_menu(self) -> None:
        """Create the standard Help menu: Shortcuts, Docs, About."""

        try:
            mb = self.menuBar()

            help_menu = mb.addMenu("&Help")

            act_shortcuts = help_menu.addAction("Keyboard shortcuts…")

            act_shortcuts.setShortcut("F1")

            act_shortcuts.triggered.connect(self._open_shortcuts_overlay)

            help_menu.addSeparator()

            act_docs = help_menu.addAction("Open documentation…")

            act_docs.triggered.connect(self.open_documentation)

            help_menu.addSeparator()

            act_about = help_menu.addAction("About CERTUS…")

            act_about.triggered.connect(self._show_about_dialog)

        except (AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
            self._log_message(f"Help menu install failed: {e}")

    def _open_shortcuts_overlay(self) -> None:
        """Delegate to certus_shortcuts_overlay if available."""

        try:
            from certus_shortcuts_overlay import open_shortcuts_overlay

            open_shortcuts_overlay(self)

        except (ImportError, AttributeError, RuntimeError, TypeError) as e:
            self._log_message(f"Shortcuts overlay unavailable: {e}")

    def _show_about_dialog(self) -> None:
        """Minimal About dialog."""

        try:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.about(
                self,
                "About CERTUS",
                "<b>CERTUS HUB</b><br>Unified Optical Suite<br><br>"
                "Version 2026 - All suite apps accessible from a single dashboard.<br>"
                "Press <code>F1</code> for keyboard shortcuts.",
            )

        except (ImportError, AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
            self._log_message(f"About dialog failed: {e}")

    # =========================================================================

    # P1.4 - Card micro-animations (hover lift + staggered fade-in)

    # =========================================================================

    def _apply_card_animations(self, card, *, index: int) -> None:
        """Attach hover-lift and a staggered fade-in on an HUB card."""

        try:
            from certus_animations import fade_in, hover_lift

        except ImportError:
            return

        try:
            hover_lift(card, lift_px=3)

        except (AttributeError, RuntimeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # Stagger the fade-in so cards appear sequentially (~60 ms apart).

        try:
            from PyQt6.QtCore import QTimer

            delay_ms = 60 * int(index)

            # Targeted fade-in on content to avoid replacing the card's shadow effect

            target = getattr(card, "content_container", card)

            QTimer.singleShot(delay_ms, lambda: fade_in(target, duration_ms=220))

        except (ImportError, AttributeError, RuntimeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


# =============================================================================


# SPLASH & ENTRY POINT


# =============================================================================


class SplashScreen(QWidget):
    """Splash screen (CERTUS 2026)"""

    def __init__(self) -> None:

        super().__init__()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(650, 380)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()

        container.setStyleSheet(f"""

            background-color: {CertusTheme.BACKGROUND}; 

            border: 2px solid {CertusTheme.PRIMARY}; 

            border-radius: {CertusTheme.RADIUS_XL}px;

        """)

        # Shadow Style 2026

        shadow = CertusTheme.get_shadow()

        shadow.setBlurRadius(30)

        shadow.setColor(QColor(0, 0, 0, 50))

        shadow.setOffset(0, 6)

        container.setGraphicsEffect(shadow)

        l = QVBoxLayout(container)

        l.setContentsMargins(
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
        )

        l.setSpacing(CertusTheme.SPACING_LG)

        # CERTUS SVG Logo - Try multiple paths

        logo_widget = None

        logo_paths = [
            get_resource_path("certus.svg"),  # Horizontal format (priority, used by create_header_logo_widget)
            get_resource_path("certus_logo.svg"),
            get_resource_path("images/certus_logo.svg"),
            get_resource_path("images/certus.svg"),
        ]

        for logo_path in logo_paths:
            if SVG_AVAILABLE and QSvgWidget and Path(logo_path).exists():
                try:
                    logo_widget = QSvgWidget(logo_path)

                    logo_widget.setFixedSize(400, 85)  # Ratio adapted for splash

                    l.addWidget(logo_widget, alignment=Qt.AlignmentFlag.AlignCenter)

                    break

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    logging.debug(f"Error loading SVG logo {logo_path}: {e}")

                    logo_widget = None

        # Fallback if SVG logo unavailable

        if logo_widget is None:
            icon_label = QLabel("💠")

            icon_label.setFont(CertusTheme.get_font(50))

            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label.setStyleSheet(f"color: {CertusTheme.PRIMARY};")

            l.addWidget(icon_label)

            title = create_styled_label("CERTUS", style="bold")

            title.setFont(CertusTheme.get_font(52))

            title.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN};")

            title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            l.addWidget(title)

        sub = create_styled_label("HUB INITIALIZATION", style="subtitle", color=CertusTheme.PRIMARY)

        sub.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 3))

        sub.setStyleSheet(f"""
            color: {CertusTheme.PRIMARY}; 
        """)

        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        l.addWidget(sub)

        l.addStretch()

        layout.addWidget(container)


class CertusApp:
    def __init__(self) -> None:

        # High DPI scaling (Must be set BEFORE creating QApplication)

        if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
            if not QApplication.instance():
                QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        self.app = QApplication(sys.argv)

        # Init theme via COMMON if available (silent mode)

        try:
            if "init_certus_app" in globals():
                init_certus_app("CERTUS Hub", app=self.app)

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.splash = SplashScreen()

        self.hub = None

    def start(self) -> Any:

        self.splash.show()

        # Screen centering

        geo = self.splash.frameGeometry()

        try:
            cp = self.app.primaryScreen().availableGeometry().center()

            geo.moveCenter(cp)

            self.splash.move(geo.topLeft())

        except (AttributeError, RuntimeError):
            # Screen geometry may not be available in some environments

            pass

        QTimer.singleShot(1200, self.show_hub)

        return self.app.exec()

    def show_hub(self) -> None:

        self.hub = CertusHub()

        self.hub.show()

        self.splash.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    manager = CertusApp()

    sys.exit(manager.start())
