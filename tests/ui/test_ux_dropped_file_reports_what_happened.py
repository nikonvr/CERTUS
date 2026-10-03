"""A dropped file is announced as loaded only when it was loaded (audit UX A02, ETAT D79).

Measured 2026-10-02 on FIELD: a file holding only `{` raised the error dialog, and the green toast
"Fichier chargé : ..." came on top of it. `CertusAppRunStateMixin._handle_dropped_file` announced success
whenever the loader returned, and a loader decorated with `safe_ui_action` returns None after it has absorbed an
error (RE returned False, which the router never read; STRAT showed its own dialog and fell off the end). Six other
drop handlers (`enable_file_drop` callbacks: DESIGN, STRAT, RE, METAL, INDEX SPLINE twice) announced "Loaded" the
same way, and a spectrum dropped on INDEX went to the configuration reader because the router picked a loader by the
mere existence of a method.

The contract: a loader returns True once the file is loaded, and `open_dropped_file` announces success on True only.
The router picks the loader by the kind of file. Three layers pin it:

* the router and the shared function, with stand-in loaders, for each thing a loader can return or do;
* the loaders an application resolves, for each kind of file: they must be able to say True;
* the real windows, with a refused file and a loaded one (tests/ui/test_ux_every_drop_handler_reports_what_happened.py).
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

import certus.ui.certus_base_app_run_mixin as run_mixin
import certus.ui.certus_ui_utils as ui_utils
from certus.ui.certus_base_app_run_mixin import CertusAppRunStateMixin

APPLICATIONS = [
    ("certus.ui.certus_design_ui", "CertusDesignApp"),
    ("certus.ui.certus_field_ui", "CertusFieldApp"),
    ("certus.ui.certus_index_ui", "CertusIndexApp"),
    ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    ("certus.ui.certus_strat_ui", "CertusStratApp"),
    ("CERTUS_RE", "CertusREApp"),
    ("certus.metal.certus_metal_single_app", "CertusMetalSingleApp"),
    ("certus.metal.certus_metal_bilayer_app", "CertusMetalBilayerApp"),
]


@pytest.fixture
def toasts(monkeypatch):
    """What was announced: (level, text) pairs, from the router and from the shared function."""
    shown: list[tuple[str, str]] = []

    def record(_parent, text, level="info", **_kwargs):
        shown.append((level, text))

    monkeypatch.setattr(run_mixin, "show_toast", record)
    monkeypatch.setattr(ui_utils, "show_toast", record)
    return shown


# ---------------------------------------------------------------------------
# 1. The router and the shared function, with a stand-in loader
# ---------------------------------------------------------------------------


class _Router(CertusAppRunStateMixin):
    """The router and nothing else: no window, loaders that do what they are told."""

    def __init__(self, outcome=True, *, data_loader: bool = False) -> None:
        self._outcome = outcome
        self.called: list[str] = []
        if data_loader:
            self.load_file = lambda path: self._answer("load_file", path)

    def _answer(self, name, path):
        self.called.append(f"{name}:{Path(path).name}")
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    def load_config(self, path):
        return self._answer("load_config", path)


@pytest.mark.parametrize(
    ("outcome", "level", "text"),
    [
        (True, "success", "Loaded: config.json"),
        (False, "error", "Load failed: config.json"),  # an explicit refusal (RE)
        (None, "error", "Load failed: config.json"),  # what `safe_ui_action` returns once it has absorbed an error
        (RuntimeError("boom"), "error", "Load failed: config.json"),  # a loader that raises
    ],
    ids=["loaded", "refused", "absorbed", "raised"],
)
def test_the_drop_announces_what_the_loader_did(toasts, outcome, level, text) -> None:
    _Router(outcome)._handle_dropped_file(str(Path("somewhere") / "config.json"))

    assert toasts == [(level, text)]


def test_a_configuration_goes_to_the_configuration_loader(toasts) -> None:
    router = _Router(True, data_loader=True)

    router._handle_dropped_file("somewhere/config.JSON")

    assert router.called == ["load_config:config.JSON"]


def test_a_data_file_goes_to_the_data_loader_not_to_the_configuration_one(toasts) -> None:
    """A spectrum dropped on INDEX used to be parsed as a JSON configuration."""
    router = _Router(True, data_loader=True)

    router._handle_dropped_file("somewhere/spectrum.csv")

    assert router.called == ["load_file:spectrum.csv"]
    assert toasts == [("success", "Loaded: spectrum.csv")]


def test_a_data_file_on_a_window_that_reads_none_is_refused_and_says_so(toasts) -> None:
    router = _Router(True)

    router._handle_dropped_file("somewhere/spectrum.csv")

    assert router.called == [], "the configuration reader was handed a spectrum"
    assert [level for level, _ in toasts] == ["error"]
    assert "spectrum.csv" in toasts[0][1]
    assert ".csv" in toasts[0][1]


# ---------------------------------------------------------------------------
# 2. The loader each application resolves, for each kind of file
# ---------------------------------------------------------------------------


def _resolve(cls, names):
    return next((n for n in names if callable(getattr(cls, n, None))), None)


@pytest.mark.parametrize(("module", "name"), APPLICATIONS, ids=[name for _, name in APPLICATIONS])
def test_the_loaders_the_router_resolves_can_report_success(module, name) -> None:
    """A loader that returns None would see its success reported as a refusal."""
    cls = getattr(importlib.import_module(module), name)

    config_loader = _resolve(cls, CertusAppRunStateMixin._CONFIG_LOADERS)
    assert config_loader, f"{name} reads no configuration: a dropped .json would be refused"
    data_loader = _resolve(cls, CertusAppRunStateMixin._DATA_LOADERS)
    for kind, loader in (("configuration", config_loader), ("data", data_loader)):
        if loader is None:
            continue
        annotation = inspect.signature(getattr(cls, loader)).return_annotation
        assert annotation in (bool, "bool"), (
            f"{name}.{loader} (the {kind} loader) is annotated {annotation!r}: a load is announced only when it returns True"
        )
