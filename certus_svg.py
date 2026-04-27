"""SVG Export Utilities for CERTUS Suite
Provides SVG export functionality for plots and diagrams."""

from typing import List, Optional, Union

import numpy as np

try:
    import svgwrite

    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False

# SVG color palette for CERTUS
CERTUS_COLORS = {
    "background": "#f8fafc",
    "surface": "#ffffff",
    "text": "#0f172a",
    "primary": "#4f46e5",
    "secondary": "#64748b",
    "success": "#22c55e",
    "warning": "#eab308",
    "danger": "#ef4444",
    "info": "#3b82f6",
    "grid": "#e5e7eb",
    "border": "#d1d5db",
}


def export_plot_to_svg(
    wavelengths: Union[np.ndarray, List[float]],
    values: Union[np.ndarray, List[float]],
    title: str = "Spectral Plot",
    xlabel: str = "Wavelength (nm)",
    ylabel: str = "Value",
    filename: str = "plot.svg",
    width: int = 800,
    height: int = 600,
    line_color: str = CERTUS_COLORS["primary"],
    grid_color: str = CERTUS_COLORS["grid"],
    background_color: str = CERTUS_COLORS["background"],
) -> str:
    """Export spectral data to SVG format.

    Args:
        wavelengths: Array of wavelengths
        values: Array of values (R, T, etc.)
        title: Plot title
        xlabel: X-axis label
        ylabel: Y-axis label
        filename: Output filename
        width: SVG width
        height: SVG height
        line_color: Line color
        grid_color: Grid color
        background_color: Background color

    Returns:
        SVG file path

    Reasons:
        ImportError: If SVG libraries are not available"""
    if not SVG_AVAILABLE:
        raise ImportError("SVG libraries not available. Install with: pip install svgwrite svglib")

    # Convert to numpy arrays if needed
    if not isinstance(wavelengths, np.ndarray):
        wavelengths = np.array(wavelengths)
    if not isinstance(values, np.ndarray):
        values = np.array(values)

    # Create SVG drawing
    dwg = svgwrite.Drawing(filename, size=(width, height))

    # Background
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=background_color))

    # Grid
    if grid_color:
        # Vertical grid lines (step 50px, x = i)
        for i in range(0, width, 50):
            x = i
            dwg.add(
                dwg.line(
                    start=(x, 0),
                    end=(x, height),
                    stroke=grid_color,
                    stroke_width=0.5,
                    opacity=0.3,
                )
            )
        # Horizontal grid lines (step 50px, y = i)
        for i in range(0, height, 50):
            y = i
            dwg.add(
                dwg.line(
                    start=(0, y),
                    end=(width, y),
                    stroke=grid_color,
                    stroke_width=0.5,
                    opacity=0.3,
                )
            )

    # Plot area
    margin = 50
    plot_width = width - 2 * margin
    plot_height = height - 2 * margin

    # Convert data to SVG coordinates
    x_min, x_max = float(np.min(wavelengths)), float(np.max(wavelengths))
    y_min, y_max = float(np.min(values)), float(np.max(values))

    # Create path for the line
    path_data = []
    for i, (x, y) in enumerate(zip(wavelengths, values)):
        svg_x = margin + (x - x_min) / (x_max - x_min) * plot_width
        svg_y = height - margin - (y - y_min) / (y_max - y_min) * plot_height

        if i == 0:
            path_data.append(f"M {svg_x:.2f} {svg_y:.2f}")
        else:
            path_data.append(f"L {svg_x:.2f} {svg_y:.2f}")

    # Draw the line
    dwg.add(dwg.path(d=path_data, stroke=line_color, stroke_width=2, fill="none"))

    # Axes
    dwg.add(
        dwg.line(
            start=(margin, height - margin),
            end=(width - margin, height - margin),
            stroke=CERTUS_COLORS["text"],
            stroke_width=1,
        )
    )
    dwg.add(
        dwg.line(
            start=(margin, margin),
            end=(margin, height - margin),
            stroke=CERTUS_COLORS["text"],
            stroke_width=1,
        )
    )

    # Title
    title_y = 30
    dwg.add(
        dwg.text(
            insert=(width // 2, title_y),
            text=title,
            font_size=16,
            fill=CERTUS_COLORS["text"],
            font_family="Arial, sans-serif",
            text_anchor="middle",
        )
    )

    # Axis labels
    dwg.add(
        dwg.text(
            insert=(width // 2, height - 20),
            text=xlabel,
            font_size=12,
            fill=CERTUS_COLORS["text"],
            font_family="Arial, sans-serif",
            text_anchor="middle",
        )
    )

    # Y-axis label
    dwg.add(
        dwg.text(
            insert=(20, height // 2),
            text=ylabel,
            font_size=12,
            fill=CERTUS_COLORS["text"],
            font_family="Arial, sans-serif",
            text_anchor="middle",
            transform=f"rotate(-90, {20}, {height // 2})",
        )
    )

    # Save the SVG
    dwg.save()

    return filename


def export_spectrum_to_svg(
    wavelengths: Union[np.ndarray, List[float]],
    R: Union[np.ndarray, List[float]],
    T: Optional[Union[np.ndarray, List[float]]] = None,
    filename: str = "spectrum.svg",
    width: int = 800,
    height: int = 600,
    show_grid: bool = True,
) -> str:
    """Export full spectrum (R and T) to SVG.

    Args:
        wavelengths: Array of wavelengths
        A: Reflectance values
        T: Transmittance values (optional)
        filename: Output filename
        width: SVG width
        height: SVG height
        show_grid: Whether to show grid

    Returns:
        SVG file path"""
    if not SVG_AVAILABLE:
        raise ImportError("SVG libraries not available. Install with: pip install svgwrite svglib")

    if T is None:
        # Only R provided
        return export_plot_to_svg(
            wavelengths,
            R,
            "Reflectance",
            "Wavelength (nm)",
            "Reflectance",
            filename,
            width,
            height,
        )
    else:
        # Both R and T: single SVG with two curves (R and T)
        if not isinstance(wavelengths, np.ndarray):
            wavelengths = np.array(wavelengths)
        if not isinstance(R, np.ndarray):
            R = np.array(R)
        if not isinstance(T, np.ndarray):
            T = np.array(T)
        dwg = svgwrite.Drawing(filename, size=(width, height))
        dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=CERTUS_COLORS["background"]))
        margin = 50
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin
        x_min, x_max = float(np.min(wavelengths)), float(np.max(wavelengths))
        y_vals = np.concatenate([np.ravel(R), np.ravel(T)])
        y_min, y_max = float(np.min(y_vals)), float(np.max(y_vals))
        if y_max <= y_min:
            y_max = y_min + 1

        def to_svg_coords(x, y):
            sx = margin + (x - x_min) / (x_max - x_min) * plot_width if x_max > x_min else margin
            sy = height - margin - (y - y_min) / (y_max - y_min) * plot_height
            return sx, sy

        if show_grid and CERTUS_COLORS.get("grid"):
            grid_color = CERTUS_COLORS["grid"]
            for i in range(0, width, 50):
                x = i
                dwg.add(
                    dwg.line(
                        start=(x, 0), end=(x, height),
                        stroke=grid_color, stroke_width=0.5, opacity=0.3,
                    )
                )
            for i in range(0, height, 50):
                y = i
                dwg.add(
                    dwg.line(
                        start=(0, y), end=(width, y),
                        stroke=grid_color, stroke_width=0.5, opacity=0.3,
                    )
                )

        path_data_r = []
        for i, (xi, yi) in enumerate(zip(wavelengths, R)):
            sx, sy = to_svg_coords(xi, yi)
            path_data_r.append(f"{'M' if i == 0 else 'L'} {sx:.2f} {sy:.2f}")
        dwg.add(
            dwg.path(
                d=" ".join(path_data_r),
                stroke=CERTUS_COLORS["primary"],
                stroke_width=2,
                fill="none",
            )
        )
        path_data_t = []
        for i, (xi, yi) in enumerate(zip(wavelengths, T)):
            sx, sy = to_svg_coords(xi, yi)
            path_data_t.append(f"{'M' if i == 0 else 'L'} {sx:.2f} {sy:.2f}")
        dwg.add(
            dwg.path(
                d=" ".join(path_data_t),
                stroke=CERTUS_COLORS["secondary"],
                stroke_width=2,
                fill="none",
            )
        )

        # Axes
        dwg.add(
            dwg.line(
                start=(margin, height - margin),
                end=(width - margin, height - margin),
                stroke=CERTUS_COLORS["text"],
                stroke_width=1,
            )
        )
        dwg.add(
            dwg.line(
                start=(margin, margin),
                end=(margin, height - margin),
                stroke=CERTUS_COLORS["text"],
                stroke_width=1,
            )
        )
        title_y = 30
        dwg.add(
            dwg.text(
                insert=(width // 2, title_y),
                text="Spectrum (R & T)",
                font_size=16,
                fill=CERTUS_COLORS["text"],
                font_family="Arial, sans-serif",
                text_anchor="middle",
            )
        )
        dwg.add(
            dwg.text(
                insert=(width // 2, height - 20),
                text="Wavelength (nm)",
                font_size=12,
                fill=CERTUS_COLORS["text"],
                font_family="Arial, sans-serif",
                text_anchor="middle",
            )
        )
        dwg.add(
            dwg.text(
                insert=(20, height // 2),
                text="R / T",
                font_size=12,
                fill=CERTUS_COLORS["text"],
                font_family="Arial, sans-serif",
                text_anchor="middle",
                transform=f"rotate(-90, {20}, {height // 2})",
            )
        )
        # Legend
        leg_x, leg_y = width - margin - 120, margin + 20
        dwg.add(
            dwg.line(
                start=(leg_x, leg_y),
                end=(leg_x + 24, leg_y),
                stroke=CERTUS_COLORS["primary"],
                stroke_width=2,
            )
        )
        dwg.add(
            dwg.text(
                insert=(leg_x + 28, leg_y + 4),
                text="R",
                font_size=11,
                fill=CERTUS_COLORS["text"],
                font_family="Arial, sans-serif",
            )
        )
        dwg.add(
            dwg.line(
                start=(leg_x, leg_y + 22),
                end=(leg_x + 24, leg_y + 22),
                stroke=CERTUS_COLORS["secondary"],
                stroke_width=2,
            )
        )
        dwg.add(
            dwg.text(
                insert=(leg_x + 28, leg_y + 26),
                text="T",
                font_size=11,
                fill=CERTUS_COLORS["text"],
                font_family="Arial, sans-serif",
            )
        )
        dwg.save()
        return filename


def create_svg_plot(
    title: str = "CERTUS Plot",
    width: int = 800,
    height: int = 600,
    background_color: str = CERTUS_COLORS["background"],
    grid_color: str = CERTUS_COLORS["grid"],
) -> str:
    """
    Create a blank SVG plot template.

    Args:
        title: Plot title
        width: SVG width
        height: SVG height
        background_color: Background color
        grid_color: Grid color

    Returns:
        SVG file path
    """
    if not SVG_AVAILABLE:
        raise ImportError("SVG libraries not available. Install with: pip install svgwrite svglib")

    filename = f"{title.lower().replace(' ', '_')}.svg"

    dwg = svgwrite.Drawing(filename, size=(width, height))

    # Background
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=background_color))

    # Grid
    if grid_color:
        for i in range(0, width, 50):
            x = i
            dwg.add(
                dwg.line(
                    start=(x, 0),
                    end=(x, height),
                    stroke=grid_color,
                    stroke_width=0.5,
                    opacity=0.3,
                )
            )
        for i in range(0, height, 50):
            y = i
            dwg.add(
                dwg.line(
                    start=(0, y),
                    end=(width, y),
                    stroke=grid_color,
                    stroke_width=0.5,
                    opacity=0.3,
                )
            )

    # Title
    title_y = 30
    dwg.add(
        dwg.text(
            insert=(width // 2, title_y),
            text=title,
            font_size=16,
            fill=CERTUS_COLORS["text"],
            font_family="Arial, sans-serif",
            text_anchor="middle",
        )
    )

    dwg.save()
    return filename


# Check SVG availability
SVG_SUPPORT_AVAILABLE = SVG_AVAILABLE

# Export functions for easy access
__all__ = [
    "export_plot_to_svg",
    "export_spectrum_to_svg",
    "create_svg_plot",
    "SVG_SUPPORT_AVAILABLE",
    "CERTUS_COLORS",
]
