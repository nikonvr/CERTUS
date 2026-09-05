import pytest
from PyQt6.QtWidgets import QWidget, QMainWindow
import numpy as np

def test_strat_ui_windows_import_and_construct(qapp):
    """Smoke test to verify that strategy UI window classes can be imported and instantiated without NameError."""
    # Ensure QApp exists
    _ = qapp

    from certus.ui.certus_strat_plots_ui import UniversalPlotWindow, CertusScientificPlot
    from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
    from certus.ui.certus_strat_table_ui import StrategiesTableWindow
    from certus.ui.certus_strat_indices_ui import InteractiveIndicesWindow
    from certus.ui.certus_strat_monitor_ui import LiveMonitorWindow, CertusStratGrowthWidget
    from certus.ui.certus_strat_thickness_ui import TransmissionVsThicknessWindow
    from certus.ui.certus_strat_spectrum_ui import InteractiveSpectrumWindow
    from certus.ui.certus_strat_performance_ui import StrategySpectralPerformanceWindow
    from certus.ui.certus_strat_stack_progress_widget import CertusStratStackProgressWidget

    # 1. Verify class definitions exist
    assert UniversalPlotWindow is not None
    assert CertusScientificPlot is not None
    assert InteractiveHeatmapWindow is not None
    assert StrategiesTableWindow is not None
    assert InteractiveIndicesWindow is not None
    assert LiveMonitorWindow is not None
    assert CertusStratGrowthWidget is not None
    assert TransmissionVsThicknessWindow is not None
    assert InteractiveSpectrumWindow is not None
    assert StrategySpectralPerformanceWindow is not None
    assert CertusStratStackProgressWidget is not None

    parent = QWidget()

    # 2. Test InteractiveHeatmapWindow instantiation
    try:
        heatmap_win = InteractiveHeatmapWindow(parent, {})
        assert heatmap_win is not None
        heatmap_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 3. Test StrategiesTableWindow instantiation
    try:
        table_win = StrategiesTableWindow(parent, [], [], False)
        assert table_win is not None
        table_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 4. Test InteractiveIndicesWindow instantiation
    try:
        indices_win = InteractiveIndicesWindow(parent, {})
        assert indices_win is not None
        indices_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 5. Test UniversalPlotWindow instantiation
    try:
        plot_win = UniversalPlotWindow(parent, {}, "unknown_type")
        assert plot_win is not None
        plot_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 6. Test LiveMonitorWindow and CertusStratGrowthWidget instantiation
    try:
        mon_win = LiveMonitorWindow(parent)
        assert mon_win is not None
        mon_win.deleteLater()
        growth_w = CertusStratGrowthWidget(parent)
        assert growth_w is not None
        growth_w.set_status_text("Testing", 50)
        growth_w.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 7. Test TransmissionVsThicknessWindow instantiation
    dummy_strategy = {"strategy": {"strategy_id": 900000001, "blocks": [], "layers": []}}
    try:
        trans_win = TransmissionVsThicknessWindow(parent, dummy_strategy, {}, {})
        assert trans_win is not None
        trans_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 8. Test InteractiveSpectrumWindow instantiation
    try:
        spec_win = InteractiveSpectrumWindow(parent, {})
        assert spec_win is not None
        spec_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 9. Test StrategySpectralPerformanceWindow instantiation
    try:
        perf_win = StrategySpectralPerformanceWindow(parent, dummy_strategy, {}, {})
        assert perf_win is not None
        perf_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 10. Test CertusStratStackProgressWidget instantiation and updates
    try:
        stack_widget = CertusStratStackProgressWidget(parent)
        assert stack_widget is not None
        stack_widget.update_progress(1, 10, 10)
        stack_widget.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    parent.deleteLater()


def test_strat_imports_do_not_poison_qpa_platform():
    """Verify that importing STRAT modules does not silently set QT_QPA_PLATFORM=offscreen."""
    import os

    # Clean env before test
    os.environ.pop("QT_QPA_PLATFORM", None)

    import certus.ui.certus_strat_ui
    import certus.ui.certus_strat_multigraine_ui
    import certus.ui.certus_strat_ui_plot

    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", (
        "Regression: an import in CERTUS-STRAT set QT_QPA_PLATFORM=offscreen, making the GUI invisible!"
    )

