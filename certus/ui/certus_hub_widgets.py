from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from certus.ui.certus_ui import CertusTheme
from PyQt6.QtGui import QColor

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


class BaseApplicationCard(QFrame):
    """Base logic for iOS-style hover animations in CERTUS Hub."""
    def __init__(self, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self.accent_color = accent_color
        self.setCursor(Qt.CursorShape.PointingHandCursor)

class ApplicationCard(BaseApplicationCard):
    """iPhone-style application icon card for the HUB 3x3 matrix."""
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
    ) -> None:
        super().__init__(accent_color, parent)
        self.script_name = script_name
        self.setFixedSize(112, 130)
        self.setObjectName("AppCard")
        
        self.setToolTip(f"<b>{title}</b><br>{subtitle}<br><br>{description}")
        
        self.setStyleSheet("#AppCard { background: transparent; }")
        
        # Inner Squircle (the iPhone icon itself)
        self.icon_bg = QFrame(self)
        self.icon_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_bg.setGeometry(14, 7, 84, 84)
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
        self.title_lbl.setGeometry(0, 95, 112, 35)
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.title_lbl.setStyleSheet(f"""
            QLabel {{
                
                font-weight: {CertusTheme.FONT_WEIGHT_SEMIBOLD};
                font-size: 11px;
                background: transparent;
            }}
        """)
        self.title_lbl.setWordWrap(True)
        
        self.content_container = self  # For the fade-in stagger

        self.anim = QPropertyAnimation(self.icon_bg, b"geometry")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
    def enterEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.icon_bg.geometry())
        self.anim.setEndValue(QRect(7, 0, 98, 98)) # Zoom in
        self.anim.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.icon_bg.geometry())
        self.anim.setEndValue(QRect(14, 7, 84, 84)) # Zoom out
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

    def mousePressEvent(self, event):
        # Just launch the first sub-app to keep it simple as iPhone icons
        if self.sub_apps:
            self._on_launch(self.sub_apps[0]["script"])
        super().mousePressEvent(event)
