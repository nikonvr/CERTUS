from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_strat_mixins_ui import CertusWindowSpyMixin
from certus.core.certus_strat_core import _compute_strategy_symmetry_score_percent
# Crash tolerance threshold, 👤 "5% lost deposition is perfect". Imported
#rather than copied: a column that colorizes using a threshold other than the one that
# ELIMINATES would lie to the operator.
from certus.core.certus_strat_robustness import CRASH_RATE_TOLERANCE

class StrategiesTableWindow(CertusWindowSpyMixin, QMainWindow):
    strategy_selected = pyqtSignal(int, object)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategiesTableWindow.closeEvent() title='%s' id=%s geometry=%s visible=%s selected_row=%s rows=%s",
            self.windowTitle(), id(self), self.geometry(), self.isVisible(),
            getattr(self, "selected_row", -1),
            self.table.rowCount() if hasattr(self, "table") else "n/a",
        )
        super().closeEvent(event)

    def __init__(
        self,
        parent,
        strategies_results: list[dict[str, Any]],
        p_thick_nominal: list[float],
        include_secondary_rmse_stats: bool = False,
    ) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategiesTableWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.p_thick_nominal = np.array(p_thick_nominal, dtype=np.float64)

        self.strategies_results = strategies_results

        self.include_secondary_rmse_stats = bool(include_secondary_rmse_stats)

        self._details_dialogs: list[Any] = []

        self.selected_row = -1

        self.setWindowTitle("Dual-Objective Strategies Comparison (+ SEEL Colors)")

        screen = QApplication.primaryScreen().availableGeometry()

        w_win = min(1800, int(screen.width() * 0.95))

        h_win = min(800, int(screen.height() * 0.85))

        self.resize(w_win, h_win)

        self.move((screen.width() - w_win) // 2, (screen.height() - h_win) // 2)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        logo_container = QWidget()

        logo_layout = QHBoxLayout(logo_container)

        logo_layout.setContentsMargins(5, 5, 0, 0)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            logo_layout.addWidget(mini_logo)

        else:
            lbl_fallback = QLabel("CERTUS")

            lbl_fallback.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 14px;")

            logo_layout.addWidget(lbl_fallback)

        logo_layout.addStretch()

        layout.addWidget(logo_container)

        title_label = QLabel("All Strategies Robustness Test - Detailed Breakdown")

        title_label.setStyleSheet(
            f"font-size: 17px; font-weight: 800; padding: 10px 10px 6px 10px; color: {CertusTheme.TEXT_MAIN};"
        )

        layout.addWidget(title_label)

        self.origin_summary_label = QLabel("Origins: -")

        self.origin_summary_label.setStyleSheet(
            f"font-size: 12px; color: {CertusTheme.TEXT_SUB}; padding: 2px 10px 8px 10px;"
        )

        layout.addWidget(self.origin_summary_label)

        self.table = ExcelTableWidget()

        self.table.cellClicked.connect(self.on_cell_clicked)

        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.update_data(strategies_results)

        layout.addWidget(self.table)

        button_layout = QHBoxLayout()

        save_strat_btn = create_styled_button("Save Selected Strategy (JSON)", variant="success")

        save_strat_btn.setToolTip(
            "Save the currently selected strategy row as a JSON file.\n"
            "Click a row first to select it, then click this button."
        )

        save_strat_btn.clicked.connect(self.save_current_strategy)

        button_layout.addWidget(save_strat_btn)

        export_btn = create_styled_button("Export to CSV", variant="secondary")

        export_btn.setToolTip("Export the full strategies table to a CSV file (all rows and columns).")

        export_btn.clicked.connect(self.handle_export_csv)

        close_btn = create_styled_button("Close", variant="secondary")

        close_btn.setToolTip("Close this strategies comparison window.")

        close_btn.clicked.connect(self.close)

        button_layout.addWidget(export_btn)

        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _calculate_worst_layers(self, strategy_result, top_k=10) -> Any:

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            if not results_per_noise:
                return ["No Res"] * top_k

            target_res = results_per_noise[0]

            for r in results_per_noise:
                if abs(r.get("noise_level", 0) - 1.0) < 0.1:
                    target_res = r

                    break

            thicknesses_all = target_res.get("thicknesses_all", [])

            if not thicknesses_all:
                return ["No Data"] * top_k

            min_len = min(len(row) for row in thicknesses_all)

            if min_len == 0:
                return ["Empty"] * top_k

            clean_data = [row[:min_len] for row in thicknesses_all]

            sim_matrix = np.array(clean_data, dtype=np.float64)

            nom_arr = self.p_thick_nominal

            if nom_arr is None or len(nom_arr) == 0:
                return [f"Ref:0 vs Sim:{min_len}"] + ["-"] * (top_k - 1)

            common_layers = min(sim_matrix.shape[1], len(nom_arr))

            if common_layers == 0:
                return ["0 Layers"] * top_k

            sim_matrix_sliced = sim_matrix[:, :common_layers]

            nom_arr_sliced = nom_arr[:common_layers]

            abs_errors = np.abs(sim_matrix_sliced - nom_arr_sliced)

            p95_errors = np.percentile(abs_errors, 95, axis=0)

            layer_stats = []

            for i, err in enumerate(p95_errors):
                layer_stats.append((i + 1, err))

            layer_stats.sort(key=lambda x: x[1], reverse=True)

            output = []

            for i in range(top_k):
                if i < len(layer_stats):
                    l_idx, err_val = layer_stats[i]

                    output.append(f"L{l_idx} {err_val:.2f}nm")

                else:
                    output.append("")

            return output

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            return [str(e)[:15]] * top_k

    def _populate_table_row(
        self, row: int, result: dict[str, Any], strat: dict[str, Any], max_blocks: int, _rmse_to_seel: Any
    ) -> None:
        """Helper method to populate a single row in the strategies table."""
        # 0: Rank
        rank_item = NumericTableWidgetItem(str(row + 1))
        rank_item.setData(Qt.ItemDataRole.UserRole, result)
        rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if row == 0:
            rank_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 0, rank_item)

        # 1: ID
        id_item = NumericTableWidgetItem(str(strat["strategy_id"]))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, id_item)

        # 2: Origin
        origin = strat.get("origin", "unknown").upper()
        display_text = origin.split("(")[0].strip()
        origin_item = QTableWidgetItem(display_text)
        origin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if any(x in origin for x in ["SMART", "DEEP", "MERGE", "HYBRID"]):
            origin_item.setBackground(QColor(CertusTheme.INFO_BG))
            origin_item.setForeground(QColor(CertusTheme.INFO_TEXT))
            origin_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
            origin_item.setToolTip(f"✨ {origin}")
        else:
            origin_item.setForeground(QColor(80, 80, 80))
            origin_item.setToolTip(origin)
        self.table.setItem(row, 2, origin_item)

        # 3: Min Res
        min_res = result.get("min_resolution", 999.0)
        res_val_str = f"{min_res:.2f}" if min_res < 100 else ">100"
        res_item = NumericTableWidgetItem(res_val_str)
        res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if min_res < 0.5:
            res_item.setBackground(QColor(CertusTheme.DANGER_BG))
        elif min_res < 1.5:
            res_item.setBackground(QColor(CertusTheme.WARNING_BG))
        else:
            res_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        limiting = result.get("limiting_layer", "?")
        res_item.setToolTip(f"Limiting Factor: Layer #{limiting}")
        self.table.setItem(row, 3, res_item)

        # 4 & 5: Ranks
        th_rank = strat.get("thickness_rank", None)
        self.table.setItem(row, 4, NumericTableWidgetItem(str(th_rank) if th_rank is not None else "N/A (not calculated)"))
        sp_rank = strat.get("spectral_rank", None)
        self.table.setItem(row, 5, NumericTableWidgetItem(str(sp_rank) if sp_rank is not None else "N/A (not calculated)"))

        # 6 & 7: Blocks / Changes
        self.table.setItem(row, 6, NumericTableWidgetItem(str(strat["n_blocks"])))
        actual_changes = strat["n_blocks"] - 1
        violated = strat.get("constraint_violated", False)
        changes_item = NumericTableWidgetItem(str(actual_changes))
        if violated:
            changes_item.setText(f"{actual_changes} (⚠️)")
            changes_item.setBackground(QColor(CertusTheme.DANGER_BG))
        self.table.setItem(row, 7, changes_item)

        # 8: Unique Lambda
        self.table.setItem(row, 8, NumericTableWidgetItem(str(result["num_unique_wavelengths"])))

        # 9: YIELD — primary metric, BEFORE score
        # Displayed as first numerical column before RMSE for operator decision-making.
        crash_rate = float(result.get("crash_rate", 0.0) or 0.0)
        yield_pct = 100.0 * (1.0 - crash_rate)
        yield_item = NumericTableWidgetItem(f"{yield_pct:.1f}")
        causes = result.get("crash_causes") or {}
        yield_item.setToolTip(
            "Depositions completing successfully, out of 100.\n"
            f"Non-completion rate: {crash_rate:.2%}\n"
            "\nThe three failure modes, separately:\n"
            f"  level never reached       : {float(causes.get('p_level_unreachable', 0.0)):.2%}\n"
            f"  divergent TP count        : {float(causes.get('p_tp_miscount', 0.0)):.2%}\n"
            f"  non-monotonic T(d)        : {float(causes.get('p_non_monotonic', 0.0)):.2%}\n"
            "\nA lost run and an out-of-spec filter are the same failure, but not the same\n"
            "cost: one costs machine time, the other costs material and is discovered late."
        )
        # 👤 "5% lost deposition is perfect": the tolerance threshold is set at 95%.
        if crash_rate >= CRASH_RATE_TOLERANCE:
            yield_item.setBackground(QColor(CertusTheme.DANGER_BG))
            yield_item.setForeground(QColor(CertusTheme.DANGER_TEXT))
        elif crash_rate > 0.0:
            yield_item.setBackground(QColor(CertusTheme.WARNING_BG))
            yield_item.setForeground(QColor(CertusTheme.WARNING_TEXT))
        else:
            yield_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
            yield_item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
        self.table.setItem(row, 9, yield_item)

        # 10: Robust Score
        score_item = NumericTableWidgetItem(f"{result['robustness_score']:.6f}")
        if row == 0:
            score_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 10, score_item)

        # 11: Symmetry Score [0..100]
        sym_score = strat.get("symmetry_score_pct", result.get("symmetry_score_pct", None))
        if sym_score is None:
            sym_score = _compute_strategy_symmetry_score_percent(
                strat.get("theoretical_layer_profile", []), SYM_DEFAULT_EXTREMA_WINDOW_OT
            )
        try:
            sym_score_f = float(sym_score)
        except (TypeError, ValueError):
            sym_score_f = 0.0
        sym_score_f = max(0.0, min(100.0, sym_score_f))
        sym_item = NumericTableWidgetItem(f"{sym_score_f:.1f}")
        sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        sym_item.setToolTip("Layer-by-layer symmetry score (0-100). 100 = perfect symmetry across the entire stack.")
        if sym_score_f >= 80.0:
            sym_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
            sym_item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
            sym_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
        elif sym_score_f >= 50.0:
            sym_item.setBackground(QColor(CertusTheme.WARNING_BG))
            sym_item.setForeground(QColor(CertusTheme.WARNING_TEXT))
        else:
            sym_item.setBackground(QColor(CertusTheme.DANGER_BG))
            sym_item.setForeground(QColor(CertusTheme.DANGER_TEXT))
        self.table.setItem(row, 11, sym_item)

        # 11: Comp. Factor
        comp_factor_str = "-"
        noise_results = result.get("results_per_noise", [])
        res_1x = next((r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1), None)
        if res_1x:
            try:
                th_data = res_1x.get("thicknesses_all", [])
                if th_data and self.p_thick_nominal is not None:
                    mat_sim = np.array(th_data)
                    limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))
                    diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])
                    avg_phys_err = np.mean(diffs)
                    rmse_val = res_1x.get("rmse_p95", res_1x.get("rmse_mean", 0.0))
                    seel_val = _rmse_to_seel(rmse_val)
                    if seel_val and seel_val > 1e-9:
                        ratio = avg_phys_err / seel_val
                        comp_factor_str = f"{ratio:.2f}"
            except (ValueError, TypeError, ZeroDivisionError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        comp_item = NumericTableWidgetItem(comp_factor_str)
        comp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        comp_item.setToolTip("Compensation Factor = Avg Phys Error / SEEL @ 1.0x Noise")
        if comp_factor_str != "-":
            val = float(comp_factor_str)
            if val > 1.5:
                comp_item.setForeground(QColor(CertusTheme.SUCCESS))
                comp_item.setFont(CertusTheme.get_font(weight=QFont.Weight.Bold))
            elif val < 0.8:
                comp_item.setForeground(QColor(CertusTheme.DANGER))
        self.table.setItem(row, 12, comp_item)

        # 12: Median extrema count per layer (theoretical)
        ext_counts = []
        for p in strat.get("theoretical_layer_profile", []):
            try:
                ext_counts.append(int(p.get("extrema_count", 0)))
            except (TypeError, ValueError):
                continue
        if ext_counts:
            ext_p50 = float(np.percentile(np.array(ext_counts, dtype=np.float64), 50))
            ext_item = NumericTableWidgetItem(f"{ext_p50:.1f}")
        else:
            ext_item = NumericTableWidgetItem("N/A")
        ext_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_item.setToolTip("Number of extrema computed on the theoretical noiseless curve")
        self.table.setItem(row, 13, ext_item)

        # 14, 15, 16: SEEL Columns (shifted by 1 due to Yield % column)
        for col_idx, noise_idx in enumerate([0, 1, 2]):
            target_col = 14 + col_idx
            if noise_idx < len(noise_results):
                rmse_val = noise_results[noise_idx].get("rmse_p95", noise_results[noise_idx]["rmse_mean"])
                seel_val = _rmse_to_seel(rmse_val)
                if seel_val is not None:
                    item_txt = f"{seel_val:.3f} nm"
                    item = NumericTableWidgetItem(item_txt)
                    item.setToolTip(f"Raw RMSE P95: {rmse_val:.6f}")
                    if seel_val < 0.3:
                        item.setBackground(QColor(CertusTheme.SUCCESS_BG))
                        item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif seel_val < 1.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    elif seel_val < 2.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    else:
                        item.setBackground(QColor(CertusTheme.DANGER_BG))
                        item.setForeground(QColor(CertusTheme.DANGER_TEXT))
                    self.table.setItem(row, target_col, item)
                else:
                    self.table.setItem(row, target_col, NumericTableWidgetItem(f"R:{rmse_val:.5f}"))
            else:
                self.table.setItem(row, target_col, QTableWidgetItem("N/A"))

        # Blocks
        start_col_blocks = 17  # 14 base columns + 3 SEEL
        blocks = strat.get("blocks", [])
        for b_idx in range(max_blocks):
            col_idx = start_col_blocks + b_idx
            if b_idx < len(blocks):
                block = blocks[b_idx]
                wl = block["wavelength"]
                l_start = block["start"] + 1
                l_end = block["end"]
                text_desc = f"{wl:.0f}nm (L{l_start}->L{l_end})"
                block_item = QTableWidgetItem(text_desc)
                block_item.setToolTip(f"Block #{b_idx + 1}\nWavelength: {wl}nm\nLayers: {l_start} to {l_end}")
                self.table.setItem(row, col_idx, block_item)
            else:
                self.table.setItem(row, col_idx, QTableWidgetItem(""))

        # Worst Layers
        start_col_errors = start_col_blocks + max_blocks
        worst_layers = self._calculate_worst_layers(result, top_k=10)
        for err_idx, text_val in enumerate(worst_layers):
            item = QTableWidgetItem(text_val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if "nm" in text_val:
                try:
                    val_part = text_val.split()[1].replace("nm", "")
                    val = float(val_part)
                    if val > 2.0:
                        item.setForeground(QColor(CertusTheme.DANGER))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif val > 1.0:
                        item.setForeground(QColor(CertusTheme.WARNING))
                except (ValueError, IndexError, AttributeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
            self.table.setItem(row, start_col_errors + err_idx, item)

    def update_data(self, strategies_results: list[dict[str, Any]]) -> float | None:
        """

        Update the strategies table with new results.

        This method updates the display table with optimization results including:

        - Strategy performance metrics

        - Layer thickness information

        - Error statistics and rankings

        - Table refresh and sorting

        Args:

            self: StrategiesTable instance

            strategies_results: List of strategy result dictionaries with performance data

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling for data processing

            - Updates table UI components

            - Handles large datasets efficiently

        """

        self.strategies_results = strategies_results

        self.table.setUpdatesEnabled(False)

        self.table.setSortingEnabled(False)

        # Internal helper for SEEL

        seel_data = APP_CONTEXT.get("seel_data")

        def _rmse_to_seel(rmse_val) -> float | None:

            if seel_data and "fit_alpha" in seel_data and "fit_k" in seel_data:
                alpha = seel_data["fit_alpha"]

                k = seel_data["fit_k"]

                return float(k * (rmse_val**alpha))

            if seel_data and "avg_rmse" in seel_data:
                seel_x = np.array(seel_data["avg_rmse"])

                seel_y = np.array(seel_data["sigmas"])

                idx = np.argsort(seel_x)

                return float(np.interp(rmse_val, seel_x[idx], seel_y[idx]))

            return None

        try:
            self.table.clearContents()

            self.table.setRowCount(len(strategies_results))

            origin_counts: dict[str, int] = {}

            for res in strategies_results:
                origin_raw = str(res.get("strategy", {}).get("origin", "UNKNOWN")).upper()

                origin_key = origin_raw.split("(")[0].strip() if origin_raw else "UNKNOWN"

                origin_counts[origin_key] = origin_counts.get(origin_key, 0) + 1

            if origin_counts:
                items = sorted(origin_counts.items(), key=lambda kv: (-kv[1], kv[0]))

                summary = " | ".join([f"{k}: {v}" for k, v in items])

                self.origin_summary_label.setText(f"Origins ({len(strategies_results)}): {summary}")

            else:
                self.origin_summary_label.setText("Origins: -")

            max_blocks = 0

            has_th_rank = False

            has_sp_rank = False

            for res in strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

                strat_local = res.get("strategy", {})

                if strat_local.get("thickness_rank", None) is not None:
                    has_th_rank = True

                if strat_local.get("spectral_rank", None) is not None:
                    has_sp_rank = True

            # --- HEADER DEFINITION (Modified) ---

            # Metric updated: Complexity out, Comp.Factor in

            base_headers = [
                "Rank",
                "ID",
                "Origin",
                "Min Res (nm)",
                "Th Rank",
                "Sp Rank",
                "Blocks",
                "Changes",
                "Unique lambda",
                "Yield %",
                "Robust Score",
                "Sym Score",
                "Comp. Factor",
                "Next",
            ]

            noise_headers = ["SEEL (0.5x)", "SEEL (1.0x)", "SEEL (2.0x)"]

            block_headers = [f"Block {i + 1}" for i in range(max_blocks)]

            error_headers = [f"Worst #{i + 1} (P95)" for i in range(10)]

            all_headers = base_headers + noise_headers + block_headers + error_headers

            self.table.setColumnCount(len(all_headers))

            self.table.setHorizontalHeaderLabels(all_headers)

            # --- HEADER TOOLTIPS ---

            _header_tips = {
                "Yield %": (
                    "Depositions completing successfully, out of 100 — THE top metric.\n"
                    "A deposition that does not complete is a lost run in the cleanroom, not a\n"
                    "quality compromise. Red beyond 5% loss: the strategy is\n"
                    "ELIMINATED from the ranking, regardless of its spectral performance.\n"
                    "Hover over a cell for details on the three failure modes."
                ),
                "Rank": "Global robustness ranking (1 = best). Sorted by Robust Score.",
                "ID": "Internal strategy identifier assigned during the Dynamic Programming search.",
                "Origin": "Algorithm that generated this strategy: DP (Dynamic Programming), "
                "SMART (elite candidate), HYBRID, MERGE, DEEP, etc.",
                "Min Res (nm)": "Minimum optical thickness resolution across all layers and blocks "
                "(nm). Low values = harder to hit the turning point precisely. "
                "<1.5 nm -> warning, <0.5 nm -> critical.",
                "Th Rank": "Thickness-based DP rank: strategies with smaller total thickness "
                "cost get a lower rank (hidden if not computed).",
                "Sp Rank": "Spectral-sensitivity DP rank: strategies with more stable spectral "
                "response near turning points get a lower rank (hidden if not computed).",
                "Blocks": "Number of monochromatic monitoring blocks. Each block = one "
                "monitoring wavelength covering one or more consecutive layers.",
                "Changes": "Number of wavelength changes (= Blocks - 1). ⚠️ if the maximum "
                "allowed changes constraint is violated.",
                "Unique lambda": "Number of distinct monitoring wavelengths used across all blocks.",
                "Robust Score": "Monte Carlo robustness score: mean RMSE of the final stack over "
                "many simulated depositions with Gaussian thickness noise. "
                "Lower = more robust. Primary sort key.",
                "Sym Score": "SYM (Symmetry) score: rewards strategies whose layer turning points "
                "are positioned far from optical extrema (local T maxima/minima), "
                "reducing sensitivity to deposition errors.",
                "Comp. Factor": "Complexity factor: composite metric balancing the number of blocks, "
                "wavelength changes, and optical sensitivity.",
                "Next": "Button to inspect this strategy in detail (spectral performance, "
                "layer-by-layer profile, extrema proximity).",
            }

            # SEEL columns

            for i, lbl in enumerate(noise_headers):
                level = ["0.5×", "1.0×", "2.0×"][i]

                _header_tips[lbl] = (
                    f"SEEL estimate at noise level {level}: equivalent production yield (%) "
                    f"predicted from the robustness RMSE via the SEEL calibration curve. "
                    f"Higher = better yield."
                )

            # Block columns

            for i in range(max_blocks):
                _header_tips[f"Block {i + 1}"] = (
                    f"Monitoring wavelength (nm) for block {i + 1}, covering the layer range "
                    f"[start … end]. Click the row to see the full block definition."
                )

            # Worst-layer columns

            for i in range(10):
                _header_tips[f"Worst #{i + 1} (P95)"] = (
                    f"Layer with the #{i + 1} highest thickness error at the 95th percentile "
                    f"across Monte Carlo simulations (noise level 1.0×). "
                    f"Format: L<index> <P95 error in nm>."
                )

            for col, label in enumerate(all_headers):
                tip = _header_tips.get(label)

                if tip:
                    item = self.table.horizontalHeaderItem(col)

                    if item:
                        item.setToolTip(tip)

            # --- END HEADER TOOLTIPS ---

            # Auto-hide row columns if no value is calculated.

            self.table.setColumnHidden(4, not has_th_rank)

            self.table.setColumnHidden(5, not has_sp_rank)

            for row, result in enumerate(strategies_results):
                strat = result["strategy"]
                self._populate_table_row(row, result, strat, max_blocks, _rmse_to_seel)

            # PERFORMANCE — single call replaces per-column loop
            # BUG HISTORY: earlier versions called
            #   for c in range(self.table.columnCount()):
            #       self.table.resizeColumnToContents(c)
            # on a table with 30-50+ columns.  Each call forces a full
            # layout pass, freezing the UI for ~1 s on large datasets.
            # RULE: always use the single ``resizeColumnsToContents()`` call;
            # it performs one layout pass for all columns at once.
            # DO NOT revert to the per-column loop.
            self.table.resizeColumnsToContents()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.getLogger("ThinFilm").error(f"Table update error: {e}")

            logging.getLogger("ThinFilm").error(traceback.format_exc())

        finally:
            self.table.setSortingEnabled(True)

            self.table.setUpdatesEnabled(True)

    def on_cell_clicked(self, row: int, col: int) -> Any:

        self.table.clearSelection()

        rank_item = self.table.item(row, 0)

        if not rank_item:
            return

        strategy_result = rank_item.data(Qt.ItemDataRole.UserRole)

        if not strategy_result and 0 <= row < len(self.strategies_results):
            # Fallback when Qt item user-data is unexpectedly missing after sorting/refresh.

            strategy_result = self.strategies_results[row]

        if not strategy_result:
            # Last fallback by strategy ID lookup from table column 1.

            id_item = self.table.item(row, 1)

            sid = str(id_item.text()).strip() if id_item else ""

            if sid:
                for res in self.strategies_results:
                    if str(res.get("strategy", {}).get("strategy_id", "")).strip() == sid:
                        strategy_result = res

                        break

        if strategy_result:
            self.strategy_selected.emit(row, strategy_result)

            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)

                if item:
                    item.setSelected(True)

            # --- POPUP EXTRA: THEORETICAL PROFILE BY LAYER ---

            strat = strategy_result.get("strategy", {})

            extrema_distances = strat.get("extrema_distances", [])

            theo_profile = strat.get("theoretical_layer_profile", [])

            if extrema_distances or theo_profile:
                msg = "Theoretical no-noise per-layer profile\n"

                msg += "Fields: Tinit, Textrema[], Tfinal, and distances to extrema (nm)\n\n"

                n_layers = max(len(extrema_distances), len(theo_profile))

                for i_layer in range(n_layers):
                    dists = extrema_distances[i_layer] if i_layer < len(extrema_distances) else {}

                    prof = theo_profile[i_layer] if i_layer < len(theo_profile) else {}

                    msg += f"--- Layer {i_layer + 1} ---\n"

                    # Distances to generic 15nm limit rule

                    def fmt_dist(v, sign="") -> Any:

                        return f"{sign}{v:.1f}nm (OT)" if v <= 15.0 else "not critical"

                    # Start (d=0)

                    msg += f"  Start (d=0): Prev Extrema @ {fmt_dist(dists.get('prev_start', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_start', 999), '+')}\n"

                    # End (d=d_nom)

                    msg += f"  End (d=nom): Prev Extrema @ {fmt_dist(dists.get('prev_end', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_end', 999), '+')}\n"

                    try:
                        t_init = prof.get("Tinit", None)

                        t_final = prof.get("Tfinal", None)

                        if t_init is not None:
                            msg += f"  Tinit:  {float(t_init) * 100:.3f}%\n"

                        if t_final is not None:
                            msg += f"  Tfinal: {float(t_final) * 100:.3f}%\n"

                        near_type = str(prof.get("nearest_end_type", "between"))

                        near_dist = float(prof.get("nearest_end_dist_nm", np.nan))

                        tf_class = str(prof.get("tfinal_class", "between"))

                        if np.isfinite(near_dist):
                            msg += f"  Tfinal class: {tf_class} (nearest {near_type}, d={near_dist:.2f}nm)\n"

                    except (TypeError, ValueError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    extrema_list = prof.get("Textrema", [])

                    if extrema_list:
                        msg += "  Textrema:\n"

                        max_show = 12

                        for e_idx, e in enumerate(extrema_list[:max_show], 1):
                            e_type = str(e.get("type", "?"))

                            e_d = float(e.get("d_nm", np.nan))

                            e_t = float(e.get("T", np.nan))

                            msg += f"    {e_idx:02d}. {e_type} @ d={e_d:.2f}nm -> T={e_t * 100:.3f}%\n"

                        if len(extrema_list) > max_show:
                            msg += f"    ... {len(extrema_list) - max_show} more extrema\n"

                    else:
                        msg += "  Textrema: none detected on [0, d_nom]\n"

                    msg += "\n"

                # We use a custom QDialog with QTextEdit for scrollable text if there are many layers

                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

                dlg = QDialog(self)

                dlg.setWindowTitle(f"Extrema Proximity - Strategy {strat.get('strategy_id', 'Unknown')}")

                dlg.resize(400, 500)

                dlg_layout = QVBoxLayout(dlg)

                txt_edit = QTextEdit()

                txt_edit.setReadOnly(True)

                txt_edit.setText(msg)

                # Use a monospaced font for better alignment

                font = txt_edit.font()

                font.setFamily("Consolas")

                txt_edit.setFont(font)

                dlg_layout.addWidget(txt_edit)

                btn = QPushButton("Close")

                btn.setToolTip("Close the proximity extrema dialog.")

                btn.clicked.connect(dlg.accept)

                dlg_layout.addWidget(btn)

                # Non-modal popup so strategy monitoring windows can open immediately.

                dlg.setModal(False)

                dlg.show()

                dlg.raise_()

                dlg.activateWindow()

                self._details_dialogs.append(dlg)

                def _remove_details_dialog(*_args, dialog=dlg) -> None:
                    if dialog in self._details_dialogs:
                        self._details_dialogs.remove(dialog)

                dlg.finished.connect(_remove_details_dialog)

    def save_current_strategy(self) -> None:

        current_row = self.table.currentRow()

        if current_row < 0:
            logging.getLogger("ThinFilm").warning("No strategy selected to save.")

            return

        rank_item = self.table.item(current_row, 0)

        if not rank_item:
            return

        result_obj = rank_item.data(Qt.ItemDataRole.UserRole)

        if not result_obj or "strategy" not in result_obj:
            return

        strategy_data = result_obj["strategy"]

        strat_id = strategy_data.get("strategy_id", "unknown")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Strategy #{strat_id}",
            str(Path(get_certus_last_dir() or ".") / f"strategy_{strat_id}.json"),
            "JSON Files (*.json)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(strategy_data, f, indent=4, default=numpy_encoder)

                logging.getLogger("ThinFilm").info(f"✓ Strategy #{strat_id} saved to {filename}")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error saving strategy: {e}")

    def handle_export_csv(self) -> None:

        max_blocks = 0

        if self.strategies_results:
            for res in self.strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

        self.export_csv(self.strategies_results, max_blocks)

    def export_csv(self, strategies_results, max_blocks) -> None:


        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Strategies Results",
            str(Path(get_certus_last_dir() or ".") / "strategies_stats.csv"),
            "CSV Files (*.csv)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                data = []

                for rank, result in enumerate(strategies_results, 1):
                    strat = result["strategy"]

                    noise_results = result.get("results_per_noise", [])

                    origin = strat.get("origin", "unknown")

                    # Calc Comp.Factor (matches update_data)

                    comp_factor = ""

                    res_1x = next(
                        (r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1),
                        None,
                    )

                    if res_1x and self.p_thick_nominal is not None:
                        try:
                            th_data = res_1x.get("thicknesses_all", [])

                            if th_data:
                                mat_sim = np.array(th_data)

                                limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))

                                diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])

                                avg_phys_err = np.mean(diffs)

                                seel_data = APP_CONTEXT.get("seel_data")

                                rmse_val = res_1x.get("rmse_p95", res_1x["rmse_mean"])

                                seel_val = None

                                if seel_data and "fit_alpha" in seel_data:
                                    seel_val = seel_data["fit_k"] * (rmse_val ** seel_data["fit_alpha"])

                                if seel_val and seel_val > 1e-9:
                                    comp_factor = f"{avg_phys_err / seel_val:.4f}"

                        except (KeyError, TypeError, ZeroDivisionError):
                            # Skip if calculation fails

                            pass

                    row = {
                        "Rank": rank,
                        "Strategy_ID": strat["strategy_id"],
                        "Origin": origin.upper(),
                        "Min_Resolution_nm": result.get("min_resolution", ""),
                        "Limiting_Layer": result.get("limiting_layer", ""),
                        "Thickness_Rank": strat.get("thickness_rank", ""),
                        "Spectral_Rank": strat.get("spectral_rank", ""),
                        "Blocks": strat["n_blocks"],
                        "Wavelength_Changes": strat["n_blocks"] - 1,
                        "Unique_Wavelengths": result.get("num_unique_wavelengths", 0),
                        # “Complexity” REMOVED
                        "Robustness_Score": f"{result['robustness_score']:.6f}",
                        "Symmetry_Score_0_100": f"{float(strat.get('symmetry_score_pct', result.get('symmetry_score_pct', 0.0))):.1f}",
                        "Compensation_Error_Factor": comp_factor,
                    }

                    for idx, noise_res in enumerate(noise_results):
                        row[f"Noise_{idx}_Level_%"] = noise_res["noise_level"]

                        row[f"Noise_{idx}_RMSE_P95"] = f"{noise_res.get('rmse_p95', noise_res['rmse_mean']):.6f}"

                        if self.include_secondary_rmse_stats:
                            row[f"Noise_{idx}_RMSE_Mean"] = f"{noise_res['rmse_mean']:.6f}"

                            row[f"Noise_{idx}_RMSE_Std"] = f"{noise_res['rmse_std']:.6f}"

                    blocks = strat.get("blocks", [])

                    for i in range(max_blocks):
                        key = f"Block_{i + 1}"

                        if i < len(blocks):
                            b = blocks[i]

                            row[key] = f"{b['wavelength']:.0f}nm (L{b['start'] + 1}->L{b['end']})"

                        else:
                            row[key] = ""

                    worst_layers = self._calculate_worst_layers(result, top_k=10)

                    for i, txt in enumerate(worst_layers):
                        row[f"Worst_Err_P95_{i + 1}"] = txt

                    data.append(row)

                # to_csv_robust: handles commas

                to_csv_robust(pd.DataFrame(data), filename, index=False)

                logging.getLogger("ThinFilm").info(f"✓ Strategies results exported to '{filename}'")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error exporting CSV: {e}")

