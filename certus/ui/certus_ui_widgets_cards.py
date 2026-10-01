import logging

import pyqtgraph.exporters  # pylint: disable=unused-import
from PyQt6.QtCore import (
    Qt,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from certus.ui.certus_theme import CertusTheme
from certus.utils.certus_ux import Typography


class CertusCard(QFrame):
    """Flat card replacing heavy QGroupBox. Exposes .body (QVBoxLayout) for content."""

    def __init__(self, title: str = "", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CertusCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._intro_fade_started = False
        self._refresh_style()
        self.setGraphicsEffect(CertusTheme.get_shadow(self))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if title:
            hdr = QWidget()
            hdr.setObjectName("CertusCardHeader")
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(12, 8, 12, 6)
            hl.setSpacing(6)
            lbl = QLabel(title)
            lbl.setObjectName("CertusCardTitle")
            lbl.setStyleSheet(
                f"font-weight: 700; font-size: {Typography.BODY_LG}pt; color: {CertusTheme.TEXT_MAIN}; letter-spacing: 0.3px;"
            )
            hl.addWidget(lbl)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setStyleSheet(f"font-size: {Typography.BODY}pt; color: {CertusTheme.TEXT_SUB};")
                hl.addWidget(sub)
            hl.addStretch(1)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {CertusTheme.BORDER};")
            outer.addWidget(hdr)
            outer.addWidget(sep)
        body_w = QWidget()
        self.body = QVBoxLayout(body_w)
        self.body.setContentsMargins(12, 8, 12, 10)
        self.body.setSpacing(6)
        outer.addWidget(body_w)

    def _refresh_style(self) -> None:
        self.setStyleSheet(
            f"#CertusCard {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; "
            f"border-radius: 8px; }}"
        )

    def refresh_theme(self) -> None:
        """Re-apply this card's own stylesheet after a theme change.

        The sheet is an f-string evaluated once, at construction; the palette it
        captured does not follow a later switch. The method already existed under
        a private name and nothing ever called it.
        """
        self._refresh_style()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(self, "_intro_fade_started", False):
            return
        self._intro_fade_started = True
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, CertusCard) or (hasattr(parent, "graphicsEffect") and parent.graphicsEffect() is not None):
                return
            parent = parent.parentWidget()
        try:
            from certus.ui.certus_animations import fade_in

            fade_in(self, duration_ms=180)
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Animation module unavailable or function not found - skip animation
            pass

class FlashyCard(QFrame):
    def refresh_theme(self) -> None:
        """Re-apply this card's own stylesheet after a theme change."""
        self.setStyleSheet(
            f"background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px;"
        )

    """

    Styled card widget for displaying feature highlights.

    Args:

        title: Card title (bold, larger font)

        subtitle: Card description text

        icon: Optional emoji or icon character

    """

    def __init__(self, title: str, subtitle: str, icon: str = "") -> None:

        super().__init__()

        self.refresh_theme()

        lay = QVBoxLayout(self)

        if icon:
            lbl = QLabel(icon)

            lbl.setStyleSheet("font-size: 48px;")

            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lay.addWidget(lbl)

        t = QLabel(title)

        t.setStyleSheet(f"font-weight: bold; font-size: 16px; color: {CertusTheme.TEXT_MAIN}")

        t.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(t)

        s = QLabel(subtitle)

        s.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")

        s.setAlignment(Qt.AlignmentFlag.AlignCenter)

        s.setWordWrap(True)

        lay.addWidget(s)

        try:
            from certus.ui.certus_animations import hover_lift

            hover_lift(self, lift_px=3)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

class CertusDashboardCard(QFrame):
    """UX-1: Professional metrics card for results dashboard."""

    def __init__(self, title: str, icon_name: str = "activity", unit: str = "") -> None:
        super().__init__()
        self.unit = unit
        self._intro_fade_started = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            CertusDashboardCard {{
                background-color: {CertusTheme.BASE_ELEVATED};
                border-radius: 8px;
                border: 1px solid {CertusTheme.BORDER};
            }}
        """)
        self.setMinimumWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: bold; font-size: {Typography.BODY_LG}pt; letter-spacing: 1px;"
        )

        self.lbl_icon = QLabel()
        try:
            from certus.ui.certus_icons import certus_icon

            icon = certus_icon(icon_name, color=CertusTheme.TEXT_SUB, size=16)
            pm = icon.pixmap(16, 16)
            if pm is None or pm.isNull():
                self.lbl_icon.setText("•")
            else:
                self.lbl_icon.setPixmap(pm)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            self.lbl_icon.setText("•")

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_icon)
        layout.addLayout(header)

        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        val_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        self.lbl_value = QLabel("---")
        # TEXT_MAIN, not TEXT: the latter is the SAME dark navy in both modes, so the
        # biggest figure of the card sat at 1.01:1 on a dark surface while its own
        # title and unit, on TEXT_SUB, followed the theme correctly.
        self.lbl_value.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 28px; font-weight: 800;")

        self.lbl_unit = QLabel(unit)
        self.lbl_unit.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: {Typography.H2}pt; font-weight: bold; margin-bottom: 4px;"
        )

        val_row.addWidget(self.lbl_value)
        val_row.addWidget(self.lbl_unit)
        layout.addLayout(val_row)

        self.lbl_msg = QLabel("Ready")
        self.lbl_msg.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: {Typography.BODY_LG}pt;")
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setVisible(False)
        layout.addWidget(self.lbl_msg)

        try:
            from certus.ui.certus_animations import hover_lift

            hover_lift(self, lift_px=2)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def update_value(self, value: str, status: str = "normal", msg: str = "") -> None:
        self.lbl_value.setText(value)

        color_map = {
            "success": CertusTheme.SUCCESS,
            "warning": CertusTheme.WARNING,
            "danger": CertusTheme.DANGER,
            "info": CertusTheme.PRIMARY,
            "normal": CertusTheme.TEXT_MAIN,
        }
        val_color = color_map.get(status, CertusTheme.TEXT_MAIN)
        self.lbl_value.setStyleSheet(f"color: {val_color}; font-size: 28px; font-weight: 800;")

        if msg:
            self.lbl_msg.setText(msg)
            self.lbl_msg.setVisible(True)
            self.lbl_msg.setStyleSheet(f"color: {val_color}; font-size: {Typography.BODY_LG}pt; font-weight: 500;")
        else:
            self.lbl_msg.setVisible(False)

        try:
            from certus.ui.certus_animations import pulse

            pulse(self.lbl_value)
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Animation module unavailable - skip pulse animation
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._intro_fade_started:
            return
        self._intro_fade_started = True
        try:
            from certus.ui.certus_animations import fade_in

            fade_in(self, duration_ms=180)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            return

