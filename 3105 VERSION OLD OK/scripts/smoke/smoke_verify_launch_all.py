import os
import subprocess
import sys
import time
import logging
from pathlib import Path

# Config
TEST_TIMEOUT = 10  # Seconds to wait for GUI to start
MAIN_APPS = [
    ("CERTUS_INDEX.py", "example/example_index/CSV-index-example.csv"),
    ("CERTUS_RE.py", "example/example_RE/reverse_sample.xlsx"),
    ("CERTUS_STRAT.py", "example/example_strat/JSON-strat-example.json"),
    ("CERTUS_INDEX_SPLINE.py", "example/example_index_spline/TOTAL.xlsx"),
    ("CERTUS_DESIGN.py", "example/example_design/JSON-design-example.json"),
    ("CERTUS_METAL_BILAYER.py", "example/example_metal_bilayer/CSV-metal-example.csv"),
    ("CERTUS_METAL_SINGLE.py", "example/example_metal_single/Target_Titane_Simu_20nm.xlsx"),
    ("certus_substrate_index.py", None),  # Can launch empty
    ("certus_curve_smoother.py", None),   # Can launch empty
]

def verify_app_launch(app_name, example_file=None):
    print(f"Testing {app_name}...")
    cmd = [sys.executable, app_name]
    if example_file:
        full_path = Path.cwd() / example_file
        if full_path.exists():
            cmd.append(str(full_path))
        else:
            print(f"  [Warning] Example file not found: {example_file}")
    
    env = os.environ.copy()
    # Optional: force offscreen if apps support it, but we want to test if they CAN open windows
    # env["QT_QPA_PLATFORM"] = "offscreen" 

    try:
        # We use a shorter timeout because we just want to see if it CRASHES at startup
        # If it survives 8 seconds, it probably launched the main window loop
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        
        # Wait a bit
        try:
            stdout, stderr = process.communicate(timeout=8)
            # If it finished before timeout, it might be an error or a scripted app
            if process.returncode != 0:
                print(f"  [FAIL] {app_name} exited with code {process.returncode}")
                print(f"  [Error] {stderr[:500]}")
                return False
            else:
                print(f"  [INFO] {app_name} exited normally (unexpected for GUI app, but OK if it worked)")
                return True
        except subprocess.TimeoutExpired:
            # GUI app is blocked in event loop -> SUCCESS
            print(f"  [PASS] {app_name} launched and reached main loop (timeout survived)")
            process.kill()
            return True
            
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"  [FAIL] Error launching {app_name}: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("CERTUS SMOKE TEST: APP LAUNCH VERIFICATION")
    print("="*60)
    
    results = []
    for app, example in MAIN_APPS:
        if Path(app).exists():
            results.append(verify_app_launch(app, example))
        else:
            print(f"Skipping {app} (not found)")
            results.append(False)
            
    print("="*60)
    if all(results):
        print("ALL APPS LAUNCHED SUCCESSFULLY")
        sys.exit(0)
    else:
        print("SOME APPS FAILED TO LAUNCH")
        sys.exit(1)
