import sys
import os
import subprocess
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
TESTS_DIR = ROOT / "tests" / "headless"

TESTS = [
    ("DESIGN", "test_design.py"),
    ("RE", "test_re.py"),
    ("STRAT", "test_strat.py"),
    ("INDEX", "test_index.py"),
    ("SPLINE", "test_spline.py"),
    ("METAL_SINGLE", "test_metal_single.py"),
    ("METAL_BILAYER", "test_metal_bilayer.py"),
]

def run_test_and_extract_rmse(name, script):
    path = TESTS_DIR / script
    if not path.exists():
        return None, f"File not found: {script}"
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    
    print(f"Running {name}...")
    try:
        result = subprocess.run(
            [PYTHON, "-u", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            timeout=600,
            env=env
        )
        output = result.stdout + result.stderr
        
        # Look for RMSE in the output
        rmse_val = None
        for line in output.splitlines():
            line = line.strip()
            # Match "Best RMSE: 0.123" or "RMSE: 0.123" or "RMSE       : 0.123" or "RMSE=0.123"
            match = re.search(r'(?:Best )?RMSE\s*[:=]\s*([\d\.\-eE]+)', line, re.IGNORECASE)
            if match:
                rmse_val = float(match.group(1))
        
        if rmse_val is not None:
            return rmse_val, output
        else:
            return None, "No RMSE found in output. Last lines:\n" + "\n".join(output.splitlines()[-10:])
            
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"

def main():
    results = {}
    print("Collecting baseline RMSE values for CERTUS examples...\n")
    for name, script in TESTS:
        rmse, details = run_test_and_extract_rmse(name, script)
        if rmse is not None:
            print(f"[{name}] RMSE: {rmse:.6f}")
            results[name] = rmse
        else:
            print(f"[{name}] FAILED to extract RMSE: {details}")
            
    # Save to baseline
    baseline_path = ROOT / "tests" / "regression" / "baseline_rmse.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_path, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nSaved {len(results)} metrics to {baseline_path}")

if __name__ == "__main__":
    main()
