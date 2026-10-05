import logging
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
        
    finished: dict = {}
    worker = REWorker(cfg)
    worker.signals.result.connect(on_result)
    worker.signals.finished.connect(finished.update)
    phase4_logs: list[str] = []

    class Phase4LogHandler(logging.Handler):
        def emit(self, record):
            if record.getMessage().startswith("RE phase 4"):
                phase4_logs.append(record.getMessage())

    root_logger = logging.getLogger()
    previous_level = root_logger.level
    handler = Phase4LogHandler()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    try:
        worker.run()
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)
    
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
    # The run must also FINISH: `result` is emitted before phase 4, and until 2026-10-04 every phase 4 that reached its
    # high-angle branch ended on an AttributeError -- `finished` then carried ok=False and no result at all.
    assert finished.get("ok") is True, "the RE worker did not finish its run"
    assert finished.get("results"), "the finished payload carries no result"
    # The retained result carries its thickness uncertainties, from the data rows alone (certus_re port).
    top = finished["results"][0]
    report = top.get("thickness_uncertainty")
    assert report is not None, "the retained result carries no thickness uncertainty"
    assert len(report["sigma_nm"]) == len(top["ep"])
    assert all(0.0 < s < 50.0 for s in report["sigma_nm"]), report["sigma_nm"]
    assert report["n_data"] > report["n_parameters"]
    # And its parameter budget: every block, the thicknesses at least, against the same data count.
    budget = top.get("parameter_budget")
    assert budget is not None, "the retained result carries no parameter budget"
    assert budget["n_free_parameters"] >= len(top["ep"])
    assert budget["n_data_points"] == report["n_data"]
    scan_candidates = [r for r in finished["results"] if "P4 aperture scan" in str(r.get("label"))]
    assert len(scan_candidates) == 1, [r.get("label") for r in finished["results"]]
    scan_apertures = list(scan_candidates[0]["re_p4_beam_ap_knots_deg"])
    assert len(scan_apertures) == 4, scan_apertures
    assert len(set(scan_apertures)) == 1, scan_apertures
    assert any("joint TRF" in m and "independent" in m for m in phase4_logs), phase4_logs
    assert not any("joint TRF disabled" in m for m in phase4_logs), phase4_logs
    assert any("scan-only candidate" in m and "final ranking" in m for m in phase4_logs), phase4_logs


def test_re_headless_with_an_imposed_aperture():
    """The PHOTON RT preset (2.0 deg total, imposed): phase 4 runs to its end without releasing the aperture."""
    if QApplication.instance() is None:
        QApplication(sys.argv)
    certus_physics.warmup_physics()
    re_app = CertusREApp()
    re_app.load_reverse_engineering_from_path(str(Path("example/example_RE/reverse_sample.xlsx").resolve()))
    cfg = re_app.build_re_worker_cfg({"re_beam_aperture_imposed_deg": 2.0})
    finished: dict = {}
    worker = REWorker(cfg)
    worker.signals.finished.connect(finished.update)
    worker.run()
    re_app.close()
    assert finished.get("ok") is True, "the RE worker did not finish its run"
    imposed = [r for r in finished["results"] if "imposed aperture" in str(r.get("label"))]
    assert imposed, [r.get("label") for r in finished["results"]]
    assert all(list(r["re_p4_beam_ap_knots_deg"]) == [2.0] * 4 for r in imposed)
    aperture = next(b for b in finished["results"][0]["parameter_budget"]["blocks"] if b["name"] == "beam aperture")
    assert aperture["count"] == 0


def test_re_headless_with_refined_indices(qapp):
    """The index-spline path must return a result and finish successfully."""
    certus_physics.warmup_physics()
    re_app = CertusREApp()
    re_app.load_reverse_engineering_from_path(str(Path("example/example_RE/reverse_sample.xlsx").resolve()))
    cfg = re_app.build_re_worker_cfg({"re_refine_h": True, "re_refine_l": True})
    received = []
    finished: dict = {}
    worker = REWorker(cfg)
    worker.signals.result.connect(received.append)
    worker.signals.finished.connect(finished.update)
    worker.run()
    re_app.close()
    assert finished.get("ok") is True, finished
    assert received, finished
    assert finished.get("results"), finished

if __name__ == "__main__":
    test_re_headless()
