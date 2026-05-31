"""CERTUS recent-files registry (U5).

Lightweight, process-wide registry that keeps track of the most recently
used files (configs, spectra, substrates, ...) per *category*, backed by
``QSettings`` under ``CERTUS/recent`` so it persists across sessions.

Design notes
------------

- **Pure-data**: the module builds no widget. It exposes
  :class:`RecentFilesRegistry` plus module-level wrappers, all usable
  without a running QApplication (falls back to an in-memory store).
- **Cap-per-category**: each category stores at most
  :data:`MAX_RECENTS_PER_CATEGORY` entries (default 12) — oldest entries
  are evicted on overflow.
- **Normalisation**: paths are normalised to absolute + case-preserving
  form. Re-recording an already-known path moves it to the top (MRU).
- **Stale entries**: :meth:`list_recent` filters out paths that no longer
  exist on disk by default (opt-out via ``drop_missing=False``).
- **Integration**: :class:`CertusBaseApp` calls
  :func:`record_recent("file.config", path)` automatically on every
  successful save/load that routes through its base implementation.

Categories
----------

Use ``RecentCategories.*`` constants to avoid typos. Custom strings are
also accepted (the registry is schema-less).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final


# =============================================================================
# Constants
# =============================================================================


MAX_RECENTS_PER_CATEGORY: Final[int] = 12
_QS_ORG: Final[str] = "CERTUS"
_QS_APP: Final[str] = "recent"


class RecentCategories:
    """Canonical category names."""

    CONFIG: Final[str] = "file.config"
    SPECTRUM: Final[str] = "file.spectrum"
    SUBSTRATE: Final[str] = "file.substrate"
    PROFILE: Final[str] = "file.profile"
    PROJECT: Final[str] = "file.project"


# =============================================================================
# Fallback in-memory store (used when QSettings is unavailable)
# =============================================================================


_MEMORY_STORE: dict[str, list[str]] = {}


def _normalize(path: str) -> str:
    """Return ``abspath`` with normalised separators."""
    if not path:
        return ""
    try:
        return str(Path(str(path)).expanduser().resolve(strict=False))
    except (TypeError, ValueError):
        return str(path)


def _qs_settings():
    """Return a ``QSettings`` instance, or ``None`` if Qt is unavailable."""
    try:
        from PyQt6.QtCore import QSettings  # type: ignore

        return QSettings(_QS_ORG, _QS_APP)
    except ImportError:
        return None


# =============================================================================
# Registry
# =============================================================================


class RecentFilesRegistry:
    """Cached proxy over the QSettings-backed store.

    Holds no state of its own — every call reads/writes the backend so
    concurrent processes stay in sync.
    """

    def __init__(self, cap: int = MAX_RECENTS_PER_CATEGORY) -> None:
        self.cap = int(cap)

    def _backend(self):
        return _qs_settings()

    def _sync(self, qs) -> None:
        try:
            qs.sync()
        except Exception:
            pass

    # -- Read -------------------------------------------------------------
    def list_recent(self, category: str, *, limit: int | None = None, drop_missing: bool = True) -> list[str]:
        """Return MRU-sorted paths for ``category``.

        Parameters
        ----------
        limit:
            Max entries to return (``None`` → up to :attr:`cap`).
        drop_missing:
            Filter out paths that do not exist on disk anymore.
        """
        items = self._read(category)
        if drop_missing:
            items = [p for p in items if Path(p).exists()]
        lim = self.cap if limit is None else max(0, int(limit))
        return items[:lim]

    # -- Write ------------------------------------------------------------
    def record(self, category: str, path: str) -> None:
        """Move/insert ``path`` at the top of ``category`` MRU list."""
        p = _normalize(path)
        if not p:
            return
        items = [x for x in self._read(category) if not _same_path(x, p)]
        items.insert(0, p)
        if len(items) > self.cap:
            items = items[: self.cap]
        self._write(category, items)

    def forget(self, category: str, path: str) -> None:
        """Remove ``path`` from ``category`` (no-op if absent)."""
        p = _normalize(path)
        items = self._read(category)
        new = [x for x in items if not _same_path(x, p)]
        if len(new) != len(items):
            self._write(category, new)

    def clear(self, category: str | None = None) -> None:
        """Clear one category or all if ``category`` is ``None``."""
        qs = self._backend()
        if qs is None:
            if category is None:
                _MEMORY_STORE.clear()
            else:
                _MEMORY_STORE.pop(category, None)
            return
        if category is None:
            qs.clear()
        else:
            qs.remove(_qs_key(category))
        self._sync(qs)

    # -- Internals --------------------------------------------------------
    def _read(self, category: str) -> list[str]:
        qs = self._backend()
        if qs is None:
            return list(_MEMORY_STORE.get(category, []))
        raw = qs.value(_qs_key(category))
        if raw is None:
            return []
        if isinstance(raw, str):
            items = [raw]
        else:
            try:
                items = list(raw)
            except TypeError:
                items = []
        return [str(x) for x in items if x]

    def _write(self, category: str, items: list[str]) -> None:
        qs = self._backend()
        if qs is None:
            _MEMORY_STORE[category] = list(items)
            return
        qs.setValue(_qs_key(category), list(items))
        self._sync(qs)


def _qs_key(category: str) -> str:
    return f"recent/{category}"


def _same_path(a: str, b: str) -> bool:
    if not a or not b:
        return False
    try:
        return Path(_normalize(a)) == Path(_normalize(b))
    except (TypeError, ValueError):
        return a == b


# =============================================================================
# Module-level convenience wrappers
# =============================================================================


_default_registry = RecentFilesRegistry()


def record_recent(category: str, path: str) -> None:
    """Add ``path`` to the MRU list for ``category``."""
    _default_registry.record(category, path)


def list_recent(category: str, limit: int | None = None, *, drop_missing: bool = True) -> list[str]:
    """Return MRU paths for ``category`` (default filters missing files)."""
    return _default_registry.list_recent(category, limit=limit, drop_missing=drop_missing)


def forget_recent(category: str, path: str) -> None:
    """Remove ``path`` from ``category``."""
    _default_registry.forget(category, path)


def clear_recent(category: str | None = None) -> None:
    """Clear one category or all if ``category`` is ``None``."""
    _default_registry.clear(category)


def short_label(path: str, max_length: int = 60) -> str:
    """Return a compact, human-friendly label for ``path``.

    Example: ``"…/2404/configs/my_long_filename.json"``.
    """
    if not path:
        return ""
    p = _normalize(path)
    if len(p) <= max_length:
        return p
    path_obj = Path(p)
    name = path_obj.name
    parent = path_obj.parent.name
    compact = str(Path("…") / parent / name) if parent else str(Path("…") / name)
    if len(compact) <= max_length:
        return compact
    # Last resort: keep only the filename
    return name


__all__ = [
    "MAX_RECENTS_PER_CATEGORY",
    "RecentCategories",
    "RecentFilesRegistry",
    "record_recent",
    "list_recent",
    "forget_recent",
    "clear_recent",
    "short_label",
]
