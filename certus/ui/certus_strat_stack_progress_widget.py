"""Widget de visualisation dynamique de l'empilement (Stack) pendant la Phase A de CERTUS-STRAT."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from certus.ui.certus_theme import CertusTheme


class LayerCard(QFrame):
    """Carte représentative d'une couche physique unique de l'empilement."""

    def __init__(self, index: int, mat: str, mult: float, thickness_nm: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.mat = mat.upper()
        self.mult = mult
        self.thickness_nm = thickness_nm
        self._state = "pending"  # "pending", "active", "done"

        self.setFixedHeight(36)
        self.setObjectName("LayerCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)

        # 1. Numéro de couche
        self.lbl_num = QLabel(f"#{index:02d}")
        self.lbl_num.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_num.setFixedWidth(34)
        layout.addWidget(self.lbl_num)

        # 2. Badge Matériau (H vs L)
        self.lbl_mat = QLabel(self.mat)
        self.lbl_mat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mat.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.lbl_mat.setFixedSize(26, 20)
        self._apply_mat_badge_style()
        layout.addWidget(self.lbl_mat)

        # 3. Épaisseur
        self.lbl_thick = QLabel(f"{self.mult:.3f} QWOT ({self.thickness_nm:.1f} nm)")
        self.lbl_thick.setFont(QFont("Segoe UI", 9))
        self.lbl_thick.setFixedWidth(160)
        layout.addWidget(self.lbl_thick)

        # 4. Statut d'analyse
        self.lbl_status = QLabel("En attente")
        self.lbl_status.setFont(QFont("Segoe UI", 8))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.lbl_status, 1)

        self.set_state("pending")

    def _apply_mat_badge_style(self) -> None:
        if self.mat == "H":
            bg = "#1e40af"
            fg = "#ffffff"
        else:
            bg = "#b45309"
            fg = "#ffffff"
        self.lbl_mat.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 4px; font-weight: bold;"
        )

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "active":
            self.setStyleSheet(
                f"#LayerCard {{ background-color: {CertusTheme.SURFACE}; "
                f"border: 2px solid {CertusTheme.PRIMARY}; border-radius: 6px; }}"
            )
            self.lbl_num.setStyleSheet(f"color: {CertusTheme.PRIMARY};")
            self.lbl_status.setText("⚡ Analyse d'admissibilité en cours...")
            self.lbl_status.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold;")
        elif state == "done":
            self.setStyleSheet(
                f"#LayerCard {{ background-color: {CertusTheme.SURFACE}; "
                f"border: 1px solid #bbf7d0; border-radius: 6px; }}"
            )
            self.lbl_num.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")
            self.lbl_status.setText("✓ Admissible")
            self.lbl_status.setStyleSheet("color: #15803d; font-weight: 600;")
        else:
            self.setStyleSheet(
                f"#LayerCard {{ background-color: rgba(255, 255, 255, 0.4); "
                f"border: 1px solid {CertusTheme.BORDER}; border-radius: 6px; opacity: 0.6; }}"
            )
            self.lbl_num.setStyleSheet(f"color: {CertusTheme.TEXT_DISABLED};")
            self.lbl_status.setText("En attente")
            self.lbl_status.setStyleSheet(f"color: {CertusTheme.TEXT_DISABLED};")


class CertusStratStackProgressWidget(QWidget):
    """Panneau central dynamique affichant l'empilement optique en cours d'analyse en Phase A."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layer_cards: list[LayerCard] = []
        self._total_layers = 0
        self._current_layer = 0
        self._total_thickness = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # 1. En-tête / Titre
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("STACK ANALYSIS — Phase A : Admissibilité couche par couche")
        self.lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN};")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.lbl_layer_pill = QLabel("Prêt")
        self.lbl_layer_pill.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_layer_pill.setStyleSheet(
            f"background-color: {CertusTheme.PRIMARY}; color: white; "
            "padding: 4px 12px; border-radius: 12px;"
        )
        header_layout.addWidget(self.lbl_layer_pill)
        root_layout.addLayout(header_layout)

        # 2. Carte de résumé (KPIs)
        kpi_card = QFrame()
        kpi_card.setStyleSheet(
            f"background-color: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; "
            "border-radius: 8px; padding: 6px;"
        )
        kpi_layout = QHBoxLayout(kpi_card)
        kpi_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_kpi_progress = QLabel("Progression : 0 / 0 couches (0%)")
        self.lbl_kpi_progress.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_kpi_progress.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN};")
        kpi_layout.addWidget(self.lbl_kpi_progress)

        kpi_layout.addStretch()

        self.lbl_kpi_thick = QLabel("Épaisseur totale : 0.0 nm")
        self.lbl_kpi_thick.setFont(QFont("Segoe UI", 9))
        self.lbl_kpi_thick.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")
        kpi_layout.addWidget(self.lbl_kpi_thick)

        root_layout.addWidget(kpi_card)

        # 3. Zone de défilement des couches
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {CertusTheme.BACKGROUND}; border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; }}"
        )

        self.layers_container = QWidget()
        self.layers_layout = QVBoxLayout(self.layers_container)
        self.layers_layout.setContentsMargins(8, 8, 8, 8)
        self.layers_layout.setSpacing(6)
        self.layers_layout.addStretch()

        self.scroll_area.setWidget(self.layers_container)
        root_layout.addWidget(self.scroll_area, 1)

    def has_stack(self) -> bool:
        return len(self.layer_cards) > 0

    def init_stack_from_table(self, table: Any, l0: float = 550.0, h_mat: str = "H", l_mat: str = "L") -> None:
        """Initialiser la liste des couches à partir de la table du cockpit."""
        # Nettoyage précédent
        for card in self.layer_cards:
            card.deleteLater()
        self.layer_cards.clear()

        # Supprimer le stretch final temporairement
        while self.layers_layout.count():
            item = self.layers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        row_count = table.rowCount()
        self._total_layers = row_count
        self._total_thickness = 0.0

        n_h_approx = 2.35
        n_l_approx = 1.48

        for r in range(row_count):
            try:
                item_mat = table.item(r, 1)
                mat_str = item_mat.text().strip() if item_mat else ("H" if r % 2 == 0 else "L")
                item_mult = table.item(r, 2)
                mult = float(item_mult.text().strip()) if item_mult else 1.0
            except (ValueError, AttributeError):
                mat_str = "H" if r % 2 == 0 else "L"
                mult = 1.0

            n_val = n_h_approx if mat_str.upper() == "H" else n_l_approx
            th_nm = mult * (l0 / (4.0 * n_val))
            self._total_thickness += th_nm

            card = LayerCard(r + 1, mat_str, mult, th_nm, self.layers_container)
            self.layer_cards.append(card)
            self.layers_layout.addWidget(card)

        self.layers_layout.addStretch()
        self.lbl_kpi_thick.setText(f"Épaisseur totale : {self._total_thickness:.1f} nm ({row_count} couches)")
        self.lbl_kpi_progress.setText(f"Progression : 0 / {row_count} couches (0%)")
        self.lbl_layer_pill.setText(f"0 / {row_count}")

    @pyqtSlot(int, int, int)
    def update_progress(self, current_layer: int, total_layers: int, pct: int) -> None:
        """Mettre à jour la couche en cours d'analyse."""
        if total_layers <= 0:
            return

        self._current_layer = current_layer
        self.lbl_layer_pill.setText(f"Couche {current_layer} / {total_layers}")
        self.lbl_kpi_progress.setText(f"Progression : {current_layer} / {total_layers} couches ({pct}%)")

        for idx, card in enumerate(self.layer_cards):
            layer_num = idx + 1
            if layer_num < current_layer:
                card.set_state("done")
            elif layer_num == current_layer:
                card.set_state("active")
                # Auto-scroll intelligent centré sur la couche active
                try:
                    target_y = card.pos().y() + card.height() // 2 - self.scroll_area.viewport().height() // 2
                    v_bar = self.scroll_area.verticalScrollBar()
                    if v_bar:
                        v_bar.setValue(max(0, target_y))
                    else:
                        self.scroll_area.ensureWidgetVisible(card, 0, 80)
                except Exception:
                    self.scroll_area.ensureWidgetVisible(card, 0, 80)
            else:
                card.set_state("pending")

    def mark_phase_a_complete(self) -> None:
        """Marquer toutes les couches comme admissibles une fois la Phase A terminée."""
        for card in self.layer_cards:
            card.set_state("done")

    def update_phase_b_progress(self, message: str, pct: int) -> None:
        """Afficher l'avancement de la Phase B (optimisation par blocs)."""
        self.mark_phase_a_complete()
        self.lbl_title.setText("OPTIMIZATION — Phase B : Groupement en blocs & Robustesse")
        self.lbl_layer_pill.setText("Phase B en cours")
        self.lbl_layer_pill.setStyleSheet(
            "background-color: #059669; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;"
        )
        self.lbl_kpi_progress.setText(f"{message} ({pct}%)")
        self.lbl_kpi_thick.setText(f"✓ Phase A validée : {len(self.layer_cards)}/{len(self.layer_cards)} couches admissibles")
