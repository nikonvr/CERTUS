"""`scripts/metrics.py` reads the indicators of the improvement plan and never invents one.

The 8-week plan of the 2026-09-30 audit opens and closes every week on the same table. A table is only worth
its numbers if a number that was not measured says so: each test below builds a small tree whose answer is
known, so a wrong port of the audit's counting (a function-level import counted as an edge, a helper named
`_assert_ok` not seen as an assertion, `n/a` printed as 0) fails here and not in the middle of week 5.

The counts on the real tree (777 files, 8 cycles, 47 upward edges, 74 swallowed excepts, 57 tests without an
assertion, 69 modules no test names) were reproduced by the script on 2026-09-30 and are not asserted here:
they move with every commit.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("certus_scripts_metrics", ROOT / "scripts" / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


metrics = _load()


def _function(lines: int) -> str:
    """A function of exactly `lines` lines, `def` line included."""
    return "def f():\n" + "    x = 1\n" * (lines - 1)


def _branches(n: int) -> str:
    """A function of complexity 1 + n."""
    return "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(n))


# =============================================================================
# Layers, cycles
# =============================================================================


def test_a_module_level_import_of_a_higher_layer_is_one_upward_edge() -> None:
    sources = {
        "certus/physics/kernel.py": "from certus.core import settings\n",
        "certus/core/settings.py": "LIMIT = 1\n",
        "certus/ui/window.py": "from certus.core import settings\n",  # ui imports core: downward
        "certus/physics/lazy.py": "def f():\n    from certus.ui import window\n    return window\n",  # not at import
    }

    measures, detail = metrics.architecture(sources)

    assert measures["arch.aretes_montantes"] == 1
    assert detail["aretes_montantes"] == {"certus.physics -> certus.core": 1}


def test_an_import_inside_a_function_is_neither_an_edge_nor_a_cycle() -> None:
    late = {
        "certus/core/a.py": "from certus.core import b\n",
        "certus/core/b.py": "def late():\n    from certus.core import a\n    return a\n",
    }
    eager = {**late, "certus/core/b.py": "from certus.core import a\n"}

    assert metrics.architecture(late)[0]["arch.cycles"] == 0
    assert metrics.architecture(eager)[0]["arch.cycles"] == 1


def test_a_relative_import_is_resolved_against_its_own_package() -> None:
    sources = {
        "certus/physics/__init__.py": "",
        "certus/physics/a.py": "from . import b\n",
        "certus/physics/b.py": "from .a import thing\n",
    }

    assert metrics.architecture(sources)[0]["arch.cycles"] == 1


# =============================================================================
# Size, complexity, swallowed exceptions
# =============================================================================


def test_a_function_is_long_above_three_hundred_lines() -> None:
    assert metrics.architecture({"certus/core/a.py": _function(300)})[0]["arch.fonctions_gt300"] == 0
    assert metrics.architecture({"certus/core/a.py": _function(301)})[0]["arch.fonctions_gt300"] == 1
    # The limit is on certus/: the same function in a script does not count.
    assert metrics.architecture({"scripts/a.py": _function(301)})[0]["arch.fonctions_gt300"] == 0


def test_complexity_is_one_plus_the_branches_and_is_high_above_sixty() -> None:
    assert metrics.architecture({"certus/core/a.py": _branches(59)})[0]["arch.fonctions_cc_gt60"] == 0
    assert metrics.architecture({"certus/core/a.py": _branches(60)})[0]["arch.fonctions_cc_gt60"] == 1


def test_only_a_broad_handler_that_does_nothing_is_swallowed() -> None:
    source = textwrap.dedent("""
        def f():
            try:
                g()
            except Exception:
                pass
            try:
                g()
            except ValueError:
                pass
            try:
                g()
            except Exception as error:
                print(error)
            try:
                g()
            except BaseException:
                ...
            for _ in range(1):
                try:
                    g()
                except:
                    continue
    """)

    assert metrics.architecture({"certus/core/a.py": source})[0]["arch.except_avales"] == 3


# =============================================================================
# Tests
# =============================================================================


def test_a_test_without_an_assertion_is_found_however_the_others_assert() -> None:
    source = textwrap.dedent("""
        import pytest

        def test_calls_only():
            run()

        def test_asserts():
            assert run() == 1

        def test_raises():
            with pytest.raises(ValueError):
                run()

        def test_helper():
            _assert_ok(run())

        def test_mock(mock):
            run()
            mock.assert_called_once()

        class TestGroup:
            def test_method_calls_only(self):
                run()

        def helper_that_is_not_a_test():
            pass
    """)
    tests = {"tests/unit/test_a.py": source, "tests/unit/helpers.py": "def test_x():\n    pass\n"}

    measures = metrics.tests_statiques(tests, [])

    assert measures["tests.fonctions"] == 6  # helpers.py is not a test file
    assert measures["tests.sans_assertion"] == 2


def test_a_local_helper_counts_for_what_it_does_and_not_for_its_name() -> None:
    """Measured 2026-09-30: four files had a `check()` that counted PASS and FAIL and never asserted; its name was
    enough for the counter to believe the 25 tests that call it asserted."""
    counting = (
        "PASS = 0\n"
        "def check(name, got, ref):\n    global PASS\n    PASS += 1\n    print(name)\n"
        "def test_a():\n    check('a', 1, 1)\n"
    )
    asserting = (
        "def check(name, got, ref):\n    assert got == ref, name\n"
        "def test_a():\n    check('a', 1, 1)\n"
        "def test_b():\n    helper()\n"  # a helper that is not named like a check, and hands the work to one that asserts
        "def helper():\n    check('b', 1, 1)\n"
    )
    imported = "from helpers import check\n\n\ndef test_a():\n    check('a', 1, 1)\n"  # not defined here: judged by its name

    assert metrics.tests_statiques({"tests/unit/test_x.py": counting}, [])["tests.sans_assertion"] == 1
    assert metrics.tests_statiques({"tests/unit/test_x.py": asserting}, [])["tests.sans_assertion"] == 0
    assert metrics.tests_statiques({"tests/unit/test_x.py": imported}, [])["tests.sans_assertion"] == 0


def test_a_module_is_named_when_a_test_says_its_name_as_a_word() -> None:
    modules = ["certus/physics/alpha_kernel.py", "certus/physics/beta_kernel.py", "certus/physics/__init__.py"]
    tests = {
        "tests/unit/test_a.py": "from certus.physics import alpha_kernel\n\n\ndef test_a():\n    assert alpha_kernel\n",
        "tests/unit/test_b.py": "beta_kernel_extra = 1\n",  # not the word `beta_kernel`
    }

    measures = metrics.tests_statiques(tests, modules)

    assert measures["tests.modules"] == 2  # __init__ is not a module of its own
    assert measures["tests.modules_sans_test"] == 1


# =============================================================================
# Lint, contrast, coverage
# =============================================================================


def test_ruff_statistics_are_summed_and_the_rules_counted() -> None:
    output = (
        "  47\tF841  \t[ ] unused-variable\n"
        "  12\tE701  \t[*] multiple-statements-on-one-line-colon\n"
        "   3\tF841  \t[ ] unused-variable\n"
        "Found 62 errors.\n"
    )

    assert metrics.lire_statistiques_ruff(output) == (62, 2)
    assert metrics.lire_statistiques_ruff("All checks passed!\n") == (0, 0)


def test_contrast_follows_wcag() -> None:
    assert metrics.contraste("#000000", "#ffffff") == pytest.approx(21.0)
    assert metrics.contraste("#ffffff", "#000000") == pytest.approx(21.0)
    assert metrics.contraste("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)  # the lightest grey that passes AA
    assert metrics.contraste("#777777", "#ffffff") < 4.5


def test_coverage_is_the_percentage_of_lines_not_the_one_that_mixes_branches(tmp_path) -> None:
    def entry(statements: int, covered: int) -> dict:
        return {"summary": {"num_statements": statements, "covered_lines": covered, "num_branches": 100,
                            "covered_branches": 0, "percent_covered": 1.0}}  # fmt: skip

    report = {"files": {
        "certus/physics/a.py": entry(100, 50),
        "certus\\core\\b.py": entry(100, 10),  # a Windows path
        "tests/unit/test_a.py": entry(100, 100),  # not certus/: not counted
    }}  # fmt: skip
    path = tmp_path / "cov.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert metrics.couverture(path) == {"lignes": 30.0, "physics": 50.0}


# =============================================================================
# The table
# =============================================================================


def test_a_target_is_reached_in_its_own_direction() -> None:
    assert metrics.atteinte("couverture.lignes", 60.0) is True  # more is better
    assert metrics.atteinte("couverture.lignes", 50.0) is False
    assert metrics.atteinte("lint.violations", 1000) is True  # less is better
    assert metrics.atteinte("lint.violations", 3319) is False
    assert metrics.atteinte("lint.violations", None) is None  # not measured is neither
    assert metrics.atteinte("arch.any", 1) is None  # no target


def test_a_measure_that_was_not_taken_is_never_printed_as_zero() -> None:
    table = metrics.rendre({"arch.cycles": None, "lint.violations": 0}, {"arch.cycles": "because of the test"})
    lines = table.splitlines()
    cycles = next(line for line in lines if line.startswith("cycles d'imports"))
    lint = next(line for line in lines if line.startswith("dette de lint masquee : violations"))

    assert "n/a" in cycles
    assert re.search(r"\s0\s", lint)  # a real zero stays a zero
    assert "because of the test" in table


def test_every_indicator_is_measured_or_explained(tmp_path) -> None:
    """Wiring a new row into the table and forgetting to measure it must not print a silent blank."""
    (tmp_path / "certus").mkdir()
    (tmp_path / "certus" / "a.py").write_text("X = 1\n", encoding="utf-8")

    measures, absent, _ = metrics.mesurer(tmp_path, statique_seulement=True)

    for key, *_ in metrics.INDICATEURS:
        if key.startswith("ouverture."):
            continue  # asked for by `--ouverture` only
        assert key in measures, f"{key} is in the table and is not measured"
        assert measures[key] is not None or key in absent, f"{key} is null and says nothing about why"


def test_the_command_prints_the_table_and_writes_the_json_with_its_provenance(tmp_path, capsys) -> None:
    (tmp_path / "certus").mkdir()
    (tmp_path / "certus" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert 1\n", encoding="utf-8")
    out = tmp_path / "mesures.json"

    assert metrics.main(["--racine", str(tmp_path), "--rapide", "--json", str(out)]) == 0

    table = capsys.readouterr().out
    assert "indicateur" in table
    assert "n/a" in table
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mesures"]["arch.fichiers_py"] == 2
    assert data["mesures"]["lint.violations"] is None  # not measured: null, not 0
    assert data["provenance"]["git_commit"]
