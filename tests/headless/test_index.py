import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer

from CERTUS_INDEX import CertusIndexApp
import certus_physics

def test_index_headless():
    print("TEST INDEX STARTING!")
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        certus_physics.warmup_physics()
        
        index_app = CertusIndexApp()
        
        example_path = Path("example/example_index/H400-RTNBrel-sapphire.xlsx").resolve()
        # It's an Index application, it loads CSV via load_file
        index_app.load_file(str(example_path))
        
        loop = QEventLoop()
        final_result = None
        
        def on_done(res):
            nonlocal final_result
            final_result = res
            loop.quit()
            
        def on_error(err):
            print("ERROR:", err)
            loop.quit()
            
        print("CALLING index run_optimization...")
        index_app.run_optimization()
        
        worker = None
        if hasattr(index_app, "worker") and index_app.worker:
            worker = index_app.worker
        elif hasattr(index_app, "_worker") and index_app._worker:
            worker = index_app._worker
            
        if worker:
            if hasattr(worker, "signals"):
                worker.signals.finished.connect(on_done)
                worker.signals.error.connect(on_error)
            else:
                worker.finished.connect(on_done)
        
        # Safeguard timeout to prevent infinite hang if worker doesn't emit or is missing
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(loop.quit)
        timeout_timer.start(120000)  # 2 minutes timeout
        
        loop.exec()
        timeout_timer.stop()
        
        print("HEADLESS INDEX DONE.")
        if final_result:
            if hasattr(final_result, "rmse_final"):
                print(f"RMSE: {final_result.rmse_final:.6f}")
            elif isinstance(final_result, dict) and "rmse" in final_result:
                print(f"RMSE: {final_result['rmse']:.6f}")
            else:
                print(f"RMSE: float('inf')  # Result: {final_result}")
        else:
            print("RMSE: float('inf')")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_index_headless()
    import os
    os._exit(0)
