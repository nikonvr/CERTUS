"""A script that loads the compiled kernels keys the Numba cache by their sources first (audit v2, plan S8.1, ETAT D49).

Left alone, Numba writes its cache next to the sources (`certus/physics/__pycache__/*.nbi`), and a function of one file that calls
a function of another keeps its machine code, with the OLD callee inside, when the callee's file changes. Measured on
2026-09-30: `cost_numba_fast` went on ignoring the substrate loss of the new `calc_spectrum_full_exact`, and four oracle tests failed
on code that was right. The test session and the applications are covered (`tests/conftest.py`, `configure_numba_env`); the scripts
of `scripts/` and `tools/` that import the kernels without an entry point were not: 15 of them measured, benchmarked or
diagnosed on a cache that could hold the code of the previous version.

`certus.core.certus_core.ensure_numba_cache_dir()` is the one call. Where it goes:

* at the head of the script, before the first import that loads Numba;
* in `scripts/bench_examples.py`, inside `qapp()`, after the QApplication is created (trap 3 of its docstring: numpy must not be
  imported before it) : every script that calls `qapp()` imports the kernels after it;
* in the check, not at the head, of `scripts/preflight.py`: a diagnostic must survive a broken import and say so.

The static rule below covers every script, the dynamic one proves the mechanism on four of them (an import of Numba costs seconds).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Modules of `certus` whose import does not load Numba (measured in a fresh interpreter by the first test below).
LIGHT = (
    "certus",
    "certus.core.certus_core",
    "certus.core.certus_metrology",
    "certus.core.certus_hub_config",
    "certus.physics",
    "certus.utils.certus_data",
    "certus.core.certus_frozen_entry",
)

#: Scripts that load kernels and do not call `ensure_numba_cache_dir`, and why.
EXEMPT = {
    "scripts/smoke/run_examples_headless.py": "sets NUMBA_DISABLE_JIT=1 at its head: nothing is compiled, nothing is cached",
}


def _scripts() -> list[Path]:
    return sorted(p for base in ("scripts", "tools") for p in (ROOT / base).rglob("*.py"))


def _is_heavy(node: ast.AST) -> bool:
    """An import of a project module that loads Numba (anything of `certus` that is not LIGHT, the CERTUS_* windows)."""
    module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
    if not module or module in LIGHT:
        return False
    return module.split(".")[0] in ("certus", "certus_physics") or module.startswith("CERTUS_")


def _facts(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    heavy = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom) and _is_heavy(n)]
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and ast.unparse(n.func).split(".")[-1] in ("ensure_numba_cache_dir", "qapp")
    ]
    ensure_calls = [n for n in calls if ast.unparse(n.func).split(".")[-1] == "ensure_numba_cache_dir"]
    module_level_heavy = [s.lineno for s in tree.body if isinstance(s, ast.Import | ast.ImportFrom) and _is_heavy(s)]
    module_level_ensure = [
        s.lineno
        for s in tree.body
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and ast.unparse(s.value.func).endswith("ensure_numba_cache_dir")
    ]
    return {
        "loads_kernels": bool(heavy),
        "sets_the_cache": bool(calls),
        "has_ensure": bool(ensure_calls),
        "module_level_heavy": min(module_level_heavy, default=None),
        "module_level_ensure": min(module_level_ensure, default=None),
    }


FACTS = {p.relative_to(ROOT).as_posix(): _facts(p) for p in _scripts()}
LOADING = {rel: f for rel, f in FACTS.items() if f["loads_kernels"]}


def _fresh(code: str, **extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "NUMBA_CACHE_DIR"}
    env.update(PYTHONIOENCODING="utf-8", QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1", **extra)
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)


def test_the_light_modules_do_not_load_numba():
    """The list that lets a script import them before the call is true: measured, one fresh interpreter each."""

    def loads_numba(module: str) -> bool:
        done = _fresh(f"import sys\nimport {module}\nprint('numba' in sys.modules)")
        assert done.returncode == 0, done.stderr[-400:]
        return done.stdout.strip().splitlines()[-1] == "True"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(LIGHT, pool.map(loads_numba, LIGHT), strict=True))
    assert not [m for m, loaded in results.items() if loaded], results


def test_scripts_are_found_and_most_of_them_load_the_kernels():
    assert len(FACTS) > 50
    assert len(LOADING) >= 25  # 36 on 2026-10-01; a count that collapses means the rule stopped reading them


@pytest.mark.parametrize("rel", sorted(LOADING))
def test_a_script_that_loads_the_kernels_keys_the_cache_first(rel):
    if rel in EXEMPT:
        pytest.skip(EXEMPT[rel])
    facts = LOADING[rel]
    assert facts["sets_the_cache"], f"{rel} imports the kernels and never calls ensure_numba_cache_dir() (nor the bench's qapp())"
    if facts["module_level_heavy"] is not None:
        assert facts["module_level_ensure"] is not None, f"{rel} imports the kernels at module level, so the call must be there too"
        assert facts["module_level_ensure"] < facts["module_level_heavy"], (
            f"{rel}: ensure_numba_cache_dir() at line {facts['module_level_ensure']} comes after the first import that loads "
            f"Numba, at line {facts['module_level_heavy']}"
        )


def test_every_exemption_names_a_script_that_exists_and_would_otherwise_fail():
    for rel in EXEMPT:
        assert rel in LOADING, f"{rel} is exempt but loads no kernel any more: drop the exemption"
        assert not LOADING[rel]["sets_the_cache"], f"{rel} calls ensure_numba_cache_dir(): drop the exemption"


def test_bench_examples_keys_the_cache_in_qapp_after_the_application_exists():
    tree = ast.parse((ROOT / "scripts" / "bench_examples.py").read_text(encoding="utf-8-sig"))
    qapp = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "qapp")
    body = ast.unparse(qapp)
    assert "ensure_numba_cache_dir()" in body
    assert body.index("QApplication(") < body.index("ensure_numba_cache_dir()")


# =============================================================================
# The mechanism, on four scripts and the bench's qapp()

HEADER = """
import importlib.util, json, os, sys
path = sys.argv[1]
sys.path.insert(0, os.path.dirname(path))
sys.argv = [path]
spec = importlib.util.spec_from_file_location("script_under_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
import numba.core.config as numba_config
print(json.dumps({"config": numba_config.CACHE_DIR, "env": os.environ.get("NUMBA_CACHE_DIR")}))
"""

QAPP = """
import json, os, sys
sys.path.insert(0, "scripts")
import bench_examples
assert "NUMBA_CACHE_DIR" not in os.environ
bench_examples.qapp()
print(json.dumps({"env": os.environ.get("NUMBA_CACHE_DIR"), "numba_loaded": "numba" in sys.modules}))
"""


def _dir_the_sources_key() -> str:
    sys.path.insert(0, str(ROOT))
    from certus.core.certus_core import numba_cache_dir

    return str(Path(numba_cache_dir()))


HEADS = [
    "scripts/assemble_testglass.py",
    "scripts/check_compensation_gain.py",
    "tools/bench_spline_hotpaths.py",
    "scripts/benchmark_3_modes.py",
]


@pytest.fixture(scope="module")
def mechanism() -> dict:
    """The four heads and `qapp()` run in fresh interpreters together (each loads Numba, which costs seconds)."""
    jobs = {rel: HEADER.replace("sys.argv[1]", repr(str(ROOT / rel))) for rel in HEADS}
    jobs["qapp"] = QAPP
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        done = dict(zip(jobs, pool.map(_fresh, jobs.values()), strict=True))
    out = {"expected": _dir_the_sources_key()}
    for name, proc in done.items():
        assert proc.returncode == 0, f"{name}: {proc.stderr[-600:]}"
        out[name] = json.loads(proc.stdout.strip().splitlines()[-1])
    return out


@pytest.mark.parametrize("rel", HEADS)
def test_importing_the_head_of_a_script_leaves_numba_on_the_keyed_directory(rel, mechanism):
    got = mechanism[rel]
    assert Path(got["config"]) == Path(mechanism["expected"])
    assert Path(got["env"]) == Path(mechanism["expected"])


def test_qapp_of_the_bench_keys_the_cache_before_any_script_imports_the_kernels(mechanism):
    assert Path(mechanism["qapp"]["env"]) == Path(mechanism["expected"])
