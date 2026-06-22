import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop

from certus.ui.certus_field_ui import CertusFieldApp
import certus_physics


def test_field_headless():
    print("TEST FIELD STARTING!")
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        certus_physics.warmup_physics()
        print("warmup_physics done")

        field_app = CertusFieldApp()
        print("CertusFieldApp created")

        # Load example JSON via on_import_design (bypassing dialog)
        example_path = Path("example/example_field/test_hr_mirror.json").resolve()
        print("Loading config from:", example_path)

        with open(example_path, "r") as f:
            data = json.load(f)

        # Bypass the QDialog popup in on_import_design
        # We directly call the internal logic
        for key, combo in [
            ("mat_H", field_app.combo_mat_H),
            ("mat_L", field_app.combo_mat_L),
            ("mat_Sub", field_app.combo_mat_Sub),
            ("mat_Sup", field_app.combo_mat_Sup),
        ]:
            if key in data:
                idx = combo.findText(data[key])
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        if "l0" in data:
            field_app.edit_l0.setValue(float(data["l0"]))
        if "seuil1" in data:
            field_app.edit_seuil1.setValue(float(data["seuil1"]))
        if "seuil2" in data:
            field_app.edit_seuil2.setValue(float(data["seuil2"]))
        if "alpha" in data:
            field_app.edit_alpha.setValue(float(data["alpha"]))
        if "theta_inc_deg" in data:
            field_app.edit_angle.setValue(float(data["theta_inc_deg"]))
        if "pol_idx" in data:
            field_app.combo_pol.setCurrentIndex(int(data["pol_idx"]))
        if "lcalc" in data:
            field_app.edit_lcalc.setText(str(data["lcalc"]))

        # Load layers
        field_app._is_updating_table = True
        try:
            if "emp_factors" in data:
                layer_types = data.get("layer_types", [])
                field_app.table_layers.setRowCount(0)
                for i, f_val in enumerate(data["emp_factors"]):
                    field_app.table_layers.insertRow(i)
                    material = None
                    if layer_types and i < len(layer_types):
                        material = "H" if layer_types[i] == 0 else "L"
                    field_app.stack_panel.add_row_to_table(i, float(f_val), mat_str=material)
        finally:
            field_app._is_updating_table = False

        field_app._update_thicknesses()
        print("Config loaded, layers count:", field_app.table_layers.rowCount())

        # Setup event loop to wait for result
        loop = QEventLoop()
        final_result = None

        def on_finished(result):
            nonlocal final_result
            final_result = result
            loop.quit()

        def on_error(err):
            print("ERROR:", err)
            loop.quit()

        def on_progress(progress, message):
            print(f"PROGRESS {progress}%: {message}")

        # Connect signals before starting worker
        # We patch on_worker_finished/error temporarily
        field_app.on_worker_finished = on_finished
        field_app.on_worker_error = on_error

        print("CALLING run_auto_calc...")
        field_app.run_auto_calc()
        print("run_auto_calc returned")

        if field_app.worker and field_app.worker.isRunning():
            field_app.worker.signals.finished.connect(on_finished)
            field_app.worker.signals.error.connect(on_error)
            loop.exec()

        print("HEADLESS FIELD DONE.")
        if final_result:
            print("Result type:", type(final_result))
            # Field result is a FieldPlotData or dict
            print("Result:", final_result)
        else:
            print("No result received (may have finished synchronously or no worker)")

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_field_headless()
    import os
    os._exit(0)
