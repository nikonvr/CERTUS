#!/usr/bin/env python3
"""
CERTUS Unified Test Runner & Verification Orchestrator.
Centralizes the execution of the pytest suite and all smoke/example validation scripts,
generating a unified JSON report and return codes for CI/CD or developer validation.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
import os
import argparse
import subprocess
import time
import json
import platform
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Resolve ROOT directory (parents[1] because we are in scripts/)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def supports_color() -> bool:
    """Check if the terminal supports ANSI color codes."""
    plat = platform.system()
    supported_platform = plat != 'Windows' or 'ANSICON' in os.environ or 'WT_SESSION' in os.environ
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

# Disable colors if not supported
if not supports_color():
    for attr in dir(Colors):
        if not attr.startswith('__') and isinstance(getattr(Colors, attr), str):
            setattr(Colors, attr, '')

def print_banner(title: str):
    print(f"\n{Colors.BOLD}{Colors.OKBLUE}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}  {title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKBLUE}{'=' * 70}{Colors.ENDC}\n")

def check_environment() -> Tuple[bool, Dict[str, Any]]:
    """Verify system requirements and Python dependencies."""
    print(f"{Colors.BOLD}[Phase 0] checking system environment and dependencies...{Colors.ENDC}")
    
    status = {}
    success = True
    
    # Python Version
    py_ver = sys.version.split()[0]
    is_target_python = sys.version_info >= (3, 14, 5)
    status["python_version"] = {"value": py_ver, "ok": is_target_python}
    if not is_target_python:
        print(f"  {Colors.WARNING}[!] Python version: {py_ver} (Target: >= 3.14.5){Colors.ENDC}")
    else:
        print(f"  {Colors.OKGREEN}[OK] Python version: {py_ver}{Colors.ENDC}")
        
    # Check essential libraries
    libs = [
        ("numpy", "Numerical Computing"),
        ("scipy", "Scientific Computing"),
        ("numba", "JIT Compiler"),
        ("PyQt6", "UI Framework"),
        ("pandas", "Data Analysis"),
        ("openpyxl", "Excel Engine")
    ]
    
    for lib_name, desc in libs:
        try:
            mod = __import__(lib_name)
            ver = getattr(mod, "__version__", "Available")
            status[lib_name] = {"value": ver, "ok": True}
            print(f"  {Colors.OKGREEN}[OK] {lib_name:<10} ({ver}): {desc}{Colors.ENDC}")
        except ImportError:
            status[lib_name] = {"value": "Missing", "ok": False}
            print(f"  {Colors.FAIL}[FAIL] {lib_name:<10} (Missing): {desc}{Colors.ENDC}")
            # Non-critical warning for openpyxl, failure for others
            if lib_name != "openpyxl":
                success = False

    return success, status

def run_step(name: str, cmd: List[str], cwd: Path) -> Dict[str, Any]:
    """Run a single validation command and stream results live."""
    print(f"{Colors.BOLD}Running: {name}...{Colors.ENDC}")
    start_time = time.time()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    inject_path = str(ROOT / "scripts" / "inject")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = inject_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = inject_path

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
            universal_newlines=True,
        )

        captured: list[str] = []
        assert proc.stdout is not None
        
        last_percent = -1
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        is_pytest = (name == "Pytest Suite")
        
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            captured.append(line)
            
            if is_pytest:
                l_strip = line.strip()
                is_test_line = False
                status = None
                
                # Detect standard test result lines
                if " PASSED " in line or l_strip.endswith(" PASSED"):
                    status = "PASSED"
                    passed_count += 1
                    is_test_line = True
                elif " FAILED " in line or l_strip.endswith(" FAILED"):
                    status = "FAILED"
                    failed_count += 1
                    is_test_line = True
                elif " SKIPPED " in line or l_strip.endswith(" SKIPPED"):
                    status = "SKIPPED"
                    skipped_count += 1
                    is_test_line = True
                elif " ERROR " in line or l_strip.endswith(" ERROR"):
                    status = "ERROR"
                    failed_count += 1
                    is_test_line = True
                
                # Extract pytest percentage
                percent = -1
                if is_test_line and "[" in line and "%]" in line:
                    try:
                        part = line.split("[")[-1].split("%]")[0].strip()
                        percent = int(part)
                    except Exception:
                        pass
                
                if is_test_line:
                    if status in ("FAILED", "ERROR"):
                        test_name = line.split("::")[-1].split(" ")[0] if "::" in line else l_strip
                        print(f"\n  {Colors.FAIL}❌ {status}: {test_name}{Colors.ENDC}", flush=True)
                    
                    if percent != -1 and (percent >= last_percent + 5 or percent == 100):
                        last_percent = percent
                        bar_width = 20
                        filled = int(bar_width * percent / 100)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        total_done = passed_count + failed_count + skipped_count
                        print(f"  {Colors.OKCYAN}✦ Progress: {percent:>3}% [{bar}] | {total_done} tests run ({passed_count} passed, {failed_count} failed){Colors.ENDC}", flush=True)
                else:
                    # Print anything that is not an individual test success/skip to show summaries and tracebacks
                    print(line, end='', flush=True)
            else:
                print(line, end='', flush=True)

        return_code = proc.wait()
        duration = time.time() - start_time
        ok = return_code == 0
        output = ''.join(captured)

        # Parse test failures from output
        failures = []
        for line in captured:
            l_strip = line.strip()
            if " FAILED " in line or " ERROR " in line or l_strip.endswith(" FAILED") or l_strip.endswith(" ERROR"):
                clean = l_strip
                if " [" in clean:
                    clean = clean.split(" [")[0]
                failures.append(clean)

        if ok:
            print(f"  {Colors.OKGREEN}[OK] PASSED ({duration:.2f}s){Colors.ENDC}")
        else:
            print(f"  {Colors.FAIL}[FAIL] FAILED ({duration:.2f}s) - Exit Code {return_code}{Colors.ENDC}")

        return {
            "name": name,
            "success": ok,
            "exit_code": return_code,
            "duration_s": duration,
            "stdout": output,
            "stderr": "",
            "failures": failures,
        }
    except Exception as e:
        duration = time.time() - start_time
        print(f"  {Colors.FAIL}[ERROR] EXCEPTION ({duration:.2f}s) - {str(e)}{Colors.ENDC}")
        return {
            "name": name,
            "success": False,
            "exit_code": -1,
            "duration_s": duration,
            "stdout": "",
            "stderr": str(e),
        }

def get_git_changed_files() -> List[str]:
    """Get list of modified and untracked files from git."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        changed_files = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format is: XY path
            if len(line) > 3:
                path = line[3:].strip().strip('"')
                if path.endswith(".py"):
                    changed_files.append(path)
        return changed_files
    except Exception as e:
        print(f"{Colors.WARNING}[!] Git not available or not a git repository: {e}{Colors.ENDC}")
        return []

def get_matching_test_files(changed_files: List[str]) -> List[str]:
    """Map changed files to their corresponding test files."""
    matched_tests = set()
    
    # 1. Collect all test files in the workspace
    all_test_files = []
    tests_dir = ROOT / "tests"
    if tests_dir.exists():
        all_test_files = list(tests_dir.rglob("*.py"))
            
    # 2. Match each changed file
    for f in changed_files:
        f_path = Path(f)
        f_name_lower = f_path.name.lower()
        
        # Case A: The changed file is already a test file (must be inside tests/)
        if f_path.suffix == ".py" and "tests/" in f.replace("\\", "/"):
            if (ROOT / f).exists():
                matched_tests.add(str((ROOT / f).resolve()))
            continue
            
        # Case B: The changed file is a source file (e.g. certus_core.py)
        # We look for a test file in all_test_files that matches the stem
        stem = f_path.stem.lower()
        for t_file in all_test_files:
            t_name_lower = t_file.name.lower()
            if f"test_{stem}" in t_name_lower or f"{stem}_test" in t_name_lower:
                matched_tests.add(str(t_file.resolve()))
                
    # Convert absolute paths back to relative paths for prettier pytest output
    relative_tests = []
    for abs_path in matched_tests:
        try:
            rel = Path(abs_path).relative_to(ROOT)
            relative_tests.append(str(rel))
        except ValueError:
            relative_tests.append(abs_path)
            
    return sorted(relative_tests)

def main():
    parser = argparse.ArgumentParser(description="CERTUS Unified Test Runner & Verification Orchestrator")
    parser.add_argument("--pytest-only", action="store_true", help="Run only standard Pytest tests")
    parser.add_argument("--headless-only", action="store_true", help="Run only headless example validations")
    parser.add_argument("--gui-only", action="store_true", help="Run only GUI application smoke tests")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage check failure thresholds")
    parser.add_argument("--allow-gui", action="store_true", help="Disable QT offscreen platform (allow windows to open)")
    parser.add_argument("--changed-only", "-c", action="store_true", help="Run only tests matching changed files in git")
    parser.add_argument("--lf", "--last-failed", action="store_true", dest="last_failed", help="Rerun only the tests that failed at the last run")
    parser.add_argument("--ff", "--failed-first", action="store_true", dest="failed_first", help="Run all tests, but run the last failures first")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel via pytest-xdist (if installed)")
    
    args = parser.parse_args()
    
    # Configure QT offscreen by default for headless runs
    if not args.allow_gui:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        
    os.makedirs(str(ROOT / "logs"), exist_ok=True)
    
    print_banner("CERTUS UNIFIED TEST RUNNER")
    
    # Phase 0: Environment Checks
    env_ok, env_status = check_environment()
    if not env_ok:
        print(f"\n{Colors.FAIL}[FAIL] Critical dependencies missing. Aborting test execution.{Colors.ENDC}")
        sys.exit(1)
        
    print()
    
    # Determine phases to run
    run_all = not (args.pytest_only or args.headless_only or args.gui_only)
    
    results = []
    global_success = True
    
    # Phase 1: Pytest Suite
    if run_all or args.pytest_only:
        print_banner("PHASE 1: PYTEST SUITE")
        pytest_cmd = [sys.executable, "-m", "pytest"]
        
        should_run = True
        if args.changed_only:
            changed_files = get_git_changed_files()
            if not changed_files:
                print(f"{Colors.OKCYAN}[INFO] No files modified in Git. Pytest Phase Skipped.{Colors.ENDC}")
                results.append({
                    "name": "Pytest Suite (No Git Changes)",
                    "success": True,
                    "exit_code": 0,
                    "duration_s": 0.0,
                    "stdout": "No changes detected in Git.",
                    "stderr": "",
                    "failures": [],
                })
                should_run = False
            else:
                matched_tests = get_matching_test_files(changed_files)
                if not matched_tests:
                    print(f"{Colors.WARNING}[!] No matching test files found for modified source files. Pytest Phase Skipped.{Colors.ENDC}")
                    results.append({
                        "name": "Pytest Suite (No Matching Tests)",
                        "success": True,
                        "exit_code": 0,
                        "duration_s": 0.0,
                        "stdout": f"Modified files: {', '.join(changed_files)}. No corresponding tests found.",
                        "stderr": "",
                        "failures": [],
                    })
                    should_run = False
                else:
                    print(f"{Colors.OKCYAN}[INFO] Running tests for changed files ({len(matched_tests)} test files found):{Colors.ENDC}")
                    for mt in matched_tests:
                        print(f"  - {mt}")
                    pytest_cmd.extend(matched_tests)
                    
        if should_run:
            # Check if pytest-timeout is available to prevent infinite JIT/loop blocks
            try:
                import pytest_timeout
                pytest_cmd.append("--timeout=30")
            except ImportError:
                pass

            # Disable coverage threshold for selective runs to avoid false failures
            if not args.no_coverage and not args.changed_only and not args.last_failed:
                pytest_cmd.append("--cov-fail-under=40")
            else:
                pytest_cmd.append("--cov-fail-under=0") # Don't fail on coverage
                if args.no_coverage:
                    pytest_cmd.append("--no-cov")
                
            if args.last_failed:
                pytest_cmd.append("--lf")
            if args.failed_first:
                pytest_cmd.append("--ff")
                
            if args.parallel:
                try:
                    import xdist  # noqa: F401
                    pytest_cmd.extend(["-n", "auto"])
                    print(f"{Colors.OKCYAN}[INFO] Parallel execution enabled via pytest-xdist (-n auto){Colors.ENDC}")
                except ImportError:
                    print(f"{Colors.WARNING}[!] pytest-xdist is not installed. Falling back to sequential run.{Colors.ENDC}")
                    print(f"    To run in parallel, install pytest-xdist: pip install pytest-xdist")
                    
            res = run_step("Pytest Suite", pytest_cmd, ROOT)
            results.append(res)
            if not res["success"]:
                global_success = False

    # Phase 2: Headless Examples / Module Integration
    if run_all or args.headless_only:
        print_banner("PHASE 2: HEADLESS / MODULE INTEGRATION")
        headless_runner = ROOT / "tests" / "headless" / "run_all.py"
        headless_script = ROOT / "scripts" / "smoke" / "run_examples_headless.py"
        headless_targets = [
            ("Headless Suite Runner", headless_runner),
            ("Headless Examples", headless_script),
        ]
        for name, script_path in headless_targets:
            if script_path.exists():
                res = run_step(name, [sys.executable, str(script_path)], ROOT)
                results.append(res)
                if not res["success"]:
                    global_success = False
            else:
                print(f"{Colors.WARNING}[!] Headless validation script not found at {script_path}{Colors.ENDC}")

    # Phase 3: GUI Smoke Tests / Exhaustive smoke discovery
    if run_all or args.gui_only:
        print_banner("PHASE 3: GUI APPLICATION SMOKE TESTS")
        smoke_dir = ROOT / "scripts" / "smoke"
        smoke_scripts = sorted(
            [p for p in smoke_dir.glob("*.py") if p.name != "__init__.py"],
            key=lambda p: p.name.lower(),
        )
        if not smoke_scripts:
            print(f"{Colors.WARNING}[!] No smoke scripts found in {smoke_dir}{Colors.ENDC}")
        for script_path in smoke_scripts:
            human_name = script_path.stem.replace("_", " ").title()
            res = run_step(human_name, [sys.executable, str(script_path)], ROOT)
            results.append(res)
            if not res["success"]:
                global_success = False

    # Phase 4: Generate Report Dashboard
    print_banner("TESTS SUMMARY REPORT")
    
    total_time = sum(r["duration_s"] for r in results)
    
    # CLI summary table
    print(f"{Colors.BOLD}{'Validation Phase':<35} | {'Status':<8} | {'Duration':<8}{Colors.ENDC}")
    print("-" * 57)
    for r in results:
        status_str = f"{Colors.OKGREEN}PASSED{Colors.ENDC}" if r["success"] else f"{Colors.FAIL}FAILED{Colors.ENDC}"
        print(f"{r['name']:<35} | {status_str:<17} | {r['duration_s']:>6.2f}s")
    print("-" * 57)
    print(f"{Colors.BOLD}Total Elapsed Time: {total_time:.2f}s{Colors.ENDC}\n")
    
    # Extract and display SMART failures diagnostic
    all_failures = []
    for r in results:
        if "failures" in r and r["failures"]:
            all_failures.extend(r["failures"])
            
    if all_failures:
        print(f"{Colors.BOLD}{Colors.FAIL}🚨 SMART DIAGNOSTIC - DETECTED TEST FAILURES:{Colors.ENDC}")
        print(f"{Colors.FAIL}{'=' * 75}{Colors.ENDC}")
        for f in all_failures:
            print(f"  ❌ {Colors.WARNING}{f}{Colors.ENDC}")
        print(f"{Colors.FAIL}{'=' * 75}{Colors.ENDC}\n")
    else:
        print(f"{Colors.BOLD}{Colors.OKGREEN}✨ SMART DIAGNOSTIC - ALL SYSTEM VERIFICATIONS PASSED SUCCESSFULLY!{Colors.ENDC}\n")
        
    # Save JSON report
    report_path = ROOT / "logs" / "test_report.json"
    report_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "global_success": global_success,
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": sys.version.split()[0],
            "dependencies": env_status
        },
        "phases": [
            {
                "name": r["name"],
                "success": r["success"],
                "exit_code": r["exit_code"],
                "duration_s": r["duration_s"]
            } for r in results
        ]
    }
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"{Colors.OKCYAN}[OK] Structured JSON report saved to {report_path}{Colors.ENDC}")
    except IOError as e:
        print(f"{Colors.WARNING}[!] Could not save JSON report: {e}{Colors.ENDC}")

    if global_success:
        print(f"\n{Colors.BOLD}{Colors.OKGREEN}RESULT: ALL TEST PHASES COMPLETED SUCCESSFULLY!{Colors.ENDC}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.BOLD}{Colors.FAIL}RESULT: SOME TEST PHASES FAILED.{Colors.ENDC}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
