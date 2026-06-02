from __future__ import annotations

try:
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication


def apply_app_zoom(owner, factor: float, *, label_attr: str, stylesheet_fn=None, toast_fn=None, base_font_size: int = 10) -> float:
    factor = max(0.85, min(1.30, float(factor)))
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
    return min(getattr(owner, "_zoom_factor", 1.0) + 0.05, 1.30)


def zoom_out_factor(owner) -> float:
    return max(getattr(owner, "_zoom_factor", 1.0) - 0.05, 0.85)


def standard_config_file_filter() -> str:
    return "JSON Files (*.json);;All Files (*)"
