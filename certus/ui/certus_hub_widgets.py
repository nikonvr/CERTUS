from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout

from certus.ui.certus_theme import CertusTheme
from certus.utils.certus_ux import Typography


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

            background-color: {CertusTheme.tint(color, 0.08)};

            color: {color};

            border: 1px solid {CertusTheme.tint(color, 0.38)};

            border-radius: {CertusTheme.RADIUS_MD}px;

            letter-spacing: 0.5px;

            font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};

        """)

        self.setFixedHeight(26)


class BaseApplicationCard(QFrame):
    """Base logic for iOS-style hover animations in CERTUS Hub."""

    #: Emitted when the card is activated, by mouse or by keyboard.
    activated = pyqtSignal()

    def __init__(self, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self.accent_color = accent_color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # These cards are the only way into the suite, and they are frames,
        # not buttons: without an explicit focus policy Tab cannot reach them
        # and the welcome window is mouse-only.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Set by a left press, cleared by the matching release.
        self._armed = False

    def mousePressEvent(self, event):  # Qt naming
        """Arm on the left button only; nothing is launched yet."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._armed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # Qt naming
        """Activate only if the same click ends inside the card.

        Acting on release is what lets a mis-click be undone: press, slide
        off the card, let go, and nothing happens.
        """
        if event.button() != Qt.MouseButton.LeftButton or not self._armed:
            super().mouseReleaseEvent(event)
            return
        self._armed = False
        if self.rect().contains(event.position().toPoint()):
            self.activated.emit()
        event.accept()

    def keyPressEvent(self, event):  # Qt naming
        """Activate on Enter or Space, the way any button would."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)

class ApplicationCard(BaseApplicationCard):
    """iPhone-style application icon card for the HUB 3x3 matrix."""

    TILE_WIDTH = 156
    TILE_HEIGHT = 184

    def __init__(
        self,
        title: str,
        subtitle: str,
        description: str,
        script_name: str,
        icon_text: str,
        accent_color: str,
        badge_text: str | None = None,
        parent=None,
        *,
        task: str = "",
    ) -> None:
        super().__init__(accent_color, parent)
        self.script_name = script_name
        self.setFixedSize(self.TILE_WIDTH, self.TILE_HEIGHT)
        self.setObjectName("AppCard")
        self.setAccessibleName(title)
        self.setAccessibleDescription(f"{task} {subtitle} - {description}" if task else f"{subtitle} - {description}")

        if task:
            self.setToolTip(f"<b>{title}</b><br>{task}<br><br>{subtitle} - {description}")
        else:
            self.setToolTip(f"<b>{title}</b><br>{subtitle}<br><br>{description}")
        
        self.setStyleSheet("#AppCard { background: transparent; }")
        
        # Inner Squircle (the iPhone icon itself)
        self.icon_bg = QFrame(self)
        self.icon_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_bg.setGeometry((self.TILE_WIDTH - 84) // 2, 7, 84, 84)
        self.icon_bg.setStyleSheet(f"""
            QFrame {{
                background-color: {accent_color};
                border-radius: 20px;
            }}
        """)
        
        # Shadow effect
        self._shadow = QGraphicsDropShadowEffect(self.icon_bg)
        self._shadow.setBlurRadius(20)
        self._shadow.setColor(QColor(0, 0, 0, 80))
        self._shadow.setOffset(0, 6)
        self.icon_bg.setGraphicsEffect(self._shadow)
        
        # The Emoji icon inside
        self.icon_lbl = QLabel(icon_text, self.icon_bg)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setGeometry(0, 0, 84, 84)
        self.icon_lbl.setStyleSheet("background: transparent; color: white; font-size: 39px;")
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Layout inside icon_bg keeps emoji centered if icon_bg resizes
        bg_layout = QVBoxLayout(self.icon_bg)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.addWidget(self.icon_lbl)
        
        # The text label underneath
        self.title_lbl = QLabel(title, self)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_lbl.setObjectName("AppCardTitle")
        self.title_lbl.setGeometry(0, 95, self.TILE_WIDTH, 35)
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.title_lbl.setStyleSheet(f"""
            QLabel {{
                
                font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};
                font-size: {Typography.BODY_LG}pt;
                background: transparent;
            }}
        """)
        self.title_lbl.setWordWrap(True)

        # What the module is for, readable without hovering (the tooltip keeps the method and the description).
        self.task_lbl = QLabel(task, self)
        self.task_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.task_lbl.setObjectName("AppCardTask")
        self.task_lbl.setGeometry(6, 132, self.TILE_WIDTH - 12, 48)
        self.task_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.task_lbl.setWordWrap(True)
        self.task_lbl.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_SUB}; font-size: {Typography.CAPTION}pt; background: transparent; }}"
        )

        self.content_container = self  # For the fade-in stagger

        self.anim = QPropertyAnimation(self.icon_bg, b"geometry")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
    def enterEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.icon_bg.geometry())
        self.anim.setEndValue(QRect((self.TILE_WIDTH - 98) // 2, 0, 98, 98)) # Zoom in
        self.anim.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.icon_bg.geometry())
        self.anim.setEndValue(QRect((self.TILE_WIDTH - 84) // 2, 7, 84, 84)) # Zoom out
        self.anim.start()
        super().leaveEvent(event)

class GroupedApplicationCard(ApplicationCard):
    """Fallback for grouped apps, rendered identically to ApplicationCard for now."""
    def __init__(
        self,
        title: str,
        icon_text: str,
        accent_color: str,
        sub_apps: list[dict[str, str]],
        badge_text: str | None = None,
        parent=None,
    ) -> None:
        # Fallback to the first sub-app's script or just an empty one
        default_script = sub_apps[0]["script"] if sub_apps else ""
        super().__init__(title, "Group", "Multiple Apps", default_script, icon_text, accent_color, badge_text, parent)
        self.launch_callback = None
        self.sub_apps = sub_apps
        
    def _on_launch(self, script) -> None:
        if self.launch_callback:
            self.launch_callback(script)

    # No mouse handler of its own: the base class emits `activated` on a
    # left release, and `script_name` already IS the first sub-app's script
    # (see __init__), so the group launches the same module either way.
