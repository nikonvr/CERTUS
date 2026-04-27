"""
Unit tests for certus_ui.py
Covers UI components, the theme system, and widgets.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

# Conditional imports depending on PyQt6 availability
try:
    from PyQt6.QtWidgets import (
        QApplication,
        QWidget,
        QPushButton,
        QLabel,
        QVBoxLayout,
        QTableWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from certus_ui import (
    CertusTheme,
    DATA_FILE_FILTER,
    DATA_FILES_FILTER_EXTENDED,
    ExcelTableWidget,
    certus_confirm_yes_no,
    certus_get_open_file_name,
    certus_get_save_file_name,
    create_styled_button,
    apply_certus_theme,
    setup_pyqtgraph_defaults,
    open_data_file_and_read,
)

# Conditional imports for components that may not be available
try:
    from certus_ui import CertusScientificPlot

    SCIENTIFIC_PLOT_AVAILABLE = True
except ImportError:
    SCIENTIFIC_PLOT_AVAILABLE = False

try:
    import pyqtgraph as pg  # noqa: F401

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False

try:
    from certus_ui import ExcelTableWidget

    EXCEL_TABLE_AVAILABLE = True
except ImportError:
    EXCEL_TABLE_AVAILABLE = False


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestDataFileFiltersAndHelper:
    """Tests for DATA_FILE_FILTER, DATA_FILES_FILTER_EXTENDED, open_data_file_and_read."""

    def test_data_file_filter_constants_exist(self):
        assert isinstance(DATA_FILE_FILTER, str)
        assert "csv" in DATA_FILE_FILTER.lower() and "xlsx" in DATA_FILE_FILTER.lower()
        assert isinstance(DATA_FILES_FILTER_EXTENDED, str)
        assert "csv" in DATA_FILES_FILTER_EXTENDED.lower()

    def test_open_data_file_and_read_returns_none_when_cancelled(self):
        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=("", "")):
            out = open_data_file_and_read()
        assert out == (None, None)

    def test_open_data_file_and_read_returns_path_and_df_when_file_selected(self):
        import pandas as pd
        fake_path = "/fake/data.csv"
        fake_df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=(fake_path, "")):
            with patch("certus_ui.read_data_file_robust", return_value=fake_df):
                path, df = open_data_file_and_read()
        assert path == fake_path
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["a", "b"]


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestCertusFileDialogHelpers:
    """certus_get_open_file_name, certus_get_save_file_name, certus_confirm_yes_no."""

    def test_open_cancel_returns_empty(self):
        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=("", "")):
            with patch("certus_ui.set_certus_last_dir") as mock_sl:
                assert certus_get_open_file_name(None, "T", "*.json") == ""
                mock_sl.assert_not_called()

    def test_open_ok_sets_last_dir(self):
        p = r"C:\tmp\cfg.json"
        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=(p, "")):
            with patch("certus_ui.set_certus_last_dir") as mock_sl:
                assert certus_get_open_file_name(None, "T", "JSON (*.json)") == p
                mock_sl.assert_called_once_with(p)

    def test_save_ok_sets_last_dir(self):
        p = r"C:\tmp\out.xlsx"
        with patch("certus_ui.QFileDialog.getSaveFileName", return_value=(p, "")):
            with patch("certus_ui.set_certus_last_dir") as mock_sl:
                assert certus_get_save_file_name(None, "T", "Excel (*.xlsx)") == p
                mock_sl.assert_called_once_with(p)

    def test_confirm_yes_no(self):
        from PyQt6.QtWidgets import QMessageBox

        with patch("certus_ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            assert certus_confirm_yes_no(None, "t", "m") is True
        with patch("certus_ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            assert certus_confirm_yes_no(None, "t", "m", default_no=True) is False


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestCertusTheme:
    """Tests for the CertusTheme class."""

    def test_theme_constants_exist(self):
        """Test that theme constants exist."""
        # Light mode colors
        assert hasattr(CertusTheme, "BACKGROUND")
        assert hasattr(CertusTheme, "SURFACE")
        assert hasattr(CertusTheme, "TEXT_MAIN")
        assert hasattr(CertusTheme, "PRIMARY")

        # Dark mode colors
        assert hasattr(CertusTheme, "DARK_BACKGROUND")
        assert hasattr(CertusTheme, "DARK_SURFACE")
        assert hasattr(CertusTheme, "DARK_TEXT_MAIN")

        # UI constants
        assert hasattr(CertusTheme, "FONT_FAMILY")
        assert hasattr(CertusTheme, "FONT_SIZE_BASE")
        assert hasattr(CertusTheme, "SPACING_SM")

    def test_theme_colors_are_strings(self):
        """Test that colors are hex strings."""
        colors = [
            CertusTheme.BACKGROUND,
            CertusTheme.SURFACE,
            CertusTheme.PRIMARY,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.DANGER,
        ]

        for color in colors:
            assert isinstance(color, str)
            assert color.startswith("#") or color.startswith("rgb")

    def test_configure_light_mode(self):
        """Test light theme configuration."""
        original_bg = CertusTheme.BACKGROUND
        original_text = CertusTheme.TEXT_MAIN
        CertusTheme.configure("light")
        assert CertusTheme.BACKGROUND is not None
        assert CertusTheme.TEXT_MAIN is not None
        CertusTheme.BACKGROUND = original_bg
        CertusTheme.TEXT_MAIN = original_text

    def test_configure_dark_mode(self):
        """Test dark theme configuration."""
        original_bg = CertusTheme.BACKGROUND
        original_text = CertusTheme.TEXT_MAIN
        CertusTheme.configure("dark")
        assert CertusTheme.BACKGROUND is not None
        assert CertusTheme.TEXT_MAIN is not None
        CertusTheme.BACKGROUND = original_bg
        CertusTheme.TEXT_MAIN = original_text

    def test_configure_auto_mode(self):
        """Test auto theme configuration (picks light or dark)."""
        original_bg = CertusTheme.BACKGROUND
        CertusTheme.configure("auto")
        assert CertusTheme.BACKGROUND is not None
        CertusTheme.BACKGROUND = original_bg

    def test_get_status_bar_stylesheet(self):
        """Test stylesheet generation for QStatusBar."""
        stylesheet = CertusTheme.get_status_bar_stylesheet()

        assert isinstance(stylesheet, str)
        assert "QStatusBar" in stylesheet
        assert "background-color" in stylesheet
        assert "border-top" in stylesheet
        assert "color" in stylesheet

    def test_get_primary_button_stylesheet(self):
        """Test stylesheet generation for primary button."""
        stylesheet = CertusTheme.get_primary_button_stylesheet()

        assert isinstance(stylesheet, str)
        assert "QPushButton" in stylesheet
        assert "background" in stylesheet
        assert "color" in stylesheet
        assert "border-radius" in stylesheet

    def test_get_danger_button_stylesheet(self):
        """Test stylesheet generation for danger button."""
        stylesheet = CertusTheme.get_danger_button_stylesheet()

        assert isinstance(stylesheet, str)
        assert "background" in stylesheet
        assert "color" in stylesheet
        assert "border-radius" in stylesheet

    @pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
    def test_apply_to_app_light_mode(self):
        """Test applying theme to application (light mode)."""
        mock_app = MagicMock()
        mock_palette = Mock()
        mock_app.palette.return_value = mock_palette

        CertusTheme.apply_to_app(mock_app, dark_mode=False)

        mock_app.setStyle.assert_called()
        mock_app.setFont.assert_called()
        mock_app.setPalette.assert_called()

    @pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
    def test_apply_to_app_dark_mode(self):
        """Test applying theme to application (dark mode)."""
        mock_app = MagicMock()
        mock_palette = Mock()
        mock_app.palette.return_value = mock_palette

        CertusTheme.apply_to_app(mock_app, dark_mode=True)

        mock_app.setStyle.assert_called()
        mock_app.setFont.assert_called()
        mock_app.setPalette.assert_called()


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestUIComponents:
    """Tests for UI components."""

    def test_create_styled_button(self, qapp):
        _ = qapp
        """Test creation of a styled button."""
        button = create_styled_button("Test Button", CertusTheme.PRIMARY)

        assert isinstance(button, QPushButton)
        assert button.text() == "Test Button"
        assert button.styleSheet() is not None

    def test_create_styled_button_with_custom_color(self, qapp):
        _ = qapp
        """Test creation of a button with a custom color."""
        custom_color = "#FF0000"
        button = create_styled_button("Custom Button", custom_color)

        assert isinstance(button, QPushButton)
        assert button.text() == "Custom Button"
        assert custom_color in button.styleSheet()

    def test_create_styled_label(self, qapp):
        _ = qapp
        """Test creation of a styled label."""
        from PyQt6.QtWidgets import QLabel

        label = QLabel("Test Label")
        label.setStyleSheet(
            f"color: {CertusTheme.TEXT_MAIN}; font-family: {CertusTheme.FONT_FAMILY};"
        )

        assert isinstance(label, QLabel)
        assert label.text() == "Test Label"
        assert label.styleSheet() is not None

    def test_create_styled_label_with_custom_color(self, qapp):
        _ = qapp
        """Test creation of a label with a custom color."""
        from PyQt6.QtWidgets import QLabel

        custom_color = "#00FF00"
        label = QLabel("Custom Label")
        label.setStyleSheet(
            f"color: {custom_color}; font-family: {CertusTheme.FONT_FAMILY};"
        )

        assert isinstance(label, QLabel)
        assert label.text() == "Custom Label"
        assert custom_color in label.styleSheet()


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestCertusScientificPlot:
    """Tests for the CertusScientificPlot class."""

    @pytest.mark.skipif(
        not SCIENTIFIC_PLOT_AVAILABLE, reason="CertusScientificPlot not available"
    )
    def test_plot_initialization(self, qapp):
        _ = qapp
        """Test scientific plot initialization."""
        plot = CertusScientificPlot()

        assert isinstance(plot, QWidget)
        # CertusScientificPlot IS a plot widget (inherits pg.PlotWidget), not HAS one
        assert hasattr(plot, "plotItem")

    @pytest.mark.skipif(
        not SCIENTIFIC_PLOT_AVAILABLE, reason="CertusScientificPlot not available"
    )
    def test_plot_add_curve(self, qapp, sample_wavelengths, sample_spectrum):
        _ = qapp
        """Test adding a curve to the plot."""
        plot = CertusScientificPlot()
        wavelengths, (R, T) = sample_wavelengths, sample_spectrum

        plot.add_curve(wavelengths, R, "Reflectance", "r")
        plot.add_curve(wavelengths, T, "Transmittance", "b")

        assert len(plot._curves) >= 2

    @pytest.mark.skipif(
        not SCIENTIFIC_PLOT_AVAILABLE, reason="CertusScientificPlot not available"
    )
    def test_plot_clear(self, qapp, sample_wavelengths, sample_spectrum):
        _ = qapp
        """Test clearing the plot."""
        plot = CertusScientificPlot()
        wavelengths, (R, _T) = sample_wavelengths, sample_spectrum

        plot.add_curve(wavelengths, R, "Test", "r")
        plot.clear()

        assert len(plot._curves) == 0

    @pytest.mark.skipif(
        not SCIENTIFIC_PLOT_AVAILABLE, reason="CertusScientificPlot not available"
    )
    def test_plot_set_labels(self, qapp):
        _ = qapp
        """Test setting plot axis labels."""
        plot = CertusScientificPlot()

        plot.set_labels("Wavelength (nm)", "Reflectance", "Test Plot")

        assert plot.plotItem.getAxis("bottom").labelText == "Wavelength (nm)"
        assert plot.plotItem.getAxis("left").labelText == "Reflectance"
        assert plot.plotItem.titleLabel.text == "Test Plot"


@pytest.mark.skipif(
    not QT_AVAILABLE or not PYQTGRAPH_AVAILABLE, reason="PyQt6 or PyQtGraph not available"
)
class TestPlotExcelExportHelpers:
    """iter_plot_data_series / DataFrame / clipboard TSV."""

    def test_build_wide_dataframe_for_export(self):
        import numpy as np
        from certus_ui import build_wide_dataframe_for_export

        series = [
            ("S1", np.array([1.0, 2.0]), np.array([10.0, 20.0])),
            ("S1", np.array([1.0]), np.array([99.0])),
        ]
        df = build_wide_dataframe_for_export(series)
        assert df is not None
        assert "S1_x" in df.columns and "S1_y" in df.columns
        assert "S1_2_x" in df.columns

    def test_plot_dataframe_from_widget(self, qapp):
        _ = qapp
        import pyqtgraph as pg
        from certus_ui import plot_dataframe_from_widget, setup_pyqtgraph_defaults

        setup_pyqtgraph_defaults()
        w = pg.PlotWidget()
        w.plot([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], name="CurveA")
        df = plot_dataframe_from_widget(w)
        assert df is not None
        assert not df.empty
        assert any("CurveA" in c for c in df.columns)

    def test_copy_plot_to_clipboard_excel(self, qapp):
        _ = qapp
        import pyqtgraph as pg
        from certus_ui import copy_plot_to_clipboard_excel, setup_pyqtgraph_defaults

        setup_pyqtgraph_defaults()
        w = pg.PlotWidget()
        w.plot([1.0, 2.0], [3.0, 4.0], name="B")
        assert copy_plot_to_clipboard_excel(w) is True
        text = QApplication.clipboard().text()
        assert "\t" in text
        assert "B" in text


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestExcelTableWidget:
    """Tests for the ExcelTableWidget class."""

    @pytest.mark.skipif(
        not EXCEL_TABLE_AVAILABLE, reason="ExcelTableWidget not available"
    )
    def test_table_initialization(self, qapp):
        _ = qapp
        """Test ExcelTableWidget initialization."""
        table = ExcelTableWidget()

        assert isinstance(table, QTableWidget)
        assert hasattr(table, "export_to_excel")

    @pytest.mark.skipif(
        not EXCEL_TABLE_AVAILABLE, reason="ExcelTableWidget not available"
    )
    def test_table_set_data(self, qapp):
        _ = qapp
        """Test setting data in the table widget."""
        table = ExcelTableWidget()

        headers = ["Column 1", "Column 2", "Column 3"]
        data = [
            ["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3"],
            ["Row 2 Col 1", "Row 2 Col 2", "Row 2 Col 3"],
        ]

        table.set_data(headers, data)

        assert table.columnCount() == len(headers)
        assert table.rowCount() == len(data)

        for col, header in enumerate(headers):
            assert table.horizontalHeaderItem(col).text() == header

    @pytest.mark.skipif(
        not EXCEL_TABLE_AVAILABLE, reason="ExcelTableWidget not available"
    )
    def test_table_export_to_excel(self, qapp, temp_directory):
        _ = qapp
        """Test Excel export."""
        table = ExcelTableWidget()

        headers = ["Test", "Value"]
        data = [["Item 1", "100"], ["Item 2", "200"]]
        table.set_data(headers, data)

        excel_file = temp_directory / "test_export.xlsx"
        result = table.export_to_excel(str(excel_file))

        assert result is True
        assert excel_file.exists()


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestThemeApplication:
    """Tests for theme application."""

    def test_apply_certus_theme_to_window(self, qapp):
        _ = qapp
        """Test applying theme to a window."""
        window = QWidget()
        apply_certus_theme(window, [])
        assert window.styleSheet() is not None

    def test_apply_certus_theme_with_plots(self, qapp):
        _ = qapp
        """Test applying theme with plot widgets."""
        window = QWidget()
        plot1 = CertusScientificPlot()
        plot2 = CertusScientificPlot()
        apply_certus_theme(window, [plot1, plot2])
        assert window.styleSheet() is not None
        assert plot1.backgroundBrush().color().name() == CertusTheme.BACKGROUND
        assert plot2.backgroundBrush().color().name() == CertusTheme.BACKGROUND


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestPyQtGraphDefaults:
    """Tests for PyQtGraph default configuration."""

    def test_setup_pyqtgraph_defaults(self):
        """Test PyQtGraph defaults setup (should not raise)."""
        setup_pyqtgraph_defaults()

        import pyqtgraph as pg

        assert pg.getConfigOption("background") is not None
        assert pg.getConfigOption("foreground") is not None


@pytest.mark.unit
class TestUIUtilities:
    """Tests for UI utilities (no PyQt6 required)."""

    def test_theme_constants_without_qt(self):
        """Test that theme constants are accessible without PyQt6."""
        assert hasattr(CertusTheme, "BACKGROUND")
        assert hasattr(CertusTheme, "PRIMARY")
        assert hasattr(CertusTheme, "FONT_FAMILY")

    def test_theme_methods_without_qt(self):
        """Test that theme methods work without PyQt6."""
        stylesheet = CertusTheme.get_status_bar_stylesheet()
        assert isinstance(stylesheet, str)

        stylesheet = CertusTheme.get_primary_button_stylesheet()
        assert isinstance(stylesheet, str)

        stylesheet = CertusTheme.get_danger_button_stylesheet()
        assert isinstance(stylesheet, str)


@pytest.mark.integration
@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestUIIntegration:
    """Integration tests for UI components."""

    def test_complete_ui_workflow(self, qapp, sample_wavelengths, sample_spectrum):
        _ = qapp
        """Test a complete UI workflow."""
        window = QWidget()
        layout = QVBoxLayout()

        button = create_styled_button("Test Button", CertusTheme.PRIMARY)
        from PyQt6.QtWidgets import QLabel

        label = QLabel("Test Label")
        label.setStyleSheet(
            f"color: {CertusTheme.TEXT_MAIN}; font-family: {CertusTheme.FONT_FAMILY};"
        )
        plot = CertusScientificPlot()
        table = ExcelTableWidget()

        wavelengths, (R, T) = sample_wavelengths, sample_spectrum
        try:
            plot.add_curve(wavelengths, R, "Reflectance", "r")
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            pytest.fail(f"add_curve failed: {e}")

        plot.set_labels("Wavelength (nm)", "R/T", "Test Plot")

        headers = ["Wavelength", "Reflectance", "Transmittance"]
        data = []
        for i, wl in enumerate(wavelengths):
            data.append([f"{wl:.1f}", f"{R[i]:.3f}", f"{T[i]:.3f}"])

        print(f"DEBUG: Headers len={len(headers)}")
        print(f"DEBUG: Data len={len(data)}")
        if len(data) > 0:
            print(f"DEBUG: First row len={len(data[0])}")

        try:
            table.set_data(headers, data)
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            pytest.fail(f"set_data failed: {e}")

        layout.addWidget(button)
        layout.addWidget(label)
        layout.addWidget(plot)
        layout.addWidget(table)
        window.setLayout(layout)

        apply_certus_theme(window, [plot])

        assert window.layout() is layout
        assert button.text() == "Test Button"
        assert label.text() == "Test Label"
        assert len(plot._curves) > 0
        assert table.rowCount() > 0
        assert window.styleSheet() is not None


@pytest.mark.ui
@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestUIInteractions:
    """Tests for UI interactions."""

    def test_button_click_interaction(self, qapp):
        _ = qapp
        """Test button click interaction."""
        button = create_styled_button("Click Me", CertusTheme.PRIMARY)
        button.click()
        assert button.isEnabled()

    def test_theme_switch_interaction(self, qapp):
        _ = qapp
        """Test theme switching between light and dark."""
        CertusTheme.configure("light")
        light_bg = CertusTheme.BACKGROUND
        CertusTheme.configure("dark")
        dark_bg = CertusTheme.BACKGROUND
        assert light_bg != dark_bg


@pytest.mark.ui
@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
def test_strat_strategies_table_headers_contract(qapp):
    _ = qapp
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    pytest.importorskip("CERTUS_STRAT")
    from CERTUS_STRAT import StrategiesTableWindow

    strategy_result = {
        "strategy": {
            "strategy_id": "s1",
            "n_blocks": 1,
            "origin": "THICKNESS",
            "blocks": [{"start": 0, "end": 2, "wavelength": 500.0, "num_layers": 2}],
        },
        "robustness_score": 0.123,
        "num_unique_wavelengths": 1,
        "min_resolution": 1.0,
        "limiting_layer": 1,
        "complexity_score": 1.0,
        "results_per_noise": [
            {
                "noise_level": 1.0,
                "rmse_mean": 0.2,
                "rmse_std": 0.0,
                "rmse_p95": 0.2,
                "rmse_p99": 0.2,
                "thicknesses_all": [[100.0, 80.0], [101.0, 79.0]],
                "rmse_all": [0.2, 0.21],
            }
        ],
        "theoretical_layer_profile": [{"extrema_count": 1}],
    }
    win = StrategiesTableWindow(None, [strategy_result], [100.0, 80.0])
    headers = [win.table.horizontalHeaderItem(i).text() for i in range(win.table.columnCount())]
    assert "Next" in headers
    assert "Sym Score" in headers
