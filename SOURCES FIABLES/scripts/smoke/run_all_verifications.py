#!/usr/bin/env python3
"""CERTUS 1103 consistency check script.

INSTRUCTIONS
------------
1. Open a terminal.
2. Go to directory 1103 (root of the project):
     cd "path/to/CERTUS/1103"
3. Throw:
     python tests/run_all_verifications.py
4. Check the output:
   - "[Directory] Check directory disabled" => OK.
   - Smoke RE: reverse_sample.xlsx / reverse_sample0.xlsx (initial RMSE).
   - Pytest: all tests in tests/ (ex. 268 passed).
   - "RESULT: All checks are OK." and exit code 0 => success.

One-liner command (from CERTUS/1103):
  python tests/run_all_verifications.py

What this script checks:
1. Obsolete directory 1002 (check disabled).
2. Smoke RE: loading + initial RMSE on the example files (without pytest subprocess).
3. Pytest: complete test suite (TMM, physics, UI, integration, etc.)."""

import os
import sys
import subprocess
from pathlib import Path

# Racine projet = scripts/smoke/ → remonter de 2 niveaux
ROOT = str(Path(__file__).resolve().parents[2])


def run_pytest(rel_test_paths, extra_args=None):
    """Run pytest on the paths listed from ROOT."""
    cmd = [sys.executable, "-m", "pytest"] + rel_test_paths + ["-v", "--tb=short"]
    if extra_args:
        cmd.extend(extra_args)
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def check_1002_removed():
    """Verifies that obsolete directory 1002 no longer exists."""
    return True, "Check directory disabled"


def run_smoke_re_reverse_samples():
    """RE : reverse_sample.xlsx / reverse_sample0.xlsx (voir tests/smoke_re_reverse_samples.py)."""
    script = Path(ROOT) / "scripts" / "smoke" / "smoke_re_reverse_samples.py"
    if not script.is_file():
        print("[Smoke RE] Script manquant:", script)
        return False
    r = subprocess.run([sys.executable, str(script)], cwd=ROOT)
    return r.returncode == 0


def main():
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    # pytest 1103 suite: the entire tests/ directory
    pytest_targets = ["tests/"]

    print("=" * 60)
    print("CERTUS 1103 VERIFICATIONS")
    print("Racine projet:", ROOT)
    print("=" * 60)

    ok_1002, msg_1002 = check_1002_removed()
    print("[Directory]", msg_1002)
    print()

    print("[Smoke RE reverse samples]")
    print("  - tests/smoke_re_reverse_samples.py")
    ok_smoke_re = run_smoke_re_reverse_samples()
    print()

    print("[Tests pytest]")
    print("  -", pytest_targets[0])
    ok_pytest = run_pytest(pytest_targets)
    print()

    print("=" * 60)
    all_ok = ok_1002 and ok_smoke_re and ok_pytest
    if all_ok:
        print("RESULT: All checks are OK.")
    elif not ok_smoke_re:
        print("RESULT: Failed (smoke RE reverse samples).")
    else:
        print("RESULT: Failed (pytest failed).")
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
