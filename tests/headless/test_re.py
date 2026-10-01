import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

import certus_physics
from certus.workers.certus_re_workers import REWorker
from CERTUS_RE import CertusREApp


def test_re_headless():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    certus_physics.warmup_physics()
    
    # Instantiate the UI headless
    re_app = CertusREApp()
    
    # Load example
    example_path = Path("example/example_RE/reverse_sample.xlsx").resolve()
    re_app.load_reverse_engineering_from_path(str(example_path))
    
    # Build config
    cfg = re_app.build_re_worker_cfg()
    
    # Hook result
    final_result = None
    def on_result(res):
        nonlocal final_result
        final_result = res
        
    worker = REWorker(cfg)
    worker.signals.result.connect(on_result)
    worker.run()
    
    if final_result:
        print("RE Result keys:", final_result.keys())
        rmse = final_result.get('rmse')
        rmse_sp = final_result.get('rmse_sp')
        rmse_qwot = final_result.get('rmse_qwot')
        print(f"RE RMSE        : {rmse}")
        print(f"RE RMSE_SP     : {rmse_sp}")
        print(f"RE RMSE_QWOT   : {rmse_qwot}")
    else:
        print("No result received.")
    assert final_result is not None, "the RE worker returned no result"
    assert 0.0 <= final_result["rmse"] < 1.0  # a finite fit, far below 100 %

if __name__ == "__main__":
    test_re_headless()
