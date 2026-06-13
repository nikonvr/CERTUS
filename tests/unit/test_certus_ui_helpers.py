"""Unit tests for the small CERTUS-UI helpers introduced in the
factorisation roadmap (Session 3): ``StatsCounter`` and ``confirm_and_stop``.

These helpers are designed to be importable without instantiating a Qt
application, so the tests run on any environment.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from certus.ui.certus_ui import StatsCounter, confirm_and_stop, format_count_kmg


# ---------------------------------------------------------------------------
# StatsCounter (P7)
# ---------------------------------------------------------------------------


class TestStatsCounter:
    def test_construction_default(self):
        c = StatsCounter()
        assert len(c) == 0
        assert c.as_dict() == {}

    def test_construction_with_initial(self):
        c = StatsCounter({"EVAL": 0, "BEST": 0, "MINIMA": 0})
        assert set(c) == {"EVAL", "BEST", "MINIMA"}
        assert all(c[k] == 0 for k in c)

    def test_inc_creates_missing_key(self):
        c = StatsCounter()
        assert c.inc("X") == 1
        assert c.inc("X", 4) == 5
        assert c["X"] == 5

    def test_set_overrides(self):
        c = StatsCounter({"A": 10})
        assert c.set("A", 3) == 3
        assert c["A"] == 3

    def test_reset_all(self):
        c = StatsCounter({"A": 1, "B": 2})
        c.reset()
        assert c.as_dict() == {"A": 0, "B": 0}

    def test_reset_subset(self):
        c = StatsCounter({"A": 1, "B": 2, "C": 3})
        c.reset("A", "C", "missing")
        assert c.as_dict() == {"A": 0, "B": 2, "C": 0}

    def test_get_default(self):
        c = StatsCounter()
        assert c.get("missing", 7) == 7

    def test_formatted_uses_kmg(self):
        c = StatsCounter({"X": 1500})
        assert c.formatted("X") == format_count_kmg(1500)
        assert c.formatted("X") == "1.5K"

    def test_setitem_getitem(self):
        c = StatsCounter()
        c["A"] = 42
        assert c["A"] == 42

    def test_contains(self):
        c = StatsCounter({"A": 0})
        assert "A" in c
        assert "B" not in c

    def test_iteration(self):
        c = StatsCounter({"A": 1, "B": 2})
        assert sorted(list(c)) == ["A", "B"]

    def test_repr(self):
        c = StatsCounter({"A": 1})
        assert "StatsCounter" in repr(c)
        assert "'A'" in repr(c)


# ---------------------------------------------------------------------------
# confirm_and_stop (P2)
# ---------------------------------------------------------------------------


class TestConfirmAndStop:
    def test_returns_false_when_user_cancels(self):
        with patch("certus.ui.certus_ui_utils.confirm_stop_with_timeout", return_value=False) as mock_dlg, \
             patch("certus.ui.certus_ui_utils.stop_worker_and_thread") as mock_stop:
            result = confirm_and_stop(parent=None, worker=object(), thread=object())
        assert result is False
        mock_dlg.assert_called_once()
        mock_stop.assert_not_called()

    def test_returns_true_when_confirmed_and_thread_stopped(self):
        with patch("certus.ui.certus_ui_utils.confirm_stop_with_timeout", return_value=True) as mock_dlg, \
             patch("certus.ui.certus_ui_utils.stop_worker_and_thread", return_value=True) as mock_stop:
            result = confirm_and_stop(
                parent=None, worker=object(), thread=object(),
                timeout_sec=5, timeout_ms=1500, label="MyWorker",
            )
        assert result is True
        mock_dlg.assert_called_once_with(None, timeout_sec=5)
        # Verify stop_worker_and_thread is forwarded the label/timeout/logger
        _, kwargs = mock_stop.call_args
        assert kwargs["timeout_ms"] == 1500
        assert kwargs["label"] == "MyWorker"

    def test_returns_false_when_thread_does_not_stop(self):
        with patch("certus.ui.certus_ui_utils.confirm_stop_with_timeout", return_value=True), \
             patch("certus.ui.certus_ui_utils.stop_worker_and_thread", return_value=False):
            result = confirm_and_stop(parent=None, worker=None, thread=None)
        assert result is False

    def test_handles_none_worker_and_thread(self):
        with patch("certus.ui.certus_ui_utils.confirm_stop_with_timeout", return_value=True), \
             patch("certus.ui.certus_ui_utils.stop_worker_and_thread", return_value=True) as mock_stop:
            result = confirm_and_stop(parent=None, worker=None, thread=None)
        assert result is True
        args, _ = mock_stop.call_args
        assert args[0] is None
        assert args[1] is None


# ---------------------------------------------------------------------------
# Public API exposure
# ---------------------------------------------------------------------------


def test_helpers_are_in_certus_ui_all():
    import certus.ui.certus_ui as certus_ui
    assert "StatsCounter" in certus_ui.__all__
    assert "confirm_and_stop" in certus_ui.__all__
