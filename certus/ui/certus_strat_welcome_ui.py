import functools
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from certus.core.certus_config import get_resource_path
from certus.ui.certus_icons import is_svg_icon_rendering_disabled, set_themed_icon
from certus.ui.certus_theme import CertusTheme
from certus.utils.certus_strat_service import APP_CONTEXT
from certus.utils.certus_ux import OBJ, Typography

#: The bundled example offered by the welcome page; it is read, never written (CLAUDE.md, rule 4).
STRAT_EXAMPLE = "example/example_strat/JSON-strat-example.json"
RECENTS_SHOWN = 5


class WelcomeGuideWidget(QWidget):
    def __init__(self, parent=None, *, on_open: Callable[[str], object] | None = None) -> None:
        # `on_open(path)` loads a configuration. Given, the page offers actions (the example, the recent files) where
        # it showed slogans (U10, decision Q37); without it, the page is the one it always was.

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
            .step-title {{ color: {CertusTheme.TEXT_MAIN}; font-size: {Typography.H3}pt; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }}
            .step-desc {{ color: {CertusTheme.TEXT_SUB}; font-size: {Typography.BODY_LG}pt; line-height: 1.35; }}

            .mission-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 14px; }}
            .dash-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px; }}
            .dash-header {{ color: {CertusTheme.PRIMARY}; font-size: {Typography.BODY}pt; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid {CertusTheme.BORDER}; padding-bottom: 6px; margin-bottom: 8px; }}

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

            lbl_ico.setFixedWidth(28)  # an emoji at 20 px is 27 px wide: 25 cut it

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: {Typography.BODY_LG}pt; background: transparent;")

            lbl_txt.setTextFormat(Qt.TextFormat.RichText)

            lbl_txt.setWordWrap(True)

            item_layout.addWidget(lbl_ico)

            item_layout.addWidget(lbl_txt)

            mission_layout.addWidget(item_widget, i // 2, i % 2)

        content_layout.addWidget(mission_frame)

        self._on_open = on_open
        self._recents_layout = None
        if on_open is not None:
            mission_frame.hide()
            content_layout.addWidget(self._build_get_started())

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
            db = APP_CONTEXT.get("materials_db")  # STRAT's RobustMaterialDatabase keeps them in `materials`
            mat_count = len(getattr(db, "materials", None) or getattr(db, "data", None) or [])

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

    def _build_get_started(self) -> QFrame:
        """Open the example, or one of the last configurations loaded in STRAT (U10)."""
        frame = QFrame()
        frame.setProperty("class", "mission-frame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        head = QLabel("GET STARTED")
        head.setProperty("class", "dash-header")
        layout.addWidget(head)

        example = Path(get_resource_path(STRAT_EXAMPLE))
        btn_example = QPushButton("Open the example")
        btn_example.setToolTip(f"Load the bundled example configuration (read only): {example}")
        btn_example.setEnabled(example.is_file())
        btn_example.clicked.connect(functools.partial(self._open, str(example)))
        layout.addWidget(btn_example, alignment=Qt.AlignmentFlag.AlignLeft)

        recent_head = QLabel("Recent configurations")
        recent_head.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-weight: 600;")
        layout.addWidget(recent_head)
        self._recents_layout = QVBoxLayout()
        self._recents_layout.setSpacing(2)
        layout.addLayout(self._recents_layout)
        self._fill_recents()
        return frame

    def _fill_recents(self) -> None:
        if self._recents_layout is None:
            return
        while self._recents_layout.count():
            widget = self._recents_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        from certus.ui.certus_recent import RecentCategories, list_recent, short_label

        paths = list_recent(RecentCategories.STRAT_CONFIG, limit=RECENTS_SHOWN)
        if not paths:
            self._recents_layout.addWidget(QLabel("None yet: the configurations you load appear here."))
            return
        for path in paths:
            btn = QPushButton(short_label(path))
            btn.setObjectName(OBJ.GHOST_BUTTON)
            btn.setToolTip(path)
            btn.clicked.connect(functools.partial(self._open, path))
            self._recents_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _open(self, path: str, *_args) -> None:
        if self._on_open is not None:
            self._on_open(path)

    def showEvent(self, event) -> None:
        # A file loaded since the page was built is offered the next time it shows.
        super().showEvent(event)
        self._fill_recents()

    def _create_status_row(self, icon, label, value) -> Any:

        row = QHBoxLayout()

        row.setSpacing(15)

        lbl_icon = QLabel(icon)

        lbl_icon.setFixedSize(28, 24)  # the emoji is 26 px wide: 24 cut it

        # The SVG of the suite in place of the emoji (U8); the emoji stays when the SVG rendering is off.
        svg = {"⚡": "zap", "📚": "book-open", "🚀": "activity"}.get(icon)
        if svg and not is_svg_icon_rendering_disabled():
            lbl_icon.setText("")
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            set_themed_icon(lbl_icon, svg, "SECONDARY", 16)

        lbl_icon.setStyleSheet(
            f"background-color: {CertusTheme.INFO_BG}; color: {CertusTheme.SECONDARY}; border-radius: 4px; font-weight: bold; font-size: {Typography.H2}pt;"
        )

        if icon == "✓":
            lbl_icon.setStyleSheet(
                f"background-color: {CertusTheme.SUCCESS_BG}; color: {CertusTheme.SUCCESS}; border-radius: 4px; font-weight: bold; font-size: {Typography.H2}pt;"
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

