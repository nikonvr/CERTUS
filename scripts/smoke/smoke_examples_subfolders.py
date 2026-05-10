import os
import subprocess
import time
import sys
from pathlib import Path

def launch_and_wait(app_script, example_file, timeout=8):
    """Launches app with example, waits for it to reach loop, then terminates."""
    print(f"Testing {app_script} with {example_file}...")
    cmd = [sys.executable, app_script, example_file]
    try:
        # We use a short timeout because we just want to see if it starts without crashing
        start_time = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Buffer stderr to check for immediate crashes
        while time.time() - start_time < timeout:
            if proc.poll() is not None:
                # Process exited early!
                stdout, stderr = proc.communicate()
                print(f"  [FAIL] {app_script} exited early with code {proc.returncode}")
                if stderr:
                    print(f"  Error: {stderr[:500]}")
                return False
            time.sleep(0.5)
        
        # If we reached here, it survived the timeout
        print(f"  [PASS] {app_script} survived {timeout}s")
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"  [ERROR] Execution failed: {e}")
        return False

def main():
    example_root = Path("example")
    
    # Mapping folder names to scripts
    mapping = {
        "example_design": "CERTUS_DESIGN.py",
        "example_index": "CERTUS_INDEX.py",
        "example_index_spline": "CERTUS_INDEX_SPLINE.py",
        "example_metal_bilayer": "CERTUS_METAL_BILAYER.py",
        "example_metal_single": "CERTUS_METAL_SINGLE.py",
        "example_RE": "CERTUS_RE.py",
        "example_strat": "CERTUS_STRAT.py"
    }

    results = []
    
    for folder, app in mapping.items():
        folder_path = example_root / folder
        if not folder_path.exists():
            print(f"Skipping {folder}: directory not found")
            continue
            
        print(f"\n--- Scanning folder: {folder_path} ---")
        files = [f for f in os.listdir(folder_path) if f.lower().endswith((".json", ".csv", ".xlsx", ".xls"))]
        
        for f in files:
            file_path = str(folder_path / f)
            # Avoid opening temp files or results if they were recreated
            if "~$" in f or "result" in f.lower():
                continue
            
            success = launch_and_wait(app, file_path)
            results.append((app, f, success))

    print("\n" + "="*60)
    print("EXHAUSTIVE EXAMPLE LAUNCH SUMMARY")
    print("="*60)
    passed = sum(1 for _, _, s in results if s)
    total = len(results)
    
    for app, f, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} | {app:<25} | {f}")
        
    print("="*60)
    print(f"TOTAL: {passed}/{total} examples launched successfully.")
    
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
