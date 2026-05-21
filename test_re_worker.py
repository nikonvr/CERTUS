import sys
import os
import time
import threading
import traceback
from PyQt6.QtWidgets import QApplication

# Import CERTUS modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from CERTUS_RE import CertusREApp
from certus_re_workers import REWorker

def dump_stacks():
    print("\n" + "="*80 + "\nTHREAD STACK DUMP\n" + "="*80)
    for thread_id, frame in sys._current_frames().items():
        print(f"\nThread ID: {thread_id}")
        traceback.print_stack(frame)
    print("="*80 + "\n")
    sys.stdout.flush()

def dump_loop():
    # Wait for things to start
    time.sleep(5)
    for _ in range(5):
        time.sleep(3)
        dump_stacks()

def main():
    # Start stack dumper thread
    t = threading.Thread(target=dump_loop, daemon=True)
    t.start()

    print("Initializing QApplication...", flush=True)
    qt_app = QApplication(sys.argv)
    
    print("Initializing CertusREApp...", flush=True)
    app = CertusREApp()
    
    # Wait for JIT warmup worker if any
    if hasattr(app, "warmup_worker") and app.warmup_worker:
        print("Waiting for warmup worker to finish...", flush=True)
        app.warmup_worker.wait()
        print("Warmup finished.", flush=True)
        
    print("Loading RE workbook explicitly...", flush=True)
    xls_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example", "example_RE", "reverse_sample.xlsx")
    success = app.load_reverse_engineering_from_path(xls_path)
    print(f"Workbook load success: {success}", flush=True)
    
    print("Building worker configuration...", flush=True)
    cfg = app.build_re_worker_cfg()
    print(f"Config built: {cfg is not None}", flush=True)
    if cfg:
        print("Creating REWorker...", flush=True)
        worker = REWorker(cfg)
        
        # Connect signals
        worker.signals.progress.connect(lambda pct, msg: print(f"[PROGRESS] {pct}%: {msg}", flush=True))
        worker.signals.finished.connect(lambda payload: print(f"[FINISHED] Payload: {payload.keys()}", flush=True))
        worker.signals.error.connect(lambda err: print(f"[ERROR] {err}", flush=True))
        
        print("Running _run_re_workflow directly...", flush=True)
        worker._run_re_workflow()
        print("worker._run_re_workflow finished.", flush=True)

if __name__ == '__main__':
    main()
