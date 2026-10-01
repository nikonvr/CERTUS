"""`scripts/mutation_pilot.py` plants one fault at a time and counts the ones the tests see, and only those.

A mutation score is only worth its number if a fault that was not run says so. Each test below builds a small
module whose faults are known, so a wrong operator (`<` mutated into `<`), a docstring that is mutated (a
"surviving" fault that changes nothing), a fault left in a copy for the next one to trip over, or a timeout
counted as a survivor fails here and not in the middle of a baseline nobody can check.

The copies of the repository and the pytest runs of the last two tests are real (a toy module, two test files), they take a
few seconds; the operators are tested on text.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("certus_scripts_mutation_pilot", ROOT / "scripts" / "mutation_pilot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mp = _load()


def _mutants(source: str):
    return mp.iter_mutants(textwrap.dedent(source), "toy.py")


def _texts(source: str, kind: str, old: str | None = None) -> list[str]:
    return [m.source for m in _mutants(source) if m.kind == kind and (old is None or m.old == old)]


# =============================================================================
# The operators


def test_a_comparison_becomes_its_neighbour():
    """`a < b` is also tried as `a <= b`: the boundary is what tests forget."""
    texts = _texts("def f(a, b):\n    return a < b\n", "compare")
    assert len(texts) == 1
    assert "a <= b" in texts[0]
    assert "a < b" not in texts[0]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def f(a, b):\n    return a + b\n", "a - b"),
        ("def f(a, b):\n    return a * b\n", "a / b"),
        ("def f(a, b):\n    return a and b\n", "a or b"),
        ("def f(a):\n    return max(a, 0)\n", "min(a, 0)"),
        ("def f(z):\n    return z.real\n", "z.imag"),
        ("def f(z):\n    return np.argmax(z)\n", "np.argmin(z)"),
        ("def f(x):\n    return not x\n", "return x"),
        ("def f(x):\n    return abs(x)\n", "return x"),
        ("def f(x):\n    return -x\n", "return x"),
        ("def f(x):\n    x += 2\n    return x\n", "x -= 2"),
    ],
)
def test_each_family_of_fault_is_posed(source, expected):
    assert any(expected in m.source for m in _mutants(source)), [m.kind for m in _mutants(source)]


def test_a_raise_becomes_a_pass_and_a_test_is_negated():
    """The check at the door that is removed, the branch that is flipped: the two faults a validation needs."""
    source = "def f(x):\n    if x < 0:\n        raise ValueError('no')\n    return x\n"
    kinds = {m.kind: m.source for m in _mutants(source)}
    assert "pass" in kinds["raise"]
    assert "raise" not in kinds["raise"]
    assert "not x < 0" in kinds["condition"]


def test_constants_move_by_one_flip_or_are_marked():
    source = "def f():\n    a = 5\n    b = 2.5\n    c = True\n    d = 'name'\n    return a, b, c, d\n"
    pairs = {(m.kind, m.old, m.new) for m in _mutants(source)}
    assert ("const-number", "5", "6") in pairs
    assert ("const-number", "2.5", "3.5") in pairs
    assert ("const-bool", "True", "False") in pairs
    assert ("const-str", "'name'", "'XXnameXX'") in pairs


def test_a_return_none_is_not_mutated_into_itself():
    assert _texts("def f():\n    return None\n", "return") == []
    assert len(_texts("def f(x):\n    return x\n", "return")) == 1


def test_docstrings_decorators_defaults_and_annotations_are_left_alone():
    source = '''
        """Module doc, 1."""
        import functools

        @functools.lru_cache(maxsize=8, typed=True)
        def f(x: int = 3) -> int:
            """Function doc, 2."""
            y: float = 1.5
            return x
    '''
    mutants = _mutants(source)
    assert mutants
    assert all("XXModule doc" not in m.source and "XXFunction doc" not in m.source for m in mutants)
    olds = {m.old for m in mutants}
    assert "8" not in olds
    assert "True" not in olds
    assert "3" not in olds
    assert "1.5" in olds


def test_a_module_constant_is_mutated_and_its_annotation_is_not():
    mutants = _mutants("from typing import Final\n\nLIMIT: Final[float] = 700.0\n")
    assert [(m.kind, m.old, m.new) for m in mutants] == [("const-number", "700.0", "701.0")]


def test_every_mutant_is_valid_python_and_differs_from_the_control():
    source = textwrap.dedent(
        """
        import math

        def f(x, y):
            if x < y and not math.isnan(x):
                return max(x, y) + 1
            for i in range(3):
                x -= i
            raise ValueError(f"bad {x}")
        """
    )
    control = mp.control_source(source)
    mutants = mp.iter_mutants(source, "toy.py")
    assert len(mutants) >= 8
    for m in mutants:
        ast.parse(m.source)
        assert m.source != control
        assert m.text


def test_the_mutant_remembers_the_original_line_not_the_unparsed_one():
    source = "def f(a, b):\n    x = (a,\n         b)\n    return a < b\n"
    (mutant,) = [m for m in mp.iter_mutants(source, "toy.py") if m.kind == "compare"]
    assert mutant.line == 4
    assert mutant.text == "return a < b"


# =============================================================================
# The count


def _result(module, status, kind="compare", line=1):
    return {"module": module, "line": line, "col": 0, "kind": kind, "old": "a", "new": "b", "status": status}


def test_the_score_counts_a_timeout_as_killed_and_an_error_as_nothing():
    results = [
        _result("m.py", "killed"),
        _result("m.py", "timeout"),
        _result("m.py", "survived"),
        _result("m.py", "survived"),
        _result("m.py", "error"),
    ]
    numbers = mp.summarize(results)["m.py"]
    assert (numbers["mutants"], numbers["killed"], numbers["timeout"], numbers["survived"], numbers["error"]) == (5, 1, 1, 2, 1)
    assert numbers["score"] == 0.5


def test_the_score_without_text_leaves_the_string_constants_aside():
    results = [_result("m.py", "killed"), _result("m.py", "survived", kind="const-str"), _result("m.py", "survived", kind="const-str")]
    numbers = mp.summarize(results)["m.py"]
    assert numbers["score"] == pytest.approx(1 / 3, abs=1e-4)
    assert numbers["score_sans_chaines"] == 1.0


def test_a_module_with_nothing_to_count_has_no_score():
    assert mp.summarize([_result("m.py", "error")])["m.py"]["score"] is None


def test_the_killer_is_the_first_test_that_failed():
    output = "....F\nFAILED tests/x.py::test_a - assert 1 == 2\nFAILED tests/x.py::test_b - boom\n"
    assert mp._killer(output) == "tests/x.py::test_a"
    assert mp._killer("ERROR tests/y.py - ImportError") == "tests/y.py"
    assert mp._killer("1 passed") == ""


def test_the_copy_holds_what_git_tracks_and_what_it_does_not_hide_and_never_the_reports(tmp_path):
    """A test written to kill a survivor counts before it is committed; the 570 MB of `reports/` never travel."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    for name in ("tracked.py", "new_test.py", "ignored.txt", "reports/big.npy"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.py", "reports/big.npy"], cwd=root, check=True, capture_output=True)
    assert mp._tracked_files(root) == [".gitignore", "new_test.py", "tracked.py"]


def test_the_tests_run_are_oracle_core_and_the_files_that_import_the_module(tmp_path):
    files = {
        "tests/oracle/test_o.py": "x = 1\n",
        "tests/core/test_c.py": "x = 1\n",
        "tests/unit/test_imports_it.py": "import certus.physics.certus_inputs\n",
        "tests/unit/test_from_import.py": "from certus.physics.certus_inputs import check_incidence_angle\n",
        "tests/unit/test_from_package.py": "from certus.physics import certus_inputs\n",
        "tests/unit/test_only_cites_it.py": 'PATH = "certus/physics/certus_inputs.py"\n',
        "tests/unit/test_does_not.py": "x = 1\n",
        "tests/unit/test_substring.py": "import certus_inputs_extra\n",
    }
    for name, content in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content, encoding="utf-8")
    assert mp.default_tests(tmp_path, "certus/physics/certus_inputs.py") == [
        "tests/oracle",
        "tests/core",
        "tests/unit/test_from_import.py",
        "tests/unit/test_from_package.py",
        "tests/unit/test_imports_it.py",
    ]


# =============================================================================
# The runs, on a toy project


TOY_MODULE = textwrap.dedent(
    """
    def clamp_low(x, low):
        if x < low:
            return low
        return x


    def never_tested(x):
        return x + 1
    """
)

TOY_TESTS = textwrap.dedent(
    """
    from toymod import clamp_low


    def test_inside():
        assert clamp_low(5, 0) == 5


    def test_below():
        assert clamp_low(-1, 0) == 0
    """
)

TOY_ARGV = ["--tests", "tests/test_toy.py", "--workers", "1", "--timeout", "60"]


def _toy(tmp_path: Path, tests: str = TOY_TESTS) -> Path:
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "toymod.py").write_text(TOY_MODULE, encoding="utf-8")
    (tmp_path / "tests" / "test_toy.py").write_text(tests, encoding="utf-8")
    return tmp_path


@pytest.fixture(scope="module")
def toy_first_run(tmp_path_factory):
    """The toy project and the JSON of one full run of the command: shared, a run costs seconds."""
    base = tmp_path_factory.mktemp("toy")
    root = _toy(base / "project")
    first = base / "first.json"
    assert mp.main(["toymod.py", "--root", str(root), *TOY_ARGV, "--json", str(first)]) == 0
    return root, first, json.loads(first.read_text(encoding="utf-8"))


def _survivors(payload: dict) -> set[tuple]:
    return {(m["line"], m["col"], m["kind"], m["new"]) for m in payload["mutants"] if m["status"] == "survived"}


def test_a_tested_fault_is_killed_an_untested_one_survives_and_the_repository_is_untouched(toy_first_run):
    root, _, payload = toy_first_run
    by_line: dict[int, list[str]] = {}
    for r in payload["mutants"]:
        by_line.setdefault(r["line"], []).append(r["status"])
    untested_line = TOY_MODULE.count("\n", 0, TOY_MODULE.index("return x + 1")) + 1
    assert by_line[untested_line] == ["survived"] * len(by_line[untested_line])
    assert len(by_line[untested_line]) == 3
    killed = [r for r in payload["mutants"] if r["status"] == "killed"]
    assert len(killed) == 3
    assert all(r["killer"].startswith("tests/test_toy.py::test_") for r in killed)
    assert (root / "toymod.py").read_text(encoding="utf-8") == TOY_MODULE


def test_the_command_writes_the_json(toy_first_run):
    _, _, payload = toy_first_run
    assert payload["modules"]["toymod.py"]["mutants"] == len(payload["mutants"]) == 7
    assert payload["modules"]["toymod.py"]["score"] == pytest.approx(3 / 7, abs=1e-4)
    assert {m["status"] for m in payload["mutants"]} <= {"killed", "survived", "timeout", "error"}


def test_a_control_that_fails_stops_the_run_before_any_fault_is_posed(tmp_path):
    root = _toy(tmp_path, tests="from toymod import clamp_low\n\n\ndef test_wrong():\n    assert clamp_low(5, 0) == 6\n")
    with pytest.raises(SystemExit, match="TEMOIN"):
        mp.run_pilot(root, ["toymod.py"], ["tests/test_toy.py"], workers=1, timeout=60, log=lambda _: None)


def _baseline(payload: dict, tmp_path: Path, accepted: bool) -> Path:
    survivors = [m for m in payload["mutants"] if m["status"] == "survived"] if accepted else []
    entries = [{k: m[k] for k in ("module", "text", "kind", "old", "new")} | {"reason": "toy"} for m in survivors]
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"accepted_survivors": entries}), encoding="utf-8")
    return path


def test_rerun_replays_only_the_survivors_and_the_baseline_fails_on_one_it_does_not_accept(toy_first_run, tmp_path, capsys):
    root, first, payload = toy_first_run
    second = tmp_path / "second.json"
    argv = ["--root", str(root), *TOY_ARGV, "--rerun", str(first), "--json", str(second)]
    assert mp.main([*argv, "--baseline", str(_baseline(payload, tmp_path, accepted=False))]) == 1
    out = capsys.readouterr().out
    assert "SURVIVANT NON ACCEPTE" in out
    after = json.loads(second.read_text(encoding="utf-8"))
    assert _survivors(after) == _survivors(payload)
    assert all(m["status"] == "survived" for m in after["mutants"])
    assert len(after["mutants"]) == len(_survivors(payload))


def test_a_baseline_that_names_every_survivor_passes(toy_first_run, tmp_path):
    _, _, payload = toy_first_run
    baseline = json.loads(_baseline(payload, tmp_path, accepted=True).read_text(encoding="utf-8"))
    unaccepted, gone = mp.compare_baseline(payload["mutants"], baseline)
    assert unaccepted == []
    assert gone == []


def test_a_survivor_the_baseline_does_not_name_is_new_and_an_accepted_one_that_died_is_reported():
    def result(text, status, line=1, module="m.py"):
        return {"module": module, "line": line, "col": 0, "kind": "compare", "old": "<", "new": "<=", "text": text, "status": status}

    def accepted(text, module="m.py"):
        return {"module": module, "text": text, "kind": "compare", "old": "<", "new": "<=", "reason": "equal floats"}

    baseline = {"accepted_survivors": [accepted("if a < b:"), accepted("if c < d:"), accepted("if x < y:", module="other.py")]}
    results = [result("if a < b:", "survived", line=40), result("if e < f:", "survived"), result("if g < h:", "killed")]
    unaccepted, gone = mp.compare_baseline(results, baseline)
    assert [r["text"] for r in unaccepted] == ["if e < f:"]  # `if a < b:` is accepted though its line moved
    assert [a["text"] for a in gone] == ["if c < d:"]  # other.py was not played: nothing is said of it


def test_an_absent_module_is_an_error_not_an_empty_run(tmp_path, capsys):
    assert mp.main(["nowhere.py", "--root", str(tmp_path)]) == 2
    assert "MODULE ABSENT" in capsys.readouterr().err
