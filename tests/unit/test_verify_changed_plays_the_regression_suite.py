"""Chantier 19: two edges the static graph of `verify_changed.py` did not see.

1. `tests/regression/` runs scripts of the repository in a subprocess, built as `ROOT / "tests" / "headless"` and named by
   their file name only (selector report of 2026-11-15, section 3): a change to `certus/` left the convergence guard
   unselected. Any change to a module of the repository now plays the whole regression suite; a change to tests alone
   does not.
2. A test that walks a package by `package.__path__` (`tests/oracle/test_all_exports_are_real.py`) reads sources it does
   not name: `--audit-calls` on `tests/oracle` (2026-11-17) found it unselected for a module without numba. It is now
   always played.
"""

from scripts import verify_changed as vc

GUARD = (  # as tests/regression/test_convergence.py names its scripts
    "import subprocess\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "ROOT = Path(__file__).parents[2]\n"
    "TESTS_DIR = ROOT / 'tests' / 'headless'\n"
    "SCRIPTS = [('RUN', 'test_run.py')]\n"
    "\n"
    "def test_guard():\n"
    "    for _name, script in SCRIPTS:\n"
    "        subprocess.run([sys.executable, '-m', 'pytest', str(TESTS_DIR / script)], check=True)\n"
)


def _tree(tmp_path, monkeypatch, extra=None):
    for folder in ("certus", "tests/regression", "tests/headless", "tests/unit"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "certus/kernel.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    (tmp_path / "tests/headless/test_run.py").write_text(
        "from certus import kernel\n\ndef test_run():\n    assert kernel.value() == 3\n", encoding="utf-8")
    (tmp_path / "tests/regression/test_guard.py").write_text(GUARD, encoding="utf-8")
    (tmp_path / "tests/unit/test_other.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")
    files = ["certus/kernel.py", "tests/headless/test_run.py", "tests/regression/test_guard.py", "tests/unit/test_other.py"]
    for name, source in (extra or {}).items():
        (tmp_path / name).write_text(source, encoding="utf-8")
        files.append(name)
    monkeypatch.setattr(vc, "ROOT", tmp_path)
    return vc.build_graph(files)


def test_a_module_change_plays_the_regression_suite(tmp_path, monkeypatch):
    graph = _tree(tmp_path, monkeypatch)

    sel = vc.select(graph, ["certus/kernel.py"], whole_files=True)

    assert "tests/headless/test_run.py" in sel.tests  # the static edge
    assert "tests/regression/test_guard.py" in sel.tests  # the subprocess edge the graph cannot see
    assert "tests/unit/test_other.py" not in sel.tests


def test_a_change_to_tests_alone_does_not(tmp_path, monkeypatch):
    graph = _tree(tmp_path, monkeypatch)

    sel = vc.select(graph, ["tests/unit/test_other.py"], whole_files=True)

    assert "tests/regression/test_guard.py" not in sel.tests


def test_a_test_that_walks_a_package_by_its_path_is_always_played(tmp_path, monkeypatch):
    walk = "from pathlib import Path\n\nimport certus\n\ndef test_walk():\n    assert list(Path(certus.__path__[0]).rglob('*.py'))\n"
    graph = _tree(tmp_path, monkeypatch, {"tests/unit/test_walk.py": walk})

    sel = vc.select(graph, ["tests/unit/test_other.py"], whole_files=True)

    assert "tests/unit/test_walk.py" in sel.tests


def test_the_audit_does_not_count_an_always_played_test_as_a_hole(tmp_path, monkeypatch):
    """The walk reaches `certus.kernel.value` by a name it builds, which no static edge can follow; the selection plays
    it whatever changes, so it can miss nothing (the hole `--audit-calls` reported on 2026-11-17)."""
    walk = (
        "import importlib\nfrom pathlib import Path\n\nimport certus\n\n"
        "def test_walk():\n"
        "    for path in sorted(Path(certus.__path__[0]).rglob('*.py')):\n"
        "        module = importlib.import_module('certus.' + path.stem)\n"
        "        assert module.value() == 3\n"
    )
    graph = _tree(tmp_path, monkeypatch, {"tests/unit/test_walk.py": walk})

    assert graph.reads["tests/unit/test_walk.py"] is None
    assert vc.audit_calls(graph, ["tests/unit/test_walk.py"]) == 0
