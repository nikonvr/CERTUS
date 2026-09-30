from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
import logging

_ZOOM_MIN: float = 0.5
_ZOOM_MAX: float = 2.5
_ZOOM_STEP: float = 0.1

def _clamp_zoom_factor(value: float) -> float:
    return max(_ZOOM_MIN, min(_ZOOM_MAX, float(value)))


def apply_app_zoom(owner, factor: float, *, label_attr: str, stylesheet_fn=None, toast_fn=None, base_font_size: int = 10) -> float:
    factor = _clamp_zoom_factor(factor)
    owner._zoom_factor = factor
    app = QApplication.instance()
    if app is not None:
        app.setFont(QFont("Segoe UI", max(9, round(base_font_size * factor))))
    label = getattr(owner, label_attr, None)
    if label is not None and hasattr(label, "setText"):
        label.setText(f"Zoom {int(round(factor * 100))}%")
    if stylesheet_fn is not None:
        try:
            owner.setStyleSheet(stylesheet_fn())
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
    if toast_fn is not None:
        try:
            toast_fn(owner, f"Zoom {int(round(factor * 100))}%", "info", duration_ms=1200)
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
    return factor


def _format_progress_duration(seconds: float) -> str:
    """Standardized duration formatter for UI progress widgets."""
    if seconds is None or seconds < 0:
        return "0 s"
    total = int(round(seconds))
    if total < 60:
        return f"{total} s"
    m, s = divmod(total, 60)
    if m < 60:
        return f"{m} min {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"
