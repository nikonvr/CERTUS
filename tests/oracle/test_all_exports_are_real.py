"""Tout nom déclaré dans un ``__all__`` doit exister à l'exécution.

Un ``__all__`` qui liste des noms inexistants fait lever ``AttributeError`` à tout
``import *`` sur le module. Le dépôt en comptait **202**, répartis sur quatre fichiers
d'interface — de quoi rendre ces modules inutilisables par étoile, sans que rien ne le
signale tant que personne n'essayait.

Ce test balaie l'ensemble du paquet, et pas seulement les quatre fichiers concernés :
la régression peut apparaître n'importe où.

POURQUOI PAS SEULEMENT RUFF
---------------------------
La règle F822 ne suffit pas. Un nom importé sous ``if TYPE_CHECKING:`` est lié dans
l'analyse statique de ruff, qui le considère donc comme défini — alors qu'il n'existe
pas à l'exécution. C'est exactement ce qui est arrivé à ``SkeletonLoaderWidget`` dans
``certus_ui_utils`` : ruff validait, l'import réel échouait. Seule une vérification
dynamique le révèle.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import certus


def _iter_module_names() -> list[str]:
    """Tous les sous-modules de ``certus``, découverts par le système de fichiers.

    ``pkgutil.walk_packages`` ne convient PAS ici : seul ``certus/domain/`` possède un
    ``__init__.py``, les sept autres sous-paquets fonctionnent en PEP 420 (paquets
    implicites, cf. CLAUDE.md §2). walk_packages n'en trouvait que 6 sur ~280 — le
    test passait donc en ne couvrant presque rien.

    Les modules qui ne s'importent pas du tout sont hors sujet ici : c'est le rôle de
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

    Le symptôme est un ``AttributeError`` au premier ``from module import *``.
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
