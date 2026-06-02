from __future__ import annotations

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication


def apply_zoom_factor(
    owner,
    factor: float,
    *,
    label_attr: str,
    stylesheet_getter=None,
    toast_fn=None,
    base_font_size: int = 10,
    min_factor: float = 0.85,
    max_factor: float = 1.30,
) -> float:
    """Apply a bounded zoom factor to a Qt window and update its label."""
    factor = max(min_factor, min(max_factor, float(factor)))
    setattr(owner, "_zoom_factor", factor)
    app = QApplication.instance()
    if app is not None:
        app.setFont(QFont("Segoe UI", max(9, round(base_font_size * factor))))
    label = getattr(owner, label_attr, None)
    if label is not None and hasattr(label, "setText"):
        label.setText(f"Zoom {int(round(factor * 100))}%")
    if stylesheet_getter is not None:
        try:
            owner.setStyleSheet(stylesheet_getter())
        except Exception:
            pass
    if toast_fn is not None:
        try:
            toast_fn(owner, f"Zoom {int(round(factor * 100))}%", "info", duration_ms=1200)
        except Exception:
            pass
    return factor
