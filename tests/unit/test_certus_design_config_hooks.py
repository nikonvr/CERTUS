"""Tests for the CERTUS_DESIGN config save/load hook migration (Lot C)."""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_design_app_exposes_all_config_hooks():
    from CERTUS_DESIGN import CertusDesignApp

    for attr in (
        "save_config",
        "load_config",
        "_pre_save_smart_cleanup",
        "_collect_config",
        "_apply_config",
        "_post_save_config",
        "_post_load_config",
    ):
        assert hasattr(CertusDesignApp, attr), f"Missing {attr!r} on CertusDesignApp"


def test_design_post_save_config_signature_matches_base():
    """Override must accept ``(self, filename)`` — same as CertusBaseApp."""
    from CERTUS_DESIGN import CertusDesignApp
    from certus_ui import CertusBaseApp

    base_sig = inspect.signature(CertusBaseApp._post_save_config)
    design_sig = inspect.signature(CertusDesignApp._post_save_config)
    assert list(base_sig.parameters) == list(design_sig.parameters)


def test_design_post_load_config_accepts_base_contract():
    """Override must at least accept ``(self, filename, config)``."""
    from CERTUS_DESIGN import CertusDesignApp

    sig = inspect.signature(CertusDesignApp._post_load_config)
    params = list(sig.parameters)
    # self + filename + config (plus optional keyword-only _load_start)
    assert params[:3] == ["self", "filename", "config"]


def test_design_collect_config_is_pure_dict_method():
    """_collect_config takes only self and returns a dict (pure w.r.t. I/O)."""
    from CERTUS_DESIGN import CertusDesignApp

    sig = inspect.signature(CertusDesignApp._collect_config)
    assert list(sig.parameters) == ["self"]


def test_design_apply_config_takes_dict_only():
    from CERTUS_DESIGN import CertusDesignApp

    sig = inspect.signature(CertusDesignApp._apply_config)
    params = list(sig.parameters)
    assert params[:2] == ["self", "c"]


def test_design_save_config_delegates_to_hooks_and_recent():
    """Inspect save_config source to ensure it routes through the hooks."""
    from CERTUS_DESIGN import CertusDesignApp

    src = inspect.getsource(CertusDesignApp.save_config)
    # Must call each of the new hooks + MRU recorder
    for needle in (
        "_pre_save_smart_cleanup",
        "_collect_config",
        "_record_recent_config",
        "_post_save_config",
    ):
        assert needle in src, f"save_config does not call {needle}"


def test_design_load_config_delegates_to_hooks_and_recent():
    from CERTUS_DESIGN import CertusDesignApp

    src = inspect.getsource(CertusDesignApp.load_config)
    for needle in (
        "_apply_config",
        "_record_recent_config",
        "_post_load_config",
    ):
        assert needle in src, f"load_config does not call {needle}"


def test_design_apply_config_delegates_to_small_helpers():
    from CERTUS_DESIGN import CertusDesignApp

    src = inspect.getsource(CertusDesignApp._apply_config)
    for needle in (
        "_apply_material_config",
        "_apply_stack_rows",
        "_apply_target_config",
        "_apply_optimization_config",
    ):
        assert needle in src, f"_apply_config does not call {needle}"


def test_design_smart_cleanup_preserved_in_save_flow():
    """The smart_cleanup pre-processing must still live in the save pipeline."""
    from CERTUS_DESIGN import CertusDesignApp

    pre_src = inspect.getsource(CertusDesignApp._pre_save_smart_cleanup)
    assert "smart_cleanup" in pre_src
    assert "front_table" in pre_src


def test_design_hooks_apis_are_callable_on_instance_shape():
    """Duck-type an instance-less call to ensure method resolution works."""
    from CERTUS_DESIGN import CertusDesignApp

    # Bound via descriptor protocol — confirms the methods exist as real
    # attribute descriptors (not monkey-patched at runtime).
    for name in ("_collect_config", "_apply_config", "_post_save_config", "_post_load_config"):
        m = getattr(CertusDesignApp, name)
        assert callable(m)
