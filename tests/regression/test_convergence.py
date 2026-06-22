import sys
import os
import subprocess
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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
            match = re.search(r'(?:Best )?RMSE\s*:\s*([\d\.\-eE]+)', line, re.IGNORECASE)
            if match:
                rmse_val = float(match.group(1))
        
        if rmse_val is not None:
            return rmse_val, output
        else:
            return None, "No RMSE found in output. Last lines:\n" + "\n".join(output.splitlines()[-10:])
            
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"

def main():
    print("=" * 60)
    print("  CERTUS CONVERGENCE TESTS (GOLDEN MASTER)")
    print("=" * 60)
    
    baseline_path = ROOT / "tests" / "regression" / "baseline_rmse.json"
    if not baseline_path.exists():
        print(f"ERROR: Baseline file not found: {baseline_path}")
        print("Please run scripts/collect_rmse.py first to generate the baseline.")
        sys.exit(1)
        
    with open(baseline_path, "r") as f:
        baseline = json.load(f)
        
    passed = 0
    failed = 0
    results = []
    
    # 1% tolerance
    TOLERANCE_MULTIPLIER = 1.01
    
    for name, script in TESTS:
        print(f"\n[RUN] {name} ...", end=" ", flush=True)
        
        if name not in baseline:
            print("SKIPPED (Not in baseline)")
            continue
            
        expected_rmse = baseline[name]
        rmse, details = run_test_and_extract_rmse(name, script)
        
        if rmse is None:
            print("FAIL")
            print(f"  Error: {details}")
            failed += 1
            results.append((name, "FAIL", f"Expected: {expected_rmse:.6f}, Got: ERROR"))
            continue
            
        # Check against baseline with 1% margin
        # A smaller RMSE is ALWAYS better! So rmse <= expected_rmse * 1.01 is passing
        allowed_rmse = expected_rmse * TOLERANCE_MULTIPLIER
        
        if rmse <= allowed_rmse:
            print("PASS")
            print(f"  RMSE: {rmse:.6f} (Baseline: {expected_rmse:.6f})")
            passed += 1
            results.append((name, "PASS", f"{rmse:.6f} <= {allowed_rmse:.6f}"))
        else:
            print("FAIL")
            print(f"  RMSE: {rmse:.6f} exceeds Baseline + 1% ({allowed_rmse:.6f})")
            failed += 1
            results.append((name, "FAIL", f"{rmse:.6f} > {allowed_rmse:.6f}"))
            
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    for name, status, msg in results:
        marker = "OK" if status == "PASS" else "!!"
        print(f"  [{marker}] {name:15s}  {msg}")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
