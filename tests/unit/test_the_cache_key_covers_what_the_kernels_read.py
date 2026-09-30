"""The Numba cache key covers every module that gives a kernel a value.

Numba freezes into the machine code of a kernel each global it reads: a constant imported from another module, a value
computed from one at module level, a function called through a facade. It drops a cached kernel when THE KERNEL'S OWN
FILE changes, and only then. `numba_cache_key` (certus_core) makes up for it by covering the sources whose text
mentions numba; a module that gives a kernel a value and does not say numba is a hole in that key. Change it and the
kernels of another file go on running with the old value, from the cache, silently
(tests/unit/test_numba_cache_is_keyed_by_the_sources.py shows the failure that the key was made for).

Found on 2026-09-30, moving the constants of the physics layer out of certus_core: `certus_tmm_core.py`, a facade that
re-exports the TMM kernels, did not say numba, and two kernel files call through it.

The analysis is static (ast) and follows a value through the module-level assignments and imports that carry it, so
a constant that reaches a kernel by way of a second module counts too.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("certus", "certus_physics")  # the folders that `numba_cache_key` reads
JIT_DECORATORS = {"njit", "jit", "vectorize", "guvectorize", "stencil", "cfunc"}


def _module_level(nodes: list[ast.stmt]):
    """The statements that run when the module is imported: not the bodies of functions and classes."""
    for node in nodes:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        yield node
        for field in ("body", "orelse", "finalbody"):
            inner = getattr(node, field, None)
            if isinstance(inner, list):
                yield from _module_level(inner)
        for handler in getattr(node, "handlers", []):
            yield from _module_level(handler.body)


def _is_kernel(node: ast.AST) -> bool:
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")) in JIT_DECORATORS:
            return True
    return False


def _reads(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


class Sources:
    """The sources that the key reads, and who feeds a kernel."""

    def __init__(self, root: Path) -> None:
        self.raw: dict[str, bytes] = {}
        for package in PACKAGES:
            for path in sorted((root / package).rglob("*.py")):
                self.raw[path.relative_to(root).as_posix()] = path.read_bytes()
        self.aliases: dict[str, dict[str, tuple[str, str | None]]] = {}  # file -> name -> (giver file, name there)
        self.assigned: dict[str, dict[str, set[str]]] = {}  # file -> name -> names its value reads
        self.kernels: dict[str, list[ast.AST]] = {}
        for rel, data in self.raw.items():
            try:
                tree = ast.parse(data.decode("utf-8-sig", "replace"), filename=rel)
            except SyntaxError:
                continue
            self.aliases[rel], self.assigned[rel] = {}, {}
            for node in _module_level(tree.body):
                self._record(rel, node)
            self.kernels[rel] = [n for n in ast.walk(tree) if _is_kernel(n)]

    def in_key(self, rel: str) -> bool:
        """The criterion of `numba_cache_key`: the text of the file contains `numba`."""
        return b"numba" in self.raw[rel]

    def _file_of(self, dotted: str) -> str | None:
        parts = dotted.split(".")
        while parts:
            base = "/".join(parts)
            for candidate in (f"{base}.py", f"{base}/__init__.py"):
                if candidate in self.raw:
                    return candidate
            parts.pop()
        return None

    def _record(self, rel: str, node: ast.stmt) -> None:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname and (giver := self._file_of(a.name)):
                    self.aliases[rel][a.asname] = (giver, None)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = rel[:-3].split("/")[:-1]
                base = ".".join([*package[: len(package) - (node.level - 1)], *([node.module] if node.module else [])])
            for a in node.names:
                submodule = self._file_of(f"{base}.{a.name}")
                whole = self._file_of(base)
                if submodule and submodule.removesuffix(".py").endswith(a.name):
                    self.aliases[rel][a.asname or a.name] = (submodule, None)  # `from pkg import module`
                elif whole:
                    self.aliases[rel][a.asname or a.name] = (whole, a.name)
        elif isinstance(node, ast.Assign | ast.AnnAssign) and getattr(node, "value", None) is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    self.assigned[rel].setdefault(target.id, set()).update(_reads(node.value))

    def _follow(self, rel: str, name: str, seen: set[tuple[str, str]], out: set[str]) -> None:
        if (rel, name) in seen or rel not in self.aliases:
            return
        seen.add((rel, name))
        for read in self.assigned[rel].get(name, ()):
            self._follow(rel, read, seen, out)
        if name in self.aliases[rel]:
            giver, original = self.aliases[rel][name]
            out.add(giver)
            if original is not None:
                self._follow(giver, original, seen, out)

    def givers(self) -> dict[str, set[str]]:
        """{module that gives some kernel a value: the kernel files it feeds}."""
        fed: dict[str, set[str]] = {}
        for rel, kernels in self.kernels.items():
            if not kernels:
                continue
            out: set[str] = set()
            seen: set[tuple[str, str]] = set()
            for kernel in kernels:
                for name in _reads(kernel):
                    self._follow(rel, name, seen, out)
                for node in ast.walk(kernel):  # `module.attribute`: the attribute comes from that module
                    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                        alias = self.aliases[rel].get(node.value.id)
                        if alias and alias[1] is None:
                            self._follow(alias[0], node.attr, seen, out)
            for giver in out - {rel}:
                fed.setdefault(giver, set()).add(rel)
        return fed

    def outside_the_key(self) -> dict[str, list[str]]:
        return {g: sorted(files) for g, files in sorted(self.givers().items()) if not self.in_key(g)}


# =============================================================================
# The repository
# =============================================================================


def test_no_module_gives_a_kernel_a_value_without_being_in_the_cache_key() -> None:
    outside = Sources(ROOT).outside_the_key()

    assert outside == {}, (
        "these files give a Numba kernel a value (a constant, a callee) and their text does not mention numba, so "
        f"editing them leaves the cache key where it was and the kernels keep the old value: {outside}"
    )


def test_the_analysis_sees_the_kernels_of_the_repository() -> None:
    # A guard that scans nothing passes forever: the physics kernels, and the file that gives them `TWO_PI`, are there.
    sources = Sources(ROOT)
    fed = sources.givers()

    assert len([rel for rel, kernels in sources.kernels.items() if kernels]) >= 25
    assert "certus/domain/constants.py" in fed
    assert len(fed["certus/domain/constants.py"]) >= 10


# =============================================================================
# The analysis itself, on small trees
# =============================================================================


def _tree(tmp_path: Path, files: dict[str, str]) -> Sources:
    for package in PACKAGES:
        (tmp_path / package).mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return Sources(tmp_path)


KERNEL = "from numba import njit\nfrom certus.core.limits import LIMIT\n\n@njit\ndef f(x):\n    return x + LIMIT\n"


def test_a_constant_read_by_a_kernel_from_a_module_that_does_not_say_numba_is_a_hole(tmp_path) -> None:
    sources = _tree(tmp_path, {"certus/physics/k.py": KERNEL, "certus/core/limits.py": "LIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {"certus/core/limits.py": ["certus/physics/k.py"]}


def test_the_same_module_is_covered_once_its_text_says_numba(tmp_path) -> None:
    sources = _tree(tmp_path, {"certus/physics/k.py": KERNEL, "certus/core/limits.py": "# read by numba kernels\nLIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {}


def test_what_no_kernel_reads_is_not_reported(tmp_path) -> None:
    python_only = (
        "from numba import njit\nfrom certus.core.limits import LIMIT\n\n@njit\ndef f(x):\n    return x + 1.0\n\n"
        "def g(x):\n    return x + LIMIT\n"
    )
    sources = _tree(tmp_path, {"certus/physics/k.py": python_only, "certus/core/limits.py": "LIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {}


def test_a_value_computed_from_an_import_at_module_level_is_followed(tmp_path) -> None:
    derived = (
        "from numba import njit\nfrom certus.core.limits import LIMIT\n\nHALF = LIMIT / 2\n\n"
        "@njit\ndef f(x):\n    return x + HALF\n"
    )
    sources = _tree(tmp_path, {"certus/physics/k.py": derived, "certus/core/limits.py": "LIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {"certus/core/limits.py": ["certus/physics/k.py"]}


def test_a_value_that_reaches_the_kernel_through_a_second_module_is_followed(tmp_path) -> None:
    # k.py -> middle.py (says numba, so it is in the key) -> limits.py (does not): the constant still comes from there.
    middle = "# numba kernels import their limits from here\nfrom certus.core.limits import LIMIT\n"
    kernel = "from numba import njit\nfrom certus.core.middle import LIMIT\n\n@njit\ndef f(x):\n    return x + LIMIT\n"
    sources = _tree(
        tmp_path,
        {"certus/physics/k.py": kernel, "certus/core/middle.py": middle, "certus/core/limits.py": "LIMIT = 1e-5\n"},
    )

    assert sources.outside_the_key() == {"certus/core/limits.py": ["certus/physics/k.py"]}


def test_a_callee_reached_through_a_facade_that_does_not_say_numba_is_a_hole(tmp_path) -> None:
    # The case of certus_tmm_core.py: the kernel calls `tmm.g` and the facade only re-exports it.
    callee = "from numba import njit\n\n@njit\ndef g(x):\n    return x * 2.0\n"
    facade = "from certus.physics.callee import g\n"
    caller = (
        "from numba import njit\nimport certus.physics.facade as tmm\n\n@njit\ndef f(x):\n    return tmm.g(x)\n"
    )
    sources = _tree(
        tmp_path,
        {"certus/physics/callee.py": callee, "certus/physics/facade.py": facade, "certus/physics/caller.py": caller},
    )

    assert sources.outside_the_key() == {"certus/physics/facade.py": ["certus/physics/caller.py"]}


def test_a_value_read_as_module_dot_attribute_is_followed_into_that_module(tmp_path) -> None:
    # The facade says numba, so it is in the key; the limit it hands to the kernel comes from a file that does not.
    facade = "# numba kernels read their limits through here\nfrom certus.core.limits import LIMIT\n"
    caller = "from numba import njit\nimport certus.physics.facade as facade\n\n@njit\ndef f(x):\n    return x + facade.LIMIT\n"
    sources = _tree(
        tmp_path,
        {"certus/physics/facade.py": facade, "certus/physics/caller.py": caller, "certus/core/limits.py": "LIMIT = 1e-5\n"},
    )

    assert sources.outside_the_key() == {"certus/core/limits.py": ["certus/physics/caller.py"]}


def test_relative_imports_are_resolved(tmp_path) -> None:
    kernel = "from numba import njit\nfrom .limits import LIMIT\n\n@njit\ndef f(x):\n    return x + LIMIT\n"
    sources = _tree(tmp_path, {"certus/physics/k.py": kernel, "certus/physics/limits.py": "LIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {"certus/physics/limits.py": ["certus/physics/k.py"]}


@pytest.mark.parametrize("decorator", ["@njit", "@njit(cache=True, fastmath=True)", "@numba.njit", "@jit(nopython=True)"])
def test_every_way_of_writing_a_kernel_is_recognised(tmp_path, decorator) -> None:
    kernel = f"import numba\nfrom numba import njit, jit\nfrom certus.core.limits import LIMIT\n\n{decorator}\ndef f(x):\n    return x + LIMIT\n"
    sources = _tree(tmp_path, {"certus/physics/k.py": kernel, "certus/core/limits.py": "LIMIT = 1e-5\n"})

    assert sources.outside_the_key() == {"certus/core/limits.py": ["certus/physics/k.py"]}
