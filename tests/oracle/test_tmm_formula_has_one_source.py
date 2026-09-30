"""No new hand-written copy of the reflection formula: `compute_RT_from_matrix` is the single source of R and T.

CLAUDE.md, prohibition 7: two wrong reimplementations of the TMM formula once gave 46 and 82 points of
reflectance error. The oracle catches a copy that is *wrong*; it cannot catch a copy that is right today and
drifts tomorrow, and it does not stop the next one from being written.

The fingerprint is structural, so a renamed variable does not hide a copy: a function whose own body holds both
halves of `r = (E*P - Q) / (E*P + Q)`, that is `E*P + Q` and `E*P - Q` over structurally identical operands
(`n_inc * B + C` and `n_inc * B - C`, or `eta * b + c` and `eta * b - c`).

A ratchet, like `test_lint_debt_ratchet.py`: the copies that exist on 2026-09-30 are listed below and may only
go away; none may come in. Removing a copy means delegating to `compute_RT_from_matrix` (or to the kernel that
does) and deleting its entry here.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("certus", "certus_physics")

ALLOWED = {
    "certus/physics/certus_opt_tmm.py::compute_RT_from_matrix": "the single source",
    # Copies that exist today. The oblique kernels work on the admittance eta = n cos(theta); the two in
    # certus_tmm_single_layer.py are the single-layer helper and INDEX's own plate (ETAT D51).
    "certus/physics/certus_tmm_oblique.py::_calc_spectrum_oblique_parallel": "copy (oblique, admittance)",
    "certus/physics/certus_tmm_oblique.py::_oblique_stack_rt_single": "copy (oblique, admittance)",
    "certus/physics/certus_tmm_oblique.py::oblique_front_rt_from_char_matrix_nsub_real": "copy (oblique, admittance)",
    "certus/physics/certus_tmm_single_layer.py::calculate_transmission_single": "copy (single layer)",
    "certus/physics/certus_tmm_single_layer.py::_calculate_RT_absorbing_sub_single": "copy (INDEX plate, ETAT D51)",
    "certus/physics/gradient_oblique.py::_make_oblique_gradient_contrib_kernel.kernel": "copy (oblique gradient)",
    "certus/physics/gradient_oblique.py::_make_oblique_rt_and_grads_kernel.kernel": "copy (oblique gradient)",
    # Same shape, other physics: the Tauc-Lorentz epsilon_1 integral and its gradient.
    "certus/physics/certus_optical_models.py::epsilon1_TL_analytic": "not TMM (Tauc-Lorentz epsilon_1)",
    "certus/physics/gradient_analytic.py::_compute_epsilon1_gradient_kernel": "not TMM (its gradient)",
}


def _own_binops(function: ast.FunctionDef | ast.AsyncFunctionDef):
    """The BinOps of a function's own body: nested functions, classes and lambdas are scanned on their own."""

    def walk(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
                continue
            if isinstance(child, ast.BinOp):
                yield child
            yield from walk(child)

    for statement in function.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(statement, ast.BinOp):
            yield statement
        yield from walk(statement)


def functions_with_the_reflection_pair(source: str) -> list[str]:
    """Qualified names of the functions that hold both `E*P + Q` and `E*P - Q` (same E, P and Q)."""
    found: list[str] = []
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def _function(self, node) -> None:
            stack.append(node.name)
            plus: set[tuple[str, str]] = set()
            minus: set[tuple[str, str]] = set()
            for op in _own_binops(node):
                if isinstance(op.left, ast.BinOp) and isinstance(op.left.op, ast.Mult):
                    key = (ast.dump(op.left), ast.dump(op.right))
                    if isinstance(op.op, ast.Add):
                        plus.add(key)
                    elif isinstance(op.op, ast.Sub):
                        minus.add(key)
            if plus & minus:
                found.append(".".join(stack))
            self.generic_visit(node)
            stack.pop()

        visit_FunctionDef = _function
        visit_AsyncFunctionDef = _function

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

    Visitor().visit(ast.parse(source))
    return found


@cache
def _found_in_the_repository() -> frozenset[str]:
    found: set[str] = set()
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            names = functions_with_the_reflection_pair(path.read_text(encoding="utf-8-sig"))
            found |= {f"{path.relative_to(ROOT).as_posix()}::{name}" for name in names}
    return frozenset(found)


def test_the_scanner_finds_a_copy_under_any_names_and_nothing_else() -> None:
    """Negative control: with a scanner that finds nothing, the two ratchets below would pass for nothing."""
    renamed = "def rt(m, eta_0, eta_s):\n    b = m[0] + m[1] * eta_s\n    c = m[2] + m[3] * eta_s\n    return (eta_0 * b - c) / (eta_0 * b + c)\n"
    intermediate = "def rt(n_inc, B, C):\n    y = n_inc * B + C\n    return (n_inc * B - C) / y\n"
    unrelated = "def f(a, b, c, d):\n    return a * b + c, a * d - c\n"  # different operands: not the pair
    nested = "def outer(x):\n    def rt(eta, b, c):\n        return (eta * b - c) / (eta * b + c)\n    return rt\n"

    assert functions_with_the_reflection_pair(renamed) == ["rt"]
    assert functions_with_the_reflection_pair(intermediate) == ["rt"]
    assert functions_with_the_reflection_pair(unrelated) == []
    assert functions_with_the_reflection_pair(nested) == ["outer.rt"]  # attributed to the inner function, not to `outer`


def test_no_new_copy_of_the_reflection_formula() -> None:
    new = _found_in_the_repository() - set(ALLOWED)

    assert not new, (
        f"New hand-written copy of the reflection formula: {sorted(new)}. CLAUDE.md prohibition 7: delegate to "
        "certus.physics.certus_opt_tmm.compute_RT_from_matrix (or to the kernel that calls it)."
    )


def test_a_copy_that_was_removed_leaves_the_list() -> None:
    stale = set(ALLOWED) - _found_in_the_repository()

    assert not stale, f"{sorted(stale)} no longer carry the pattern: remove them from ALLOWED."
