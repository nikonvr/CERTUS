from __future__ import annotations
from certus.ui.certus_strat_common import *

class WelcomeGuideWidget(QWidget):
    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"""
            QWidget {{ font-family: 'Segoe UI', sans-serif; }}

            QScrollArea, QWidget#ContentContainer {{ background: {CertusTheme.BACKGROUND}; border: none; }}

            QScrollBar:vertical {{ width: 10px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {CertusTheme.BORDER}; border-radius: 5px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            .step-card {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 16px;
            }}
            .step-number {{ font-size: 34px; font-weight: 900; opacity: 0.20; }}
            .step-title {{ color: {CertusTheme.TEXT_MAIN}; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }}
            .step-desc {{ color: {CertusTheme.TEXT_SUB}; font-size: 11px; line-height: 1.35; }}

            .mission-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 14px; }}
            .dash-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px; }}
            .dash-header {{ color: {CertusTheme.PRIMARY}; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid {CertusTheme.BORDER}; padding-bottom: 6px; margin-bottom: 8px; }}

        """)

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_container = QWidget()

        self.content_container.setObjectName("ContentContainer")

        main_layout = QVBoxLayout(self.content_container)

        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.content_container)

        outer_layout.addWidget(self.scroll_area)

        content_wrapper = QWidget()

        content_wrapper.setStyleSheet("background-color: transparent;")

        content_layout = QVBoxLayout(content_wrapper)

        content_layout.setContentsMargins(8, 14, 8, 10)

        content_layout.setSpacing(14)

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(10)

        cards_layout.addWidget(
            self._create_step_card(
                "01",
                "DESIGN",
                "Define optical stack,\nmaterials & target.",
                CertusTheme.SECONDARY,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "02",
                "OPTIMIZE",
                "Hybrid algorithm for\nstable monitoring.",
                CertusTheme.ACCENT,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "03",
                "VALIDATE",
                "Monte Carlo sims to\nensure robustness.",
                CertusTheme.SUCCESS,
            )
        )

        content_layout.addLayout(cards_layout)

        mission_frame = QFrame()

        mission_frame.setProperty("class", "mission-frame")

        mission_layout = QGridLayout(mission_frame)

        mission_layout.setContentsMargins(14, 14, 14, 14)

        points = [
            (
                "🎯",
                "<b>Precision Targeting:</b> Identify exact wavelengths to cancel errors.",
            ),
            ("🧬", "<b>Hybrid Intelligence:</b> DP engine finds global minimuum."),
            (
                "🛡️",
                "<b>Robustness First:</b> Validation via thousands of Monte Carlo sims.",
            ),
            (
                "⚡",
                "<b>Real-Time Physics:</b> JIT engine simulating layer growth in ms.",
            ),
            (
                "📉",
                "<b>Zero-Bias Strategy:</b> Eliminate empiricism with proven paths.",
            ),
            (
                "📈",
                "<b>Yield Assurance:</b> Turn theoretical robustness into production gains.",
            ),
        ]

        for i, (icon, text) in enumerate(points):
            item_widget = QWidget()

            item_layout = QHBoxLayout(item_widget)

            item_layout.setContentsMargins(0, 0, 0, 0)

            lbl_ico = QLabel(icon)

            lbl_ico.setStyleSheet("font-size: 20px; background: transparent;")

            lbl_ico.setFixedWidth(25)

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; background: transparent;")

            lbl_txt.setTextFormat(Qt.TextFormat.RichText)

            lbl_txt.setWordWrap(True)

            item_layout.addWidget(lbl_ico)

            item_layout.addWidget(lbl_txt)

            mission_layout.addWidget(item_widget, i // 2, i % 2)

        content_layout.addWidget(mission_frame)

        dash_frame = QFrame()

        dash_frame.setProperty("class", "dash-frame")

        shadow_dash = QGraphicsDropShadowEffect()

        shadow_dash.setBlurRadius(15)

        shadow_dash.setColor(QColor(0, 0, 0, 10))

        shadow_dash.setOffset(0, 2)

        dash_frame.setGraphicsEffect(shadow_dash)

        dash_layout = QHBoxLayout(dash_frame)

        dash_layout.setContentsMargins(12, 12, 12, 12)

        dash_layout.setSpacing(12)

        # Get approximate total CPU count

        from certus.core.certus_core import _get_cpu_count

        cpu_count = _get_cpu_count()

        try:
            mat_count = len(APP_CONTEXT.get("materials_db").data) if APP_CONTEXT.get("materials_db") else 0

        except (AttributeError, TypeError):
            mat_count = 0

        sys_layout = QVBoxLayout()

        sys_head = QLabel("SYSTEM READINESS")

        sys_head.setProperty("class", "dash-header")

        sys_layout.addWidget(sys_head)

        sys_layout.addLayout(self._create_status_row("⚡", "HPC Active", f"<b>{cpu_count} Threads</b>"))

        sys_layout.addLayout(self._create_status_row("📚", "Database", f"<b>{mat_count} Materials</b>"))

        sys_layout.addLayout(self._create_status_row("🚀", "JIT Engine", "<b>Compiled & Ready</b>"))

        sys_layout.addStretch()

        cap_layout = QVBoxLayout()

        cap_head = QLabel("CORE CAPABILITIES")

        cap_head.setProperty("class", "dash-header")

        cap_layout.addWidget(cap_head)

        cap_layout.addLayout(self._create_status_row("✓", "Hybrid Exploration", "DP + hybridization"))

        cap_layout.addLayout(self._create_status_row("✓", "Simulation", "Adaptive Nucleation"))

        cap_layout.addLayout(self._create_status_row("✓", "Analysis", "Yield & Robustness"))

        cap_layout.addStretch()

        dash_layout.addLayout(sys_layout)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.VLine)

        line.setStyleSheet(f"color: {CertusTheme.SURFACE_HOVER};")

        dash_layout.addWidget(line)

        dash_layout.addLayout(cap_layout)

        content_layout.addWidget(dash_frame)

        main_layout.addWidget(content_wrapper)

        main_layout.addStretch()

    def _create_step_card(self, number, title, desc, accent_color) -> Any:

        card = QFrame()

        card.setProperty("class", "step-card")

        card.setStyleSheet(
            f".step-card {{ border-bottom: 4px solid {accent_color}; padding: 10px 12px; }}"
        )

        card.setMinimumWidth(160)

        card.setMaximumWidth(220)

        card.setMinimumHeight(130)

        shadow = QGraphicsDropShadowEffect()

        shadow.setBlurRadius(18)

        shadow.setColor(QColor(0, 0, 0, 16))

        shadow.setOffset(0, 6)

        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)

        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.setSpacing(2)

        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_num = QLabel(number)

        lbl_num.setProperty("class", "step-number")

        lbl_num.setStyleSheet(f"color: {accent_color}; background: transparent;")

        lbl_title = QLabel(title)

        lbl_title.setProperty("class", "step-title")

        lbl_title.setStyleSheet("background: transparent;")

        lbl_desc = QLabel(desc)

        lbl_desc.setProperty("class", "step-desc")

        lbl_desc.setStyleSheet("background: transparent;")

        vbox.addWidget(lbl_num)

        vbox.addWidget(lbl_title)

        vbox.addWidget(lbl_desc)

        return card

    def _create_status_row(self, icon, label, value) -> Any:

        row = QHBoxLayout()

        row.setSpacing(15)

        lbl_icon = QLabel(icon)

        lbl_icon.setFixedSize(24, 24)

        lbl_icon.setStyleSheet(
            f"background-color: {CertusTheme.INFO_BG}; color: {CertusTheme.SECONDARY}; border-radius: 4px; font-weight: bold; font-size: 14px;"
        )

        if icon == "✓":
            lbl_icon.setStyleSheet(
                f"background-color: {CertusTheme.SUCCESS_BG}; color: {CertusTheme.SUCCESS}; border-radius: 4px; font-weight: bold; font-size: 14px;"
            )

        lbl_text = QLabel(label)

        lbl_text.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 13px; font-weight: 500; background: transparent;"
        )

        lbl_val = QLabel(value)

        lbl_val.setTextFormat(Qt.TextFormat.RichText)

        lbl_val.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 13px; background: transparent;")

        row.addWidget(lbl_icon)

        row.addWidget(lbl_text)

        row.addStretch()

        row.addWidget(lbl_val)

        return row

