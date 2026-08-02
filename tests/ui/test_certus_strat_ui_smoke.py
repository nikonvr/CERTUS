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
    from certus.ui.certus_strat_monitor_ui import LiveMonitorWindow

    # 1. Verify class definitions exist
    assert UniversalPlotWindow is not None
    assert CertusScientificPlot is not None
    assert InteractiveHeatmapWindow is not None
    assert StrategiesTableWindow is not None
    assert InteractiveIndicesWindow is not None
    assert LiveMonitorWindow is not None

    parent = QWidget()

    # 2. Test InteractiveHeatmapWindow instantiation
    # Constructor: __init__(self, parent, raw_data_thickness)
    try:
        heatmap_win = InteractiveHeatmapWindow(parent, {})
        assert heatmap_win is not None
        heatmap_win.deleteLater()
    except Exception as e:
        # We allow other errors like missing data keys, but NOT NameError/AttributeError on imports
        assert not isinstance(e, NameError)

    # 3. Test StrategiesTableWindow instantiation
    # Constructor: __init__(self, parent, strategies_results, p_thick_nominal, include_secondary_rmse_stats=False)
    try:
        table_win = StrategiesTableWindow(parent, [], [], False)
        assert table_win is not None
        table_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 4. Test InteractiveIndicesWindow instantiation
    # Constructor: __init__(self, parent, data_obj)
    try:
        indices_win = InteractiveIndicesWindow(parent, {})
        assert indices_win is not None
        indices_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)

    # 5. Test UniversalPlotWindow instantiation
    # Constructor: __init__(self, parent, data_obj, plot_type)
    try:
        plot_win = UniversalPlotWindow(parent, {}, "unknown_type")
        assert plot_win is not None
        plot_win.deleteLater()
    except Exception as e:
        assert not isinstance(e, NameError)
