"""Unit tests for the P3/P5/P6/A7 scaffolds introduced in Session 6:

- ``MetalJobSpec`` + canonical ``METAL_SINGLE_SPEC`` / ``METAL_BILAYER_SPEC``
- ``MetalBaseApp._collect_config`` / ``_apply_config`` bridge over the
  legacy ``_get_config_dict`` / ``_apply_config_dict`` hooks
- ``reset_app_to_defaults`` module-level helper in ``certus_reset_framework``

No Qt instantiation: we exercise the dataclasses and the bridge via
lightweight dummies so these tests run anywhere.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# MetalJobSpec (P3 scaffold)
# ---------------------------------------------------------------------------


class TestMetalJobSpec:
    def test_dataclass_is_frozen(self):
        from certus.metal.certus_metal_common import MetalJobSpec
        spec = MetalJobSpec(variant="single", n_layers=1)
        with pytest.raises((AttributeError, Exception)):
            spec.variant = "bilayer"  # type: ignore[misc]

    def test_default_fields(self):
        from certus.metal.certus_metal_common import MetalJobSpec
        spec = MetalJobSpec(variant="single", n_layers=1)
        assert spec.report_sheets == ()
        assert spec.beam_analysis_kind == ""
        assert spec.extra == {}

    def test_canonical_single_spec(self):
        from certus.metal.certus_metal_common import METAL_SINGLE_SPEC
        assert METAL_SINGLE_SPEC.variant == "single"
        assert METAL_SINGLE_SPEC.n_layers == 1
        assert METAL_SINGLE_SPEC.beam_analysis_kind == "gaussian_bands"
        assert "Summary" in METAL_SINGLE_SPEC.report_sheets

    def test_canonical_bilayer_spec(self):
        from certus.metal.certus_metal_common import METAL_BILAYER_SPEC
        assert METAL_BILAYER_SPEC.variant == "bilayer"
        assert METAL_BILAYER_SPEC.n_layers == 2
        assert METAL_BILAYER_SPEC.beam_analysis_kind == "dbscan_multi_valleys"
        assert "Layer Interactions" in METAL_BILAYER_SPEC.report_sheets


# ---------------------------------------------------------------------------
# _collect_config / _apply_config bridge (P5 partial)
# ---------------------------------------------------------------------------


class TestMetalBaseAppConfigBridge:
    """Test the bridge that makes CertusBaseApp's ``_collect_config`` /
    ``_apply_config`` hooks forward to the legacy METAL hooks when
    subclasses have not overridden them.

    We can't instantiate ``MetalBaseApp`` (it's a full QWidget) so we test
    the *method objects* by calling them via ``__func__`` on a ``MagicMock``
    instance. This exercises the bridge logic without Qt.
    """

    def _make_dummy(self, legacy_collect_returns=None, **hooks):
        """Create a dummy object with METAL hooks."""

        from certus.metal.certus_metal_common import MetalBaseApp
        dummy = MagicMock()
        # Bind the bridge methods from MetalBaseApp to the dummy
        dummy._collect_config = MetalBaseApp._collect_config.__get__(dummy)
        dummy._apply_config = MetalBaseApp._apply_config.__get__(dummy)
        # Legacy hooks return what the caller wants
        dummy._get_config_dict = MagicMock(return_value=legacy_collect_returns or {})
        dummy._apply_config_dict = MagicMock()
        # Avoid MagicMock truthiness: _collect_config merges file/optim extras only
        # when these are set on a real app instance.
        dummy.target_data = None
        dummy.final_results = None
        dummy.widgets = {}
        for k, v in hooks.items():
            setattr(dummy, k, v)
        return dummy

    def test_collect_config_delegates_to_legacy(self):
        dummy = self._make_dummy(legacy_collect_returns={"k": 42})
        out = dummy._collect_config()
        dummy._get_config_dict.assert_called_once()
        assert out == {"k": 42}

    def test_apply_config_delegates_to_legacy(self):
        dummy = self._make_dummy()
        # Unified hook requires a minimal physical_params block (same as JSON saves).
        cfg = {"layer_count": 2, "physical_params": {}}
        dummy._apply_config(cfg)
        dummy._apply_config_dict.assert_called_once_with(cfg)


# ---------------------------------------------------------------------------
# reset_app_to_defaults (A7 scaffold)
# ---------------------------------------------------------------------------


class TestResetAppToDefaults:
    def test_is_exported_from_framework(self):
        import certus.utils.certus_reset_framework as certus_reset_framework
        assert "reset_app_to_defaults" in certus_reset_framework.__all__

    def test_confirm_false_bypasses_dialog(self):
        from certus.utils.certus_reset_framework import reset_app_to_defaults
        app = MagicMock()
        app.findChildren = MagicMock(return_value=[])
        # With confirm=False we should reach the reset logic without showing
        # the QMessageBox. Patch the whole reset flow to verify it was called.
        with patch("certus.utils.certus_reset_framework.QMessageBox") as mock_box, \
             patch("certus.utils.certus_reset_framework.gc") as _gc:
            result = reset_app_to_defaults(app, confirm=False)
        assert result is True
        # The confirmation dialog must NOT have been invoked
        mock_box.question.assert_not_called()

    def test_confirm_true_shows_dialog_and_respects_no(self):
        from certus.utils.certus_reset_framework import reset_app_to_defaults
        from PyQt6.QtWidgets import QMessageBox as RealQMessageBox
        app = MagicMock()
        with patch("certus.utils.certus_reset_framework.QMessageBox") as mock_box:
            mock_box.StandardButton = RealQMessageBox.StandardButton
            mock_box.question.return_value = RealQMessageBox.StandardButton.No
            result = reset_app_to_defaults(app, confirm=True)
        assert result is False
        mock_box.question.assert_called_once()
