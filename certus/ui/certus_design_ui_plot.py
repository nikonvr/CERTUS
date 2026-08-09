from __future__ import annotations
from certus.ui.certus_design_common import *

class PlotManager:
    def __init__(self, ui):
        self.ui = ui
    """Mixin class isolating plot and pareto functionality."""

    def _finish_pareto_decimation(self) -> None:
        """Clean up after decimation loop."""

        self.ui._decimation_polishing = False

        self.ui._set_busy(False)

        self.ui.log(
            f"▼ Pareto Decimation complete: {len(self.ui.pareto_history)} layer counts recorded",
            "SUCCESS",
        )

    def _export_pareto_report(self) -> None:
        """Export a grouped HTML report summarizing the full Pareto front."""

        try:

            from certus.core.certus_core import get_resource_path

            if not self.ui.pareto_history:
                return

            reports_dir = get_resource_path("reports")

            os.makedirs(reports_dir, exist_ok=True)

            ts = certus_timestamp_file()

            filename = str(Path(reports_dir) / f"Pareto_Summary_{ts}.html")

            manifest_dict: dict[str, Any] = {}
            try:
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                seed_val = None
                for _seed_candidate in (
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                ):
                    if _seed_candidate is None:
                        continue
                    try:
                        seed_val = int(_seed_candidate)
                        break
                    except (TypeError, ValueError):
                        continue
                svc = IndexFitService(runner=lambda _cfg: dict(getattr(self, "pareto_history", {}) or {}))
                req = IndexFitRequest(
                    config={
                        "module": "CERTUS_DESIGN",
                        "export_kind": "pareto_summary",
                        "pareto_count": int(len(self.ui.pareto_history)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "filename", "") or "").strip(),
                            str(getattr(self, "_last_config_file", "") or "").strip(),
                        )
                        if p
                    ],
                    seed=seed_val,
                    app_id="CERTUS_DESIGN",
                    app_version=__version__,
                    warnings=list(getattr(self, "validation_warnings", []) or []),
                    status=status_val,
                )
                manifest_dict = svc.fit(req).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.ui.log(f"Pareto manifest generation failed: {exc}", "WARNING")
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.ui.log(
                    "Pareto report blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
                    "WARNING",
                )
                return

            # =====================================================================

            # BARRIER: HTML Report Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

            # =====================================================================

            # Build summary table rows

            rows = []

            for N in sorted(self.ui.pareto_history.keys()):
                rec = self.ui.pareto_history[N]

                best_rmse = rec.get("best_rmse", float("inf"))

                best_mc = rec.get("best_mc", float("inf"))

                best_fab = rec.get("best_fab", float("inf"))

                dmin_r = rec.get("dmin_rmse", 0.0)

                dmin_m = rec.get("dmin_mc", 0.0)

                dmin_f = rec.get("dmin_fab", 0.0)

                rmse_per_n = best_rmse / N if N > 0 and best_rmse < float("inf") else float("inf")

                # Fabricability flags

                fab_ok_fab = dmin_f >= 5.0 and best_fab < float("inf")

                rows.append(
                    [
                        str(N),
                        f"{best_rmse:.6f}" if best_rmse < float("inf") else "-",
                        f"{dmin_r:.1f}",
                        f"{best_mc:.6f}" if best_mc < float("inf") else "-",
                        f"{dmin_m:.1f}",
                        f"{best_fab:.6f}" if best_fab < float("inf") else "-",
                        f"{dmin_f:.1f}" if dmin_f > 0 else "-",
                        f"{rmse_per_n * 1000:.4f}" if rmse_per_n < float("inf") else "-",
                        "✅" if fab_ok_fab else ("⚠️" if best_fab < float("inf") else "-"),
                    ]
                )

            # =====================================================================

            sections = [
                {
                    "title": "Pareto Front - Panel of optimized designs",
                    "type": "text",
                    "content": (
                        f"Smart decimation: {len(self.ui.pareto_history)} designs registered. "
                        f"Reference RMSE: {getattr(self.ui, '_workflow_best_rmse', 0):.6f}. "
                        f"RMSE/N×1000 = efficiency (lower = better complexity/performance). "
                        f"✅ = fabricable (d_min >= 5nm)."
                    ),
                },
                {
                    "title": "Summary table",
                    "type": "table",
                    "headers": [
                        "N",
                        "Best RMSE",
                        "d_min(nm)",
                        "Best MC +/-0.3nm",
                        "d_min MC(nm)",
                        "Best Fab",
                        "d_min Fab(nm)",
                        "RMSE/N×1000",
                        "Fab",
                    ],
                    "rows": rows,
                },
                {
                    "title": "Run Manifest",
                    "type": "table",
                    "headers": ["Key", "Value"],
                    "rows": [[str(k), str(v)] for k, v in manifest_dict.items()],
                },
            ]

            ok = generate_html_report(filename, "CERTUS - Pareto Front Summary", sections)

            if ok:
                self.ui.log(f"📄 Pareto report: {Path(filename).name}", "SUCCESS")

            else:
                self.ui.log("Pareto report generation failed", "WARNING")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.ui.log(f"Pareto report error: {e}", "WARNING")



    def _clear_pareto(self) -> None:

        self.ui.pareto_history = {}

        self.ui._decimation_done = False

        self._refresh_pareto_table()

    def _load_pareto_design(self, row: int, col: int) -> None:

        try:
            N = int(self.ui.pareto_table.item(row, 0).text())

            rec = self.ui.pareto_history[N]

            # col 1-2 = load best RMSE; col 3-4 = load best MC; col 5-6 = load best Fab

            load_mc = col >= 3 and col <= 4

            load_fab = col >= 5 and col <= 6

            if load_fab and rec.get("ep_fab") is not None:
                self._restore_pareto_champion(rec["table_fab"], rec["ep_fab"])

                self.ui.log(
                    f" Loaded FAB champion for N={N} (RMSE={rec['best_fab']:.6f}, d_min={rec['dmin_fab']:.1f}nm)",
                    "SUCCESS",
                )

            elif load_mc and rec.get("ep_mc") is not None:
                self._restore_pareto_champion(rec["table_mc"], rec["ep_mc"])

                self.ui.log(f"Loaded MC champion for N={N} (RMSE={rec['best_mc']:.6f})", "INFO")

            elif rec.get("ep_rmse") is not None:
                self._restore_pareto_champion(rec["table_rmse"], rec["ep_rmse"])

                self.ui.log(f"Loaded RMSE champion for N={N} (RMSE={rec['best_rmse']:.6f})", "INFO")

            # Switch view to Structure and run Eval to update plot

            self.ui.front_tabs.setCurrentIndex(0)

            self.ui._schedule_eval(True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.ui.log(f"Failed to load Pareto design: {e}", "ERROR")

    def _restore_pareto_champion(self, table_state: list[Dict[str, Any]], ep: np.ndarray) -> None:
        """Restore table state and current thicknesses from a stored Pareto champion."""
        self.ui._restore_table_state(table_state)
        self.ui.ep_current = ep.copy()
        self.ui._update_thickness_display()

    def _show_pareto_context_menu(self, pos) -> None:
        from PyQt6.QtWidgets import QMenu
        try:
            item = self.ui.pareto_table.itemAt(pos)
            if item is None:
                return
            row = item.row()
            N = int(self.ui.pareto_table.item(row, 0).text())
            
            menu = QMenu(self.ui.pareto_table)
            action = menu.addAction("Voir le catalogue...")
            res = menu.exec(self.ui.pareto_table.viewport().mapToGlobal(pos))
            if res == action:
                self._show_catalog_dialog(N)
        except Exception as e:
            self.ui.log(f"Context menu error: {e}", "ERROR")

    def _show_catalog_dialog(self, N: int) -> None:
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QDialogButtonBox, QLabel
        rec = self.ui.pareto_history.get(N)
        if not rec or "catalog" not in rec or not rec["catalog"]:
            self.ui.log("Catalogue vide pour ce nombre de couches.", "WARNING")
            return
            
        dialog = QDialog(self.ui.front_tabs)
        dialog.setWindowTitle(f"Pareto Catalog - {N} layers")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Available variants for N={N} (sorted by RMSE):"))
        
        list_widget = QListWidget()
        for idx, entry in enumerate(rec["catalog"]):
            rmse = entry.get("rmse", float('inf'))
            ep = entry.get("ep", [])
            stack = entry.get("stack", [])
            dmin = np.min(ep) if len(ep) > 0 else 0
            materials = "".join([s.mat for s in stack])
            
            desc = f"[{idx+1}] RMSE: {rmse:.6f} | d_min: {dmin:.1f}nm | {materials[:30]}..."
            list_widget.addItem(desc)
            
        layout.addWidget(list_widget)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dialog.reject)
        
        load_btn = QPushButton("Charger la configuration")
        btn_box.addButton(load_btn, QDialogButtonBox.ButtonRole.ActionRole)
        
        def on_load():
            selected = list_widget.currentRow()
            if selected >= 0 and selected < len(rec["catalog"]):
                entry = rec["catalog"][selected]
                self._restore_pareto_champion(entry["table"], entry["ep"])
                self.ui.log(f"Catalog: Configuration {selected+1} loaded for N={N} (RMSE={entry['rmse']:.6f})", "SUCCESS")
                self.ui.front_tabs.setCurrentIndex(0)
                self.ui._schedule_eval(True)
                dialog.accept()
                
        load_btn.clicked.connect(on_load)
        layout.addWidget(btn_box)
        
        dialog.exec()
        self.ui._use_exact_ep = True

    def _populate_pareto_table_row(self, row_index: int, n_layers: int, rec: Dict[str, Any]) -> None:
        """Render one row of the Pareto table, preserving fixed column semantics."""
        # Colonne 0: N
        i_layers = QTableWidgetItem(str(n_layers))
        i_layers.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_layers.setToolTip(
            "Double-click col.1-2 = load best theoretical\n"
            "Double-click col.3-4 = load best robust\n"
            "Double-click col.5-6 = load best manufacturable"
        )

        # Column 1: Best RMSE (theoretical, can be <5nm)
        i_rmse = QTableWidgetItem(f"{rec.get('best_rmse', float('inf')):.5f}")
        i_rmse.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_rmse.setToolTip("Best theoretical RMSE (may have layers < 5nm)")

        # Colonne 2: d_min RMSE
        dmin_rmse = rec.get("dmin_rmse", 0)
        i_dmin_rmse = QTableWidgetItem(f"{dmin_rmse:.1f}")
        i_dmin_rmse.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_rmse < 5.0:  # Visual warning if below critical 5nm limit
            i_dmin_rmse.setForeground(Qt.GlobalColor.red)
        i_dmin_rmse.setToolTip("Min. thickness of RMSE champion")

        # Column 3: Best MC (robust, can be <5nm)
        i_mc = QTableWidgetItem(f"{rec.get('best_mc', float('inf')):.5f}")
        i_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_mc.setToolTip("Best robust RMSE (MC +/-0.3nm)")

        # Colonne 4: d_min MC
        dmin_mc = rec.get("dmin_mc", 0)
        i_dmin_mc = QTableWidgetItem(f"{dmin_mc:.1f}")
        i_dmin_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_mc < 5.0:  # Visual warning if below critical 5nm limit
            i_dmin_mc.setForeground(Qt.GlobalColor.red)
        i_dmin_mc.setToolTip("Min. thickness of MC champion")

        # =====================================================================
        # BARRIER: Columns 5-6 - Best Fab (FABRICABLE) - CRITICAL LOGIC
        # =====================================================================
        best_fab = rec.get("best_fab", float("inf"))
        i_fab = QTableWidgetItem(f"{best_fab:.5f}" if best_fab < float("inf") else "-")
        i_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if best_fab < float("inf"):
            i_fab.setToolTip("Best manufacturable RMSE (all layers >= 5nm)")
            i_fab.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_fab.setToolTip("No manufacturable design found for this N")
            i_fab.setForeground(Qt.GlobalColor.gray)

        # Column 6: d_min Fab (must be >= 5.0 by definition)
        dmin_fab = rec.get("dmin_fab", 0)
        i_dmin_fab = QTableWidgetItem(f"{dmin_fab:.1f}" if dmin_fab > 0 else "-")
        i_dmin_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_fab >= 5.0:
            i_dmin_fab.setForeground(Qt.GlobalColor.darkGreen)
            i_dmin_fab.setToolTip("Min. thickness of manufacturable champion (>=5.0nm guaranteed)")
        else:
            i_dmin_fab.setForeground(Qt.GlobalColor.gray)
            i_dmin_fab.setToolTip("No manufacturable design")

        # Colonne 7: RMSE/N efficiency metric
        best_rmse_val = rec.get("best_rmse", float("inf"))
        rmse_per_n = best_rmse_val / n_layers if n_layers > 0 and best_rmse_val < float("inf") else float("inf")
        i_eff = QTableWidgetItem(f"{rmse_per_n * 1000:.4f}" if rmse_per_n < float("inf") else "-")
        i_eff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_eff.setToolTip("RMSE/N ×1000 - efficiency: lower = better complexity/performance balance")

        # =====================================================================
        # BARRIER: Column order - DO NOT MODIFY
        # =====================================================================
        self.ui.pareto_table.setItem(row_index, 0, i_layers)  # N
        self.ui.pareto_table.setItem(row_index, 1, i_rmse)  # Best RMSE
        self.ui.pareto_table.setItem(row_index, 2, i_dmin_rmse)  # d_min RMSE
        self.ui.pareto_table.setItem(row_index, 3, i_mc)  # Best MC
        self.ui.pareto_table.setItem(row_index, 4, i_dmin_mc)  # d_min MC
        self.ui.pareto_table.setItem(row_index, 5, i_fab)  # Best Fab
        self.ui.pareto_table.setItem(row_index, 6, i_dmin_fab)  # d_min Fab
        self.ui.pareto_table.setItem(row_index, 7, i_eff)  # RMSE/N

    def _refresh_pareto_table(self) -> None:

        # =====================================================================

        # BARRIER: Pareto Display Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

        # =====================================================================

        self.ui.pareto_table.setRowCount(0)

        sorted_keys = sorted(
            self.ui.pareto_history.keys(),
            key=lambda N: (self.ui.pareto_history[N].get("best_rmse", float("inf")), N)
        )
        for d, N in enumerate(sorted_keys):
            self.ui.pareto_table.insertRow(d)
            rec = self.ui.pareto_history[N]
            self._populate_pareto_table_row(d, N, rec)

    def _update_pareto_record(self, current_ep=None, current_rmse=None) -> None:
        """Records current configuration in Pareto history if strictly better.

        ==============================================================================

        BARRIER PROTECTION: DO NOT MODIFY THIS STRUCTURE WITHOUT UNDERSTANDING

        ==============================================================================

        Maintains THREE champions per layer count N:

          - 'best_rmse': lowest theoretical RMSE (can have layers < 5nm)

          - 'best_mc': lowest MC RMSE (most robust to +/-0.3nm thickness errors)

          - 'best_fab': lowest RMSE with ALL layers >= 5nm (manufacturable)

        IMPORTANT: best_fab guarantees that no layers < 5nm are stored

        =============================================================================="""

        if current_ep is None:
            current_ep = self.ui.ep_current

            if current_ep is None:
                return

        if current_rmse is None or not np.isfinite(current_rmse) or current_rmse < 0.0:
            return

        N = len(current_ep)

        rmse_val = current_rmse

        if rmse_val > 10.0:  # Relaxed to allow all reasonable designs
            return

        # Manufacturing rule: we tolerate everything in Pareto (> 0.1nm)

        # but we will display in red in the table if < 5nm.

        if isinstance(current_ep, list):
            current_ep = np.array(current_ep)

        if np.any(current_ep < 0.1):
            return

        # --- Compute MC RMSE ---
        mc_rmse = self._compute_pareto_mc_rmse(current_ep, rmse_val)

        # =====================================================================

        # BARRIER: Pareto History Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

        # =====================================================================

        rec = self.ui.pareto_history.setdefault(
            N,
            {
                "best_rmse": float("inf"),
                "ep_rmse": None,
                "table_rmse": None,
                "best_mc": float("inf"),
                "ep_mc": None,
                "table_mc": None,
                "best_fab": float("inf"),
                "ep_fab": None,
                "table_fab": None,
                "catalog": [],
            },
        )

        # =====================================================================

        updated = False

        # =====================================================================

        # BARRIER: 3-champion logic - DO NOT CHANGE ORDER

        # =====================================================================

        #Champion 1: best theoretical RMSE (can have layers < 5nm)
        if self._update_pareto_rmse_champion(rec, current_ep, rmse_val, mc_rmse):
            updated = True

        # Champion 2: best MC RMSE (most robust design)
        if self._update_pareto_mc_champion(rec, current_ep, mc_rmse):
            updated = True

        # =====================================================================

        # BARRIERE: Champion 3 - best_fab (FABRICABLE) - LOGIQUE CRITIQUE

        # =====================================================================

        # Only if ALL layers >= 5nm
        if self._update_pareto_fab_champion(rec, current_ep, rmse_val):
            updated = True

        # =====================================================================

        self._update_pareto_catalog(rec, current_ep, rmse_val, mc_rmse)

        if updated:
            self.ui.orchestrator.schedule_refresh_pareto_table()

    def _update_pareto_catalog(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        rmse_val: float,
        mc_rmse: float,
    ) -> None:
        """Maintain a catalogue of the best unique solutions for this layer count."""
        # Only keep interesting solutions (e.g., within 2x of best_rmse, or top 10)
        best_known = rec["best_rmse"]
        if rmse_val > best_known * 5.0 and len(rec["catalog"]) >= 10:
            return  # Not interesting enough compared to best
            
        # Check uniqueness (avoid saving almost identical arrays)
        for cat_item in rec["catalog"]:
            existing_ep = cat_item["ep"]
            if len(existing_ep) == len(current_ep):
                if np.max(np.abs(existing_ep - current_ep)) < 0.5:
                    # Very similar to an existing catalog entry, check if better
                    if rmse_val < cat_item["rmse"]:
                        cat_item["rmse"] = rmse_val
                        cat_item["mc_rmse"] = mc_rmse
                        cat_item["ep"] = current_ep.copy()
                    return

        # Add new item
        rec["catalog"].append({
            "rmse": rmse_val,
            "mc_rmse": mc_rmse,
            "ep": current_ep.copy(),
            "timestamp": time.time()
        })
        
        # Sort catalog by rmse and keep top 20
        rec["catalog"].sort(key=lambda x: x["rmse"])
        rec["catalog"] = rec["catalog"][:20]

    def _update_pareto_fab_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        rmse_val: float,
    ) -> bool:
        """Update manufacturable champion when all layers satisfy >=5nm."""
        is_fabricable = (current_ep is not None) and np.all(current_ep >= 5.0)
        if not is_fabricable or rmse_val >= rec["best_fab"] - 1e-6:
            return False

        rec["best_fab"] = rmse_val
        rec["ep_fab"] = current_ep.copy()
        rec["table_fab"] = self._build_pareto_table_state(current_ep)
        rec["dmin_fab"] = float(np.min(current_ep))  # >= 5.0 guaranteed
        return True

    def _update_pareto_mc_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        mc_rmse: float,
    ) -> bool:
        """Update the robust MC champion for this layer count."""
        if mc_rmse >= rec["best_mc"] - 1e-6:
            return False

        rec["best_mc"] = mc_rmse
        rec["ep_mc"] = current_ep.copy()
        rec["table_mc"] = self._build_pareto_table_state(current_ep)
        rec["dmin_mc"] = float(np.min(current_ep[current_ep > 0.01])) if np.any(current_ep > 0.01) else 0.0
        return True

    def _update_pareto_rmse_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        rmse_val: float,
        mc_rmse: float,
    ) -> bool:
        """Update the theoretical RMSE champion for this layer count."""
        if rmse_val >= rec["best_rmse"] - 1e-6:
            return False

        rec["best_rmse"] = rmse_val
        rec["ep_rmse"] = current_ep.copy()
        rec["table_rmse"] = self._build_pareto_table_state(current_ep)
        rec["mc_of_best_rmse"] = mc_rmse
        rec["dmin_rmse"] = float(np.min(current_ep[current_ep > 0.01])) if np.any(current_ep > 0.01) else 0.0
        return True

    def _compute_pareto_mc_rmse(self, current_ep: np.ndarray, rmse_val: float) -> float:
        """Estimate robust RMSE with lightweight MC sampling around current thicknesses."""
        mc_rmse = rmse_val
        local_seed = int(getattr(self, "run_seed", 0) or 0)
        rng = np.random.default_rng(local_seed)
        var_idx = self._pareto_variable_indices(current_ep)

        if len(var_idx) == 0:
            return mc_rmse

        def _compute_mc_evals(cost_func) -> Any:
            evals = []
            for _ in range(5):  # quick MC estimate
                noise = rng.normal(0, 0.3, size=current_ep.shape)
                noisy_ep = np.maximum(current_ep + noise, 0)
                try:
                    mse = cost_func(noisy_ep[var_idx])
                    if mse is not None and mse < 1e20:
                        evals.append(np.sqrt(mse))
                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ):
                    pass
            return evals

        if hasattr(self.ui, "optim_worker") and hasattr(self.ui.optim_worker, "cost_func"):
            mc_evals = _compute_mc_evals(self.ui.optim_worker.cost_func)
            if mc_evals:
                return float(np.mean(mc_evals))

        if hasattr(self.ui, "_last_cost_func") and self.ui._last_cost_func is not None:
            mc_evals = _compute_mc_evals(self.ui._last_cost_func)
            if mc_evals:
                return float(np.mean(mc_evals))

        return mc_rmse

    def _pareto_variable_indices(self, ep: np.ndarray) -> np.ndarray:
        """Return indices of variable layers from the current table state."""
        var_list: list[int] = []
        for r in range(min(len(ep), self.ui.front_table.rowCount())):
            var = True
            cw = self.ui.front_table.cellWidget(r, 3)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb:
                    var = cb.isChecked()
            if var:
                var_list.append(r)
        return np.array(var_list, dtype=np.int64)

    def _build_pareto_table_state(self, ep: np.ndarray) -> list[Dict[str, Any]]:
        """Rebuild table snapshot from thickness vector and current UI material/var states."""
        mats = self.ui._get_materials()
        l0 = self.ui.l0_spin.value()
        state: list[Dict[str, Any]] = []
        table_rows = self.ui.front_table.rowCount()

        for r in range(min(len(ep), table_rows)):
            mat = self.ui._safe_get_combo_text(r, 0)
            d_val = ep[r]

            mat_obj = mats.get(mat)
            n_val = 1.45
            if mat_obj:
                if hasattr(mat_obj, "n4"):
                    n_val = mat_obj.n4
                elif isinstance(mat_obj, dict):
                    n_val = mat_obj.get("n4", 1.45)

            qw_val = (4.0 * n_val * d_val) / l0 if abs(l0) > 1e-9 else 0.0

            var = True
            cw = self.ui.front_table.cellWidget(r, 3)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb:
                    var = cb.isChecked()

            state.append({"mat": mat, "qw": qw_val, "var": var})

        return state

    def _update_optim_live_plot_normal_mode(self, data: Dict, wls: np.ndarray) -> None:
        """Update live transmission curve and sampled optimization points in normal mode."""

        Ts = data["Ts"]

        if not hasattr(self.ui, "_live_curves") or "transmission" not in self.ui._live_curves:
            if not hasattr(self.ui, "_live_curves"):
                self.ui._live_curves = {}

            self.ui._live_curves["transmission"] = plot_widget_plot_finite(
                self.ui.spectrum_plot,
                wls,
                Ts,
                pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2.5),
                name="Transmission",
            )

        else:
            self.ui._live_curves["transmission"].setData(wls, Ts)

        detached_targets = self.ui._get_plot_targets("spectrum", self.ui.spectrum_plot)[1:]

        for widget in detached_targets:
            widget.plotItem.clear()

            plot_widget_plot_finite(
                widget,
                wls,
                Ts,
                pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2.5),
                name="Transmission",
            )

        active_tgts = [t for t in self.ui._get_tgts() if t.valid()]

        if active_tgts:
            mask = np.zeros(len(wls), dtype=bool)

            for t in active_tgts:
                mask |= (wls >= t.lmin) & (wls <= t.lmax)

            wls_filtered = wls[mask]

            Ts_filtered = Ts[mask]

            n_display_points = 50

            if len(wls_filtered) > n_display_points:
                clues = np.linspace(0, len(wls_filtered) - 1, n_display_points, dtype=int)

                wls_points = wls_filtered[clues]

                Ts_points = Ts_filtered[clues]

            else:
                wls_points = wls_filtered

                Ts_points = Ts_filtered

        else:
            wls_points = np.array([])

            Ts_points = np.array([])

        if len(wls_points) > 0:
            if not hasattr(self.ui, "_live_points") or self.ui._live_points is None:
                self.ui._live_points = plot_widget_plot_finite(
                    self.ui.spectrum_plot,
                    wls_points,
                    Ts_points,
                    pen=None,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=CertusTheme.ERROR,
                    name="Optim Points",
                    animate=False,
                )

            else:
                self.ui._live_points.setData(wls_points, Ts_points)

        elif hasattr(self.ui, "_live_points") and self.ui._live_points is not None:
            self.ui.spectrum_plot.removeItem(self.ui._live_points)

            self.ui._live_points = None

        self.ui.spectrum_plot.plotItem.setLabel("left", "Transmission", color="black", size="12pt")

        auto_scale = self.ui.auto_scale_y_check.isChecked() if hasattr(self.ui, "auto_scale_y_check") else True

        if not auto_scale:
            self.ui.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            self.ui._auto_scale_spectrum_y(Ts)

        self.ui._rebuild_target_scatter(wls, False)

    def _finalize_oblique_live_plot(self, active_curve_keys: set, wls: np.ndarray) -> None:
        """Finalize oblique live plot: cleanup, scaling, legend and redraw."""

        for curve_key in list(self.ui._live_curves.keys()):
            if curve_key not in active_curve_keys:
                self.ui.spectrum_plot.removeItem(self.ui._live_curves[curve_key])

                del self.ui._live_curves[curve_key]

        if hasattr(self.ui, "_live_points") and self.ui._live_points is not None:
            self.ui.spectrum_plot.removeItem(self.ui._live_points)

            self.ui._live_points = None

        self.ui.spectrum_plot.plotItem.setLabel("left", "R / T", color="black", size="12pt")

        auto_scale = self.ui.auto_scale_y_check.isChecked() if hasattr(self.ui, "auto_scale_y_check") else True

        if not auto_scale:
            self.ui.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            all_spectra = []

            for curve_key in self.ui._live_curves:
                _, y_data = self.ui._live_curves[curve_key].getData()

                if y_data is not None:
                    all_spectra.extend(y_data)

            if all_spectra:
                self.ui._auto_scale_spectrum_y(np.array(all_spectra))

        if not hasattr(self.ui.spectrum_plot.plotItem, "legend") or self.ui.spectrum_plot.plotItem.legend is None:
            self.ui.spectrum_plot.plotItem.addLegend(offset=(10, 10), labelTextSize="10pt")

        elif not self.ui.spectrum_plot.plotItem.legend.isVisible():
            self.ui.spectrum_plot.plotItem.legend.setVisible(True)

        self.ui._rebuild_target_scatter(wls, True)

        self.ui.spectrum_plot.update()

        self.ui.spectrum_plot.repaint()

    def _update_oblique_detached_plots(self, oblique_tgts: list, spectra_display: Dict, wls: np.ndarray) -> None:
        """Refresh detached spectrum widgets for oblique mode."""

        detached_targets = self.ui._get_plot_targets("spectrum", self.ui.spectrum_plot)[1:]

        for widget in detached_targets:
            widget.plotItem.clear()

        if not detached_targets:
            return

        for tgt in oblique_tgts:
            if not tgt.valid():
                continue

            sk3d = (tgt.angle, tgt.pol, tgt.include_backside)

            spec_key = sk3d if sk3d in spectra_display else (tgt.angle, tgt.pol)

            if spec_key not in spectra_display or tgt.target_type not in spectra_display[spec_key]:
                continue

            spectrum = spectra_display[spec_key][tgt.target_type]

            color = "#dc2626" if tgt.target_type == "R" else "#2563eb"

            label = f"{tgt.target_type}{tgt.pol} ({tgt.angle}°)"

            for widget in detached_targets:
                plot_widget_plot_finite(
                    widget,
                    wls,
                    spectrum,
                    pen=pg.mkPen(color, width=2.5),
                    name=label,
                )

    def _update_optim_live_plot_oblique_mode(self, data: Dict, wls: np.ndarray) -> None:
        """Update live oblique spectra and detached plots."""

        spectra_display = data.get("spectra_display", {})

        oblique_tgts = data.get("oblique_tgts", [])

        if not oblique_tgts:
            oblique_tgts = self.ui._get_oblique_tgts()

        if not hasattr(self.ui, "_oblique_spectrum_colors"):
            self.ui._oblique_spectrum_colors = {}

        else:
            self.ui._oblique_spectrum_colors.clear()

        if not hasattr(self.ui, "_live_curves"):
            self.ui._live_curves = {}

        active_curve_keys = set()

        color_idx = 0

        for tgt in oblique_tgts:
            if not tgt.valid():
                continue

            sk3 = (tgt.angle, tgt.pol, tgt.include_backside)

            spec_key = sk3 if sk3 in spectra_display else (tgt.angle, tgt.pol)

            if spec_key not in spectra_display:
                continue

            if tgt.target_type not in spectra_display[spec_key]:
                continue

            spectrum = spectra_display[spec_key][tgt.target_type]

            if tgt.target_type == "R":
                color = "#dc2626"

            else:
                color = "#2563eb"

            tgt_id = (tgt.angle, tgt.pol, tgt.target_type, tgt.lmin, tgt.lmax)

            self.ui._oblique_spectrum_colors[tgt_id] = color

            label = f"{tgt.target_type}{tgt.pol} ({tgt.angle}°)"

            curve_key = (tgt.angle, tgt.pol, tgt.target_type, tgt.include_backside)

            active_curve_keys.add(curve_key)

            if curve_key not in self.ui._live_curves:
                self.ui._live_curves[curve_key] = plot_widget_plot_finite(
                    self.ui.spectrum_plot,
                    wls,
                    spectrum,
                    pen=pg.mkPen(color, width=2.5),
                    name=label,
                )

            else:
                self.ui._live_curves[curve_key].setData(wls, spectrum)

            color_idx += 1

        self._update_oblique_detached_plots(oblique_tgts, spectra_display, wls)

        self._finalize_oblique_live_plot(active_curve_keys, wls)

    def _update_optim_live_profile_tabs(self, data: Dict) -> None:
        """Refresh profile and n(lambda) tabs during live optimization updates."""

        if "ep" not in data:
            return

        try:
            ep_back = data.get("ep_back")

            if ep_back is None:
                ep_back = getattr(self, "ep_back_current", None)

            self.ui._plot_profile(
                data["ep"],
                self.ui._get_front_stack(),
                ep_back,
                self.ui._get_back_stack(),
            )

            self.ui._plot_nk()

        except NUMERICAL_FAULT_EXCEPTIONS as profile_err:
            logging.debug(f"Live profile/nk update: {profile_err}")

    def _update_optim_live_plot_title(
        self,
        data: Dict,
        rmse_valid: bool,
        rmse: Any,
        evals: int,
        is_global_best: bool,
    ) -> None:
        """Update the spectrum plot title with current optimization status."""

        status = "★ NEW BEST" if is_global_best else "Optimizing"

        color = "#10b981" if is_global_best else "#f97316"

        n_points = self.ui.points_per_target_spin.value()

        n_total = len(self.ui._get_optim_wls())

        n_layers_disp = len(data["ep"]) if "ep" in data else 0

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            title_prefix = f"[{src_name}] " if src_name else ""

        except NUMERICAL_FAULT_EXCEPTIONS:
            title_prefix = ""

        rmse_str = f"{rmse:.6f}" if rmse_valid else "N/A"

        self.ui.spectrum_plot.plotItem.setTitle(
            f"{title_prefix}{status} | Layers: {n_layers_disp} | Evals: {evals} | RMSE:  {rmse_str} | Points/Target: {n_points} ({n_total} total)",
            color=color,
            size="11pt",
        )

    def _update_optim_live_plot(self, data: Dict) -> None:
        """Updates the graph with the current curve and displays the current iteration.

        Updates Spectrum, Profile and n(lambda) regardless of which tab is displayed."""

        wls = data.get("wls")
        if wls is None:
            wls = data.get("wavelengths")
        if wls is None:
            return

        oblique_mode = data.get("oblique_mode", False)

        rmse = data.get("rmse")
        import numpy as np
        rmse_valid = rmse is not None and not np.isnan(rmse)

        evals = data.get("evals", 0) + getattr(self, "accumulated_evals", 0)

        is_global_best = bool(data.get("is_global_best", False))


        # Initial Cleanup

        if not hasattr(self.ui, "_initial_cleared") or not self.ui._initial_cleared:
            items_to_keep = [
                self.ui.spectrum_plot.vLine,
                self.ui.spectrum_plot.hLine,
                self.ui.spectrum_plot.info_label,
            ]

            if self.ui.target_scatter is not None:
                items_to_keep.append(self.ui.target_scatter)

            for item in self.ui.spectrum_plot.plotItem.items[:]:
                if item not in items_to_keep:
                    self.ui.spectrum_plot.removeItem(item)

            self.ui._initial_cleared = True

            self.ui._live_curves = {}  # Dict to store curves in oblique mode

            self.ui._live_points = None

        # Display by mode

        if oblique_mode:
            self._update_optim_live_plot_oblique_mode(data, wls)

        else:
            self._update_optim_live_plot_normal_mode(data, wls)

        self.ui._refresh_optim_target_scatter_foreground()

        self._update_optim_live_plot_title(data, rmse_valid, rmse, evals, is_global_best)

        self._update_optim_live_profile_tabs(data)

    def _on_intermediate_spectrum(self, data: Dict) -> None:
        """Callback for intermediate spectral update"""

        if data.get("type") != "intermediate":
            return

        rmse = data.get("rmse")
        import numpy as np
        rmse_valid = rmse is not None and not np.isnan(rmse)

        evals = data.get("evals", 0) + getattr(self, "accumulated_evals", 0)


        if rmse_valid:
            workflow_best = getattr(self.ui, "_workflow_best_rmse", float("inf"))

            is_improved = rmse < workflow_best

            display_rmse = min(rmse, workflow_best)

            if is_improved:
                self.ui._workflow_best_rmse = rmse

                display_rmse = rmse

                if "ep" in data:
                    self.ui._update_pareto_record(data["ep"], rmse)

            if "ep" in data:
                self.ui._stack_info_best_ep = np.asarray(data["ep"]).flatten().copy()

                self.ui._stack_info_best_rmse = rmse

                now = getattr(self, "_stack_info_last_update", 0.0)


                t = time.time()

                if is_improved or (t - now) >= 1.0:
                    self.ui._stack_info_last_update = t

                    self.ui.orchestrator.schedule_update_substrate_info()

            self.ui.best_rmse_label.setText(f"Best RMSE: {display_rmse:.6f}")

            # Update convergence plot (monotonic best solution only)

            current_best = rmse

            if not hasattr(self.ui, "mse_data") or "errors" not in self.ui.mse_data:
                self.ui.mse_data = {"iterations": [], "errors": []}

            if self.ui.mse_data["errors"] and len(self.ui.mse_data["errors"]) > 0:
                previous_best = self.ui.mse_data["errors"][-1]

                if current_best > previous_best:
                    current_best = previous_best

            # Append only if improved or first point (to avoid flat lines filling memory?)

            # Actually, showing flat line is good to see iterations.

            self.ui.mse_data["iterations"].append(evals)

            self.ui.mse_data["errors"].append(current_best)

            # Force update on main plot

            try:
                self.ui.convergence_curve.setData(self.ui.mse_data["iterations"], self.ui.mse_data["errors"])

                # Update Detached Convergence Plots

                for widget in self.ui._get_plot_targets("convergence", self.ui.plot_convergence)[1:]:
                    items = widget.listDataItems()

                    if items:
                        items[0].setData(self.ui.mse_data["iterations"], self.ui.mse_data["errors"])

                    else:
                        # Should not happen if cloned correctly, but fallback

                        plot_widget_plot_finite(
                            widget,
                            self.ui.mse_data["iterations"],
                            self.ui.mse_data["errors"],
                            pen=pg.mkPen(CertusTheme.ERROR, width=2),
                            animate=False,
                        )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.warning(f"Failed to update convergence plot: {e}")

            try:
                self._update_optim_live_plot(data)

            except NUMERICAL_FAULT_EXCEPTIONS as live_e:
                logging.debug(f"Live plot update: {live_e}")

    def _plot_nk(self) -> None:
        """n(lambda) curves for design materials (2-point Cauchy model)."""

        mats = self.ui._get_materials()

        cols = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ACCENT,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.ERROR,
        ]

        w = np.linspace(380.0, 1000.0, 400)

        for plot_widget in self.ui._get_plot_targets("nk", self.ui.nk_plot):
            plot_widget.plotItem.clear()

            for i, (k, m) in enumerate(mats.items()):
                n_nominal = m.get_nk(w).real

                plot_widget_plot_finite(
                    plot_widget,
                    w,
                    n_nominal,
                    pen=pg.mkPen(cols[i % len(cols)], width=2),
                    name=k,
                )

    def _plot_profile(
        self,
        ep: np.ndarray,
        stack: list[Layer],
        ep_back: np.ndarray,
        stack_back: list[Layer],
    ) -> None:
        """Plots refractive index profile (Live update on detached) with throttling."""
        now = time.time()
        last_t = getattr(self, "_last_profile_plot_time", 0.0)
        self._pending_profile_args = (ep, stack, ep_back, stack_back)

        if now - last_t < 0.1:  # Limit to 10 FPS to prevent GUI lag
            if not hasattr(self, "_profile_timer"):
                self._profile_timer = QTimer(self.ui)
                self._profile_timer.setSingleShot(True)
                self._profile_timer.timeout.connect(self._on_deferred_profile_plot)
            if not self._profile_timer.isActive():
                self._profile_timer.start(100)
            return

        if hasattr(self, "_profile_timer"):
            self._profile_timer.stop()

        self._plot_profile_actual(ep, stack, ep_back, stack_back)

    def _on_deferred_profile_plot(self) -> None:
        args = getattr(self, "_pending_profile_args", None)
        if args is not None:
            self._plot_profile_actual(*args)

    def _plot_profile_actual(
        self,
        ep: np.ndarray,
        stack: list[Layer],
        ep_back: np.ndarray,
        stack_back: list[Layer],
    ) -> None:
        """Actual plotting logic for refractive index profile"""
        self._last_profile_plot_time = time.time()

        ep_len = len(ep) if ep is not None else None
        stack_len = len(stack) if stack else 0
        ep_back_len = len(ep_back) if ep_back is not None else None
        stack_back_len = len(stack_back) if stack_back else 0

        self.ui.log(
            (
                "[DESIGN.profile] plot requested | ep_len=%s | stack_len=%d | back_ep_len=%s | back_stack_len=%d"
            )
            % (
                ep_len,
                stack_len,
                ep_back_len,
                stack_back_len,
            ),
            "INFO",
        )

        if ep is None or not stack or ep_len != stack_len:
            self.ui.log(
                f"[DESIGN.profile] plot skipped: inconsistent front state (ep_len={ep_len}, stack_len={stack_len}) | "
                f"best_rmse={getattr(self.ui, '_best_eval_rmse', 'N/A')} | "
                f"wf_best={getattr(self.ui, '_workflow_best_rmse', 'N/A')} | "
                f"use_exact_ep={getattr(self.ui, '_use_exact_ep', False)}",
                "WARNING",
            )
            return

        for plot_widget in self.ui._get_plot_targets("profile", self.ui.profile_plot):
            try:
                plot_widget.plotItem.clear()

                mats = self.ui._get_materials()

                self.ui.log("[DESIGN.profile] materials loaded | keys=%s" % list(mats.keys()), "INFO")

                sub_key = "substrate" if "substrate" in mats else ("Substrate" if "Substrate" in mats else None)

                if sub_key is None:
                    self.ui.log("[DESIGN.profile] profile plot skipped: no substrate key in materials", "WARNING")

                    continue

                ns = mats[sub_key].n4

                x, y = [0.0, 0.0], [ns, mats[stack[0].mat].n4] if stack else [ns, 1.0]

                if ep is not None and len(ep) > 0:
                    cs = np.cumsum(ep)

                    n_vals = [mats[l.mat].n4 for l in stack]

                    # Protection against index out of bounds (oblique mode may have more thicknesses than layers)

                    n_layers = min(len(ep) - 1, len(n_vals) - 1)

                    for i in range(n_layers):
                        x.extend([cs[i], cs[i]])

                        y.extend([n_vals[i], n_vals[i + 1]])

                    if n_vals:
                        x.extend([cs[-1], cs[-1], cs[-1] + max(50.0, 0.1 * cs[-1])])

                        y.extend([n_vals[-1], 1.0, 1.0])

                else:
                    x, y = [0.0, 50.0], [ns, 1.0]

                self.ui.log(
                    f"[PROFILE] Plotting {len(x)} points, x range [{min(x):.1f},{max(x):.1f}], y range [{min(y):.2f},{max(y):.2f}]",
                    "INFO",
                )

                plot_widget_plot_finite(
                    self.ui.profile_plot,
                    x,
                    y,
                    pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                    fillLevel=0,
                    brush=(30, 58, 138, 30),
                )

                # Backside

                if self.ui.back_check.isChecked() and ep_back is not None and ep_back.size > 0 and stack_back:
                    xb, yb = [0.0, 0.0], [ns, mats[stack_back[0].mat].n4]

                    csb = np.cumsum(ep_back)

                    nb = [mats[l.mat].n4 for l in stack_back]

                    # Protection against index out of bounds

                    n_layers_back = min(len(ep_back) - 1, len(nb) - 1)

                    for i in range(n_layers_back):
                        xb.extend([csb[i], csb[i]])

                        yb.extend([nb[i], nb[i + 1]])

                    if nb:
                        xb.extend([csb[-1], csb[-1], csb[-1] + max(50.0, 0.1 * csb[-1])])

                        yb.extend([nb[-1], 1.0, 1.0])

                    off = max(x) + 100.0

                    plot_widget_plot_finite(
                        self.ui.profile_plot,
                        [v + off for v in xb],
                        yb,
                        pen=pg.mkPen(CertusTheme.ERROR, width=2),
                        fillLevel=0,
                        brush=(239, 68, 68, 30),
                    )

            except NUMERICAL_FAULT_EXCEPTIONS as _profile_ex:
                self.ui.log(f"[PROFILE] Exception in _plot_profile: {_profile_ex}", "INFO")

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """DESIGN specific plot info mapping."""

        if widget == self.ui.spectrum_plot:
            return "spectrum", "Spectrum (T)"

        elif widget == self.ui.profile_plot:
            return "profile", "Refractive Index Profile"

        elif widget == self.ui.nk_plot:
            return "nk", "Dispersion n(lambda)"

        elif widget == self.ui.color_plot:
            return "color", "CIE a*b* Diagram"

        elif widget == self.ui.plot_convergence:
            return "convergence", "Optimization Convergence"

        return None

    def _on_update_spectrum_y_scale_signal(self, *_args) -> None:

        self.ui._update_spectrum_y_scale()

    def _ensure_pareto_ui(self) -> bool:
        """Create Pareto window/table lazily and only when Qt is ready."""

        if QApplication.instance() is None:
            self.ui.log("Pareto is not available yet: Qt application is not ready.", "WARNING")
            return False

        if getattr(self.ui, "pareto_table", None) is None:
            self.ui.log("Pareto is not available yet: table is still initializing.", "WARNING")
            return False

        if getattr(self.ui, "pareto_window", None) is None:
            parent = self if isinstance(self, QWidget) else None
            self.ui.pareto_window = QDialog(parent)
            self.ui.pareto_window.setWindowTitle("Pareto Front Explorer")
            self.ui.pareto_window.setMinimumSize(850, 400)

            p_lay = QVBoxLayout(self.ui.pareto_window)

            lbl = QLabel(
                "Double-click col 1-2 = load Best RMSE | "
                "Double-click col 3-4 = load Best MC | "
                "Double-click col 5-6 = load Best Fab (>=5nm)"
            )
            lbl.setStyleSheet("font-size: 12px; margin-bottom: 5px;")
            p_lay.addWidget(lbl)

            p_lay.addWidget(self.ui.pareto_table)

            f_p_btns = QHBoxLayout()

            clr_btn = QPushButton("Clear Pareto")
            clr_btn.setToolTip("Clear the Pareto front table.")
            clr_btn.clicked.connect(self.ui._clear_pareto)

            exp_btn = QPushButton("Export HTML Report")
            exp_btn.setToolTip("Export Pareto front to an HTML report.")
            exp_btn.clicked.connect(self.ui._export_pareto_report)

            f_p_btns.addWidget(clr_btn)
            f_p_btns.addStretch()
            f_p_btns.addWidget(exp_btn)
            p_lay.addLayout(f_p_btns)

        return True

    def _show_pareto_window(self) -> None:
        """Display the Pareto table in a detachable window."""

        if not self._ensure_pareto_ui():
            return

        self.ui.pareto_window.show()
        self.ui.pareto_window.raise_()
        self.ui.pareto_window.activateWindow()

        self.ui.pareto_window.activateWindow()
