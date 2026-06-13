import ast
import glob
from pathlib import Path
import pytest


def test_no_toplevel_import_of_physics_impl_in_monoliths():
    """
    ARCHITECTURE GUARD:
    CERTUS_*.py monolithic applications must go through the ``certus_physics``
    facade (see ``certus_physics/__init__.py``). Direct top-level imports of
    ``_certus_physics_impl`` bypass the facade and make the Numba JIT internals
    part of each app's public import surface.

    Conditional/lazy imports inside function bodies are tolerated because they
    are sometimes needed for specialized Numba kernels (see
    ``CERTUS_STRAT.py`` ``_dp_kernel`` path).
    """
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in sorted(glob.glob(str(root / "CERTUS_*.py"))):
        # Windows globs are case-insensitive; keep only uppercase CERTUS_ monoliths.
        path_obj = Path(path)
        if not path_obj.name.startswith("CERTUS_"):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in tree.body:  # module-level only
            if isinstance(node, ast.ImportFrom) and node.module == "_certus_physics_impl":
                offenders.append(path_obj.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "_certus_physics_impl":
                        offenders.append(path_obj.name)
    if offenders:
        pytest.fail(
            "CERTUS_* monoliths must import through certus_physics facade. "
            "Top-level _certus_physics_impl import found in: "
            + ", ".join(sorted(set(offenders)))
        )


# Files explicitly allowed to import ``_certus_physics_impl`` at top level.
# Each entry MUST be justified. Adding a new entry requires sign-off because it
# enlarges the public import surface of the Numba JIT internals.
#
# Session 5 (B8 migration) emptied this whitelist: all three former offenders
# (``certus_pointwise_ir``, ``CERTUS_STRAT``, ``spline_objective``) now consume
# the kernels via the ``certus_physics`` facade. Keep this dict even if empty
# so new legacy imports can be whitelisted with justification if strictly
# required.
_PHYSICS_IMPL_TOPLEVEL_WHITELIST: dict[str, str] = {}


def test_no_new_toplevel_import_of_physics_impl():
    """
    ARCHITECTURE GUARD (P10/B8):
    Generalises ``test_no_toplevel_import_of_physics_impl_in_monoliths`` to
    every ``.py`` file at the project root. A small whitelist
    (``_PHYSICS_IMPL_TOPLEVEL_WHITELIST``) tolerates known legacy sites; any
    new file importing ``_certus_physics_impl`` at module scope must either
    join the whitelist (with justification) or migrate to the
    ``certus_physics`` facade.
    """
    root = Path(__file__).resolve().parents[2]
    offenders: dict[str, list[int]] = {}
    for path in sorted(glob.glob(str(root / "*.py"))):
        name = Path(path).name
        # The implementation file itself is allowed to define the symbols.
        if name in {"_certus_physics_impl.py", "_certus_physics_implOLD.py"}:
            continue
        if name in _PHYSICS_IMPL_TOPLEVEL_WHITELIST:
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
        except (SyntaxError, UnicodeDecodeError):
            # Skip unparsable files (none expected at root, but stay defensive).
            continue
        for node in tree.body:  # module-level only
            if isinstance(node, ast.ImportFrom) and node.module == "_certus_physics_impl":
                offenders.setdefault(name, []).append(node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "_certus_physics_impl":
                        offenders.setdefault(name, []).append(node.lineno)

    if offenders:
        details = "; ".join(
            f"{name} (lines {','.join(map(str, lines))})"
            for name, lines in sorted(offenders.items())
        )
        pytest.fail(
            "Direct top-level import of _certus_physics_impl detected outside the "
            "documented whitelist. Either route through ``certus_physics`` or add "
            "a justified entry to _PHYSICS_IMPL_TOPLEVEL_WHITELIST. Offenders: "
            + details
        )


def test_no_processpoolexecutor_in_strat():
    """
    ARCHITECTURE GUARD:
    ProcessPoolExecutor is banned in CERTUS_STRAT.py due to Windows process
    spawning overhead and memory cloning latency.
    We MUST use ThreadPoolExecutor to fully benefit from Numba's nogil=True.
    """
    strat_path = Path(__file__).resolve().parents[2] / "CERTUS_STRAT.py"

    with open(strat_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(strat_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if "ProcessPoolExecutor" in [alias.name for alias in node.names]:
                pytest.fail(
                    "ProcessPoolExecutor import found in CERTUS_STRAT.py. ThreadPoolExecutor must be used."
                )
        elif isinstance(node, ast.Name):
            if node.id == "ProcessPoolExecutor":
                pytest.fail(
                    "ProcessPoolExecutor usage found in CERTUS_STRAT.py. ThreadPoolExecutor must be used."
                )


def test_no_sequential_pglobal():
    """
    ARCHITECTURE GUARD:
    PGlobalOptimizer must use parallelism. Sequential looping over batches
    should only happen as a fallback.
    """
    physics_path = Path(__file__).resolve().parents[2] / "certus" / "physics" / "certus_optimizers.py"

    with open(physics_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(physics_path))

    pglobal_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PGlobalOptimizer":
            pglobal_found = True

            # Check for ThreadPoolExecutor presence
            uses_threadpool = False
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Name) and subnode.id == "ThreadPoolExecutor":
                    uses_threadpool = True
                    break

            assert (
                uses_threadpool
            ), "PGlobalOptimizer must contain ThreadPoolExecutor for parallelism."

    assert pglobal_found, "PGlobalOptimizer class not found in certus_optimizers.py"

def test_numba_nogil_enabled():
    """
    ARCHITECTURE GUARD:
    Crucial Numba kernels must explicitly define `nogil=True` and `parallel=True`
    to allow Python multi-threading to bypass the GIL.
    """
    certus_dir = Path(__file__).resolve().parents[2] / "certus" / "physics"
    kernel_files = [
        certus_dir / "certus_opt_kernels.py",
        certus_dir / "certus_strat_kernels.py"
    ]

    # We check specific kernels that MUST be parallel + nogil.
    target_functions = [
        "needle_scan_cached",
        "calculate_RT_batch_kernel",
    ]

    trees = []
    for f_path in kernel_files:
        with open(f_path, "r", encoding="utf-8") as f:
            trees.append(ast.parse(f.read(), filename=str(f_path)))

    found = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_functions:
                found.add(node.name)
                is_nogil = False
                is_parallel = False

                for decorator in node.decorator_list:
                    if (
                        isinstance(decorator, ast.Call)
                        and hasattr(decorator.func, "id")
                        and decorator.func.id == "njit"
                    ):
                        for kw in decorator.keywords:
                            if (
                                kw.arg == "nogil"
                                and getattr(kw.value, "value", False) is True
                            ):
                                is_nogil = True
                            if (
                                kw.arg == "parallel"
                                and getattr(kw.value, "value", False) is True
                            ):
                                is_parallel = True

                assert (
                    is_nogil
                ), f"Function {node.name} MUST have nogil=True in @njit decorator to allow threading."
                assert (
                    is_parallel
                ), f"Function {node.name} MUST have parallel=True in @njit decorator for performance."

    missing = sorted(set(target_functions) - found)
    assert not missing, f"Missing critical kernels in guard check: {missing}"
