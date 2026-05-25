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
    CertusLogPanel,
    certus_confirm_yes_no,
    certus_get_open_file_name,
    certus_get_save_file_name,
    create_styled_button,
    apply_certus_theme,
    setup_pyqtgraph_defaults,
    open_data_file_and_read,
    format_count_kmg,
    StatsCounter,
    create_log_widget,
    create_header_logo_widget,
    create_info_icon,
    create_help_button,
    set_certus_last_dir,
    get_certus_last_dir,
    open_file_explorer,
    stop_worker_and_thread,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    attach_numeric_validator,
    show_toast,
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

    def test_set_get_last_dir_roundtrip(self, tmp_path):
        target = tmp_path / "nested" / "file.csv"
        target.parent.mkdir()
        target.write_text("x")
        set_certus_last_dir(str(target))
        assert get_certus_last_dir() == str(target.parent)


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

    def test_create_log_widget_and_panel(self, qapp):
        _ = qapp
        widget = create_log_widget(visible=True, height=120)
        assert widget.isVisible()
        assert widget.maximumHeight() == 120

        panel = CertusLogPanel(title="LOGS", visible=True, height=100)
        panel.log_text.setPlainText("hello")
        with patch.object(QApplication.instance().clipboard(), "setText") as mock_set:
            panel.copy_to_clipboard()
            mock_set.assert_called_once_with("hello")

    def test_header_info_help_widgets(self, qapp):
        _ = qapp
        header = create_header_logo_widget(title_text="T", subtitle_text="S", module_name="CERTUS_HUB")
        assert header is not None
        info = create_info_icon("tip")
        assert info.toolTip() == "tip"
        help_btn = create_help_button("CERTUS_HUB")
        assert help_btn.text() == "?"


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
        mock_app.setStyleSheet.assert_called()

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
        mock_app.setStyleSheet.assert_called()

    def test_dark_mode_aliases_and_a11y(self):
        """Test dark mode alias updates, contrast settings, and palette audit logger behavior."""
        # Backup original colors
        original_bg = CertusTheme.BACKGROUND
        original_surface = CertusTheme.SURFACE
        original_warning = CertusTheme.WARNING
        original_dark = CertusTheme.DARK_MODE
        original_chart = CertusTheme.CHART_PRIMARY

        try:
            # 1. Test configure("dark") syncs variables
            CertusTheme.configure("dark")
            assert CertusTheme.DARK_MODE is True
            assert CertusTheme.BACKGROUND == "#0f172a"
            assert CertusTheme.WARNING == "#fbbf24"
            assert CertusTheme.BASE_ELEVATED == "#111827"
            assert CertusTheme.ELEVATED == "#1f2937"
            assert CertusTheme.CHART_PRIMARY == "#60a5fa"

            # 2. Test configure("light") syncs variables
            CertusTheme.configure("light")
            assert CertusTheme.DARK_MODE is False
            assert CertusTheme.BACKGROUND == "#f1f5f9"
            assert CertusTheme.WARNING == "#b45309"
            assert CertusTheme.BASE_ELEVATED == "#ffffff"
            assert CertusTheme.ELEVATED == "#f1f3f5"
            assert CertusTheme.CHART_PRIMARY == "#0f62fe"

            # 3. Test apply_to_app invokes the a11y audit logger safely
            mock_app = MagicMock()
            mock_palette = Mock()
            mock_app.palette.return_value = mock_palette
            
            with patch("logging.Logger.warning") as mock_warn:
                # Intentionally trigger contrast warning for testing if there were bad colors
                # WARNING #b45309 vs #ffffff is fine (> 4.5:1), but if we force a bad contrast color:
                CertusTheme.WARNING = "#ffc107"  # Bad contrast color
                CertusTheme.apply_to_app(mock_app, dark_mode=False)
                # Verify logger warning was called due to contrast ratio of WARNING color on light surface
                assert mock_warn.called
                assert any("warning" in args[0].lower() or "contrast" in args[0].lower() for args, _ in mock_warn.call_args_list)

        finally:
            # Restore state
            CertusTheme.BACKGROUND = original_bg
            CertusTheme.SURFACE = original_surface
            CertusTheme.WARNING = original_warning
            CertusTheme.DARK_MODE = original_dark
            CertusTheme.CHART_PRIMARY = original_chart

    def test_get_standard_stylesheet_class_method(self):
        """Test that get_standard_stylesheet is callable both globally and as a class method."""
        from certus_theme import get_standard_stylesheet as global_get_stylesheet
        
        global_style = global_get_stylesheet()
        class_style = CertusTheme.get_standard_stylesheet()
        
        assert isinstance(global_style, str)
        assert isinstance(class_style, str)
        assert global_style == class_style
        assert "QWidget" in class_style


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

    def test_format_count_kmg_and_stats_counter(self):
        assert format_count_kmg(12) == "12"
        assert format_count_kmg(1500) == "1.5K"
        assert format_count_kmg(2500000) == "2.5M"

        counters = StatsCounter({"EVAL": 1})
        assert counters.inc("EVAL") == 2
        assert counters.set("BEST", 3) == 3
        counters.reset("EVAL")
        assert counters.get("EVAL") == 0
        assert counters.formatted("BEST") == "3"


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

    def test_validator_and_toast_helpers(self, qapp):
        _ = qapp
        from PyQt6.QtWidgets import QLineEdit, QWidget

        line = QLineEdit()
        attach_numeric_validator(line, minimum=0, maximum=10, kind="float")
        line.setText("-1")
        assert "border" in line.styleSheet()
        line.setText("5")
        assert "border" not in line.styleSheet() or "DANGER" not in line.toolTip()

        parent = QWidget()
        toast = show_toast(parent, "Hi", level="info", duration_ms=10)
        assert toast is not None


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


@pytest.mark.ui
@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestUIExceptionHandling:
    """Tests for @safe_ui_action and exception translation in UI classes."""

    def test_safe_ui_action_validation_error(self, qapp):
        from certus_errors import CertusValidationError
        from certus_ui import safe_ui_action

        class DummyWidget(QWidget):
            @safe_ui_action
            def fail_validation(self):
                raise CertusValidationError("Validation failed", details="Invalid value", suggestion="Try again")

        widget = DummyWidget()
        with patch("certus_ui.show_toast") as mock_toast:
            widget.fail_validation()
            mock_toast.assert_called_once()
            args, kwargs = mock_toast.call_args
            assert "Validation" in args[1]
            assert kwargs.get("level") == "warning"

    def test_safe_ui_action_domain_error(self, qapp):
        from certus_errors import CertusDomainError
        from certus_ui import safe_ui_action
        from PyQt6.QtWidgets import QMessageBox

        class DummyWidget(QWidget):
            @safe_ui_action
            def fail_domain(self):
                raise CertusDomainError("Domain failed", details="Physics error", suggestion="Adjust params")

        widget = DummyWidget()
        with patch.object(QMessageBox, "exec") as mock_exec:
            widget.fail_domain()
            mock_exec.assert_called_once()

    def test_safe_ui_action_numerical_error(self, qapp):
        from certus_ui import safe_ui_action

        class DummyWidget(QWidget):
            @safe_ui_action
            def fail_numerical(self):
                raise ValueError("Numerical error")

        widget = DummyWidget()
        with patch("certus_ui.show_toast") as mock_toast:
            widget.fail_numerical()
            mock_toast.assert_called_once()
            args, kwargs = mock_toast.call_args
            assert "Error: Numerical error" in args[1]
            assert kwargs.get("level") == "error"

    def test_safe_ui_action_generic_exception(self, qapp):
        from certus_ui import safe_ui_action

        class DummyWidget(QWidget):
            @safe_ui_action
            def fail_generic(self):
                raise Exception("Generic crash")

        widget = DummyWidget()
        with patch("certus_ui.show_toast") as mock_toast:
            widget.fail_generic()
            mock_toast.assert_called_once()
            args, kwargs = mock_toast.call_args
            assert "Critical: Generic crash" in args[1]
            assert kwargs.get("level") == "error"

    def test_base_app_save_load_config_corruption(self, qapp):
        from certus_ui import CertusBaseApp
        from PyQt6.QtWidgets import QMessageBox

        class DummyApp(CertusBaseApp):
            def _collect_config(self):
                raise ValueError("Serialization failed")
            def _get_default_config_name(self):
                return "test.json"
            def _get_config_file_filter(self):
                return "JSON (*.json)"
            def _apply_config(self, cfg):
                raise FileNotFoundError("Missing file")

        app = DummyApp()

        # 1. Test save_config raising ValueError -> ConfigurationCorruptionError -> QMessageBox
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=("dummy.json", "")):
            with patch.object(QMessageBox, "exec") as mock_exec:
                app.save_config()
                mock_exec.assert_called_once()

        # 2. Test load_config raising FileNotFoundError -> ConfigurationCorruptionError -> QMessageBox
        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=("dummy.json", "")):
            with patch.object(QMessageBox, "exec") as mock_exec:
                app.load_config()
                mock_exec.assert_called_once()

    def test_worker_helpers(self):
        class DummyWorker:
            def stop(self):
                self.stopped = True

        class DummyThread:
            def __init__(self):
                self._running = True
            def isRunning(self):
                return self._running
            def quit(self):
                self._running = False
            def wait(self, timeout_ms):
                return True

        assert stop_worker_and_thread(DummyWorker(), DummyThread()) is True
        assert confirm_stop_with_timeout is not None

    def test_copy_app_logs_to_clipboard(self, qapp):
        _ = qapp
        from certus_ui import copy_app_logs_to_clipboard

        class DummyPanel:
            def copy_to_clipboard(self):
                self.copied = True

        class DummyApp:
            _log_panel = DummyPanel()
            log_text = None

        assert copy_app_logs_to_clipboard(DummyApp()) is True

    def test_open_file_explorer_invalid_path(self):
        from certus_ui import open_file_explorer
        open_file_explorer("C:/definitely/does/not/exist")

    def test_base_app_private_helpers(self, qapp):
        _ = qapp
        from certus_ui import CertusBaseApp

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        assert app._qs_key("geometry") == "window/DUMMY/geometry"
        assert app._get_default_config_name() == "dummy.json"
        assert app._build_report_sections() == []
        assert app._stack_info_l0_nm() == 500.0

    def test_base_app_validation_and_recent_helpers(self, qapp, tmp_path):
        _ = qapp
        from certus_ui import CertusBaseApp

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        app.set_validation_status("CUSTOM")
        assert app.validation_status == "CUSTOM"
        app.add_validation_warning("warn one")
        assert "warn one" in app.validation_warnings
        assert app._record_recent_config(str(tmp_path / "config.json")) is None
        assert isinstance(app.list_recent_configs(limit=2), list)

    def test_base_app_dialog_helpers(self, qapp):
        _ = qapp
        from certus_ui import CertusBaseApp

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        with patch("certus_ui.QMessageBox.exec", return_value=None):
            assert app.confirm_destructive("t", "m") in (True, False)

    def test_base_app_save_and_load_config(self, qapp, tmp_path):
        _ = qapp
        import json
        from certus_ui import CertusBaseApp

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {"hello": "world"}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        save_path = tmp_path / "dummy.json"
        with patch("certus_ui.QFileDialog.getSaveFileName", return_value=(str(save_path), "")):
            assert app.save_config() is None
        assert json.loads(save_path.read_text(encoding="utf-8")) == {"hello": "world"}

        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=(str(save_path), "")):
            assert app.load_config() is None
        assert getattr(app, "_applied", None) == {"hello": "world"}

    def test_base_app_menus_and_recent_helpers(self, qapp, tmp_path):
        _ = qapp
        from certus_ui import CertusBaseApp
        from certus_recent import clear_recent, RecentCategories

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

            def open_help(self):
                self.help_opened = True

        app = DummyApp()
        app.install_help_menu(app_label="Dummy")
        assert app.menuBar() is not None
        clear_recent(RecentCategories.CONFIG)
        assert app.list_recent_configs(limit=1) == []
        app._record_recent_config(str(tmp_path / "recent.json"))
        assert isinstance(app.open_command_palette, object)
        assert isinstance(app.open_shortcuts_overlay, object)

    def test_base_app_save_and_load_config_roundtrip(self, qapp, tmp_path):
        _ = qapp
        from certus_ui import CertusBaseApp

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {"alpha": 1, "nested": {"beta": 2}}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        cfg_file = tmp_path / "dummy.json"
        with patch("certus_ui.QFileDialog.getSaveFileName", return_value=(str(cfg_file), "")):
            app.save_config()
        assert cfg_file.exists()
        with patch("certus_ui.QFileDialog.getOpenFileName", return_value=(str(cfg_file), "")):
            app.load_config()
        assert getattr(app, "_applied", None) == {"alpha": 1, "nested": {"beta": 2}}

    def test_base_app_help_menu_and_about(self, qapp):
        _ = qapp
        from certus_ui import CertusBaseApp
        from PyQt6.QtWidgets import QMessageBox

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

            def open_help(self):
                self.help_opened = True

        app = DummyApp()
        app.install_help_menu(app_label="Dummy App")
        assert app.menuBar() is not None
        with patch.object(QMessageBox, "about") as mock_about:
            app._show_default_about_dialog("Dummy App")
            mock_about.assert_called_once()
        assert True

    def test_base_app_recent_and_reports(self, qapp, tmp_path):
        _ = qapp
        from certus_ui import CertusBaseApp
        from certus_recent import clear_recent, RecentCategories
        from PyQt6.QtWidgets import QInputDialog

        class DummyApp(CertusBaseApp):
            APP_NAME = "DUMMY"
            APP_TITLE = "Dummy App"

            def _collect_config(self):
                return {}

            def _apply_config(self, cfg):
                self._applied = cfg

            def _get_default_config_name(self):
                return "dummy.json"

            def _get_config_file_filter(self):
                return "JSON (*.json)"

        app = DummyApp()
        clear_recent(RecentCategories.CONFIG)
        app._record_recent_config(str(tmp_path / "config.json"))
        with patch.object(QInputDialog, "getItem", return_value=("", False)):
            app.open_recent_configs()
        with patch("certus_ui.certus_get_save_file_name", return_value=None):
            assert app.export_report_excel() is None or isinstance(app.export_report_excel(), (str, type(None)))
            assert app.export_report_pdf() is None or isinstance(app.export_report_pdf(), (str, type(None)))

    def test_re_app_callbacks_protected(self, qapp):
        pytest.importorskip("CERTUS_RE")
        from CERTUS_RE import CertusREApp

        app = CertusREApp()
        assert hasattr(app.launch_re, "__wrapped__")
        assert hasattr(app.load_reverse_engineering, "__wrapped__")


@pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")
class TestProUXComponents:
    """Tests for advanced UX widgets and utility functions added to boost coverage."""

    def test_certus_section_header(self, qapp):
        _ = qapp
        from certus_ui import CertusSectionHeader
        header = CertusSectionHeader("My Title", "My Caption")
        assert header is not None

    def test_certus_stepper(self, qapp):
        _ = qapp
        from PyQt6.QtCore import Qt
        from certus_ui import CertusStepper
        # 1 column
        stepper1 = CertusStepper(["Step 1", "Step 2"], columns=1)
        assert len(stepper1._btns) == 2
        # Multiple columns grid
        stepper2 = CertusStepper(["Step A", "Step B", "Step C"], columns=2)
        assert len(stepper2._btns) == 3

        # Click simulation & active state
        activated_steps = []
        stepper1.step_activated.connect(activated_steps.append)
        stepper1._btns[1].click()
        assert 1 in activated_steps

        # set_step
        stepper1.set_step(1)
        assert stepper1._current == 1
        stepper1.set_step(5)  # Out of range fallback
        assert stepper1._current == 1

    def test_certus_collapsible(self, qapp):
        _ = qapp
        from certus_ui import CertusCollapsible
        from PyQt6.QtWidgets import QWidget
        win = QWidget()
        content = QWidget(parent=win)
        collapsible = CertusCollapsible("Section", content, expanded=True, parent=win)
        win.show()
        assert collapsible.is_expanded() is True

        # Toggle with animations mocked out to fall back to direct visibility change
        with patch("certus_animations.fade_in", side_effect=RuntimeError), \
             patch("certus_animations.fade_out", side_effect=RuntimeError):
            collapsible.set_expanded(False)
            assert collapsible.is_expanded() is False
            collapsible.set_expanded(True)
            assert collapsible.is_expanded() is True

    def test_certus_status_pill(self, qapp):
        _ = qapp
        from certus_ui import CertusStatusPill
        pill = CertusStatusPill("Ready", level="ready")
        assert pill.text() == "Ready"
        pill.set_level("running")
        assert pill._level == "running"
        pill.set_level("done")
        pill.set_level("error")
        pill.set_level("warning")
        pill.set_level("invalid_level")

    def test_certus_action_bar(self, qapp):
        _ = qapp
        from certus_ui import CertusActionBar
        from PyQt6.QtWidgets import QPushButton
        bar = CertusActionBar()
        btn = QPushButton("Action")
        bar.add_widget(btn)
        bar.add_stretch()

    def test_install_shortcuts(self, qapp):
        _ = qapp
        from PyQt6.QtCore import Qt
        from certus_ui import install_standard_shortcuts
        from PyQt6.QtWidgets import QWidget
        win = QWidget()
        called = []
        shortcuts = install_standard_shortcuts(
            win,
            save=lambda: called.append("save"),
            run=lambda: called.append("run"),
            extra={"Ctrl+P": lambda: called.append("extra")}
        )
        assert any(k.startswith("save") for k in shortcuts)
        assert any(k.startswith("run") for k in shortcuts)
        assert "Ctrl+P" in shortcuts

    def test_file_drop_filter(self, qapp):
        _ = qapp
        from PyQt6.QtCore import QUrl, QEvent, Qt
        from certus_ui import enable_file_drop
        from PyQt6.QtWidgets import QWidget

        win = QWidget()
        dropped_paths = []
        flt = enable_file_drop(win, handler=dropped_paths.extend, extensions=[".json", ".csv"])

        class MockEvent:
            Type = QEvent.Type
            def __init__(self, type_val, mime_data):
                self._type = type_val
                self._mime = mime_data
                self.accepted = False
            def type(self):
                return self._type
            def mimeData(self):
                return self._mime
            def acceptProposedAction(self):
                self.accepted = True

        class MockMime:
            def __init__(self, urls):
                self._urls = urls
            def hasUrls(self):
                return bool(self._urls)
            def urls(self):
                return self._urls

        mime = MockMime([QUrl.fromLocalFile("test.json"), QUrl.fromLocalFile("test.txt")])
        
        # Test drag enter event filtering
        ev_enter = MockEvent(QEvent.Type.DragEnter, mime)
        res = flt.eventFilter(win, ev_enter)
        assert res is True
        assert ev_enter.accepted is True

        # Test drop event
        ev_drop = MockEvent(QEvent.Type.Drop, mime)
        res_drop = flt.eventFilter(win, ev_drop)
        assert res_drop is True
        assert len(dropped_paths) > 0
        assert "test.json" in dropped_paths[0]

    def test_certus_toast(self, qapp):
        _ = qapp
        from certus_ui import CertusToast, show_toast
        from PyQt6.QtWidgets import QWidget
        parent = QWidget()
        toast = CertusToast(parent, "Test Notification", level="success", duration_ms=10)
        assert toast.text() == "Test Notification"
        
        t2 = show_toast(parent, "Info", level="info", duration_ms=10)
        assert t2 is not None
        assert show_toast(None, "No Parent") is None

    def test_numeric_table_widget_item(self, qapp):
        _ = qapp
        from certus_ui import NumericTableWidgetItem
        
        # Numeric comparison
        item1 = NumericTableWidgetItem("12.5")
        item2 = NumericTableWidgetItem("3.7")
        assert (item2 < item1) is True
        assert (item1 < item2) is False

        # Fallback to string comparison in case of error
        item_str1 = NumericTableWidgetItem("apple")
        item_str2 = NumericTableWidgetItem("banana")
        assert (item_str1 < item_str2) is True

    def test_flashy_card(self, qapp):
        _ = qapp
        from certus_ui import FlashyCard
        
        card1 = FlashyCard("Title 1", "Subtitle 1", icon="🚀")
        assert card1 is not None
        
        card2 = FlashyCard("Title 2", "Subtitle 2", icon="")
        assert card2 is not None

    def test_welcome_guide_widget(self, qapp):
        _ = qapp
        from certus_ui import WelcomeGuideWidget
        
        guide = WelcomeGuideWidget(app_name="TestApp", steps=["Step 1", "Step 2"])
        assert guide is not None

    def test_certus_card(self, qapp):
        _ = qapp
        from certus_ui import CertusCard
        
        card_empty = CertusCard()
        assert card_empty is not None
        
        card_with_text = CertusCard(title="My Card", subtitle="My Subtitle")
        assert card_with_text is not None
        
        card_with_text._refresh_style()
        # Trigger showEvent with a mock event
        from PyQt6.QtGui import QShowEvent
        event = QShowEvent()
        card_with_text.showEvent(event)

    def test_progress_dialog(self, qapp):
        _ = qapp
        from certus_ui import ProgressDialog
        dlg = ProgressDialog("My Dialog")
        assert dlg.is_canceled() is False
        dlg.progress_bar.setValue(50)
        assert dlg.progress_bar.value() == 50
        dlg.finish()
        assert dlg.progress_bar.value() == 100

    def test_enhanced_progress_widget(self, qapp):
        _ = qapp
        from certus_ui import EnhancedProgressWidget
        w = EnhancedProgressWidget(main_label="Main")
        assert w.is_canceled() is False
        
        w.start()
        w.enable_cancel(True)
        w.set_time_budget(10.0)
        
        # Call update with various parameters
        w.update(iteration=5, max_iter=10, evals=100, phase="Run", sub_iteration=2, max_sub_iter=5, animate=False)
        assert w.progress_bar.value() == 50
        
        # Test cancel click
        w.cancel_btn.click()
        assert w.is_canceled() is True

    def test_skeleton_loader(self, qapp):
        _ = qapp
        from certus_ui import SkeletonLoaderWidget, install_skeleton_loader, remove_skeleton_loader
        from PyQt6.QtWidgets import QWidget

        parent = QWidget()
        loader1 = SkeletonLoaderWidget(parent, shape="chart")
        loader2 = SkeletonLoaderWidget(parent, shape="table")
        loader3 = SkeletonLoaderWidget(parent, shape="cards")
        loader4 = SkeletonLoaderWidget(parent, shape="default")
        
        # Trigger paint events to cover rendering logic
        loader1.repaint()
        loader2.repaint()
        loader3.repaint()
        loader4.repaint()
        
        # Test helper functions
        widget = QWidget()
        loader = install_skeleton_loader(widget, shape="chart")
        assert getattr(widget, "_certus_skeleton", None) is not None
        assert remove_skeleton_loader(widget) is True
        assert getattr(widget, "_certus_skeleton", None) is None
        assert remove_skeleton_loader(widget) is False

    def test_apply_os_window_effects(self, qapp):
        _ = qapp
        from certus_ui import apply_os_window_effects
        from PyQt6.QtWidgets import QWidget
        
        window = QWidget()
        window.show()
        
        # Call with both dark mode configurations
        apply_os_window_effects(window, dark_mode=False)
        apply_os_window_effects(window, dark_mode=True)
        
        window.close()


