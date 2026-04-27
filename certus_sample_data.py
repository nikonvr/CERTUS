"""CERTUS sample-data registry (U9 helper).

Bundles the paths to ready-to-use demo inputs (config files, spectra,
substrates) shipped with the distribution, so empty-state widgets can
offer a one-click "Load sample data" shortcut without the user having
to find their own file.

Design
------

- **Read-only**: samples are discovered by scanning a well-known folder
  (``samples/`` at the repo root). Missing folder is *not* an error; the
  registry just reports an empty list.
- **Grouped by category**: :class:`SampleCategory` constants mirror
  :class:`certus_recent.RecentCategories` when possible.
- **Pure-python**: no Qt dependency; callers wire the paths into their
  own UI.
- **Deterministic order**: ``list_samples(category)`` returns alpha-
  sorted entries for reproducibility.

Public API
----------

- :class:`SampleCategory` - canonical names.
- :class:`SampleEntry` - frozen descriptor.
- :func:`list_samples(category, *, root=None)` -> list[SampleEntry]
- :func:`sample_path(category, name)` -> absolute path or None
- :func:`default_sample(category)` -> first entry of a category
- :func:`set_sample_root(path)` - override the discovery root (tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final


class SampleCategory:
    CONFIG: Final[str] = "config"
    SPECTRUM: Final[str] = "spectrum"
    SUBSTRATE: Final[str] = "substrate"
    PROFILE: Final[str] = "profile"
    PROJECT: Final[str] = "project"


@dataclass(frozen=True)
class SampleEntry:
    """A single sample file bundled with the distribution."""

    category: str
    name: str
    path: str
    description: str = ""

    @property
    def exists(self) -> bool:
        try:
            return Path(self.path).exists()
        except (TypeError, ValueError, OSError):
            return False


# =============================================================================
# Discovery
# =============================================================================


_CATEGORY_GLOBS: Final[dict[str, tuple[str, ...]]] = {
    SampleCategory.CONFIG: ("*.json",),
    SampleCategory.SPECTRUM: ("*.csv", "*.txt"),
    SampleCategory.SUBSTRATE: ("*.csv",),
    SampleCategory.PROFILE: ("*.json", "*.csv"),
    SampleCategory.PROJECT: ("*.json", "*.zip"),
}


_ROOT_OVERRIDE: str | None = None


def set_sample_root(path: str | None) -> None:
    """Override the sample-discovery root (primarily for tests)."""
    global _ROOT_OVERRIDE
    _ROOT_OVERRIDE = str(path) if path else None


def _default_root() -> str:
    """Return the default samples folder (repo root / 'samples')."""
    here = Path(__file__).resolve().parent
    return str(here / "samples")


def _resolve_root(explicit: str | None) -> str:
    if explicit:
        return str(explicit)
    if _ROOT_OVERRIDE:
        return _ROOT_OVERRIDE
    return _default_root()


def list_samples(category: str, *, root: str | None = None) -> list[SampleEntry]:
    """Return all sample files for ``category`` found under ``root``.

    Returns an empty list if the root or the category folder does not
    exist, making this function safe to call at startup without setup.
    """
    base = Path(_resolve_root(root))
    folder = base / category
    if not folder.is_dir():
        return []

    patterns = _CATEGORY_GLOBS.get(category, ("*",))
    # Primary samples keyed by stem; .txt that is a sidecar for an existing
    # primary sample is suppressed from the listing.
    primary: dict[str, SampleEntry] = {}
    sidecar_stems: set[str] = set()
    order: list[str] = []
    for pat in patterns:
        for p in sorted(folder.glob(pat), key=lambda q: q.name.lower()):
            stem = p.stem
            if p.suffix.lower() == ".txt":
                # Sidecars are silently skipped when a non-txt file with
                # the same stem already exists in the folder.
                siblings = [q for q in folder.glob(stem + ".*") if q.suffix.lower() != ".txt"]
                if siblings:
                    sidecar_stems.add(stem)
                    continue
            if stem in primary:
                continue
            primary[stem] = SampleEntry(
                category=category,
                name=stem,
                path=str(p),
                description=_read_description(p),
            )
            order.append(stem)
    return [primary[s] for s in order if s in primary]


def sample_path(category: str, name: str, *, root: str | None = None) -> str | None:
    """Return the absolute path for a specific sample, or ``None``."""
    for entry in list_samples(category, root=root):
        if entry.name == name:
            return entry.path
    return None


def default_sample(category: str, *, root: str | None = None) -> SampleEntry | None:
    """Return the first sample found for ``category``."""
    items = list_samples(category, root=root)
    return items[0] if items else None


def has_any_samples(*, root: str | None = None) -> bool:
    for cat in (
        SampleCategory.CONFIG,
        SampleCategory.SPECTRUM,
        SampleCategory.SUBSTRATE,
        SampleCategory.PROFILE,
        SampleCategory.PROJECT,
    ):
        if list_samples(cat, root=root):
            return True
    return False


def _read_description(path: Path) -> str:
    """Look for a co-located ``<name>.txt`` as human description."""
    try:
        desc_path = path.with_suffix(".txt")
        if desc_path.is_file():
            with open(desc_path, "r", encoding="utf-8") as f:
                return f.read().strip().splitlines()[0] if f else ""
    except (OSError, UnicodeDecodeError, ValueError):
        pass
    return ""


__all__ = [
    "SampleCategory",
    "SampleEntry",
    "list_samples",
    "sample_path",
    "default_sample",
    "has_any_samples",
    "set_sample_root",
]
