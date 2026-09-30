"""The Numba cache directory names the sources it was compiled from.

Numba drops a cached function when ITS source file changes, and only then: a function that calls another of a
different file keeps its cached machine code, with the OLD callee inside, when the callee's file changes.
Measured while writing the absorbing-substrate kernels: `cost_numba_fast` (gradient_utils.py) went on running
the `calc_spectrum_full_exact` of the previous certus_tmm_matrix.py, so its cost ignored the substrate that the
new code reads, until the cache directory was emptied by hand. After an update, the numerical results of the
old version, silently.

`numba_cache_dir` (used by `configure_numba_env`) is now `CERTUS_Numba_Cache/<key>`, where the key covers the
sources that mention `numba`, and the versions of Python and Numba.

`ensure_numba_cache_dir` gives the same directory to what does not start from the entry point of an application,
the test session first. Measured on 2026-09-30: a pytest run read the cache that Numba keeps next to the sources
(`certus/physics/__pycache__`) when nobody says otherwise, found there a `cost_numba_fast` compiled against the
old `calc_spectrum_full_exact`, and four oracle tests failed on code that was right.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _tree(tmp_path: Path, kernel: str = "return x + 1.0", interface: str = "label = 'a'") -> Path:
    for package in ("certus/core", "certus/ui", "certus_physics"):
        (tmp_path / package).mkdir(parents=True, exist_ok=True)
    (tmp_path / "certus/core/kernel.py").write_text(f"from numba import njit\n\n@njit\ndef f(x):\n    {kernel}\n")
    (tmp_path / "certus/ui/window.py").write_text(f"{interface}\n")
    (tmp_path / "certus_physics/facade.py").write_text("import numba\n")
    return tmp_path


@pytest.fixture
def key():
    from certus.core.certus_core import _numba_cache_key_of, numba_cache_key

    _numba_cache_key_of.cache_clear()
    yield numba_cache_key
    _numba_cache_key_of.cache_clear()


def test_the_key_is_twelve_hex_digits_and_stable(key, tmp_path) -> None:
    root = _tree(tmp_path)

    assert re.fullmatch(r"[0-9a-f]{12}", key(root))
    assert key(root) == key(root)
    assert re.fullmatch(r"[0-9a-f]{12}", key())  # the repository itself


def test_a_change_in_a_kernel_changes_the_key(key, tmp_path) -> None:
    before = key(_tree(tmp_path))

    (tmp_path / "certus/core/kernel.py").write_text("from numba import njit\n\n@njit\ndef f(x):\n    return x + 2.0\n")
    from certus.core.certus_core import _numba_cache_key_of

    _numba_cache_key_of.cache_clear()

    assert key(tmp_path) != before


def test_a_module_that_gives_a_kernel_its_constants_counts_as_a_kernel(key, tmp_path) -> None:
    # `K_MAX_*`, `TWO_PI`: frozen into the machine code at compile time, so they move the key like a kernel.
    from certus.core.certus_core import _numba_cache_key_of

    root = _tree(tmp_path)
    before = key(root)
    (root / "certus/core/constants.py").write_text("# numba reads this at compile time\nLIMIT = 1e-5\n")
    _numba_cache_key_of.cache_clear()
    after_added = key(root)
    (root / "certus/core/constants.py").write_text("# numba reads this at compile time\nLIMIT = 1e-3\n")
    _numba_cache_key_of.cache_clear()

    assert after_added != before
    assert key(root) != after_added


def test_editing_the_interface_does_not_recompile_the_kernels(key, tmp_path) -> None:
    from certus.core.certus_core import _numba_cache_key_of

    root = _tree(tmp_path)
    before = key(root)

    (root / "certus/ui/window.py").write_text("label = 'another label'\n")
    (root / "certus/ui/another_window.py").write_text("x = 1\n")
    _numba_cache_key_of.cache_clear()

    assert key(root) == before


def test_the_same_sources_in_another_folder_share_the_cache(key, tmp_path) -> None:
    first = _tree(tmp_path / "one")
    second = _tree(tmp_path / "two")

    assert key(first) == key(second)


def test_configure_numba_env_uses_the_keyed_directory(tmp_path) -> None:
    code = (
        "import os, sys; sys.path.insert(0, sys.argv[1]);"
        "from certus.core.certus_core import configure_numba_env, numba_cache_key;"
        "configure_numba_env();"
        "print(os.environ['NUMBA_CACHE_DIR']); print(numba_cache_key())"
    )
    env = {**os.environ, "TMP": str(tmp_path), "TEMP": str(tmp_path), "TMPDIR": str(tmp_path)}
    env.pop("_CERTUS_NUMBA_CONFIGURED", None)
    env.pop("NUMBA_CACHE_DIR", None)  # the test session sets one (tests/conftest.py)

    out = subprocess.run([sys.executable, "-c", code, str(ROOT)], env=env, capture_output=True, text=True, check=True)
    directory, key_printed = out.stdout.split()

    assert Path(directory) == tmp_path / "CERTUS_Numba_Cache" / key_printed
    assert Path(directory).is_dir()


# =============================================================================
# The defect itself: the callee changes, the caller keeps the old one
# =============================================================================

CALLEE = "from numba import njit\n\n@njit(cache=True)\ndef inner(x):\n    return x + {constant}\n"
CALLER = (
    "from numba import njit\nfrom callee import inner\n\n"
    "@njit(cache=True)\ndef outer(x):\n    return inner(x) * 2.0\n"
)
RUN = "import sys; sys.path.insert(0, sys.argv[1]); from caller import outer; print(outer(1.0))"


def _run(folder: Path, cache: Path) -> float:
    env = {**os.environ, "NUMBA_CACHE_DIR": str(cache), "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", RUN, str(folder)], env=env, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def test_a_new_directory_per_version_reads_the_new_callee(tmp_path) -> None:
    # Two versions of a callee in another file than its caller. Compiled and cached for the first, then the
    # callee changes: a cache directory keyed by the sources is another directory, and the answer is the new one.
    from certus.core.certus_core import _numba_cache_key_of, numba_cache_key

    folder = tmp_path / "package"
    (folder / "certus").mkdir(parents=True)
    (folder / "certus_physics").mkdir()
    (folder / "caller.py").write_text(CALLER)

    def compute(constant: float) -> float:
        (folder / "certus" / "callee.py").write_text(CALLEE.format(constant=constant))
        (folder / "callee.py").write_text(CALLEE.format(constant=constant))
        _numba_cache_key_of.cache_clear()
        return _run(folder, tmp_path / "cache" / numba_cache_key(folder))

    first = compute(1.0)
    second = compute(10.0)

    assert first == 4.0  # (1 + 1) * 2
    assert second == 22.0  # (1 + 10) * 2


# =============================================================================
# The test session does not start from the entry point of an application
# =============================================================================

HEAD = (
    "import json, os, sys; sys.path.insert(0, sys.argv[1]);"
    "from certus.core.certus_core import ensure_numba_cache_dir, numba_cache_key;"
    "names = lambda: {k for k in os.environ if k.startswith(('NUMBA_', '_CERTUS_NUMBA'))};"
    "before = names();"
)


def _fresh(code: str, tmp_path: Path, **environment: str) -> dict:
    env = {**os.environ, "TMP": str(tmp_path), "TEMP": str(tmp_path), "TMPDIR": str(tmp_path)}
    for name in ("NUMBA_CACHE_DIR", "_CERTUS_NUMBA_CONFIGURED", "NUMBA_NUM_THREADS", "NUMBA_THREADING_LAYER"):
        env.pop(name, None)
    env.update(environment)
    out = subprocess.run([sys.executable, "-c", code, str(ROOT)], env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


ENSURE = (
    HEAD + "returned = ensure_numba_cache_dir();"
    "print(json.dumps({'returned': returned, 'env': os.environ['NUMBA_CACHE_DIR'], 'key': numba_cache_key(),"
    " 'added': sorted(names() - before)}))"
)


def test_ensure_numba_cache_dir_sets_the_keyed_directory_and_only_that(tmp_path) -> None:
    got = _fresh(ENSURE, tmp_path)

    assert Path(got["returned"]) == Path(got["env"]) == tmp_path / "CERTUS_Numba_Cache" / got["key"]
    assert Path(got["returned"]).is_dir()
    # no thread count, no threading layer, no "configured" flag: those change how a parallel sum adds up
    assert got["added"] == ["NUMBA_CACHE_DIR"]


def test_a_directory_chosen_by_the_caller_is_kept(tmp_path) -> None:
    chosen = str(tmp_path / "mine")

    got = _fresh(ENSURE, tmp_path, NUMBA_CACHE_DIR=chosen)

    assert got["returned"] == got["env"] == chosen
    assert got["added"] == []
    assert not (tmp_path / "CERTUS_Numba_Cache").exists()


KERNELS = (
    "import certus.physics.gradient_utils; import numba;"
    "print(json.dumps({'numba': numba.config.CACHE_DIR}))"
)


def test_the_kernels_read_the_keyed_directory_once_it_is_asked(tmp_path) -> None:
    from certus.core.certus_core import numba_cache_key

    got = _fresh(HEAD + "ensure_numba_cache_dir();" + KERNELS, tmp_path)

    assert Path(got["numba"]) == tmp_path / "CERTUS_Numba_Cache" / numba_cache_key()


def test_left_alone_numba_keeps_its_cache_next_to_the_sources(tmp_path) -> None:
    # The defect: with nobody to say otherwise the location is empty, i.e. `certus/physics/__pycache__`.
    got = _fresh(HEAD + KERNELS, tmp_path)

    assert got["numba"] == ""


def test_this_test_session_reads_a_directory_of_the_kind_the_applications_read() -> None:
    import numba

    # Set by tests/conftest.py before the first import that loads Numba; without it, the kernels of this session
    # read the cache next to the sources, and an old callee inside a new caller.
    assert numba.config.CACHE_DIR
    assert numba.config.CACHE_DIR == os.environ["NUMBA_CACHE_DIR"]
    assert Path(numba.config.CACHE_DIR).is_dir()
