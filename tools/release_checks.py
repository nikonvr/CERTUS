from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where `tools/build_frozen.ps1` leaves the build (PyInstaller's default).
DIST_DIR = REPO_ROOT / "dist"

#: The frozen suite is a FOLDER (`dist/CERTUS_HUB/`): one executable, that is the hub and every
#: module (`CERTUS_HUB.exe --run-module NAME`), and the data next to it. See `certus_hub.spec`.
FROZEN_NAME = "CERTUS_HUB"

#: Read by the code through `get_resource_path`, so they must sit next to the executable.
FROZEN_REQUIRED_FILES = (
    "certus.ico",
    "certus.svg",
    "data/materials_v1.json",
    "pages/CERTUS_HUB.html",
)

#: Sanity bounds on the size of the whole folder (Qt, NumPy, SciPy and Numba are in it).
FROZEN_MIN_BYTES = 50_000_000
FROZEN_MAX_BYTES = 3_000_000_000

#: How often a started process is looked at (seconds).
POLL_SEC = 0.1


def _parse_pyproject_dependencies(pyproject_path: Path) -> set[str]:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(
        r"^\[project\]\s.*?^dependencies\s*=\s*\[(.*?)^\]\s*$",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Cannot read [project].dependencies in pyproject.toml")
    block = match.group(1)
    names: set[str] = set()
    for raw_line in block.splitlines():
        line = raw_line.strip().strip(",").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith('"') and line.endswith('"'):
            spec = line[1:-1]
        else:
            spec = line
        pkg = re.split(r"[<>=!~;\[\s]", spec, maxsplit=1)[0].strip()
        if pkg:
            names.add(pkg.lower())
    return names


def _parse_lock_requirements(lock_path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==", 1)[0].strip()
        if pkg:
            names.add(pkg.lower())
    return names


def check_lock_is_strictly_pinned() -> list[str]:
    lockfile = REPO_ROOT / "requirements.lock"
    if not lockfile.exists():
        return [f"Missing file: {lockfile.name}"]
    errors: list[str] = []
    for idx, raw_line in enumerate(lockfile.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash="):
            continue
        if "==" not in line:
            errors.append(
                f"requirements.lock:{idx} not strictly pinned (expected 'package==version'): {line}"
            )
            continue
        pkg, ver = line.split("==", 1)
        if not pkg.strip() or not ver.strip():
            errors.append(f"requirements.lock:{idx} invalid lock entry: {line}")
    return errors


def check_lock_consistency() -> list[str]:
    pyproject = REPO_ROOT / "pyproject.toml"
    lockfile = REPO_ROOT / "requirements.lock"
    if not pyproject.exists():
        return [f"Missing file: {pyproject.name}"]
    if not lockfile.exists():
        return [f"Missing file: {lockfile.name}"]

    pyproject_deps = _parse_pyproject_dependencies(pyproject)
    lock_deps = _parse_lock_requirements(lockfile)
    missing = sorted(dep for dep in pyproject_deps if dep not in lock_deps)
    errors: list[str] = []
    if missing:
        errors.append(
            "pyproject dependencies missing from lockfile: " + ", ".join(missing)
        )
    return errors


def _frozen_folder() -> Path:
    return DIST_DIR / FROZEN_NAME


def _frozen_exe() -> Path:
    return _frozen_folder() / f"{FROZEN_NAME}.exe"


def check_frozen_artifact() -> list[str]:
    folder = _frozen_folder()
    exe = _frozen_exe()
    errors: list[str] = []
    if not exe.exists():
        errors.append(f"Missing frozen artifact: dist/{FROZEN_NAME}/{exe.name}")
        return errors

    try:
        with exe.open("rb") as handle:
            head = handle.read(65536)
        if len(head) < 64 or head[:2] != b"MZ":
            errors.append("Invalid frozen artifact: missing DOS/PE signature (MZ)")
        else:
            pe_off = int.from_bytes(head[0x3C:0x40], "little")
            if pe_off + 4 > len(head) or head[pe_off:pe_off + 4] != b"PE\x00\x00":
                errors.append("Invalid frozen artifact: PE header not found")
    except OSError as exc:
        errors.append(f"Cannot read frozen artifact: {exc}")

    # The executable of a folder build is only the launcher: what makes the build complete is
    # what sits next to it, and the size of the whole folder.
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    if size < FROZEN_MIN_BYTES:
        errors.append(f"Frozen folder too small ({size} bytes) - build potentially incomplete")
    if size > FROZEN_MAX_BYTES:
        errors.append(f"Frozen folder abnormally large ({size} bytes)")
    if not list(folder.glob("python3*.dll")):
        errors.append("Frozen folder holds no Python runtime (python3*.dll)")
    for name in FROZEN_REQUIRED_FILES:
        if not (folder / name).is_file():
            errors.append(f"Frozen folder is missing a file the code reads: {name}")
    return errors


def _newest_log_tail(folder: Path, since: float, lines: int = 6) -> str:
    """Last lines of the log the frozen process wrote after `since` (a windowed exe has no console).

    The start-up failure log is the one that says why, so it comes first.
    """
    logs = [p for p in folder.glob("*.log") if p.stat().st_mtime >= since]
    if not logs:
        return ""
    startup = folder / "certus_frozen_startup.log"
    newest = startup if startup in logs else max(logs, key=lambda p: p.stat().st_mtime)
    try:
        tail = newest.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return ""
    return f" [{newest.name}: " + " | ".join(line.strip() for line in tail if line.strip()) + "]"


def _window_titles_of(pid: int) -> list[str]:
    """Titles of the visible windows that process `pid` owns (Windows only).

    The checks run with `QT_QPA_PLATFORM=offscreen`, where Qt draws no native window: a visible one
    is a native dialog, and the one that matters is PyInstaller's "Unhandled exception in script"
    box, which keeps a failed process alive and looking healthy.
    """
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    titles: list[str] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, 256)
            titles.append(buffer.value)
        return True

    user32.EnumWindows(visit, 0)
    return titles


def _process_stays_up(command: list[str], label: str, timeout_sec: float) -> list[str]:
    """Start `command` headless; it must still be running after `timeout_sec`, and show no dialog.

    A GUI process that ends by itself while nobody touches it has failed to start, whatever its
    exit code: a healthy one waits for the user. One that stays up behind an error box has failed
    as well.
    """
    folder = _frozen_folder()
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    start = time.time()
    proc = subprocess.Popen(command, env=env, cwd=str(folder))
    try:
        while (time.time() - start) < float(timeout_sec):
            code = proc.poll()
            if code is not None:
                return [
                    f"{label} stopped by itself after {time.time() - start:.1f}s with code {code}"
                    + _newest_log_tail(folder, start - 1.0)
                ]
            titles = _window_titles_of(proc.pid)
            if titles:
                return [f"{label} opened a dialog: {titles}" + _newest_log_tail(folder, start - 1.0)]
            time.sleep(POLL_SEC)
        return []
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def _hub_catalog() -> tuple[str, tuple[str, ...]]:
    """The flag that starts a module, and the modules of the hub catalog (what the frozen hub can start)."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from certus.core.certus_frozen_entry import catalog_modules
        from certus.core.certus_hub_config import RUN_MODULE_FLAG
    finally:
        sys.path.remove(str(REPO_ROOT))
    return RUN_MODULE_FLAG, catalog_modules()


def check_frozen_functional_startup(timeout_sec: int = 12) -> list[str]:
    exe = _frozen_exe()
    if not exe.exists():
        return [f"Missing frozen artifact: dist/{FROZEN_NAME}/{exe.name}"]
    return _process_stays_up([str(exe)], "Frozen hub", timeout_sec)


def check_frozen_modules_startup(timeout_sec: int = 12) -> list[str]:
    """Every module of the catalog, started the way the frozen hub starts it."""
    exe = _frozen_exe()
    if not exe.exists():
        return [f"Missing frozen artifact: dist/{FROZEN_NAME}/{exe.name}"]

    flag, modules = _hub_catalog()
    errors: list[str] = []
    for name in modules:
        errors.extend(_process_stays_up([str(exe), flag, name], f"Frozen module {name}", timeout_sec))
    return errors


def check_release_structure() -> list[str]:
    errors: list[str] = []

    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        errors.append("Missing file: pyproject.toml")
    else:
        py_text = pyproject.read_text(encoding="utf-8")
        if 'requires-python = ">=3.14.5"' not in py_text:
            errors.append("pyproject.toml must enforce requires-python >= 3.14.5")

    workflow = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"
    if not workflow.exists():
        return ["Missing workflow: .github/workflows/release-windows.yml"]
    wf_text = workflow.read_text(encoding="utf-8")
    required_tokens = [
        'python-version: [ "3.14.5" ]',
        "Confirm Python release target",
        "python tools/release_checks.py",
        "python tools/release_checks.py --check-frozen",
        "python tools/release_checks.py --check-frozen-run",
        "./tools/smoke_release.ps1",
        "./tools/build_frozen.ps1",
        "actions/upload-artifact@",
        "dist/CERTUS_HUB/**",
        "tests/unit/test_release_guardrails.py",
    ]
    for token in required_tokens:
        if token not in wf_text:
            errors.append(f"Release workflow incomplete (missing token): {token}")

    smoke_script = REPO_ROOT / "tools" / "smoke_release.ps1"
    if not smoke_script.exists():
        errors.append("Missing script: tools/smoke_release.ps1")
    else:
        smoke_text = smoke_script.read_text(encoding="utf-8")
        if "QT_QPA_PLATFORM" not in smoke_text or "offscreen" not in smoke_text:
            errors.append("Non-compliant smoke script: QT_QPA_PLATFORM=offscreen required")
        if "test_gui_smoke.py" not in smoke_text or "test_smoke_certus_index_spline.py" not in smoke_text:
            errors.append("Incomplete smoke script: expected smoke tests missing")

    spec_file = REPO_ROOT / "certus_hub.spec"
    if not spec_file.exists():
        errors.append("Missing spec: certus_hub.spec")
    else:
        spec_text = spec_file.read_text(encoding="utf-8")
        for token in (
            "frozen_entry.py",
            'name="CERTUS_HUB"',
            'icon="certus.ico"',
            'contents_directory="."',
            "COLLECT(",
        ):
            if token not in spec_text:
                errors.append(f"Incomplete frozen spec (missing token): {token}")
        if 'console=False' not in spec_text:
            errors.append("Incomplete frozen spec: expected console=False")

    for entry in ("tools/frozen_entry.py", "certus/core/certus_frozen_entry.py"):
        if not (REPO_ROOT / entry).exists():
            errors.append(f"Missing frozen entry: {entry}")

    for asset in ("certus.ico", "certus.svg"):
        if not (REPO_ROOT / asset).exists():
            errors.append(f"Missing release asset: {asset}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Release checks for CERTUS CI")
    parser.add_argument(
        "--check-frozen",
        action="store_true",
        help="Check the presence/quality of the frozen artifact.",
    )
    parser.add_argument(
        "--check-frozen-run",
        action="store_true",
        help="Checks for minimal functional startup of the frozen hub and of each frozen module.",
    )
    parser.add_argument(
        "--startup-timeout-sec",
        type=int,
        default=12,
        help="Timeout (seconds) for each frozen boot check.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    failures.extend(check_lock_consistency())
    failures.extend(check_lock_is_strictly_pinned())
    failures.extend(check_release_structure())
    if args.check_frozen:
        failures.extend(check_frozen_artifact())
    if args.check_frozen_run:
        timeout = int(args.startup_timeout_sec)
        failures.extend(check_frozen_functional_startup(timeout_sec=timeout))
        failures.extend(check_frozen_modules_startup(timeout_sec=timeout))

    if failures:
        print("[CERTUS] release checks FAILED")
        for item in failures:
            print(f"- {item}")
        return 1

    print("[CERTUS] release checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
