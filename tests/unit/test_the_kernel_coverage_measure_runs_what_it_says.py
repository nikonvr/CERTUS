"""`scripts/measure_kernel_coverage.py` measures the compiled kernels without compiling them, and says which tests it ran (audit v2, plan S3.1 / S3.2).

The measure of 2026-09-30 ran `tests/oracle` and `tests/core` with `NUMBA_DISABLE_JIT=1` and read 45.9 % for `certus/physics/`. It ignored the tests written
afterwards for the STRAT kernels, which live in `tests/unit`; with them the same package reads 74.0 %. The `kernels` marker (registered in `pyproject.toml`
since S3.2, carried by five files and by no job) is now the list, and the script is the job. What is pinned here, with a fake runner (the real measure takes
a minute and a half):

    the two runs: the three whole directories, then `tests/unit -m kernels`, appended to the same coverage data, with the compilation off
    the percentage is the one of `certus/physics/` alone, read from `coverage json`
    --check refuses a measure under the floor of `tests/coverage_floors.json`, and a failing test makes the measure fail instead of passing quietly
    the marker is registered, the files that carry it are the ones the measure counts, and the committed floor protects the measure of the day
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import measure_kernel_coverage as measure  # noqa: E402


def report(physics: tuple[int, int], elsewhere: tuple[int, int] = (0, 100)) -> dict:
    """A `coverage json` with `physics = (covered, statements)` for one file of certus/physics/ and a file elsewhere."""
    return {
        "files": {
            "certus/physics/certus_tmm_core.py": {"summary": {"covered_lines": physics[0], "num_statements": physics[1]}},
            "certus/core/certus_core.py": {"summary": {"covered_lines": elsewhere[0], "num_statements": elsewhere[1]}},
        }
    }


class FakeRunner:
    """Stands for subprocess.run: records the commands, writes the report the second command is asked for, and returns the exit codes it is given."""

    def __init__(self, coverage_report: dict | None, codes: tuple[int, int] = (0, 0)) -> None:
        self.report = coverage_report
        self.codes = list(codes)
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command, cwd=None, env=None):
        self.calls.append((command, env))
        target = next((a.split("json:", 1)[1] for a in command if a.startswith("--cov-report=json:")), None)
        if target and self.report is not None:
            Path(target).write_text(json.dumps(self.report), encoding="utf-8")
        return SimpleNamespace(returncode=self.codes.pop(0))


def floors_file(tmp_path: Path, floor: float) -> Path:
    path = tmp_path / "floors.json"
    path.write_text(json.dumps({"noyaux": {"certus/physics/": floor}}), encoding="utf-8")
    return path


# --- what is run -----------------------------------------------------------------------------------------------------------------------------


def test_the_first_run_is_the_three_whole_directories_and_writes_no_report():
    first, _ = measure.commands(Path("out.json"))
    assert first[-4:-1] == ["tests/oracle", "tests/core", "tests/property"]
    assert first[-1] == "--cov-report="
    assert "--cov-append" not in first


def test_the_second_run_is_the_marked_unit_tests_appended_to_the_same_data():
    _, second = measure.commands(Path("out.json"))
    assert second[second.index("tests/unit") + 1 : second.index("tests/unit") + 3] == ["-m", "kernels"]
    assert "--cov-append" in second
    assert "--cov-report=json:out.json" in second


def test_both_runs_measure_certus_and_drop_the_default_options_that_would_write_html():
    for command in measure.commands(Path("out.json")):
        assert "--cov=certus" in command
        assert "addopts=" in command


def test_the_compilation_is_off_and_the_coverage_data_is_kept_aside(tmp_path):
    env = measure.environment(tmp_path / "coverage.data")
    assert env["NUMBA_DISABLE_JIT"] == "1"
    assert env["COVERAGE_FILE"] == str(tmp_path / "coverage.data")


def test_main_runs_both_commands_in_the_environment_without_compilation(tmp_path):
    runner = FakeRunner(report((60, 100)))
    measure.main(["--json", str(tmp_path / "r.json")], run=runner)
    assert len(runner.calls) == 2
    assert all(env["NUMBA_DISABLE_JIT"] == "1" for _, env in runner.calls)


# --- what is read ----------------------------------------------------------------------------------------------------------------------------


def test_the_percentage_is_the_one_of_the_physics_package_alone():
    assert measure.physics_lines(report((60, 100), elsewhere=(0, 900))) == (60, 100)


def test_a_report_without_the_physics_package_is_an_error():
    with pytest.raises(KeyError):
        measure.physics_lines({"files": {"certus/core/x.py": {"summary": {"covered_lines": 1, "num_statements": 2}}}})


def test_main_prints_the_percentage_and_keeps_the_report(tmp_path, capsys):
    kept = tmp_path / "kept.json"
    assert measure.main(["--json", str(kept)], run=FakeRunner(report((60, 100)))) == 0
    assert "60.0 % (60/100 lignes)" in capsys.readouterr().out
    assert kept.is_file()


def test_an_unreadable_or_missing_report_is_exit_2(tmp_path, capsys):
    assert measure.main(["--json", str(tmp_path / "none.json")], run=FakeRunner(None)) == 2
    assert "JSON illisible" in capsys.readouterr().err


# --- what is refused -------------------------------------------------------------------------------------------------------------------------


def test_check_refuses_a_measure_under_the_floor(tmp_path, capsys):
    status = measure.main(["--json", str(tmp_path / "r.json"), "--check", "--planchers", str(floors_file(tmp_path, 70.0))], run=FakeRunner(report((60, 100))))
    assert status == 1
    assert "SOUS LE PLANCHER" in capsys.readouterr().out


def test_check_accepts_a_measure_above_the_floor_and_says_when_the_floor_can_rise(tmp_path, capsys):
    status = measure.main(["--json", str(tmp_path / "r.json"), "--check", "--planchers", str(floors_file(tmp_path, 50.0))], run=FakeRunner(report((60, 100))))
    out = capsys.readouterr().out
    assert status == 0
    assert "SOUS LE PLANCHER" not in out
    assert "a relever" in out


def test_without_check_a_low_measure_is_only_reported(tmp_path):
    assert measure.main(["--json", str(tmp_path / "r.json"), "--planchers", str(floors_file(tmp_path, 99.0))], run=FakeRunner(report((60, 100)))) == 0


@pytest.mark.parametrize("codes", [(1, 0), (0, 1)])
def test_a_failing_test_fails_the_measure_even_above_the_floor(tmp_path, capsys, codes):
    status = measure.main(["--json", str(tmp_path / "r.json"), "--check", "--planchers", str(floors_file(tmp_path, 10.0))], run=FakeRunner(report((60, 100)), codes))
    assert status == 1
    assert "UN TEST A ECHOUE" in capsys.readouterr().err


# --- the marker and the floor ----------------------------------------------------------------------------------------------------------------


def _files_carrying_the_marker() -> list[str]:
    found = []
    for path in sorted((ROOT / "tests" / "unit").glob("test_*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "pytestmark" for t in node.targets) and "kernels" in ast.unparse(node.value):
                found.append(path.name)
    return found


def test_the_marker_is_registered():
    assert '"kernels:' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_unit_tests_of_the_kernels_carry_the_marker():
    carrying = _files_carrying_the_marker()
    assert len(carrying) >= 17  # five written for S3.2 and S5.1, twelve more that the 74.0 % measure counts
    for name in ("test_strat_batch_kernels_match_the_oracle_and_their_definitions.py", "test_strat_poem.py", "test_physics_properties.py"):
        assert name in carrying


def test_the_committed_floor_protects_the_measure_of_the_day_and_names_the_script():
    floors = json.loads((ROOT / "tests" / "coverage_floors.json").read_text(encoding="utf-8"))
    assert floors["noyaux"]["certus/physics/"] >= 70.0  # the plan's target, reached by this measure and not by oracle + core alone
    assert "measure_kernel_coverage" in floors["_mesure_noyaux"]
