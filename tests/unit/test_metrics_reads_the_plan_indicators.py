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

import ast
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


def test_the_upward_edges_are_named_module_to_module_and_the_count_is_made_from_them() -> None:
    # tests/architecture_debt.json lists these names; swapping one edge for another leaves the count where it was.
    sources = {
        "certus/physics/kernel.py": "from certus.core import settings\nfrom certus.ui import window\n",
        "certus/physics/other.py": "from certus.core import settings\n",
        "certus/core/settings.py": "LIMIT = 1\n",
        "certus/ui/window.py": "from certus.core import settings\n",
    }
    trees = {f: ast.parse(t) for f, t in sources.items()}
    graph, modules = metrics.graphe_imports(trees)

    assert metrics.liste_aretes_montantes(graph, modules) == [
        ("certus.physics.kernel", "certus.core.settings"),
        ("certus.physics.kernel", "certus.ui.window"),
        ("certus.physics.other", "certus.core.settings"),
    ]
    assert metrics.aretes_montantes(graph, modules) == {("certus.physics", "certus.core"): 2, ("certus.physics", "certus.ui"): 1}


def test_an_import_inside_a_function_is_neither_an_edge_nor_a_cycle() -> None:
    late = {
        "certus/core/a.py": "from certus.core import b\n",
        "certus/core/b.py": "def late():\n    from certus.core import a\n    return a\n",
    }
    eager = {**late, "certus/core/b.py": "from certus.core import a\n"}

    assert metrics.architecture(late)[0]["arch.cycles"] == 0
    assert metrics.architecture(eager)[0]["arch.cycles"] == 1


def test_an_import_under_type_checking_is_an_upward_edge_but_never_a_cycle() -> None:
    # The standard remedy for a cycle (certus_ui_utils.py documents it) must not be counted as one; the layering still sees it.
    sources = {
        "certus/core/a.py": "from certus.core import b\n",
        "certus/core/b.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from certus.core import a\n",
        "certus/physics/p.py": "import typing\nif typing.TYPE_CHECKING:\n    from certus.core import a\n",
    }

    measures, detail = metrics.architecture(sources)

    assert measures["arch.cycles"] == 0
    assert detail["cycles_avec_imports_de_typage"] == 1
    assert measures["arch.aretes_montantes"] == 1  # physics -> core


def test_what_runs_next_to_type_checking_still_counts_as_an_import() -> None:
    def cycles(b: str) -> int:
        sources = {"certus/core/a.py": "from certus.core import b\n", "certus/core/b.py": b}
        return metrics.architecture(sources)[0]["arch.cycles"]

    assert cycles("import typing\nif typing.TYPE_CHECKING:\n    pass\nelse:\n    from certus.core import a\n") == 1
    assert cycles("from typing import TYPE_CHECKING\nif not TYPE_CHECKING:\n    from certus.core import a\n") == 1
    assert cycles("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from certus.core import a\n") == 0


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


def test_functions_are_named_by_qualified_name_and_duplicates_are_numbered() -> None:
    source = textwrap.dedent("""
        class A:
            def m(self):
                def inner():
                    pass
                return inner

            @property
            def p(self):
                return 1

            @p.setter
            def p(self, value):
                pass

        def f():
            pass

        if True:
            def f():
                pass

        try:
            def g():
                pass
        except ImportError:
            def g():
                pass
    """)

    names = [name for name, *_ in metrics._fonctions_qualifiees(ast.parse(source))]

    assert names == ["A.m", "A.m.<locals>.inner", "A.p", "A.p#2", "f", "f#2", "g", "g#2"]


def _named(name: str, lines: int) -> str:
    return f"def {name}():\n" + "    x = 1\n" * (lines - 1) + "\n"


def _branchy(name: str, branches: int) -> str:
    return f"def {name}(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(branches)) + "\n"


def test_the_debt_names_what_goes_over_a_threshold_and_keeps_its_measure() -> None:
    sources = {
        "certus/core/a.py": _named("just_under", 300) + _named("over", 301) + _branchy("simple", 59) + _branchy("branchy", 61),
        "scripts/a.py": _named("script_over", 400),  # the limit is on certus/, as for the indicators
    }

    debt = metrics.dette(sources)

    assert debt["fonctions_longues"] == {"certus/core/a.py::over": 301}
    assert debt["fonctions_complexes"] == {"certus/core/a.py::branchy": 62}  # 1 + 61 branches; 60 is not over
    assert debt["fichiers_longs"] == {}


def test_a_file_is_long_above_fifteen_hundred_lines_and_only_under_certus() -> None:
    assert metrics.dette({"certus/core/big.py": "x = 1\n" * 1500})["fichiers_longs"] == {}
    assert metrics.dette({"certus/core/big.py": "x = 1\n" * 1501})["fichiers_longs"] == {"certus/core/big.py": 1501}
    assert metrics.dette({"certus_physics/big.py": "x = 1\n" * 1501})["fichiers_longs"] == {"certus_physics/big.py": 1501}
    assert metrics.dette({"scripts/big.py": "x = 1\n" * 1501})["fichiers_longs"] == {}


def test_the_debt_and_the_indicators_count_the_same_offenders() -> None:
    sources = {"certus/core/a.py": _named("over", 301) + _branchy("branchy", 61), "certus/core/big.py": "x = 1\n" * 1501}

    measures, _ = metrics.architecture(sources)
    debt = metrics.dette(sources)

    assert measures["arch.fonctions_gt300"] == len(debt["fonctions_longues"]) == 1
    assert measures["arch.fonctions_cc_gt60"] == len(debt["fonctions_complexes"]) == 1
    assert measures["arch.fichiers_gt1500"] == len(debt["fichiers_longs"]) == 1


def test_dette_writes_the_ledger_from_the_folders_the_cache_key_reads_and_stops(tmp_path) -> None:
    for rel, text in {
        "certus/core/a.py": "from certus.ui import w\n",
        "certus/ui/w.py": "x = 1\n",
        "certus_physics/big.py": "x = 1\n" * 1501,
        "scripts/not_read.py": "from certus.ui import w\n",
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    out = tmp_path / "debt.json"

    assert metrics.main(["--racine", str(tmp_path), "--dette", str(out)]) == 0

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["aretes_montantes"] == ["certus.core.a -> certus.ui.w"]
    assert written["fichiers_longs"] == {"certus_physics/big.py": 1501}
    assert set(written) == {
        "_commentaire", "aretes_montantes", "cycles", "fonctions_longues", "fonctions_complexes", "fichiers_longs",
    }  # fmt: skip


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


def _coverage_file(path, **files: tuple[int, int]):
    report = {"files": {name: {"summary": {"num_statements": lines, "covered_lines": covered}} for name, (covered, lines) in files.items()}}
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_a_weak_module_is_one_that_no_measure_covers_and_only_the_larger_ones_count(tmp_path) -> None:
    ordinary = _coverage_file(
        tmp_path / "ordinary.json",
        **{
            "certus/physics/kernel.py": (5, 60),  # 8 %: the JIT hides it in an ordinary run
            "certus/core/fine.py": (50, 60),
            "certus/core/tiny.py": (0, 40),  # under 50 lines: not counted
            "certus\\ui\\window.py": (3, 100),  # a Windows path: counted, 3 %
            "tests/unit/test_x.py": (0, 500),  # not certus/
        },
    )
    kernels = _coverage_file(tmp_path / "kernels.json", **{"certus/physics/kernel.py": (45, 60), "certus/ui/window.py": (0, 100)})

    assert metrics.modules_faibles([ordinary]) == 2
    assert metrics.modules_faibles([ordinary, kernels]) == 1  # the kernel is covered once the JIT is off: best of both
    assert metrics.modules_faibles([ordinary], seuil=2.0) == 0


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
