from __future__ import annotations
from certus.ui.certus_field_common import *

class CertusFieldEventsMixin:
    """CertusFieldEventsMixin."""

    def _on_table_item_changed(self, item):
        if self._is_updating_table or self.stack_panel.is_updating_table or item is None:
            return
        col = item.column()
        if col in (0, 1):
            self._update_thicknesses()
        elif col == 2:
            self._update_qwot_from_thickness(item.row())

    def _build_plot_export_frames(self, plot_data: dict) -> dict[str, pd.DataFrame]:
        return FieldExportService.build_plot_export_frames(plot_data)

    def export_data(self):
        if not self._last_plot_data:
            show_toast(self, "No data to export. Run a calculation first.", "warning")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = get_resource_path("reports")
            os.makedirs(report_dir, exist_ok=True)

            base_name = f"Report_FIELD_{timestamp}"
            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")
            html_path = str(Path(report_dir) / f"{base_name}.html")

            params = self._get_params()
            sheets = {"Summary": self._build_summary_frame(params)}
            sheets.update(self._build_plot_export_frames(self._last_plot_data))
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

            if self._export_results_html(html_path):
                show_toast(self, "Excel and HTML reports generated successfully.", "success")
                self.logger.info(f"Reports generated in: {report_dir}")
            else:
                show_toast(self, "HTML error, Excel generated.", "warning")

        except Exception as e:
            show_toast(self, f"Export error: {e}", "error")
            self.logger.error(f"Export Error: {e}\n{traceback.format_exc()}")

    def export_png(self):
        if not self._last_plot_data:
            show_toast(self, "No plot to capture.", "warning")
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = get_resource_path("reports")
            os.makedirs(report_dir, exist_ok=True)
            png_path = str(Path(report_dir) / f"Capture_FIELD_{timestamp}.png")
            
            exporter = pyqtgraph.exporters.ImageExporter(self.plot_widget.plotItem)
            # High quality parameters
            exporter.parameters()['width'] = 1920
            exporter.export(png_path)
            show_toast(self, f"Screenshot saved: {png_path}", "success")
        except Exception as e:
            show_toast(self, f"Screenshot error: {e}", "error")

    def _on_mat_h_changed(self, mat_name: str):
        for key, val in LIDT_PRESETS.items():
            if key in mat_name:
                self.edit_seuil1.setValue(val)
                break

    def _on_mat_l_changed(self, mat_name: str):
        for key, val in LIDT_PRESETS.items():
            if key in mat_name:
                self.edit_seuil2.setValue(val)
                break

    def on_calc_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="calculate", params=params))

    def on_opt_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self._initial_field_data = getattr(self, "_last_plot_data", None)
        self._initial_spectral_data = getattr(self, "_last_spectral_data", None)

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)

        if self.chk_allow_growth.isChecked():
            self._synthesis_active = True
            self._synthesis_best_cost = float('inf')
            self._synthesis_stagnation_count = 0
            self._synthesis_checkpoint = {
                "emp_factors": list(params.emp_factors),
                "layer_types": list(params.layer_types),
                "cost": float('inf')
            }
            self.logger.info("Starting hidden Needle Synthesis loop (Authorize change of number layer mode)...")
            params.synthesis_mode = True
        else:
            self._synthesis_active = False

        self._start_worker(FieldWorkerRequest(action="optimize", params=params))

    def on_mc_clicked(self):
        try:
            params = self._get_params()
        except ValueError as e:
            show_toast(self, str(e), "warning")
            return
            
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="tolerate", params=params))

    def on_load_json_clicked(self):
        self.on_import_design()

    def on_export_csv_clicked(self):
        """Export current field data to Excel (xlsx).

        Uses _last_plot_data (set after every successful calculation)
        instead of current_result which is never assigned.
        FieldExportService.build_plot_export_frames returns dict[str, DataFrame].
        """
        if not self._last_plot_data:
            show_toast(self, "No result to export. Run a calculation first.", "warning")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "", "Excel Files (*.xlsx)")
        if not filename:
            return

        try:
            sheets = FieldExportService.build_plot_export_frames(self._last_plot_data)
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            self.logger.info(f"Exported field data to {filename}")
            show_toast(self, "Data exported successfully.", "success")
        except Exception as e:
            self.logger.error(f"Export error: {str(e)}")
            show_toast(self, f"Export failed: {str(e)}", "error")

    def _export_results_html(self, html_path: str) -> bool:
        from certus.ui.certus_ui_utils import open_file_explorer
        """Generate a professional standalone HTML report for field optimization."""
        try:
            params = self._get_params()
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare stack table rows
            rows = ""
            for r in range(self.table_layers.rowCount()):
                mat = self._normalize_layer_material(r)
                thick = self.table_layers.item(r, 2).text() if self.table_layers.item(r, 2) else "0.0"
                rows += f"<tr><td>{r+1}</td><td>{mat}</td><td>{thick} nm</td></tr>"

            html = f"""
            <html><head>
            <style>
                body {{ font-family: sans-serif; margin: 40px; color: #333; }}
                h1 {{ color: #2563eb; border-bottom: 2px solid #2563eb; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f8fafc; }}
                .meta {{ background: #f1f5f9; padding: 15px; border-radius: 8px; }}
            </style>
            </head><body>
                <h1>CERTUS-FIELD Report</h1>
                <div class="meta"><p>Generated: {now}</p><p>Objective: {params.l0}nm center λ</p></div>
                <h2>Layer Structure</h2>
                <table><tr><th>#</th><th>Material</th><th>Thickness</th></tr>{rows}</table>
            </body></html>"""
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            return True
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return False

    def on_export_html_clicked(self):
        """Export a full HTML report.

        Guards on _last_plot_data instead of current_result
        (current_result is never assigned — _export_results_html
        reads the stack table and plot widgets directly).
        """
        if not self._last_plot_data:
            show_toast(self, "No result to export. Run a calculation first.", "warning")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "HTML Report", "", "HTML Files (*.html)")
        if not filename:
            return

        try:
            if self._export_results_html(filename):
                self.logger.info(f"Report generated at {filename}")
                show_toast(self, "Report generated.", "success")
            else:
                show_toast(self, "HTML Report generation failed.", "error")
        except Exception as e:
            self.logger.error(f"Report generation error: {str(e)}")
            show_toast(self, f"Report generation failed: {str(e)}", "error")

    def on_open_reports_clicked(self):
        report_dir = os.path.join(get_resource_path("."), "reports")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir, exist_ok=True)
        open_file_explorer(report_dir)

    def _export_pareto_report(self) -> None:
        """Export a grouped HTML report summarizing the full Pareto front for Field."""
        if not self.pareto_history:
            show_toast(self, "Pareto history is empty.", "warning")
            return

        report_dir = os.path.join(get_resource_path("."), "reports")
        os.makedirs(report_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(report_dir, f"Pareto_Field_Summary_{ts}.html")

        rows_html = []
        for N in sorted(self.pareto_history.keys()):
            rec = self.pareto_history[N]
            best_cost = rec.get("best_cost", float("inf"))
            best_mc = rec.get("best_mc", float("inf"))
            best_fab = rec.get("best_fab", float("inf"))
            dmin_r = rec.get("dmin_rmse", 0.0)
            dmin_m = rec.get("dmin_mc", 0.0)
            dmin_f = rec.get("dmin_fab", 0.0)
            
            eff = best_cost / N if N > 0 and best_cost < float("inf") else 0.0
            
            rows_html.append(f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 12px; text-align: center; font-weight: bold; color: #1e293b;">{N}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #2563eb;">{best_cost:.5f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: {'#dc2626' if dmin_r < 5.0 else '#1e293b'};">{dmin_r:.1f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #d97706;">{best_mc:.5f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: {'#dc2626' if dmin_m < 5.0 else '#1e293b'};">{dmin_m:.1f}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #16a34a;">{f"{best_fab:.5f}" if best_fab < float('inf') else '-'}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #16a34a;">{f"{dmin_f:.1f}" if dmin_f > 0 else '-'}</td>
                    <td style="padding: 12px; text-align: center; font-family: monospace; color: #64748b;">{eff * 1000:.4f}</td>
                </tr>
            """)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <title>CERTUS-FIELD - Pareto Front Summary</title>
    <style>
        body {{ background: #f8fafc; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 40px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 32px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
        h1 {{ font-size: 28px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
        p {{ color: #64748b; font-size: 14px; margin-bottom: 24px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th {{ background: #f1f5f9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; padding: 12px; border-bottom: 2px solid #e2e8f0; }}
        tr:hover {{ background: #f8fafc; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏆 Pareto Front Summary</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Module: CERTUS-FIELD</p>
        <table>
            <thead>
                <tr>
                    <th>N Layers</th>
                    <th>Best Cost</th>
                    <th>d_min Cost (nm)</th>
                    <th>Best MC Cost</th>
                    <th>d_min MC (nm)</th>
                    <th>Best Fab Cost</th>
                    <th>d_min Fab (nm)</th>
                    <th>Cost/N &times;1000</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_template)
            self.logger.info(f"Pareto HTML report generated at {filename}")
            show_toast(self, "Pareto report generated successfully.", "success")
        except Exception as e:
            self.logger.error(f"Failed to generate Pareto report: {e}")
            show_toast(self, f"Generation failed: {str(e)}", "error")
