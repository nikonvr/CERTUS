from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_release_workflow_runs_critical_guardrails() -> None:
    repo = Path(__file__).resolve().parents[2]
    workflow = repo / ".github" / "workflows" / "release-windows.yml"
    assert workflow.exists(), "Workflow release-windows.yml missing"
    text = workflow.read_text(encoding="utf-8")

    required_tokens = [
        "tests/unit/test_seed_contract_global.py",
        "tests/unit/test_certus_services.py",
        "tests/unit/test_release_guardrails.py",
        "python tools/release_checks.py",
        "python tools/release_checks.py --check-frozen",
        "python tools/release_checks.py --check-frozen-run",
        "./tools/smoke_release.ps1",
    ]
    missing = [tok for tok in required_tokens if tok not in text]
    assert not missing, "Guardrails not connected in the workflow: " + ", ".join(missing)


@pytest.mark.unit
def test_critical_guardrail_files_exist() -> None:
    repo = Path(__file__).resolve().parents[2]
    required_files = [
        repo / "tests" / "unit" / "test_seed_contract_global.py",
        repo / "tests" / "unit" / "test_certus_services.py",
        repo / "tools" / "release_checks.py",
        repo / "tools" / "smoke_release.ps1",
    ]
    missing = [str(p.relative_to(repo)) for p in required_files if not p.exists()]
    assert not missing, "Guardrail files missing: " + ", ".join(missing)


# =============================================================================
# The frozen build: what `tools/release_checks.py` accepts and refuses
# =============================================================================


def _release_checks():
    """`tools/release_checks.py` as a module (`tools/` is not a package)."""
    path = Path(__file__).resolve().parents[2] / "tools" / "release_checks.py"
    spec = importlib.util.spec_from_file_location("release_checks_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_the_release_structure_holds_on_the_repository() -> None:
    assert _release_checks().check_release_structure() == []


def _frozen_folder(tmp_path: Path, rc, *, data: bool = True, runtime: bool = True, openmp: bool = True) -> Path:
    """A folder that looks like `dist/CERTUS_HUB/`: a PE launcher, the runtime, Numba's OpenMP layer, the data."""
    folder = tmp_path / rc.FROZEN_NAME
    folder.mkdir()
    header = bytearray(b"MZ" + bytes(0x7E))
    header[0x3C:0x40] = (0x80).to_bytes(4, "little")
    (folder / f"{rc.FROZEN_NAME}.exe").write_bytes(bytes(header) + b"PE" + bytes(2) + bytes(64))
    if runtime:
        (folder / "python314.dll").write_bytes(b"runtime")
    if openmp:
        (folder / "numba" / "np" / "ufunc").mkdir(parents=True)
        (folder / "numba" / "np" / "ufunc" / "omppool.cp314-win_amd64.pyd").write_bytes(b"layer")
        (folder / "VCOMP140.DLL").write_bytes(b"runtime")
    for name in rc.FROZEN_REQUIRED_FILES if data else ():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"data")
    return folder


@pytest.fixture
def rc(tmp_path, monkeypatch):
    module = _release_checks()
    monkeypatch.setattr(module, "DIST_DIR", tmp_path)
    monkeypatch.setattr(module, "FROZEN_MIN_BYTES", 1)  # the size floor is for a real build
    return module


@pytest.mark.unit
def test_a_complete_frozen_folder_is_accepted(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc)

    assert rc.check_frozen_artifact() == []


@pytest.mark.unit
def test_a_frozen_folder_without_the_data_the_code_reads_is_refused(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc, data=False)

    errors = rc.check_frozen_artifact()

    assert [name for name in rc.FROZEN_REQUIRED_FILES if not any(name in e for e in errors)] == []


@pytest.mark.unit
def test_a_frozen_folder_without_the_python_runtime_is_refused(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc, runtime=False)

    assert any("Python runtime" in e for e in rc.check_frozen_artifact())


@pytest.mark.unit
def test_a_frozen_folder_without_numba_s_openmp_layer_is_refused(tmp_path, rc) -> None:
    """D87: the frozen build computes on the OpenMP layer; without it the first parallel kernel fails."""
    _frozen_folder(tmp_path, rc, openmp=False)

    errors = rc.check_frozen_artifact()

    assert any("OpenMP layer" in e for e in errors)
    assert any("vcomp140.dll" in e for e in errors)


@pytest.mark.unit
def test_a_missing_frozen_build_is_reported(rc) -> None:
    assert any("Missing frozen artifact" in e for e in rc.check_frozen_artifact())
    assert any("Missing frozen artifact" in e for e in rc.check_frozen_functional_startup(timeout_sec=1))
    assert any("Missing frozen artifact" in e for e in rc.check_frozen_modules_startup(timeout_sec=1))


@pytest.mark.unit
def test_a_process_that_stays_up_is_accepted_and_stopped(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc)

    assert rc._process_stays_up([sys.executable, "-c", "import time; time.sleep(60)"], "Frozen hub", 1) == []


@pytest.mark.unit
@pytest.mark.parametrize("code", [0, 3])
def test_a_process_that_stops_by_itself_is_refused_whatever_its_exit_code(tmp_path, rc, code) -> None:
    # Exit code 0 is the trap: the module that ran a library file as `__main__` "succeeded" at once.
    _frozen_folder(tmp_path, rc)

    errors = rc._process_stays_up([sys.executable, "-c", f"import sys; sys.exit({code})"], "Frozen module X", 30)

    assert len(errors) == 1
    assert "Frozen module X stopped by itself" in errors[0]
    assert f"code {code}" in errors[0]


@pytest.mark.unit
def test_the_refusal_quotes_the_log_the_process_wrote(tmp_path, rc) -> None:
    folder = _frozen_folder(tmp_path, rc)
    (folder / "certus_x.log").write_text(chr(10).join(["first", "failed to open the database"]), encoding="utf-8")

    errors = rc._process_stays_up([sys.executable, "-c", "pass"], "Frozen module X", 30)

    assert "failed to open the database" in errors[0]


@pytest.mark.unit
def test_a_frozen_crash_reports_native_stderr_and_watchdog_dump(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc)
    code = (
        "from pathlib import Path; import sys; "
        "Path('logs').mkdir(exist_ok=True); "
        "Path('logs/crash_dump.log').write_text('Fatal Python error: Aborted'); "
        "sys.stderr.write('QThread: Destroyed while thread is still running\\n'); "
        "sys.stderr.flush(); sys.exit(3)"
    )

    errors = rc._process_stays_up([sys.executable, "-c", code], "Frozen module CERTUS_RE", 30)

    assert len(errors) == 1
    assert "code 3" in errors[0]
    assert "QThread: Destroyed while thread is still running" in errors[0]
    assert "Fatal Python error: Aborted" in errors[0]


@pytest.mark.unit
def test_a_living_module_that_reports_unsafe_numba_concurrency_is_refused(tmp_path, rc) -> None:
    _frozen_folder(tmp_path, rc)
    code = (
        "import sys, time; "
        "sys.stderr.write('Numba workqueue threading layer is terminating: '",
        "'Concurrent access has been detected.\\n'); "
        "sys.stderr.flush(); time.sleep(60)"
    )

    errors = rc._process_stays_up([sys.executable, "-c", "".join(code)], "Frozen module CERTUS_RE", 1)

    assert len(errors) == 1
    assert "Concurrent access has been detected" in errors[0]


@pytest.mark.unit
def test_release_keeps_frozen_diagnostics_after_a_failed_startup() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/release-windows.yml").read_text(
        encoding="utf-8"
    )

    assert "name: Upload frozen diagnostics" in workflow
    diagnostics = workflow.split("name: Upload frozen diagnostics", 1)[1]
    assert "always()" in diagnostics
    assert "dist/CERTUS_HUB/logs/**" in diagnostics
    assert "dist/CERTUS_HUB/*.log" in diagnostics


@pytest.mark.unit
def test_every_module_of_the_catalog_is_started_the_way_the_hub_starts_it(tmp_path, rc, monkeypatch) -> None:
    from certus.core.certus_hub_config import RUN_MODULE_FLAG

    folder = _frozen_folder(tmp_path, rc)
    started = []
    monkeypatch.setattr(rc, "_process_stays_up", lambda command, label, timeout: started.append((command, label)) or [])

    assert rc.check_frozen_modules_startup(timeout_sec=1) == []

    commands = [command for command, _label in started]
    assert all(command[:2] == [str(folder / "CERTUS_HUB.exe"), RUN_MODULE_FLAG] for command in commands)
    assert [command[2] for command in commands] == list(rc._hub_catalog()[1])
    assert len(commands) == 10


@pytest.mark.unit
@pytest.mark.skipif(sys.platform != "win32", reason="the native dialog of a frozen Windows build")
def test_a_process_that_stays_up_behind_a_dialog_is_refused(tmp_path, rc) -> None:
    # PyInstaller's "Unhandled exception in script" box keeps a failed module alive and looking
    # healthy: STRAT passed a "stays up" check for as long as `scripts/` was missing from the build.
    _frozen_folder(tmp_path, rc)
    code = "import ctypes; ctypes.windll.user32.MessageBoxW(0, 'boom', 'Unhandled exception in script', 0)"

    errors = rc._process_stays_up([sys.executable, "-c", code], "Frozen module X", 30)

    assert len(errors) == 1
    assert "opened a dialog" in errors[0]
    assert "Unhandled exception in script" in errors[0]


@pytest.mark.unit
def test_the_refusal_quotes_the_startup_log_before_any_other(tmp_path, rc) -> None:
    folder = _frozen_folder(tmp_path, rc)
    (folder / "certus_frozen_startup.log").write_text(
        chr(10).join(["Traceback", "ModuleNotFoundError: No module named 'x'"]), encoding="utf-8"
    )
    (folder / "certus_zzz.log").write_text("something written later", encoding="utf-8")

    errors = rc._process_stays_up([sys.executable, "-c", "pass"], "Frozen module X", 30)

    assert "ModuleNotFoundError: No module named 'x'" in errors[0]
    assert "something written later" not in errors[0]
