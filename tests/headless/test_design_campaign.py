import sys
from pathlib import Path
import json
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer

from CERTUS_DESIGN import CertusDesignApp
import certus_physics

logging.basicConfig(level=logging.WARNING)

def run_campaign_worker(output_file: str):
    print("CAMPAIGN WORKER STARTING! Output:", output_file)
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        certus_physics.warmup_physics()

        design_app = CertusDesignApp()

        example_path = Path("example/example_design/JSON-design-example.json").resolve()
        design_app._post_load_config = lambda *args: None
        design_app.load_config(str(example_path))
        # Ensure it runs needle search
        design_app.n100_spin.setValue(5)
        design_app.global_cycles_spin.setValue(1)
        design_app.orchestrator._target_layer_count = 150

        loop = QEventLoop()
        best_rmse_seen = [float("inf")]

        def read_rmse():
            rmse = getattr(design_app, "_workflow_best_rmse", float("inf"))
            if rmse < best_rmse_seen[0]:
                best_rmse_seen[0] = rmse
            idle_timer.setInterval(100)

        design_app.optimization_finished_signal.connect(lambda: QTimer.singleShot(200, read_rmse))

        def on_timeout():
            print("Timeout reached (900s = 15m)")
            loop.quit()

        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.start(900_000) # 15 minutes

        idle_check_count = 0
        def check_idle():
            nonlocal idle_check_count
            is_busy = getattr(design_app, "_is_busy", False)
            if not is_busy:
                idle_check_count += 1
                if idle_check_count >= 10:
                    loop.quit()
            else:
                idle_check_count = 0

        idle_timer = QTimer()
        idle_timer.timeout.connect(check_idle)
        idle_timer.start(1000)

        design_app.run_optim("healing") # Use healing mode for needle

        loop.exec()

        timeout_timer.stop()
        idle_timer.stop()

        final_rmse = getattr(design_app, "_workflow_best_rmse", float("inf"))
        if final_rmse < best_rmse_seen[0]:
            best_rmse_seen[0] = final_rmse

        # Extract final stack BEFORE any cleanup that might crash
        stack = []
        for row in range(design_app.front_table.rowCount()):
            mat_widget = design_app.front_table.cellWidget(row, 0)
            th_widget = design_app.front_table.cellWidget(row, 1)
            
            mat = mat_widget.currentText() if mat_widget else ""
            if th_widget and hasattr(th_widget, "value"):
                th = float(th_widget.value())
            else:
                item = design_app.front_table.item(row, 1)
                th = float(item.text()) if item else 0.0
                
            stack.append({"material": mat, "thickness": th})

        result = {
            "best_rmse": best_rmse_seen[0],
            "layers": len(stack),
            "stack": stack
        }

        with open(output_file, "w") as f:
            json.dump(result, f, indent=4)

        print(f"WORKER DONE. Final RMSE: {best_rmse_seen[0]:.6f}")

        try:
            if hasattr(design_app, "worker_manager"):
                design_app.worker_manager._workflow_stopped = True
            if hasattr(design_app, "optim_worker") and design_app.optim_worker is not None:
                design_app.optim_worker.request_stop()
        except Exception:
            pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    else:
        output_file = "D:/1406/1406/campaign_result_fallback.json"
    run_campaign_worker(output_file)
    sys.exit(0)
