# =============================================================================
# CERTUS THEME CONFIGURATION
# Extracted from certus_theme.py to decouple Core and UI
# =============================================================================

from dataclasses import dataclass

@dataclass(frozen=True)
class ThemeColors:
    DARK_MODE: bool = False
    FONT_FAMILY: str = "'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif"
    FONT_SIZE_BASE: int = 10
    
    BACKGROUND: str = "#eef2f7"
    SURFACE: str = "#ffffff"
    BASE_ELEVATED: str = "#ffffff"
    SURFACE_HOVER: str = "#f8fafc"
    BORDER: str = "#d7dfe8"
    TEXT_MAIN: str = "#0f172a"
    TEXT: str = "#0f172a"
    TEXT_SUB: str = "#475569"
    TEXT_DISABLED: str = "#94a3b8"
    PRIMARY: str = "#0f62fe"
    SECONDARY: str = "#334155"
