from PyQt6.QtWidgets import QWidget


def _builds_without_a_name_error(build):
    """Build a window and dispose of it. Building one with nothing to show may fail in many ways; an undefined name is the one
    failure this smoke test is for, and it is re-raised."""
    try:
        window = build()
    except NameError:
        raise
    except Exception:
        return
    assert window is not None
    window.deleteLater()


def test_strat_ui_windows_import_and_construct(qapp):
    """Smoke test to verify that strategy UI window classes can be imported and instantiated without NameError."""
    # Ensure QApp exists
    _ = qapp

    from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
    from certus.ui.certus_strat_indices_ui import InteractiveIndicesWindow
    from certus.ui.certus_strat_monitor_ui import CertusStratGrowthWidget, LiveMonitorWindow
    from certus.ui.certus_strat_performance_ui import StrategySpectralPerformanceWindow
    from certus.ui.certus_strat_plots_ui import CertusScientificPlot, UniversalPlotWindow
    from certus.ui.certus_strat_spectrum_ui import InteractiveSpectrumWindow
    from certus.ui.certus_strat_stack_progress_widget import CertusStratStackProgressWidget
    from certus.ui.certus_strat_table_ui import StrategiesTableWindow
    from certus.ui.certus_strat_thickness_ui import TransmissionVsThicknessWindow

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

    # 2. to 10. Every window instantiates, or fails for a reason other than an undefined name
    dummy_strategy = {"strategy": {"strategy_id": 900000001, "blocks": [], "layers": []}}

    def monitor_and_growth():
        mon_win = LiveMonitorWindow(parent)
        mon_win.deleteLater()
        growth_w = CertusStratGrowthWidget(parent)
        growth_w.set_status_text("Testing", 50)
        return growth_w

    def stack_progress():
        stack_widget = CertusStratStackProgressWidget(parent)
        stack_widget.update_progress(1, 10, 10)
        return stack_widget

    for build in (
        lambda: InteractiveHeatmapWindow(parent, {}),
        lambda: StrategiesTableWindow(parent, [], [], False),
        lambda: InteractiveIndicesWindow(parent, {}),
        lambda: UniversalPlotWindow(parent, {}, "unknown_type"),
        monitor_and_growth,
        lambda: TransmissionVsThicknessWindow(parent, dummy_strategy, {}, {}),
        lambda: InteractiveSpectrumWindow(parent, {}),
        lambda: StrategySpectralPerformanceWindow(parent, dummy_strategy, {}, {}),
        stack_progress,
    ):
        _builds_without_a_name_error(build)

    parent.deleteLater()


def test_strat_imports_do_not_poison_qpa_platform():
    """Verify that importing STRAT modules does not silently set QT_QPA_PLATFORM=offscreen."""
    import os

    # Clean env before test
    os.environ.pop("QT_QPA_PLATFORM", None)

    import certus.ui.certus_strat_multigraine_ui
    import certus.ui.certus_strat_ui
    import certus.ui.certus_strat_ui_plot

    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", (
        "Regression: an import in CERTUS-STRAT set QT_QPA_PLATFORM=offscreen, making the GUI invisible!"
    )

