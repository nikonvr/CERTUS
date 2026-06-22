from __future__ import annotations

try:
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication


_ZOOM_MIN = 0.85
_ZOOM_MAX = 1.30
_ZOOM_STEP = 0.05


def _clamp_zoom_factor(value: float) -> float:
    return max(_ZOOM_MIN, min(_ZOOM_MAX, float(value)))


def apply_app_zoom(owner, factor: float, *, label_attr: str, stylesheet_fn=None, toast_fn=None, base_font_size: int = 10) -> float:
    factor = _clamp_zoom_factor(factor)
    setattr(owner, "_zoom_factor", factor)
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
            pass
    if toast_fn is not None:
        try:
            toast_fn(owner, f"Zoom {int(round(factor * 100))}%", "info", duration_ms=1200)
        except Exception:
            pass
    return factor


def zoom_in_factor(owner) -> float:
    return _clamp_zoom_factor(getattr(owner, "_zoom_factor", 1.0) + _ZOOM_STEP)


def zoom_out_factor(owner) -> float:
    return _clamp_zoom_factor(getattr(owner, "_zoom_factor", 1.0) - _ZOOM_STEP)


def standard_config_file_filter() -> str:
    return "Fichier JSON (*.json);;Fichier Excel (*.xlsx)"


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
