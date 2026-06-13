"""Contract tests for the CertusBaseApp config hook surface (Lot C).

These checks validate that the ``_collect_config`` / ``_apply_config`` /
``_post_save_config`` / ``_post_load_config`` hooks exist on
``CertusBaseApp`` and that INDEX properly overrides them.

Round-trip behavior (load -> apply -> collect -> compare) requires a live
QApplication and fully wired widgets; it is exercised by the existing
manual smoke procedure in ``docs/AUDIT_CERTUS_2404.md`` and not by these
unit tests.
"""

from __future__ import annotations

import inspect

import pytest


def test_certus_base_app_exposes_config_hooks():
    from certus.ui.certus_ui import CertusBaseApp

    for hook in (
        "_collect_config",
        "_apply_config",
        "_post_save_config",
        "_post_load_config",
        "save_config",
        "load_config",
    ):
        assert hasattr(CertusBaseApp, hook), f"CertusBaseApp missing {hook!r}"


def test_post_save_and_post_load_hooks_signatures():
    from certus.ui.certus_ui import CertusBaseApp

    sig_save = inspect.signature(CertusBaseApp._post_save_config)
    assert list(sig_save.parameters) == ["self", "filename"]

    sig_load = inspect.signature(CertusBaseApp._post_load_config)
    assert list(sig_load.parameters) == ["self", "filename", "config"]


def test_certus_index_app_overrides_hooks():
    """INDEX must override _collect_config / _apply_config (Lot C migration)."""
    from CERTUS_INDEX import CertusIndexApp
    from certus.ui.certus_ui import CertusBaseApp

    # The override replaces the base no-op with a real implementation.
    assert CertusIndexApp._collect_config is not CertusBaseApp._collect_config
    assert CertusIndexApp._apply_config is not CertusBaseApp._apply_config
    assert CertusIndexApp._post_save_config is not CertusBaseApp._post_save_config
    assert CertusIndexApp._post_load_config is not CertusBaseApp._post_load_config


def test_certus_index_app_does_not_override_save_load():
    """After Lot C migration, INDEX must inherit save_config / load_config."""
    from CERTUS_INDEX import CertusIndexApp
    from certus.ui.certus_ui import CertusBaseApp

    assert CertusIndexApp.save_config is CertusBaseApp.save_config
    assert CertusIndexApp.load_config is CertusBaseApp.load_config


class _FakeIndexAppNoWidgets:
    """Duck-typed stand-in with no widget attributes: exercises hasattr fallbacks."""

    source_file_path = None


def test_certus_index_collect_config_returns_expected_keys():
    """_collect_config must return a dict with the expected core keys."""
    from CERTUS_INDEX import CertusIndexApp

    cfg = CertusIndexApp._collect_config(_FakeIndexAppNoWidgets())

    assert isinstance(cfg, dict)
    for key in (
        "version",
        "substrate",
        "frosted",
        "data_type",
        "file_loaded",
        "thickness_min",
        "thickness_max",
        "normalized",
        "exclude_oh",
        "exclude_min",
        "exclude_max",
        "model_type",
        "params",
        "optimization",
        "weight_T",
        "weight_R",
    ):
        assert key in cfg, f"CertusIndexApp._collect_config missing key {key!r}"


def test_collect_config_without_widgets_is_resilient():
    """_collect_config must not raise when all widgets are absent (all fallbacks)."""
    from CERTUS_INDEX import CertusIndexApp

    cfg = CertusIndexApp._collect_config(_FakeIndexAppNoWidgets())

    assert cfg["weight_T"] == 1.0
    assert cfg["weight_R"] == 1.0
    assert cfg["params"] == []
    assert cfg["optimization"] == {}
    assert cfg["substrate"] == ""
    assert cfg["frosted"] is False
    assert cfg["model_type"] == "TLU"
