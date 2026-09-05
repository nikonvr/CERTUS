# =============================================================================
# CERTUS THEME
# Extracted from certus.ui.certus_ui.py to solve 8 circular imports
# =============================================================================

from enum import Enum
import sys
from typing import Any, Dict

from certus.ui.certus_qt_widgets import QColor, QGraphicsDropShadowEffect, QIcon
from PyQt6.QtGui import QPalette, QBrush, QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton

class CertusTheme:
    """

    Centralized theme configuration for CERTUS (Style 2026/Opus 4.5).

    """

    DARK_MODE = False

    # Fonts

    FONT_FAMILY = "'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif"

    FONT_SIZE_BASE = 10

    # Colors (Light Mode Default)

    BACKGROUND = "#eef2f7"

    SURFACE = "#ffffff"
    BASE_ELEVATED = SURFACE  # Backward compatibility alias used by dashboard cards

    SURFACE_HOVER = "#f8fafc"

    BORDER = "#d7dfe8"

    TEXT_MAIN = "#0f172a"
    TEXT = TEXT_MAIN  # Backward compatibility alias

    TEXT_SUB = "#475569"

    TEXT_DISABLED = "#94a3b8"

    PRIMARY = "#0f62fe"
    PRIMARY_TEXT = "#ffffff"
    PRIMARY_HOVER = "#0353e9"
    #: Label ON the solid DANGER fill. NOT DANGER_TEXT, which is the text of a
    #: light DANGER_BG badge (#b91c1c on #fee2e2) and would be illegible here.
    #: Measured 2026-09-04: white on the dark-mode DANGER #f87171 is 2.77:1,
    #: below AA 4.5:1; #0f172a reaches 6.45:1.
    DANGER_LABEL = "#ffffff"
    DANGER_HOVER = "#b02a37"

    SECONDARY = "#334155"

    SUCCESS = "#15803d"

    WARNING = "#b45309"

    DANGER = "#dc2626"

    INFO = "#0369a1"

    ACCENT = PRIMARY  # Alias for backward compatibility

    ERROR = DANGER  # Alias for backward compatibility

    # Extended Palette (Backgrounds/Texts for tables)

    SUCCESS_BG = "#dcfce7"

    SUCCESS_TEXT = "#166534"

    WARNING_BG = "#fef3c7"

    WARNING_TEXT = "#92400e"

    DANGER_BG = "#fee2e2"

    DANGER_TEXT = "#b91c1c"

    INFO_BG = "#dbeafe"

    INFO_TEXT = "#1d4ed8"

    @staticmethod
    def get_status_bar_stylesheet() -> str:
        """Returns the standardized stylesheet for QStatusBar across all modules."""

        return f"""

            QStatusBar {{

                background-color: {CertusTheme.SURFACE};

                border-top: 1px solid {CertusTheme.BORDER};

                color: {CertusTheme.TEXT_MAIN};

            }}

            QLabel {{ font-family: {CertusTheme.FONT_FAMILY}; }}

        """

    @staticmethod
    def get_primary_button_stylesheet() -> str:
        """DEPRECATED: Use OBJ.PRIMARY_BUTTON instead. Returns U1 premium styling inline."""

        return f"""

            QPushButton {{

                background-color: {CertusTheme.PRIMARY};

                color: {CertusTheme.PRIMARY_TEXT};

                border: none;

                border-radius: 10px;

                padding: 8px 16px;

                font-weight: 600;

                min-height: 28px;

                font-family: {CertusTheme.FONT_FAMILY};

            }}

            QPushButton:hover {{ background-color: {CertusTheme.PRIMARY_HOVER}; }}

            QPushButton:pressed {{

                background-color: {CertusTheme.PRIMARY};

                padding-top: 9px;

            }}

            QPushButton:disabled {{

                background-color: {CertusTheme.BORDER};

                color: {CertusTheme.TEXT_SUB};

            }}

        """

    @staticmethod
    def get_danger_button_stylesheet() -> str:
        """DEPRECATED: Returns standard danger button style with U1 tokens."""

        return f"""

            QPushButton {{

                background-color: {CertusTheme.DANGER};

                color: {CertusTheme.DANGER_LABEL};

                border: none;

                border-radius: 10px;

                padding: 8px 16px;

                font-weight: 600;

                min-height: 28px;

                font-family: {CertusTheme.FONT_FAMILY};

            }}

            QPushButton:hover {{ background-color: {CertusTheme.DANGER_HOVER}; }}

            QPushButton:pressed {{

                background-color: {CertusTheme.DANGER};

                padding-top: 9px;

            }}

        """

    # Chart Colors

    CHART_PRIMARY = PRIMARY

    CHART_SECONDARY = SECONDARY

    CHART_DANGER = DANGER

    CHART_PURPLE = "#a855f7"

    CHART_SUCCESS = SUCCESS

    CHART_WARNING = WARNING

    CHART_INFO = INFO

    CHART_ACCENT = PRIMARY  # Added missing

    CHART_COLORS = [PRIMARY, SECONDARY, DANGER, CHART_PURPLE, WARNING, INFO]

    # Brand Colors (Module Specific) - Added missing

    BRAND_INDEX = "#3b82f6"  # Blue

    BRAND_DESIGN = "#8b5cf6"  # Violet

    BRAND_METAL = "#64748b"  # Slate

    BRAND_STRAT = "#10b981"  # Emerald

    # UI Constants - Added missing

    ELEVATED = SURFACE_HOVER

    DARK_BORDER = "#334155"

    RADIUS_XL = 16

    SPACING_XS = 2

    SPACING_SM = 4

    SPACING_MD = 8

    SPACING_LG = 16

    SPACING_XL = 24

    # Font Weights (Qt Constants) - Added missing

    FONT_WEIGHT_NORMAL = 50  # QFont.Weight.Normal

    FONT_WEIGHT_MEDIUM = 57  # QFont.Weight.Medium

    FONT_WEIGHT_SEMIBOLD = 63  # QFont.Weight.DemiBold

    # Dark Mode Colors

    DARK_BACKGROUND = "#0f172a"

    DARK_SURFACE = "#1e293b"

    DARK_CARD = "#334155"

    DARK_TEXT_MAIN = "#e2e8f0"

    DARK_TEXT_SUB = "#94a3b8"

    # Radii

    RADIUS_SM = 4

    RADIUS_MD = 6

    RADIUS_LG = 12

    @classmethod
    def get_progress_bar_style(cls) -> str:
        """Centralized Pro 2026 style for QProgressBar with smooth transitions."""

        return f"""

        QProgressBar {{

            border: 1px solid {cls.BORDER};

            border-radius: 10px;

            background-color: {cls.ELEVATED};

            text-align: center;

            color: {cls.TEXT_MAIN};

            font-size: 11px;

            font-weight: 600;

            min-height: 18px;

        }}

        QProgressBar::chunk {{

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {cls.PRIMARY}, stop:1 {cls.SECONDARY});

            border-radius: 9px;

        }}

        """

    @classmethod
    def get_font(cls, size: int = None, weight: int = FONT_WEIGHT_NORMAL) -> QFont:
        """Returns a standardized QFont using the theme's font family."""

        family = cls.FONT_FAMILY.split(",")[0].strip("'")

        font = QFont(family, size if size is not None else cls.FONT_SIZE_BASE)

        # Handle QFont.Weight enum vs int for backward/forward compatibility

        if isinstance(weight, int):
            # Map standard ints to QFont.Weight if needed by PyQt6

            # In PyQt6 QFont.Weight is an enum: Normal=50, Medium=57, DemiBold=63, Bold=75

            if weight == 50:
                fw = QFont.Weight.Normal

            elif weight == 57:
                fw = QFont.Weight.Medium

            elif weight == 63:
                fw = QFont.Weight.DemiBold

            elif weight >= 75:
                fw = QFont.Weight.Bold

            else:
                fw = QFont.Weight(weight)

        else:
            fw = weight

        font.setWeight(fw)

        return font

    @classmethod
    def configure(cls, mode: str = "auto") -> None:
        """Configures theme based on mode ('light', 'dark', 'auto')"""

        if mode == "auto":
            # Simple heuristic or default to light
            mode = "light"

        if mode == "dark":
            cls.DARK_MODE = True
            cls.BACKGROUND = "#0f172a"
            cls.SURFACE = "#111827"
            cls.SURFACE_HOVER = "#1f2937"
            cls.BORDER = "#2d3748"
            cls.TEXT_MAIN = "#e2e8f0"
            cls.TEXT_SUB = "#94a3b8"
            cls.TEXT_DISABLED = "#4a5568"
            cls.PRIMARY = "#60a5fa"
            cls.PRIMARY_TEXT = "#0f172a"
            cls.PRIMARY_HOVER = "#93c5fd"
            cls.SECONDARY = "#94a3b8"
            cls.SUCCESS = "#34d399"
            cls.WARNING = "#fbbf24"
            cls.DANGER = "#f87171"
            cls.DANGER_LABEL = "#0f172a"
            cls.DANGER_HOVER = "#fca5a5"
            cls.INFO = "#60a5fa"
        else:
            cls.DARK_MODE = False
            cls.BACKGROUND = "#eef2f7"
            cls.SURFACE = "#ffffff"
            cls.SURFACE_HOVER = "#f8fafc"
            cls.BORDER = "#d7dfe8"
            cls.TEXT_MAIN = "#0f172a"
            cls.TEXT_SUB = "#475569"
            cls.TEXT_DISABLED = "#94a3b8"
            cls.PRIMARY = "#0f62fe"
            cls.PRIMARY_TEXT = "#ffffff"
            cls.PRIMARY_HOVER = "#0353e9"
            cls.SECONDARY = "#334155"
            cls.SUCCESS = "#15803d"
            cls.WARNING = "#b45309"
            cls.DANGER = "#dc2626"
            cls.DANGER_LABEL = "#ffffff"
            cls.DANGER_HOVER = "#b02a37"
            cls.INFO = "#0369a1"

        # Synchronize backward compatibility aliases and derivatives
        cls.BASE_ELEVATED = cls.SURFACE
        cls.ACCENT = cls.PRIMARY
        cls.ERROR = cls.DANGER
        cls.ELEVATED = cls.SURFACE_HOVER

        cls.CHART_PRIMARY = cls.PRIMARY
        cls.CHART_SECONDARY = cls.SECONDARY
        cls.CHART_DANGER = cls.DANGER
        cls.CHART_SUCCESS = cls.SUCCESS
        cls.CHART_WARNING = cls.WARNING
        cls.CHART_INFO = cls.INFO
        cls.CHART_ACCENT = cls.PRIMARY
        cls.CHART_COLORS = [cls.PRIMARY, cls.SECONDARY, cls.DANGER, cls.CHART_PURPLE, cls.WARNING, cls.INFO]

    @classmethod
    def load_inter_font(cls) -> str:
        """
        Attempts to load Inter font. First checks if already registered.
        If not, attempts to load from cached font files or downloads them dynamically.
        """
        from PyQt6.QtGui import QFontDatabase
        families = QFontDatabase.families()
        if "Inter" in families:
            return "Inter"

        import os
        import urllib.request
        from pathlib import Path

        # Store in user's AppData/Temp dir
        try:
            cache_dir = Path(os.environ.get("APPDATA", "")) / "certus_fonts"
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            import tempfile
            cache_dir = Path(tempfile.gettempdir()) / "certus_fonts"
            cache_dir.mkdir(parents=True, exist_ok=True)

        regular_path = cache_dir / "Inter-Regular.ttf"
        bold_path = cache_dir / "Inter-Bold.ttf"

        urls = {
            regular_path: "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.ttf",
            bold_path: "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Bold.ttf"
        }

        font_loaded = False
        for path, url in urls.items():
            if not path.exists():
                try:
                    # Low timeout to prevent blocking app startup
                    with urllib.request.urlopen(url, timeout=2) as response:
                        path.write_bytes(response.read())
                except Exception:
                    pass

            if path.exists():
                try:
                    font_id = QFontDatabase.addApplicationFont(str(path))
                    if font_id != -1:
                        font_loaded = True
                except Exception:
                    pass

        if font_loaded:
            return "Inter"
        return "Segoe UI"

    @classmethod
    def apply_to_app(cls, app: QApplication, dark_mode: bool = False) -> None:
        from certus.ui.certus_ui import update_global_plot_config
        from certus.core.certus_core import load_font_config
        """Applies theme to QApplication"""

        # Synchronize active theme configuration
        cls.configure("dark" if dark_mode else "light")

        # Load font preference
        font_choice = load_font_config()
        
        # Ensure Inter is available as a reliable fallback or if explicitly chosen
        cls.load_inter_font()
        
        if font_choice == "Gemini":
            base_font = "Google Sans"
        elif font_choice == "iOS (San Francisco)":
            base_font = ".AppleSystemUIFont"
        elif font_choice == "Roboto":
            base_font = "Roboto"
        elif font_choice == "Open Sans":
            base_font = "Open Sans"
        elif font_choice == "Inter":
            base_font = "Inter"
        else:
            base_font = "Segoe UI"

        cls.FONT_FAMILY = f"'{base_font}', 'Inter', 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif"

        app.setStyle("Fusion")
        app.setFont(QFont(base_font, cls.FONT_SIZE_BASE))

        p = QPalette()
        if dark_mode:
            p.setColor(QPalette.ColorRole.Window, QColor(cls.DARK_BACKGROUND))
            p.setColor(QPalette.ColorRole.WindowText, QColor(cls.DARK_TEXT_MAIN))
            p.setColor(QPalette.ColorRole.Base, QColor(cls.DARK_SURFACE))
            p.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.DARK_CARD))
            p.setColor(QPalette.ColorRole.Button, QColor(cls.DARK_SURFACE))
            p.setColor(QPalette.ColorRole.ButtonText, QColor(cls.DARK_TEXT_MAIN))
            p.setColor(QPalette.ColorRole.Highlight, QColor(cls.PRIMARY))
            p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            p.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.WindowText,
                QColor(cls.TEXT_SUB),
            )
        else:
            p.setColor(QPalette.ColorRole.Window, QColor(cls.BACKGROUND))
            p.setColor(QPalette.ColorRole.WindowText, QColor(cls.TEXT_MAIN))
            p.setColor(QPalette.ColorRole.Base, QColor(cls.SURFACE))
            p.setColor(QPalette.ColorRole.AlternateBase, QColor("#e2e8f0"))
            p.setColor(QPalette.ColorRole.Button, QColor(cls.SURFACE))
            p.setColor(QPalette.ColorRole.ButtonText, QColor(cls.TEXT_MAIN))
            p.setColor(QPalette.ColorRole.Highlight, QColor(cls.PRIMARY))
            p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

        app.setPalette(p)

        # Audit theme palette accessibility against surface background
        try:
            from certus.ui.certus_a11y import audit_palette
            import logging
            logger = logging.getLogger("certus_theme")
            # Only audit foreground/accent colors against surface (not background-vs-surface,
            # which is a background-on-background pair and WCAG AA 4.5:1 does not apply).
            _BACKGROUND_ONLY_KEYS = {"background", "surface"}
            palette_dict = {
                "surface": cls.SURFACE,
                "primary": cls.PRIMARY,
                "secondary": cls.SECONDARY,
                "success": cls.SUCCESS,
                "warning": cls.WARNING,
                "danger": cls.DANGER,
                "info": cls.INFO,
            }
            report = audit_palette(palette_dict, background_key="surface")
            for key, val in report.items():
                if key == "_summary":
                    continue
                if key in _BACKGROUND_ONLY_KEYS:
                    continue
                if not val.get("passes_aa", True):
                    logger.warning(
                        f"Accessibility Contrast Warning: Theme color '{key}' ({palette_dict[key]}) vs 'surface' ({cls.SURFACE}) "
                        f"has contrast ratio {val.get('ratio')}:1 (min WCAG AA requirement is 4.5:1)"
                    )
        except Exception:
            pass

        # Apply theme stylesheet to app (if supported) instead of relying on QApplication.instance()
        # This handles testing with mocks better
        if hasattr(app, "setStyleSheet"):
            app.setStyleSheet(cls.get_standard_stylesheet())

        # If running globally, update other widgets if needed but prioritize robustness
        instance = QApplication.instance()
        if instance and instance != app:
            cls.apply_to_app(instance, dark_mode=dark_mode)

        update_global_plot_config(dark_mode)

    @classmethod
    def get_log_stylesheet(cls) -> Any:
        """Returns the standardized stylesheet for log windows."""

        return (
            f"QTextEdit {{ border: none; border-top: 1px solid {cls.BORDER}; "
            f"font-family: 'Consolas', monospace; font-size: 10pt; "
            f"color: {cls.TEXT_MAIN}; background-color: {cls.SURFACE}; }}"
        )

    @classmethod
    def get_button_style(cls, variant: str = "primary") -> str:

        colors = {
            "primary": (cls.PRIMARY, cls.PRIMARY_TEXT),
            "secondary": (cls.SECONDARY, "#ffffff"),
            "info": (cls.INFO, "#000000"),
            "success": (cls.SUCCESS, "#ffffff"),
            "warning": (cls.WARNING, "#000000"),
            "danger": (cls.DANGER, "#ffffff"),
        }

        if variant in colors:
            bg, fg = colors[variant]

        else:
            # Assume custom color if not a known variant

            bg, fg = variant, "#ffffff"

        return f"""

            QPushButton {{

                background-color: {bg}; color: {fg}; border: none; border-radius: 10px;

                padding: 7px 14px; font-weight: 700; font-family: {cls.FONT_FAMILY};

                min-height: 28px;

            }}

            QPushButton:hover {{ background-color: {bg}e6; }}

            QPushButton:pressed {{ background-color: {bg}cc; }}

            QPushButton:disabled {{ background-color: {cls.BORDER}; color: {cls.TEXT_DISABLED}; }}

        """

    @staticmethod
    def get_shadow(parent=None) -> "QGraphicsDropShadowEffect":
        """Returns a standard drop shadow effect"""

        shadow = QGraphicsDropShadowEffect(parent)

        shadow.setBlurRadius(16)

        shadow.setOffset(0, 4)

        shadow.setColor(QColor(0, 0, 0, 30))

        return shadow

    @classmethod
    def get_hint_text_style(cls) -> str:
        """Returns standard styling for small hint texts and labels."""
        return f"color: {cls.TEXT_SUB}; font-size: 11px;"

    @staticmethod
    def hex_to_rgba_tuple(hex_color: str, alpha: float = 1.0) -> tuple:
        """Converts #RRGGBB to (r, g, b, a) with alpha as 0-255 int."""

        c = QColor(hex_color)

        alpha_int = int(alpha) if alpha > 1 else int(alpha * 255)

        return (c.red(), c.green(), c.blue(), alpha_int)

    @staticmethod
    def get_standard_stylesheet() -> str:
        return f"""

            /* ── Base ────────────────────────────────────────────────────────── */
            QWidget {{
                font-family: {CertusTheme.FONT_FAMILY};
                font-size: {CertusTheme.FONT_SIZE_BASE}pt;
                color: {CertusTheme.TEXT_MAIN};
            }}
            QMainWindow, QDialog, QDockWidget, QScrollArea {{
                background: {CertusTheme.BACKGROUND};
            }}

            /* ── Inputs ──────────────────────────────────────────────────────── */
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                padding: 5px 10px;
                min-height: 28px;
                border-radius: 10px;
                color: {CertusTheme.TEXT_MAIN};
                selection-background-color: {CertusTheme.PRIMARY};
                selection-color: white;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {CertusTheme.PRIMARY};
                background: {CertusTheme.SURFACE};
                outline: none;
            }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QComboBox::down-arrow {{ image: none; }}

            /* ── GroupBox (flat) ─────────────────────────────────────────────── */
            QGroupBox {{
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 14px;
                margin-top: 1.1em;
                background: {CertusTheme.SURFACE};
                padding: 8px 10px 10px 10px;
            }}
            QGroupBox::title {{
                color: {CertusTheme.PRIMARY};
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                font-weight: 700;
                font-size: 10pt;
            }}

            /* ── Tables ──────────────────────────────────────────────────────── */
            QTableWidget {{
                gridline-color: {CertusTheme.BORDER};
                background: {CertusTheme.SURFACE};
                alternate-background-color: {CertusTheme.SURFACE_HOVER};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 12px;
                selection-background-color: {CertusTheme.INFO_BG};
            }}
            QHeaderView::section {{
                background: {CertusTheme.SURFACE_HOVER};
                border: none;
                padding: 8px 10px;
                border-right: 1px solid {CertusTheme.BORDER};
                border-bottom: 1px solid {CertusTheme.BORDER};
                color: {CertusTheme.TEXT_SUB};
                font-weight: 700;
                font-size: 9pt;
            }}
            QTableCornerButton::section {{
                background: {CertusTheme.SURFACE_HOVER};
                border: 1px solid {CertusTheme.BORDER};
            }}

            /* ── Tabs (underline style) ───────────────────────────────────────── */
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {CertusTheme.BORDER};
                background: {CertusTheme.SURFACE};
            }}
            QTabWidget::tab-bar {{ alignment: left; }}
            QTabBar {{
                background: {CertusTheme.BACKGROUND};
                border-bottom: 1px solid {CertusTheme.BORDER};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {CertusTheme.TEXT_SUB};
                padding: 9px 18px;
                font-weight: 600;
                font-size: 9pt;
                border: none;
                border-bottom: 2px solid transparent;
                margin-bottom: -1px;
            }}
            QTabBar::tab:selected {{
                color: {CertusTheme.PRIMARY};
                font-weight: 700;
                border-bottom: 2px solid {CertusTheme.PRIMARY};
                background: {CertusTheme.SURFACE};
            }}
            QTabBar::tab:hover:!selected {{
                color: {CertusTheme.TEXT_MAIN};
                border-bottom: 2px solid {CertusTheme.BORDER};
            }}

            /* ── Scrollbars (thin, modern) ────────────────────────────────────── */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {CertusTheme.BORDER};
                min-height: 24px;
                border-radius: 4px;
                margin: 1px 1px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {CertusTheme.TEXT_SUB}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {CertusTheme.BORDER};
                min-width: 24px;
                border-radius: 4px;
                margin: 1px 1px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {CertusTheme.TEXT_SUB}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

            /* ── Splitter ─────────────────────────────────────────────────────── */
            QSplitter::handle {{
                background: {CertusTheme.BORDER};
            }}
            QSplitter::handle:horizontal {{ width: 1px; }}
            QSplitter::handle:vertical {{ height: 1px; }}

            /* ── ProgressBar ──────────────────────────────────────────────────── */
            QProgressBar {{
                text-align: center;
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 8px;
                background: {CertusTheme.SURFACE_HOVER};
                color: {CertusTheme.TEXT_MAIN};
                font-size: 9pt;
                min-height: 14px;
            }}
            QProgressBar::chunk {{
                background: {CertusTheme.PRIMARY};
                border-radius: 7px;
            }}

            /* ── Checkboxes / Radio ───────────────────────────────────────────── */
            QCheckBox {{ color: {CertusTheme.TEXT_MAIN}; spacing: 6px; }}
            QRadioButton {{ color: {CertusTheme.TEXT_MAIN}; spacing: 6px; }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 3px;
                background: {CertusTheme.SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background: {CertusTheme.PRIMARY};
                border-color: {CertusTheme.PRIMARY};
            }}

            /* ── Menu ─────────────────────────────────────────────────────────── */
            QMenu {{
                background-color: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 6px;
                padding: 4px 0;
            }}
            QMenu::item {{ padding: 5px 24px; color: {CertusTheme.TEXT_MAIN}; }}
            QMenu::item:selected {{ background-color: {CertusTheme.PRIMARY}; color: white; border-radius: 4px; }}
            QMenu::separator {{ height: 1px; background: {CertusTheme.BORDER}; margin: 4px 8px; }}

            /* ── ToolTip ──────────────────────────────────────────────────────── */
            QToolTip {{
                background: {CertusTheme.SURFACE};
                color: {CertusTheme.TEXT_MAIN};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 9pt;
            }}

            /* ── Scroll area ──────────────────────────────────────────────────── */
            QScrollArea {{ border: none; background: transparent; }}

            /* ── Typography object-names ──────────────────────────────────────── */
            QLabel#h1 {{ font-size: 14pt; font-weight: 700; color: {CertusTheme.TEXT_MAIN}; }}
            QLabel#h2 {{ font-size: 11pt; font-weight: 700; color: {CertusTheme.TEXT_MAIN}; }}
            QLabel#caption {{ font-size: 9pt; color: {CertusTheme.TEXT_SUB}; }}

        """

def get_standard_stylesheet() -> str:
    return CertusTheme.get_standard_stylesheet()

