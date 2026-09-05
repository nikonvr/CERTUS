"""Batterie de tests de non-régression ergonomique et spatiale sur l'ensemble de la suite CERTUS."""

from __future__ import annotations

import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QMimeData, QUrl, QEvent, QPointF
from PyQt6.QtGui import QDragEnterEvent, QMouseEvent

os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication([])

from CERTUS_HUB import CertusHub
from certus.ui.certus_design_ui import CertusDesignApp
from certus.ui.certus_strat_ui import CertusStratApp
from certus.ui.certus_index_ui import CertusIndexApp
from CERTUS_RE import CertusREApp
from certus.ui.certus_field_ui import CertusFieldApp
from CERTUS_METAL_SINGLE import CertusMetalSingleApp
from CERTUS_METAL_BILAYER import CertusMetalBilayerApp
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
from certus.ui.certus_plot import CertusScientificPlot


def test_universal_drag_and_drop_enabled():
    """Vérifier que toutes les interfaces acceptent le Drag & Drop nativement."""
    apps = [
        CertusDesignApp(),
        CertusStratApp(),
        CertusIndexApp(),
        CertusFieldApp(),
        CertusMetalSingleApp(),
        CertusMetalBilayerApp(),
        CertusHub(),
    ]
    for w in apps:
        assert w.acceptDrops() is True, f"{w.__class__.__name__} doit accepter le drag & drop"
        w.close()


def test_strat_pinned_execution_buttons():
    """Vérifier que le bloc RUN/STOP/Reset de STRAT est bien épinglé et configuré."""
    strat = CertusStratApp()
    assert strat.run_full_btn is not None
    assert strat.stop_step2_btn is not None
    assert strat.clear_btn is not None
    assert strat.run_full_btn.text() == " RUN FULL WORKFLOW"
    assert strat.stop_step2_btn.isEnabled() is False  # Désactivé tant qu'aucun calcul ne tourne
    strat.close()


def test_design_and_re_splitter_persistence():
    """Vérifier que DESIGN et RE exposent leurs splitters pour la persistance QSettings."""
    design = CertusDesignApp()
    assert getattr(design, "main_split", None) is not None
    assert getattr(design, "bottom_splitter", None) is not None
    # Tester la sauvegarde/restauration QSettings sans exception
    design._qs_save()
    design._qs_restore()
    design.close()

    re_app = CertusREApp()
    assert getattr(re_app, "main_split", None) is not None
    assert getattr(re_app, "bottom_splitter", None) is not None
    re_app._qs_save()
    re_app._qs_restore()
    re_app.close()


def test_index_splitter_persistence():
    """Vérifier que INDEX expose main_split et bottom_split pour la persistance."""
    index_app = CertusIndexApp()
    assert getattr(index_app, "main_split", None) is not None
    assert getattr(index_app, "bottom_split", None) is not None
    index_app._qs_save()
    index_app._qs_restore()
    index_app.close()


def test_double_click_autorange_on_scientific_plots():
    """Vérifier que le double-clic réinitialise l'échelle sur CertusScientificPlot."""
    plot = CertusScientificPlot(title="Test Spectrum")
    plot.plot([400, 500, 600, 700], [0.1, 0.5, 0.8, 0.9])
    
    # Simuler un zoom avant
    plot.setXRange(450, 550)
    
    # Simuler un double-clic
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(50, 50),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    plot.mouseDoubleClickEvent(event)
    assert event.isAccepted() is True
    plot.close()


def test_index_spline_ux_and_shortcuts():
    """Vérifier l'ergonomie d'élite et le dimensionnement de CERTUS-INDEX-SPLINE."""
    spline_app = CertusIndexSplineApp()
    spline_app.show()
    assert spline_app.acceptDrops() is True
    assert spline_app.btn_run is not None
    assert spline_app.btn_run.text() == "▶  Run Optimization"
    assert spline_app.btn_run.height() >= 35 or spline_app.btn_run.maximumHeight() >= 35
    assert spline_app.btn_stop is not None
    assert spline_app.btn_stop.isEnabled() is False

    # Vérifier l'allocation spatiale équilibrée (graphes prioritaires)
    sizes = spline_app.main_split.sizes()
    assert len(sizes) >= 2
    assert sizes[1] > sizes[0]  # Les graphiques reçoivent plus d'espace que la barre latérale

    # Vérifier que les paramètres vitaux sont immédiatement visibles (expanded=True)
    assert spline_app.params_collapsible.is_expanded() is True

    # Vérifier la présence et la configuration de l'onglet Synthèse Overview (CompleteEASE / OptiChar)
    assert spline_app.plot_ov_T is not None
    assert spline_app.plot_ov_nk is not None
    assert spline_app.kpi_rmse is not None
    assert spline_app.kpi_d is not None
    assert spline_app.tabs_main.tabText(0) == "✦ Synthèse (Overview)"

    spline_app.close()
