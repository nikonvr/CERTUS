"""Tests for the CERTUS recent-files registry (U5)."""

from __future__ import annotations

from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch, tmp_path):
    """Force the in-memory fallback store for each test (no QSettings pollution)."""
    import certus_recent as m

    monkeypatch.setattr(m, "_qs_settings", lambda: None)
    m._MEMORY_STORE.clear()
    yield
    m._MEMORY_STORE.clear()


# =============================================================================
# Registry semantics
# =============================================================================


def test_record_and_list_simple(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    f = tmp_path / "config.json"
    f.write_text("{}", encoding="utf-8")
    record_recent(RecentCategories.CONFIG, str(f))

    items = list_recent(RecentCategories.CONFIG)
    assert items == [str(f.resolve())]


def test_record_moves_existing_to_top(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    a = tmp_path / "a.json"; a.write_text("{}")
    b = tmp_path / "b.json"; b.write_text("{}")

    record_recent(RecentCategories.CONFIG, str(a))
    record_recent(RecentCategories.CONFIG, str(b))
    record_recent(RecentCategories.CONFIG, str(a))  # re-record a

    items = list_recent(RecentCategories.CONFIG)
    assert items[0] == str(a.resolve())
    assert items[1] == str(b.resolve())
    # No duplicates
    assert len(items) == 2


def test_cap_is_enforced(tmp_path):
    from certus_recent import MAX_RECENTS_PER_CATEGORY, RecentCategories, list_recent, record_recent

    paths = []
    for i in range(MAX_RECENTS_PER_CATEGORY + 5):
        p = tmp_path / f"f{i}.json"
        p.write_text("{}")
        paths.append(p)
        record_recent(RecentCategories.CONFIG, str(p))

    items = list_recent(RecentCategories.CONFIG, limit=100)
    assert len(items) == MAX_RECENTS_PER_CATEGORY
    # The oldest entries must have been evicted; last-recorded is on top.
    assert items[0] == str(paths[-1].resolve())


def test_list_recent_drops_missing_by_default(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    existing = tmp_path / "existing.json"
    existing.write_text("{}")
    ghost = tmp_path / "ghost.json"  # never created

    record_recent(RecentCategories.CONFIG, str(ghost))
    record_recent(RecentCategories.CONFIG, str(existing))

    items = list_recent(RecentCategories.CONFIG)
    assert str(ghost) not in items
    assert str(existing.resolve()) in items

    # Opt-out: keep missing entries
    items_all = list_recent(RecentCategories.CONFIG, drop_missing=False)
    assert any(Path(p).name == "ghost.json" for p in items_all)


def test_forget_and_clear(tmp_path):
    from certus_recent import RecentCategories, clear_recent, forget_recent, list_recent, record_recent

    a = tmp_path / "a.json"; a.write_text("{}")
    b = tmp_path / "b.json"; b.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(a))
    record_recent(RecentCategories.CONFIG, str(b))

    forget_recent(RecentCategories.CONFIG, str(a))
    items = list_recent(RecentCategories.CONFIG)
    assert str(a.resolve()) not in items

    clear_recent(RecentCategories.CONFIG)
    assert list_recent(RecentCategories.CONFIG) == []


def test_categories_are_isolated(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    a = tmp_path / "a.json"; a.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(a))
    assert list_recent(RecentCategories.SPECTRUM) == []
    assert len(list_recent(RecentCategories.CONFIG)) == 1


def test_empty_or_invalid_paths_are_ignored(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    record_recent(RecentCategories.CONFIG, "")
    record_recent(RecentCategories.CONFIG, None)  # type: ignore[arg-type]
    assert list_recent(RecentCategories.CONFIG, drop_missing=False) == []


def test_short_label_truncates_nicely():
    from certus_recent import short_label

    # Short input: returned verbatim (abspath)
    assert short_label("test.json").endswith("test.json")
    # Very long input: shorter than original
    long_path = str(Path(*(["deep"] * 30), "file_with_long_name.json"))
    s = short_label(long_path, max_length=40)
    assert len(s) <= max(40, len("file_with_long_name.json"))
    # Fallback keeps filename
    assert "file_with_long_name.json" in s


def test_same_path_is_case_insensitive_and_normalised(tmp_path):
    from certus_recent import RecentCategories, list_recent, record_recent

    a = tmp_path / "Mixed.json"
    a.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(a))
    # Recording with a different case must dedupe (on Windows at least)
    record_recent(RecentCategories.CONFIG, str(a).upper())
    items = list_recent(RecentCategories.CONFIG, drop_missing=False)
    # Exactly one entry regardless of case on case-insensitive filesystems.
    assert len(items) == 1


# =============================================================================
# CertusBaseApp integration
# =============================================================================


def test_u5_certus_base_app_exposes_recent_hooks():
    from certus_ui import CertusBaseApp

    for attr in ("_record_recent_config", "list_recent_configs", "open_recent_configs"):
        assert hasattr(CertusBaseApp, attr), f"Missing {attr!r}"


def test_u5_record_recent_config_is_called_on_save(tmp_path, monkeypatch):
    """Recording is best-effort; verify direct helper path uses the registry."""
    from certus_recent import RecentCategories, list_recent
    from certus_ui import CertusBaseApp

    class _Stub:
        logger = None

    f = tmp_path / "cfg.json"; f.write_text("{}")
    CertusBaseApp._record_recent_config(_Stub(), str(f))
    items = list_recent(RecentCategories.CONFIG)
    assert str(f.resolve()) in items


def test_u5_list_recent_configs_reads_from_registry(tmp_path):
    from certus_recent import RecentCategories, record_recent
    from certus_ui import CertusBaseApp

    f = tmp_path / "c.json"; f.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(f))

    class _Stub:
        pass

    items = CertusBaseApp.list_recent_configs(_Stub(), limit=3)
    assert items == [str(f.resolve())]


def test_u5_default_commands_surface_recent_when_available(tmp_path):
    """When MRU is non-empty, the "Open recent" entry is added to the palette."""
    from certus_recent import RecentCategories, record_recent
    from certus_ui import CertusBaseApp

    f = tmp_path / "c.json"; f.write_text("{}")
    record_recent(RecentCategories.CONFIG, str(f))

    class _Stub:
        # Expose the bound methods so the introspective _default_commands
        # path can discover them on a non-Qt stub instance.
        list_recent_configs = CertusBaseApp.list_recent_configs
        open_recent_configs = CertusBaseApp.open_recent_configs
        _auto_discovered_commands = CertusBaseApp._auto_discovered_commands

        def load_config(self):
            pass

        def save_config(self):
            pass

    cmds = CertusBaseApp._default_commands(_Stub())
    ids = {c.id for c in cmds}
    assert "file.open_recent" in ids


def test_u5_default_commands_hide_recent_when_empty():
    from certus_ui import CertusBaseApp

    class _Stub:
        list_recent_configs = CertusBaseApp.list_recent_configs
        open_recent_configs = CertusBaseApp.open_recent_configs
        _auto_discovered_commands = CertusBaseApp._auto_discovered_commands

        def load_config(self):
            pass

        def save_config(self):
            pass

    cmds = CertusBaseApp._default_commands(_Stub())
    ids = {c.id for c in cmds}
    assert "file.open_recent" not in ids
