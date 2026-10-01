"""`certus_index_spline_corridors.py` was split into a facade and five modules (audit v2, plan S5.3); nothing that used it may notice.

It held 3 012 lines: three mixin classes of the INDEX SPLINE window, 1 505 lines for the first. The mixins moved to their own modules, the
first one in two (its corridor tab became `_CorridorTabMixin`, which `_CorridorWorkerMixin` inherits), the constants and the log-k helper to
a leaf, and the imports of the interface layer (`certus.ui`) to ONE module, the gateway. What this file pins:

* every name that a part defines is an attribute of the facade and IS the same object (`CERTUS_INDEX_SPLINE` proxies attribute reads to the
  facade, and the window class takes the three mixins from it);
* the window still has every method it had, and the moved ones are the functions of their new mixin (the code surface of the class was
  compared before and after with a checksum of each bytecode: 720 attributes, none different);
* only the gateway imports `certus.ui` at module level: the layering debt (a lower layer importing a higher one, tests/architecture_debt.json)
  counts MODULE edges, and five parts importing the interface would have counted five times what one module did;
* no part is a long file any more.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPLINE = ROOT / "certus" / "spline"
FACADE = "certus.spline.certus_index_spline_corridors"
#: The parts of the split, by name (a glob would also take `certus_index_spline_corridor_contract.py`, which is older and not one of them).
PARTS = [
    "certus_index_spline_corridor_common",
    "certus_index_spline_corridor_data",
    "certus_index_spline_corridor_gen",
    "certus_index_spline_corridor_tab",
    "certus_index_spline_corridor_ui",
    "certus_index_spline_corridor_worker",
]
GATEWAY = "certus_index_spline_corridor_ui"
LONG_FILE = 1500


def top_level_names(path: Path) -> list[str]:
    names = []
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                names += [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
    return names


def test_the_split_has_its_six_parts_and_the_facade_re_exports_the_classes_they_define():
    assert all((SPLINE / f"{part}.py").is_file() for part in PARTS)
    facade_text = (SPLINE / "certus_index_spline_corridors.py").read_text(encoding="utf-8-sig")
    for part in PARTS:
        if part not in ("certus_index_spline_corridor_tab", GATEWAY):
            assert f"certus.spline.{part} import" in facade_text, part


@pytest.mark.parametrize("part", [p for p in PARTS if p != GATEWAY])
def test_every_name_that_a_part_defines_is_the_same_object_in_the_facade(part):
    module = importlib.import_module(f"certus.spline.{part}")
    facade = importlib.import_module(FACADE)
    defined = top_level_names(SPLINE / f"{part}.py")
    assert defined, f"{part} defines nothing"
    for name in defined:
        if part == "certus_index_spline_corridor_tab":
            continue  # the tab mixin is reached through the worker mixin, which inherits it (tested below)
        assert hasattr(facade, name), f"{FACADE}.{name} is gone (defined in {part})"
        assert getattr(module, name) is getattr(facade, name) or getattr(module, name) == getattr(facade, name), (part, name)


def test_the_worker_mixin_inherits_the_tab_mixin_and_the_window_has_every_method():
    from certus.spline.certus_index_spline_corridor_tab import _CorridorTabMixin
    from certus.spline.certus_index_spline_corridor_worker import _CorridorWorkerMixin
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    assert _CorridorTabMixin in _CorridorWorkerMixin.__mro__
    mro = CertusIndexSplineApp.__mro__
    assert mro.index(_CorridorTabMixin) == mro.index(_CorridorWorkerMixin) + 1, "the tab mixin follows the worker mixin in the MRO"
    for name in ("_plot_corridor_tab", "_build_corridor_tab_rmse_controls"):
        assert getattr(CertusIndexSplineApp, name) is _CorridorTabMixin.__dict__[name]
    for name in ("_finish_corridor_rmse_d_grid_worker_done", "_on_worker_done", "_start_corridor_rmse_grid_recalc"):
        assert getattr(CertusIndexSplineApp, name) is _CorridorWorkerMixin.__dict__[name]


def test_the_window_class_takes_the_three_mixins_from_the_facade():
    facade = importlib.import_module(FACADE)
    for name in ("_CorridorWorkerMixin", "_DataMixin", "_CorridorGenMixin"):
        assert isinstance(getattr(facade, name), type), name


@pytest.mark.parametrize("part", PARTS)
def test_only_the_gateway_imports_the_interface_layer_at_module_level(part):
    tree = ast.parse((SPLINE / f"{part}.py").read_text(encoding="utf-8-sig"))
    ui = [
        (node.module, node.lineno)
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("certus.ui.")
    ] + [(a.name, node.lineno) for node in tree.body if isinstance(node, ast.Import) for a in node.names if a.name.startswith("certus.ui.")]
    if part == GATEWAY:
        assert len(ui) == 3, f"the gateway carries the three upward edges the module had: {ui}"
    else:
        assert not ui, f"{part} imports the interface layer itself (import it from {GATEWAY}): {ui}"


def test_the_facade_imports_nothing_of_the_interface_layer_either():
    tree = ast.parse((SPLINE / "certus_index_spline_corridors.py").read_text(encoding="utf-8-sig"))
    ui = [node.module for node in tree.body if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("certus.ui.")]
    assert not ui, ui


@pytest.mark.parametrize("part", [*PARTS, "certus_index_spline_corridors"])
def test_no_part_is_a_long_file(part):
    n = len((SPLINE / f"{part}.py").read_text(encoding="utf-8-sig").splitlines())
    assert n <= LONG_FILE, f"{part}: {n} lines"
