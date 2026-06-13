"""Centralized UI design tokens (#44 incremental)."""

from __future__ import annotations


TOKENS = {
    "slider_corridor_groove_bg": "#d7deea",
    "slider_corridor_subpage_bg": "#7a3cff",
    "slider_corridor_addpage_bg": "#eef2f8",
    "slider_corridor_handle_bg": "#ff4d4f",
}


def slider_corridor_half_stylesheet() -> str:
    """Stylesheet for the RMSE corridor manual half-width slider."""
    return (
        "QSlider::groove:horizontal { height: 8px; background: "
        + TOKENS["slider_corridor_groove_bg"]
        + "; border-radius: 4px; }"
        "QSlider::sub-page:horizontal { background: " + TOKENS["slider_corridor_subpage_bg"] + "; border-radius: 4px; }"
        "QSlider::add-page:horizontal { background: " + TOKENS["slider_corridor_addpage_bg"] + "; border-radius: 4px; }"
        "QSlider::handle:horizontal { width: 14px; margin: -4px 0; border-radius: 7px; background: "
        + TOKENS["slider_corridor_handle_bg"]
        + "; }"
    )
