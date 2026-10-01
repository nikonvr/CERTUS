"""No package goes below its coverage floor, and a floor that is too low says so (S3.1).

`scripts/check_coverage_floors.py` reads a `coverage json` report and `tests/coverage_floors.json`. Each test
builds a small report whose answer is known, so a comparison written the wrong way round, a percentage of
branches read instead of lines, or a package with no measured line counted as 0 % fails here.

The floors on disk are the measure of 2026-09-30 minus one point: they protect what exists and set no goal.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("certus_scripts_floors", ROOT / "scripts" / "check_coverage_floors.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


floors_script = _load()


def _report(**packages: tuple[int, int]) -> dict:
    """A `coverage json` report: `physics=(covered, statements)` becomes one file under certus/physics/."""
    return {
        "files": {
            f"certus/{name}/module.py": {
                "summary": {"covered_lines": covered, "num_statements": lines, "num_branches": 50, "covered_branches": 0,
                            "percent_covered": 0.0},
            }
            for name, (covered, lines) in packages.items()
        }
    }


def test_a_package_under_its_floor_fails_and_names_itself() -> None:
    below, to_raise, missing = floors_script.check(_report(core=(40, 100)), {"certus/core/": 50.0})

    assert len(below) == 1
    assert "certus/core/" in below[0]
    assert "40.0" in below[0]
    assert to_raise == []
    assert missing == []


def test_a_package_at_its_floor_passes_and_one_far_above_says_to_raise_it() -> None:
    at_floor = floors_script.check(_report(core=(50, 100)), {"certus/core/": 50.0})
    far_above = floors_script.check(_report(core=(60, 100)), {"certus/core/": 50.0})

    assert at_floor == ([], [], [])
    assert far_above[0] == []
    assert "a relever" in far_above[1][0]


def test_lines_are_read_not_the_percentage_that_mixes_branches() -> None:
    report = _report(core=(50, 100))
    report["files"]["certus/core/module.py"]["summary"]["percent_covered"] = 1.0  # 50 branches, none covered

    assert floors_script.check(report, {"certus/core/": 50.0}) == ([], [], [])


def test_a_package_with_no_measured_line_is_reported_and_not_counted_as_zero() -> None:
    below, _, missing = floors_script.check(_report(core=(50, 100)), {"certus/physics/": 45.0})

    assert below == []  # 0 lines is not 0 %: the JIT hides physics in an ordinary run
    assert missing == ["certus/physics/"]


def test_the_prefix_is_matched_on_the_folder_and_windows_paths_are_read() -> None:
    report = _report(core=(50, 100))
    report["files"]["certus\\core_extra\\other.py"] = {"summary": {"covered_lines": 0, "num_statements": 1000}}

    below, _, _ = floors_script.check(report, {"certus/core/": 50.0})

    assert below == []  # `certus/core_extra/` does not count as `certus/core/`


def test_the_command_exits_one_under_a_floor_and_zero_otherwise(tmp_path, capsys) -> None:
    floors = tmp_path / "floors.json"
    floors.write_text(json.dumps({"lignes": {"certus/core/": 50.0}, "noyaux": {}}), encoding="utf-8")
    low, high = tmp_path / "low.json", tmp_path / "high.json"
    low.write_text(json.dumps(_report(core=(40, 100))), encoding="utf-8")
    high.write_text(json.dumps(_report(core=(52, 100))), encoding="utf-8")

    assert floors_script.main([str(low), "--planchers", str(floors)]) == 1
    assert "SOUS LE PLANCHER" in capsys.readouterr().out
    assert floors_script.main([str(high), "--planchers", str(floors)]) == 0
    assert floors_script.main([str(tmp_path / "absent.json"), "--planchers", str(floors)]) == 2


def test_the_floors_on_disk_are_well_formed() -> None:
    floors = json.loads((ROOT / "tests" / "coverage_floors.json").read_text(encoding="utf-8"))

    assert set(floors) >= {"lignes", "noyaux"}
    for section in ("lignes", "noyaux"):
        assert floors[section], f"no floor in `{section}`"
        for prefix, floor in floors[section].items():
            assert prefix.startswith("certus/"), prefix
            assert prefix.endswith("/"), prefix
            assert 0.0 < floor <= 100.0, (prefix, floor)


@pytest.mark.parametrize("prefix", ["certus/", "certus/core/", "certus/utils/"])
def test_the_ordinary_run_has_a_floor_for_the_packages_it_can_see(prefix) -> None:
    floors = json.loads((ROOT / "tests" / "coverage_floors.json").read_text(encoding="utf-8"))

    assert prefix in floors["lignes"]
