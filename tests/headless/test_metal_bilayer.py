import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop

from CERTUS_METAL_BILAYER import CertusMetalBilayerApp
import certus_physics


def test_metal_bilayer_headless():
    print("TEST STARTING!")
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        print("app created")

        certus_physics.warmup_physics()
        print("warmup_physics done")

        metal_app = CertusMetalBilayerApp()
        print("CertusMetalBilayerApp created")

        # User constraint: Substrate MUST be SiO2
        if hasattr(metal_app, "combo_substrate"):
            metal_app.combo_substrate.setCurrentText("SiO2")
            print("setCurrentText SiO2 done")

        example_path = Path("example/example_metal_bilayer/JSON-metal-bilayer-example.json").resolve()
        print("calling load_config from:", example_path)
        # BYPASS QMessageBox that freezes headless test!
        metal_app._post_load_config = lambda *args: None
        metal_app.load_config(str(example_path))
        print("load_config done")

        loop = QEventLoop()
        final_result = None

        def on_done(res):
            nonlocal final_result
            final_result = res
            loop.quit()

        def on_error(err):
            print("ERROR:", err)
            loop.quit()

        def on_progress(payload):
            print("PROGRESS:", payload)

        print("CALLING start_optimization...")
        metal_app.start_optimization()
        print("start_optimization RETURNED!")

        worker = metal_app.worker
        if worker:
            if hasattr(worker, "signals") and hasattr(worker.signals, "finished"):
                worker.signals.finished.connect(on_done)
                worker.signals.error.connect(on_error)
                if hasattr(worker.signals, "progress"):
                    worker.signals.progress.connect(on_progress)
            else:
                worker.finished.connect(on_done)
                if hasattr(worker, "error"):
                    worker.error.connect(on_error)
                if hasattr(worker, "progress"):
                    worker.progress.connect(on_progress)

            loop.exec()

        print("HEADLESS METAL BILAYER DONE.")
        print("Final result object:", final_result)

        if final_result:
            res = final_result.get("result")
            if res is not None:
                rmse = res.fun ** 0.5
                print(f"RMSE: {rmse:.6f}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_metal_bilayer_headless()
    import os
    os._exit(0)
