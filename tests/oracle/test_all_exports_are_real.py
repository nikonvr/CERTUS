"""Any name declared in an ``__all__`` must exist at runtime.

A ``__all__`` which lists non-existent names causes ``AttributeError`` to be raised at all
``import *`` on the module. The repository had **202**, spread over four files
interface — enough to make these modules unusable per star, without anything
signaled until no one tried.

This test scans the entire package, not just the four affected files:
regression can appear anywhere.

WHY NOT JUST RUFF
---------------------------
Rule F822 is not enough. A name imported under ``if TYPE_CHECKING:`` is linked in
the static analysis of ruff, which therefore considers it as defined - even though it does not exist
not at execution. This is exactly what happened to ``SkeletonLoaderWidget`` in
``certus_ui_utils``: ruff validated, the actual import failed. Only verification
dynamic reveals it.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import certus


def _iter_module_names() -> list[str]:
    """All submodules of ``certus``, discovered by the file system.

    ``pkgutil.walk_packages`` is NOT suitable here: only ``certus/domain/`` has a
    ``__init__.py``, les sept autres sous-paquets fonctionnent en PEP 420 (paquets
    implicites, cf. CLAUDE.md §2). walk_packages n'en trouvait que 6 sur ~280 — le
    test therefore passed by covering almost nothing.

    Modules that do not import at all are off topic here: that is the role of
    tests/ui/test_ui_module_imports.py.
    """
    root = Path(certus.__path__[0])
    names = []

    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).with_suffix("")
        names.append("certus." + ".".join(relative.parts))

    return names


MODULE_NAMES = _iter_module_names()


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_all_ne_declare_que_des_noms_existants(module_name: str) -> None:
    """GARDE-FOU : 202 violations de ce contrat existaient dans les 4 fichiers UI.

    The symptom is an ``AttributeError`` at the first ``from module import *``.
    """
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 — l'importabilite est testee ailleurs
        pytest.skip(f"module non importable ({type(exc).__name__}) : hors sujet ici")

    declared = getattr(module, "__all__", None)
    if not declared:
        return

    missing = [name for name in declared if not hasattr(module, name)]

    assert not missing, (
        f"{module_name} : {len(missing)} nom(s) declares dans __all__ mais absents "
        f"a l'execution — tout `import *` sur ce module leve AttributeError.\n"
        f"  {missing}"
    )
