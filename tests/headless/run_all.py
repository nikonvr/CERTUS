"""
CERTUS Headless Test Suite — Runner
Runs all module integration tests sequentially and reports pass/fail + RMSE.

Usage:
    python tests/headless/run_all.py
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = sys.executable
TESTS_DIR = Path(__file__).resolve().parent

TESTS = [
    ("METAL_SINGLE",  "test_metal_single.py",  "RMSE"),
    ("METAL_BILAYER", "test_metal_bilayer.py",  "RMSE"),
    ("FIELD",         "test_field.py",           "success=True"),
    ("RE",            "test_re.py",              "RMSE"),
    ("DESIGN",        "test_design.py",          "Best RMSE"),
    ("SPLINE",        "test_spline.py",          "RMSE"),
]


def run_test(name: str, script: str) -> tuple[bool, str]:
    path = TESTS_DIR / script
    if not path.exists():
        return False, f"MISSING: {path}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    result = subprocess.run(
        [PYTHON, "-u", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=300,
        env=env
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    output = stdout + stderr
    ok = result.returncode == 0 and "Error" not in stderr
    return ok, output


def main():
    print("=" * 60)
    print("  CERTUS HEADLESS TEST SUITE")
    print("=" * 60)

    passed = 0
    failed = 0
    results = []

    for name, script, key in TESTS:
        print(f"\n[RUN] {name} ...", end=" ", flush=True)
        try:
            ok, output = run_test(name, script)
        except subprocess.TimeoutExpired:
            ok = False
            output = "TIMEOUT (>300s)"

        # Extract key line from output
        key_line = next(
            (ln.strip() for ln in output.splitlines() if key in ln),
            "(no output)"
        )

        status = "PASS" if ok else "FAIL"
        print(f"{status}")
        print(f"  {key_line}")
        results.append((name, status, key_line))

        if ok:
            passed += 1
        else:
            failed += 1
            # Print last 5 lines of output for context
            tail = output.strip().splitlines()[-5:]
            for ln in tail:
                print(f"  | {ln}")

    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    for name, status, line in results:
        marker = "OK" if status == "PASS" else "!!"
        print(f"  [{marker}] {name:15s}  {line}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
