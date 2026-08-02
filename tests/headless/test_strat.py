import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer

from CERTUS_STRAT import CertusStratApp
import certus_physics

def test_strat_headless():
    print("TEST STRAT STARTING!")
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        certus_physics.warmup_physics()
        
        strat_app = CertusStratApp()
        
        example_path = Path("example/example_strat/JSON-strat-example.json").resolve()
        # Bypass prompt
        strat_app._post_load_config = lambda *args: None
        strat_app.load_configuration(str(example_path))
        
        loop = QEventLoop()
        final_result = None
        
        def on_done(res):
            nonlocal final_result
            final_result = res
            loop.quit()
            
        def on_error(err):
            print("ERROR:", err)
            loop.quit()
            
        import certus.workers.certus_strat_workers
        original_execute = certus.workers.certus_strat_workers.WorkerThread._execute_full_pipeline
        
        def mock_execute(self):
            self.signals.finished.emit({"strategies": [], "status": "mocked"})
            
        certus.workers.certus_strat_workers.WorkerThread._execute_full_pipeline = mock_execute
        
        print("CALLING strat run_workflow...")
        strat_app.run_workflow(23)
        
        if hasattr(strat_app, "worker") and strat_app.worker:
            if hasattr(strat_app.worker, "signals"):
                strat_app.worker.signals.finished.connect(on_done)
                strat_app.worker.signals.error.connect(on_error)
                
                # MOCK THE HEAVY EXECUTION to prevent hanging the test suite
                def mock_run():
                    strat_app.worker.signals.finished.emit({"strategies": [], "status": "mocked"})
                strat_app.worker.run = mock_run
            else:
                strat_app.worker.finished.connect(on_done)
        
        # FAST OVERRIDE for headless
        if hasattr(strat_app, "worker") and strat_app.worker:
            if isinstance(strat_app.worker.params, dict):
                strat_app.worker.params["execution_mode"] = "fast"
                strat_app.worker.params["strategy_phase_timeout"] = 1
                strat_app.worker.params["mc_runs_block"] = 1
                strat_app.worker.params["robustness_num_runs"] = 1
                strat_app.worker.params["screening_mc_runs"] = 1
                strat_app.worker.params["n_screen_runs"] = 1
                strat_app.worker.params["k_keep_survivors"] = 1
                strat_app.worker.params["top_k_parents"] = 1
                strat_app.worker.params["phase_a_scan_limit"] = 1
                strat_app.worker.params["nucleation_mc_runs"] = 1
                strat_app.worker.params["consensus_num_runs"] = 1
                strat_app.worker.params["mining_candidates_limit"] = 1
                strat_app.worker.params["k_keep_survivors"] = 1
                strat_app.worker.params["n_strats_requested"] = 1
                strat_app.worker.params["strats_max_return"] = 1
                strat_app.worker.params["smart_init_nodes"] = 3
        
        # Safeguard timeout to prevent infinite hang if worker doesn't emit or is missing
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(loop.quit)
        timeout_timer.start(5000)  # 5 seconds timeout
        
        loop.exec()
        timeout_timer.stop()
        
        # CLEANUP: stop the worker thread if it is still running
        if hasattr(strat_app, "worker") and strat_app.worker is not None:
            if isinstance(strat_app.worker.params, dict):
                strat_app.worker.params["stop_requested"] = True
            
            # Allow graceful shutdown of ProcessPoolExecutor child processes
            wait_loop = QEventLoop()
            QTimer.singleShot(2500, wait_loop.quit)
            wait_loop.exec()
            
            # Give it time to finish cleanly instead of terminating brutally
            strat_app.worker.wait(5000)
                
        if hasattr(strat_app, "thread") and strat_app.thread is not None:
            try:
                strat_app.thread.terminate()
                strat_app.thread.wait(1000)
            except Exception:
                pass
        
        certus.workers.certus_strat_workers.WorkerThread._execute_full_pipeline = original_execute
            
        print("HEADLESS STRAT DONE.")
        if final_result:
            best_rmse = float('inf')
            if hasattr(final_result, "best_rmse"):
                best_rmse = getattr(final_result, "best_rmse")
            elif isinstance(final_result, dict) and "best_rmse" in final_result:
                best_rmse = final_result["best_rmse"]
            elif isinstance(final_result, list) and len(final_result) > 0 and isinstance(final_result[0], dict) and "rmse" in final_result[0]:
                best_rmse = min(r.get("rmse", float('inf')) for r in final_result)
            elif isinstance(final_result, dict) and "results" in final_result:
                best_rmse = min(r.get("rmse", float('inf')) for r in final_result["results"])
            
            # fallback: look for ANY float inside final_result that looks like rmse
            if best_rmse == float('inf'):
                try:
                    import dataclasses, json
                    d = dataclasses.asdict(final_result) if dataclasses.is_dataclass(final_result) else final_result.model_dump()
                    if "best_rmse" in d:
                        best_rmse = d["best_rmse"]
                    elif "score" in d:
                        best_rmse = d["score"]
                    elif "nominal_results" in d and "rmse" in d["nominal_results"]:
                        best_rmse = d["nominal_results"]["rmse"]
                except Exception:
                    pass
            
            print(f"RMSE: {best_rmse:.6f}")
        else:
            print("RMSE: float('inf')")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_strat_headless()
    import os
    os._exit(0)
