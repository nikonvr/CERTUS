"""What a corridor mixin reads on the window is written down, and the corridor state has one table.

The INDEX SPLINE window is built from twenty-one mixins. A corridor mixin reads attributes and calls methods that the
window or another mixin provides, and it keeps its state as plain attributes of the window, written from nine modules.
None of it was declared: a method could start to depend on a widget built elsewhere, or read an attribute with a
fallback that differs from its neighbour's, and nothing would say so.

Two modules declare it now, and this test holds the code to them, by reading the sources:

* certus/ui/certus_index_spline_corridor_host.py: `CONTRACTS` lists, for each corridor mixin, the names it reads on `self`
  and does not define; the protocols give them a type. The lists are exact, so a new coupling has to be written there.
* certus/ui/certus_index_spline_corridor_state.py: `CORRIDOR_STATE` gives each `self._corridor_...` attribute its type,
  the function where it is born, whether `_load_defaults` resets it and the fallbacks passed to `getattr`.

Three properties of the inheritance are frozen with them: no name is defined by two classes of the window apart from the
listed overrides of the base class, no mixin has a constructor (the window calls QMainWindow's, a mixin's would never
run), and no mixin is a protocol or an abstract base (its metaclass would clash with the one of QMainWindow).

The last section holds the eight other windows of the suite to the same three properties, each with the list of the
names it overrides today, and all nine to a fourth one. `CertusBaseApp(QMainWindow, thirteen mixins)` puts the Qt class
first: a name that one of these mixins defined and that QMainWindow or one of its bases also has would never be reached,
and nothing would say so. No such name exists; the test keeps it so.
"""

from __future__ import annotations

import abc
import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtWidgets import QMainWindow

from certus.ui.certus_base_app import CertusBaseApp
from certus.ui.certus_index_spline_corridor_common import _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN
from certus.ui.certus_index_spline_corridor_host import CONTRACTS
from certus.ui.certus_index_spline_corridor_state import (
    CORRIDOR_STATE,
    GRAPHIC_OBJECTS,
    NEVER_ASSIGNED,
    initial_corridor_state,
)
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

ROOT = Path(__file__).resolve().parents[2]
GROUP = sorted((ROOT / "certus" / "ui").glob("certus_index_spline*.py"))
HOST = ROOT / "certus" / "ui" / "certus_index_spline_corridor_host.py"
PROJECT = [k for k in CertusIndexSplineApp.__mro__ if k.__module__.startswith(("certus", "CERTUS"))]
CORRIDOR_MIXINS = {k.__name__: k for k in PROJECT if "Corridor" in k.__name__}
PROTOCOLS = ("IndexSplineRunHost", "IndexSplineViewHost", "CorridorStateHost", "CorridorWidgetsHost")

#: The names two classes of the window define: each time a class of INDEX SPLINE over the base class, on purpose.
OVERRIDES = {
    "APP_NAME", "APP_TITLE", "DEFAULT_WIDTH", "DEFAULT_HEIGHT", "MIN_WIDTH", "MIN_HEIGHT", "__init__",
    "_COMPUTATION_THREADS", "_apply_config", "_collect_config", "_build_ui", "_get_log_widget", "_setup_logger",
    "_warmup_numba", "closeEvent",
}
CLASS_MACHINERY = {
    "__module__", "__dict__", "__weakref__", "__doc__", "__qualname__", "__firstlineno__", "__static_attributes__",
    "__annotations__", "__annotate__", "__annotate_func__", "__annotations_cache__", "__classdictcell__",
}

_TREES: dict[Path, ast.Module] = {}


def tree(path: Path) -> ast.Module:
    if path not in _TREES:
        _TREES[path] = ast.parse(path.read_text(encoding="utf-8-sig"))
    return _TREES[path]


def class_node(klass: type) -> ast.ClassDef:
    nodes = ast.walk(tree(Path(inspect.getsourcefile(klass))))
    return next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == klass.__name__)


def is_self(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "self"


def is_window(node: ast.AST) -> bool:
    """`self`, or `app`: the builders of certus_index_spline_managers_ui write the widgets on the window they are given."""
    return isinstance(node, ast.Name) and node.id in ("self", "app")


def guarded(call: ast.AST) -> str | None:
    """The name in `getattr(self, "name", ...)` or `hasattr(self, "name")`."""
    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in ("getattr", "hasattr"):
        if len(call.args) >= 2 and is_self(call.args[0]) and isinstance(call.args[1], ast.Constant):
            return str(call.args[1].value)
    return None


def reads_of(node: ast.AST) -> set[str]:
    """What the code under `node` reads on the window: `self.x`, `self.__class__.x`, `type(self).x`, the lazy
    `CertusIndexSplineApp.x`, and the names it looks up with getattr / hasattr."""
    found = {name for sub in ast.walk(node) if (name := guarded(sub)) is not None}
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Load)):
            continue
        base = sub.value
        through_class = isinstance(base, ast.Attribute) and is_self(base.value) and base.attr == "__class__"
        through_type = (
            isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "type"
            and bool(base.args) and is_self(base.args[0])
        )
        through_proxy = isinstance(base, ast.Name) and base.id == CertusIndexSplineApp.__name__
        if is_self(base) or through_class or through_type or through_proxy:
            found.add(sub.attr)
    return found


def assigned_of(node: ast.AST) -> set[str]:
    """The attributes the code under `node` sets on the window."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Store) and is_window(sub.value):
            found.add(sub.attr)
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "setattr":
            if len(sub.args) >= 2 and is_window(sub.args[0]) and isinstance(sub.args[1], ast.Constant):
                found.add(str(sub.args[1].value))
    return found


def defined_of(node: ast.ClassDef) -> set[str]:
    names = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for statement in node.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            for target in statement.targets if isinstance(statement, ast.Assign) else [statement.target]:
                names |= {x.id for x in ast.walk(target) if isinstance(x, ast.Name)}
    return names


def required_by(klass: type) -> set[str]:
    """What `klass` reads on the window and neither it nor its own bases define or build. The corridor state counts
    even when the mixin writes it: it is the window's, whoever sets it."""
    own = [base for base in klass.__mro__ if base in PROJECT]
    defined = set().union(*(defined_of(class_node(base)) for base in own))
    built = set().union(*(assigned_of(class_node(base)) for base in own)) - set(CORRIDOR_STATE)
    return {
        name
        for name in reads_of(class_node(klass)) - defined - built
        if not (name.startswith("__") and name.endswith("__")) and not hasattr(QMainWindow, name)
    }


def protocol_members() -> dict[str, dict[str, str]]:
    """Protocol -> member -> its annotation (`def` for a method), read in the source of the host module."""
    members: dict[str, dict[str, str]] = {}
    for node in tree(HOST).body:
        if isinstance(node, ast.ClassDef) and node.name in PROTOCOLS:
            found = {}
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    found[statement.target.id] = ast.unparse(statement.annotation)
                elif isinstance(statement, ast.FunctionDef):
                    found[statement.name] = "def"
            members[node.name] = found
    return members


def set_somewhere() -> set[str]:
    """Every attribute that a class of the window, or a module of the group, sets on the window."""
    found = set().union(*(assigned_of(class_node(klass)) for klass in PROJECT))
    return found.union(*(assigned_of(tree(path)) for path in GROUP))


def scopes(path: Path):
    """(`module:Class.function`, node) for every function of a class of `path`."""
    stem = path.stem.replace("certus_index_spline_", "")
    for klass in tree(path).body:
        if isinstance(klass, ast.ClassDef):
            for function in klass.body:
                if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{stem}:{klass.name}.{function.name}", function


def corridor_attributes_set_in(node: ast.AST) -> set[str]:
    return {name for name in assigned_of(node) if name.startswith("_corridor_")}


# =============================================================================
# The contracts
# =============================================================================
def test_every_corridor_mixin_of_the_window_has_a_contract() -> None:
    assert set(CONTRACTS) == set(CORRIDOR_MIXINS)


@pytest.mark.parametrize("mixin", sorted(CORRIDOR_MIXINS))
def test_a_corridor_mixin_reads_on_the_window_exactly_what_its_contract_says(mixin) -> None:
    read = required_by(CORRIDOR_MIXINS[mixin])
    declared = set(CONTRACTS[mixin])
    assert sorted(read - declared) == [], f"{mixin} reads these on the window and its contract does not say so"
    assert sorted(declared - read) == [], f"{mixin} no longer reads these: take them out of its contract"
    assert list(CONTRACTS[mixin]) == sorted(CONTRACTS[mixin])


def test_the_protocols_type_every_name_of_the_contracts_and_nothing_else() -> None:
    typed = set().union(*(set(members) for members in protocol_members().values()))
    contracted = set().union(*(set(names) for names in CONTRACTS.values()))
    assert sorted(contracted - typed) == [], "read by a corridor mixin, and no protocol gives it a type"
    assert sorted(typed - contracted) == [], "typed by a protocol, and no corridor mixin reads it"


def test_a_name_belongs_to_one_protocol_only() -> None:
    seen: dict[str, str] = {}
    for protocol, members in protocol_members().items():
        for name in members:
            assert name not in seen, f"{name} is in {seen.get(name)} and in {protocol}"
            seen[name] = protocol


def test_the_window_provides_every_member_of_the_protocols() -> None:
    absent = object()
    built = set_somewhere()
    missing = [
        f"{protocol}.{name}"
        for protocol, members in protocol_members().items()
        for name in members
        if inspect.getattr_static(CertusIndexSplineApp, name, absent) is absent and name not in built
    ]
    assert missing == [], "the window has no such attribute, and nothing sets it"


def test_a_method_of_a_protocol_is_a_method_of_the_window_with_the_same_parameters() -> None:
    different = []
    for node in tree(HOST).body:
        if not (isinstance(node, ast.ClassDef) and node.name in PROTOCOLS):
            continue
        for stub in (s for s in node.body if isinstance(s, ast.FunctionDef)):
            real = inspect.unwrap(getattr(CertusIndexSplineApp, stub.name))
            a = stub.args
            every = [*a.posonlyargs, *a.args, a.vararg, *a.kwonlyargs, a.kwarg]
            declared = [arg.arg for arg in every if arg is not None and arg.arg != "self"]
            actual = [p for p in inspect.signature(real).parameters if p != "self"]
            if declared != actual:
                different.append(f"{stub.name}: {declared} declared, {actual} in the window")
    assert different == []


def test_the_state_protocol_is_the_state_table() -> None:
    declared = protocol_members()["CorridorStateHost"]
    assert set(declared) <= set(CORRIDOR_STATE)
    assert {name: CORRIDOR_STATE[name].annotation for name in declared} == declared


# =============================================================================
# The corridor state
# =============================================================================
def test_the_table_names_every_corridor_attribute_the_group_sets_and_only_those() -> None:
    set_by_the_group = set().union(*(corridor_attributes_set_in(tree(path)) for path in GROUP))
    assert set_by_the_group == set(CORRIDOR_STATE) | set(GRAPHIC_OBJECTS)
    assert not set(NEVER_ASSIGNED) & set_by_the_group


def test_an_attribute_is_born_where_the_table_says_and_reset_when_it_says() -> None:
    set_in: dict[str, set[str]] = {}
    for path in GROUP:
        for where, function in scopes(path):
            set_in[where] = corridor_attributes_set_in(function)
    reset = set_in["state_mixin:CertusIndexSplineStateMixin._load_defaults"]
    for name, entry in CORRIDOR_STATE.items():
        assert name in set_in.get(entry.born_in, set()), f"{name} is not set in {entry.born_in}"
        assert entry.reset == (name in reset), f"{name}: reset={entry.reset}, and _load_defaults says otherwise"


def test_nothing_looks_up_a_corridor_attribute_that_nothing_sets() -> None:
    """`_plot_result` read `_corridor_rmse_profile_win` through getattr, with None as fallback. Nothing ever set it: the
    block under it never ran, and the method it would have called on the value exists nowhere (audit, Q13)."""
    looked_up = {
        name for path in GROUP for call in ast.walk(tree(path)) if (name := guarded(call)) is not None and name.startswith("_corridor_")
    }
    set_or_defined = {name for name in looked_up if name in set_somewhere() or hasattr(CertusIndexSplineApp, name)}
    assert sorted(looked_up - set_or_defined) == []
    assert NEVER_ASSIGNED == ()


def fallbacks_in_the_code() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in GROUP:
        for call in ast.walk(tree(path)):
            name = guarded(call)
            if name is not None and name.startswith("_corridor_") and call.func.id == "getattr" and len(call.args) > 2:
                found.setdefault(name, set()).add(ast.unparse(call.args[2]))
    return found


def test_a_getattr_on_a_corridor_attribute_passes_the_fallback_the_table_declares() -> None:
    used = fallbacks_in_the_code()
    for name in NEVER_ASSIGNED:
        assert used.pop(name) == {"None"}
    assert {name: sorted(spellings) for name, spellings in used.items()} == {
        name: sorted(entry.fallbacks) for name, entry in CORRIDOR_STATE.items() if entry.fallbacks
    }


def alike(a: object, b: object) -> bool:
    """The same value, an empty list and an empty array being both `no point yet`, and nan being nan."""
    if isinstance(a, (list, np.ndarray)) or isinstance(b, (list, np.ndarray)):
        return isinstance(a, (list, np.ndarray)) and isinstance(b, (list, np.ndarray)) and len(a) == len(b) == 0
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return type(a) is type(b) and a == b


@pytest.mark.parametrize("name", sorted(n for n, entry in CORRIDOR_STATE.items() if entry.fallbacks))
def test_the_default_of_an_attribute_is_what_its_fallback_gives(name) -> None:
    entry = CORRIDOR_STATE[name]
    names = {"np": np, "_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN": _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN}
    for spelling in entry.fallbacks:
        assert alike(entry.default(), eval(spelling, names)), f"{name}: default {entry.default()!r}, fallback {spelling}"


def test_the_constructor_starts_from_fresh_defaults_that_two_windows_do_not_share() -> None:
    first, second = initial_corridor_state(), initial_corridor_state()
    assert list(first) == list(CORRIDOR_STATE)
    for name, entry in CORRIDOR_STATE.items():
        assert alike(first[name], entry.default()), name
    assert [n for n in first if isinstance(first[n], (list, dict, np.ndarray)) and first[n] is second[n]] == []


def test_what_the_constructor_still_assigns_by_hand_is_the_default_of_the_table() -> None:
    """The constructor sets the whole table first, then six of its attributes again, with their type: the same values."""
    constructor = "ui:CertusIndexSplineApp.__init__"
    [init] = [function for where, function in scopes(ROOT / "certus" / "ui" / "certus_index_spline_ui.py") if where == constructor]
    by_hand = {}
    for node in ast.walk(init):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Attribute) and is_self(target.value) and target.attr.startswith("_corridor_"):
                    by_hand[target.attr] = ast.unparse(node.value)
    assert sorted(by_hand) == sorted(name for name, entry in CORRIDOR_STATE.items() if entry.born_in == constructor)
    for name, spelling in by_hand.items():
        assert alike(CORRIDOR_STATE[name].default(), eval(spelling, {"np": np})), name


# =============================================================================
# The inheritance
# =============================================================================
def test_no_name_is_defined_by_two_classes_of_the_window_but_the_listed_overrides() -> None:
    twice = {}
    for name in set().union(*(set(vars(klass)) for klass in PROJECT)) - CLASS_MACHINERY:
        owners = [klass.__name__ for klass in PROJECT if name in vars(klass)]
        if len(owners) > 1:
            twice[name] = owners
    assert sorted(twice) == sorted(OVERRIDES), twice


def test_no_mixin_of_the_window_has_a_constructor() -> None:
    mixins = [klass for klass in PROJECT if klass not in (CertusIndexSplineApp, CertusBaseApp)]
    assert [klass.__name__ for klass in mixins if "__init__" in vars(klass)] == []


def test_no_mixin_of_the_window_is_a_protocol_or_an_abstract_base() -> None:
    offenders = [k.__name__ for k in PROJECT if getattr(k, "_is_protocol", False) or isinstance(k, abc.ABCMeta)]
    assert offenders == []


# =============================================================================
# The other windows of the suite
# =============================================================================
#: What `python -c` measures, in a fresh interpreter, on the windows scripts/refactor_guard.py lists: importing the nine
#: of them here would leave their modules, and what these patch at import, in the interpreter of the other tests.
SWEEP = r"""
import abc, importlib, importlib.util, json, os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("certus_scripts_refactor_guard", os.path.join("scripts", "refactor_guard.py"))
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)
MACHINERY = set(json.loads(sys.argv[1]))


def project(klass):
    return klass.__module__.startswith(("certus", "CERTUS"))


report = {}
for window in guard.WINDOWS:
    module, _, name = window.partition(":")
    mro = getattr(importlib.import_module(module), name).__mro__
    own = [k for k in mro if project(k)]
    twice = sorted(
        n for n in set().union(*(set(vars(k)) for k in own)) - MACHINERY if sum(n in vars(k) for k in own) > 1
    )
    hidden = sorted(
        f"{k.__name__}.{n} (hidden by {q.__name__})"
        for i, k in enumerate(mro) if project(k)
        for q in mro[:i] if not project(q) and q is not object
        for n in set(vars(k)) - MACHINERY if n in vars(q)
    )
    report[window] = {
        "twice": twice,
        "constructors": [k.__name__ for k in own if "__init__" in vars(k)],
        "protocols": [k.__name__ for k in own if getattr(k, "_is_protocol", False) or isinstance(k, abc.ABCMeta)],
        "hidden": hidden,
    }
print("SWEEP=" + json.dumps(report))
"""

#: The names two classes of a window define, window by window: a subclass or a mixin over the base class, on purpose.
#: INDEX SPLINE is not here: `OVERRIDES`, above, is its list.
SPLINE_WINDOW = f"{CertusIndexSplineApp.__module__}:{CertusIndexSplineApp.__name__}"
OVERRIDES_OF = {
    "certus.ui.certus_design_ui:CertusDesignApp": {
        "APP_NAME", "APP_TITLE", "DEFAULT_HEIGHT", "DEFAULT_WIDTH", "MIN_HEIGHT", "MIN_WIDTH",
        "_COMPUTATION_THREADS", "__init__", "_apply_config", "_apply_theme", "_build_status_bar",
        "_collect_config", "_config_load_problems", "_get_default_splitter_sizes",
        "_get_substrate_info_display", "_on_front_thickness_updated", "_on_layer_added", "_on_layer_deleted",
        "_on_qwot_changed_connection", "_on_warmup_done", "_post_load_config", "_post_save_config",
        "_pre_save_smart_cleanup", "_trigger_post_undo_action", "_update_busy_ui", "closeEvent",
        "smart_cleanup",
    },
    "certus.ui.certus_field_ui:CertusFieldApp": {
        "APP_NAME", "APP_TITLE", "__init__", "_apply_config", "_collect_config", "_get_plot_targets",
        "_post_load_config", "_post_save_config", "copy_logs_to_clipboard", "detach_current_plot",
        "reattach_plot",
    },
    "certus.ui.certus_index_ui:CertusIndexApp": {
        "APP_NAME", "APP_TITLE", "DEFAULT_HEIGHT", "DEFAULT_WIDTH", "MIN_HEIGHT", "MIN_WIDTH",
        "_COMPUTATION_THREADS", "__init__", "_apply_config", "_apply_theme", "_apply_ui_zoom",
        "_build_log_container", "_build_ui", "_collect_config", "_config_load_problems",
        "_get_config_file_filter", "_get_log_widget", "_on_error", "_post_load_config", "_post_save_config",
        "_update_zoom_status", "_warmup_numba", "closeEvent", "detach_current_plot", "sig_numba_error",
        "sig_numba_ready",
    },
    "CERTUS_RE:CertusREApp": {
        "APP_NAME", "APP_TITLE", "DEFAULT_HEIGHT", "DEFAULT_WIDTH", "MIN_HEIGHT", "MIN_WIDTH",
        "_COMPUTATION_THREADS", "_SESSION_FILE_LOADER", "__init__", "_add_front_row", "_apply_theme", "_apply_ui_zoom",
        "_build_status_bar", "_collect_config", "_get_default_splitter_sizes", "_get_front_stack",
        "_get_plot_info", "_get_substrate_info_display", "_merge_adjacent_layers", "_on_layer_added",
        "_on_layer_deleted", "_on_qwot_changed_connection", "_stack_info_front_table_cols",
        "_trigger_post_undo_action", "_update_busy_ui", "_update_layer_count", "_update_qwot_from_ep",
        "_update_target_table_headers", "_update_thickness_display", "closeEvent", "load_config",
    },
    "certus.ui.certus_strat_ui:CertusStratApp": {
        "APP_NAME", "APP_TITLE", "DEFAULT_HEIGHT", "DEFAULT_WIDTH", "MIN_HEIGHT", "MIN_WIDTH", "_SESSION_FILE_LOADER",
        "__init__", "_apply_theme", "_apply_ui_zoom", "_build_log_container", "_collect_config", "_get_log_widget",
        "_save_undo_state", "_warmup_numba", "closeEvent", "save_config", "sig_numba_error", "sig_numba_ready",
        "timerEvent",
    },
    "certus.ui.certus_metal_single_gui:CertusMetalSingleApp": {
        "MODULE_ID", "_COMPUTATION_THREADS", "__init__", "_apply_config", "_apply_config_dict", "_apply_theme",
        "_collect_config", "_create_material_params_group", "_create_physical_params_group",
        "_do_export_results", "_get_config_dict", "_get_log_widget", "_post_load_config", "_post_save_config",
        "_setup_parameter_grid", "_setup_plots", "_warmup_numba", "closeEvent", "detach_current_plot",
        "eventFilter", "load_target_file", "reattach_plot", "sig_numba_error", "sig_numba_ready",
        "start_optimization",
    },
    "certus.ui.certus_metal_bilayer_gui:CertusMetalBilayerApp": {
        "APP_NAME", "EXPORT_FAILURE_LOG", "MODULE_ID", "_COMPUTATION_THREADS", "__init__", "_apply_config",
        "_apply_config_dict", "_apply_theme", "_collect_config", "_create_labeled_input",
        "_create_live_params_group", "_create_material_params_group", "_create_physical_params_group",
        "_do_export_results", "_get_config_dict", "_get_log_widget", "_load_defaults", "_post_load_config",
        "_post_save_config", "_setup_parameter_grid", "_setup_plots", "_warmup_numba", "closeEvent",
        "detach_current_plot", "eventFilter", "reattach_plot", "sig_numba_error", "sig_numba_ready",
        "start_optimization",
    },
    "CERTUS_HUB:CertusHub": set(),
}


@pytest.fixture(scope="module")
def windows() -> dict[str, dict[str, list[str]]]:
    out = subprocess.run(
        [sys.executable, "-c", SWEEP, json.dumps(sorted(CLASS_MACHINERY))], capture_output=True, text=True, cwd=ROOT, timeout=900
    )
    assert out.returncode == 0, out.stderr[-1500:]
    [line] = [x for x in out.stdout.splitlines() if x.startswith("SWEEP=")]
    return json.loads(line.removeprefix("SWEEP="))


def test_the_sweep_sees_the_nine_windows(windows) -> None:
    assert set(windows) == set(OVERRIDES_OF) | {SPLINE_WINDOW}
    assert sorted(windows[SPLINE_WINDOW]["twice"]) == sorted(OVERRIDES)


@pytest.mark.parametrize("window", sorted(OVERRIDES_OF))
def test_no_name_is_defined_by_two_classes_of_another_window_but_its_listed_overrides(windows, window) -> None:
    twice = set(windows[window]["twice"])
    assert sorted(twice - OVERRIDES_OF[window]) == [], f"{window}: defined twice, and not listed"
    assert sorted(OVERRIDES_OF[window] - twice) == [], f"{window}: no longer defined twice, take them off the list"


def test_no_mixin_of_any_window_has_a_constructor(windows) -> None:
    offenders = {w: [k for k in found["constructors"] if "Mixin" in k] for w, found in windows.items()}
    assert {w: ks for w, ks in offenders.items() if ks} == {}


def test_no_class_of_any_window_is_a_protocol_or_an_abstract_base(windows) -> None:
    assert {w: found["protocols"] for w, found in windows.items() if found["protocols"]} == {}


def test_no_name_of_a_project_class_is_hidden_by_a_qt_class_placed_before_it(windows) -> None:
    assert {w: found["hidden"] for w, found in windows.items() if found["hidden"]} == {}
