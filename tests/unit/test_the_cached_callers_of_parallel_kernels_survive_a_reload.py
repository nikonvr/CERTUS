"""A cached function that calls a cached parallel kernel must not be cached itself.

Numba 0.65.1 to 0.68.0, Windows, Python 3.12 and 3.14: a `cache=True` function that is SAVED while the
`cache=True, parallel=True` kernel it calls is LOADED from the cache brings the interpreter down (segmentation fault,
exit 139) the next time it is loaded. The same code compiled cold, or both functions compiled by one process, reload
fine. A caller that is itself parallel survived the minimal case. Measured with a 20-line Numba-only script
(reports/AUDIT_SUITE_CERTUS_2026-10-18.md, C18, annex); `calc_spectrum_front` died of it in this repository.

Three layers:
  1. a scan of the sources: no cached serial function of the packages calls a cached parallel one (direct calls by
     name; the exceptions are not forbidden, they do not exist);
  2. the sequence of the defect replayed in three processes on the real callers, with a cache of their own;
  3. a sentinel on Numba alone, expected to fail, that goes red the day Numba is fixed: then `cache=False` of the
     callers and the first layer can go.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("certus", "certus_physics")


# =============================================================================
# 1. The scan
# =============================================================================


def _flags(decorator: ast.expr) -> tuple[bool, bool] | None:
    """(cache, parallel) of an `@njit(...)` or `@jit(...)` decorator; None for any other decorator."""
    call = decorator if isinstance(decorator, ast.Call) else None
    target = decorator.func if call else decorator
    name = target.id if isinstance(target, ast.Name) else (target.attr if isinstance(target, ast.Attribute) else None)
    if name not in {"njit", "jit"}:
        return None
    options = {k.arg: k.value.value for k in (call.keywords if call else []) if isinstance(k.value, ast.Constant)}
    return bool(options.get("cache")), bool(options.get("parallel"))


def _compiled_functions() -> dict[str, list[tuple[str, bool, bool, ast.FunctionDef]]]:
    """name -> [(file, cache, parallel, node)] of every @njit function of the packages."""
    found: dict[str, list[tuple[str, bool, bool, ast.FunctionDef]]] = {}
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        flags = _flags(decorator)
                        if flags is not None:
                            found.setdefault(node.name, []).append((path.relative_to(ROOT).as_posix(), *flags, node))
    return found


@pytest.mark.unit
def test_no_cached_serial_function_calls_a_cached_parallel_kernel() -> None:
    functions = _compiled_functions()
    parallel_cached = {name for name, defs in functions.items() if any(c and p for _f, c, p, _n in defs)}
    assert len(parallel_cached) > 20, "the scan must see the parallel kernels of the packages"
    offenders = []
    for name, defs in functions.items():
        for file, cached, parallel, node in defs:
            if not cached or parallel:
                continue
            called = {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            offenders += [f"{file}: {name} calls {callee}" for callee in sorted((called & parallel_cached) - {name})]
    assert offenders == [], (
        "a cached serial function calls a cached parallel kernel: Numba crashes the interpreter when it reloads it "
        "(reports/AUDIT_SUITE_CERTUS_2026-10-18.md, C18). Declare the caller cache=False:\n  " + "\n  ".join(offenders)
    )


# =============================================================================
# 2. The sequence of the defect, on the real callers
# =============================================================================

#: "kernel": only the parallel kernel runs. "callers": the callers run, with the kernel loaded from the cache.
SCRIPT = """
import hashlib, sys
import numpy as np

wls = np.linspace(380.0, 780.0, 81)
d = np.array([100.0, 60.0])
n = np.ascontiguousarray((np.array([[2.3], [1.46]]) * np.ones((2, 81)) + 0j).T)
ns = np.full(81, 1.52 + 0j)
if sys.argv[1] == "kernel":
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside
    out = calculate_RT_no_backside(d, n, ns, wls)
else:
    from certus.physics.certus_tmm_matrix import calc_spectrum_front, calc_spectrum_full
    out = calc_spectrum_front(wls, d, n, ns) + calc_spectrum_full(wls, d, n, d, n, ns)
print(hashlib.sha256(b"".join(np.asarray(a).tobytes() for a in out)).hexdigest())
"""


def _run(args: list[str], cache: Path, **kwargs) -> subprocess.CompletedProcess:
    # JIT on and a cache of its own: the kernel-coverage job runs with NUMBA_DISABLE_JIT=1, where nothing is compiled.
    env = {**os.environ, "NUMBA_CACHE_DIR": str(cache), "NUMBA_DISABLE_JIT": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False, **kwargs)


@pytest.mark.unit
def test_the_real_callers_are_reloaded_from_the_cache_without_crashing(tmp_path) -> None:
    cache = tmp_path / "cache"
    first = _run([sys.executable, "-c", SCRIPT, "kernel"], cache)  # the parallel kernel alone is compiled and saved
    second = _run([sys.executable, "-c", SCRIPT, "callers"], cache)  # kernel loaded from disk, callers compiled
    third = _run([sys.executable, "-c", SCRIPT, "callers"], cache)  # whatever the second process saved is loaded

    assert first.returncode == 0, first.stderr[-1500:]
    assert second.returncode == 0, second.stderr[-1500:]
    assert third.returncode == 0, f"exit code {third.returncode} when the callers are reloaded: {third.stderr[-1500:]}"
    assert third.stdout == second.stdout, "the callers do not give the same bits from one process to the next"


# =============================================================================
# 3. The sentinel: Numba alone
# =============================================================================

REPRO = """
import sys
import numpy as np
from numba import njit, prange


@njit(cache=True, parallel=True)
def callee(x):
    out = np.empty_like(x)
    for i in prange(x.size):
        out[i] = x[i] * 2.0
    return out


@njit(cache=True)
def caller(x):
    return callee(x).sum()


x = np.arange(10.0)
print(callee(x).sum() if sys.argv[1] == "callee" else caller(x))
"""


@pytest.mark.unit
@pytest.mark.skipif(sys.platform != "win32", reason="measured on Windows 11 only; Linux was not tried")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Numba (0.65.1 to 0.68.0) segfaults when it reloads a cached serial function saved while the cached parallel "
        "kernel it calls was loaded from disk. When this test passes Numba is fixed: drop the cache=False of the callers "
        "(calc_spectrum_front, calc_spectrum_full, compute_batch_rmse) and the scan above."
    ),
)
def test_numba_reloads_a_cached_serial_function_saved_with_a_loaded_parallel_callee(tmp_path) -> None:
    cache = tmp_path / "cache"
    codes = [_run([sys.executable, "-c", REPRO, mode], cache).returncode for mode in ("callee", "caller", "caller")]
    assert codes == [0, 0, 0], codes
