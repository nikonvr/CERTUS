from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _full_attr_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _find_seed_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    forbidden_global_random = {
        "np.random.normal",
        "np.random.uniform",
        "np.random.random",
        "np.random.randn",
        "np.random.rand",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = _full_attr_name(node.func)
        if fn == "np.random.default_rng" and len(node.args) == 0 and not node.keywords:
            violations.append(
                f"{path.name}:{node.lineno} -> np.random.default_rng() sans seed explicite"
            )
        if fn in forbidden_global_random:
            violations.append(
                f"{path.name}:{node.lineno} -> {fn} interdit (utiliser un Generator seedé)"
            )
    return violations


@pytest.mark.unit
def test_seed_contract_no_unseeded_rng_in_critical_modules() -> None:
    repo = Path(__file__).resolve().parents[2]
    targets: list[Path] = []
    targets.extend(repo.glob("CERTUS_*.py"))
    targets.extend(repo.glob("certus_*.py"))
    targets.append(repo / "certus" / "core" / "_certus_physics_impl.py")
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    dedup_targets: list[Path] = []
    for t in targets:
        if "OLD" in t.name.upper():
            continue
        if t in seen:
            continue
        seen.add(t)
        dedup_targets.append(t)
    violations: list[str] = []
    for target in dedup_targets:
        if not target.exists():
            continue
        violations.extend(_find_seed_violations(target))
    assert not violations, "Violations contrat seed:\n" + "\n".join(violations)

