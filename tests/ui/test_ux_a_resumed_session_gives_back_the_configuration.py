"""A resumed session gives the window back the configuration it held (U12 A).

The session file holds what the window's `_collect_config` returned; resuming hands it to `_apply_config`. For each
window that resumes a session, the configuration collected from one window, applied to a fresh one, must come back
the same: otherwise a resumed session would be a different configuration that looks like the old one.
STRAT and RE are not here: they reload only from a file, and resume no session yet (REPRISE.md, U12 A).
"""

from __future__ import annotations

import importlib
import json

import pytest

WINDOWS = [
    ("certus.ui.certus_design_ui", "CertusDesignApp"),
    ("certus.ui.certus_field_ui", "CertusFieldApp"),
    ("certus.ui.certus_index_ui", "CertusIndexApp"),
    ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
    ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
]


def _canonical(config) -> str:
    return json.dumps(config, sort_keys=True, default=str)


@pytest.mark.parametrize(("module_name", "class_name"), WINDOWS)
def test_collect_then_apply_gives_back_the_same_configuration(qapp, module_name, class_name) -> None:
    cls = getattr(importlib.import_module(module_name), class_name)
    first = cls()
    try:
        assert first._session_supported()
        config = first._collect_config()
    finally:
        first.close()
    second = cls()
    try:
        second._apply_config(json.loads(json.dumps(config, default=str)))
        assert _canonical(second._collect_config()) == _canonical(config)
    finally:
        second.close()
