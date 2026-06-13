"""CERTUS accessibility toolkit (P4).

A focused helper module that raises the accessibility (a11y) baseline of
every CERTUS window by **walking the widget tree** and filling in the
fields that Qt leaves empty by default:

- :func:`apply_accessibility_defaults(root)` assigns a reasonable
  :meth:`QWidget.setAccessibleName` on every input widget that still has
  an empty name (screen reader support) and forces
  ``Qt.FocusPolicy.StrongFocus`` on inputs that expect keyboard focus.
- :func:`compute_tab_order(widgets)` returns a consistent tab chain from
  a list of widgets so apps can call ``setTabOrder`` in a loop.
- :func:`contrast_ratio(hex_fg, hex_bg)` / :func:`passes_wcag_aa(...)` :
  pure-python WCAG 2.1 contrast computation to audit the theme palette.

Design rules
------------

- **Additive**: every helper is a no-op on widgets that already declare
  an accessible name or a tab order.
- **Safe**: a11y walks catch their own exceptions so an ill-formed
  widget cannot break the parent's ``__init__``.
- **Pure-python where possible**: contrast math is testable without Qt.
- **No Qt import at module load**: everything is lazy, keeping test
  collection fast.

Public API
----------

- :func:`apply_accessibility_defaults(root, *, label_map=None)`
- :func:`compute_tab_order(widgets)`
- :func:`contrast_ratio(hex_fg, hex_bg)`
- :func:`passes_wcag_aa(fg, bg, *, large_text=False)`
- :func:`audit_palette(palette)` - small dict-in / report-out helper
"""

from __future__ import annotations

from typing import Any, Final, Iterable, Mapping


# =============================================================================
# Contrast math (pure-python)
# =============================================================================


WCAG_AA_NORMAL: Final[float] = 4.5
WCAG_AA_LARGE: Final[float] = 3.0
WCAG_AAA_NORMAL: Final[float] = 7.0
WCAG_AAA_LARGE: Final[float] = 4.5


def _parse_hex(color: str) -> tuple[int, int, int]:
    """Parse a ``#RRGGBB`` or ``#RGB`` string into ``(r, g, b)`` 0-255."""
    s = str(color).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) not in (6, 8):
        raise ValueError(f"Invalid hex color: {color!r}")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(hex_fg: str, hex_bg: str) -> float:
    """Return the WCAG 2.1 contrast ratio between two hex colors.

    The ratio is in ``[1.0, 21.0]``; higher is better.
    """
    fg = _relative_luminance(_parse_hex(hex_fg))
    bg = _relative_luminance(_parse_hex(hex_bg))
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def passes_wcag_aa(hex_fg: str, hex_bg: str, *, large_text: bool = False) -> bool:
    """Return ``True`` if the pair passes WCAG 2.1 AA (normal or large text)."""
    ratio = contrast_ratio(hex_fg, hex_bg)
    threshold = WCAG_AA_LARGE if large_text else WCAG_AA_NORMAL
    return ratio >= threshold


def audit_palette(palette: Mapping[str, str], *, background_key: str = "surface") -> dict[str, Any]:
    """Compute contrast ratios against ``palette[background_key]``.

    Returns a dict ``{name: {ratio, passes_aa, passes_aa_large}}`` for
    every non-background entry, plus an overall ``worst`` summary.
    """
    if background_key not in palette:
        raise KeyError(f"Background key {background_key!r} not in palette")
    bg = palette[background_key]
    report: dict[str, Any] = {}
    worst_name = None
    worst_ratio = float("inf")
    for name, fg in palette.items():
        if name == background_key:
            continue
        try:
            ratio = contrast_ratio(fg, bg)
        except ValueError:
            continue
        passes = ratio >= WCAG_AA_NORMAL
        report[name] = {
            "ratio": round(ratio, 2),
            "passes_aa": passes,
            "passes_aa_large": ratio >= WCAG_AA_LARGE,
        }
        if ratio < worst_ratio:
            worst_ratio = ratio
            worst_name = name
    report["_summary"] = {
        "background": bg,
        "worst_pair": worst_name,
        "worst_ratio": round(worst_ratio, 2) if worst_name else None,
        "pairs_tested": len(report),
    }
    return report


# =============================================================================
# Widget-tree walker (lazy Qt)
# =============================================================================


# Widget classes that should receive focus + an accessible name if empty.
_INPUT_CLASS_NAMES: Final[tuple[str, ...]] = (
    "QLineEdit",
    "QSpinBox",
    "QDoubleSpinBox",
    "QComboBox",
    "QPushButton",
    "QCheckBox",
    "QRadioButton",
    "QSlider",
    "QTextEdit",
    "QPlainTextEdit",
    "QDateEdit",
    "QTimeEdit",
    "QDateTimeEdit",
)


def _cls_name(widget) -> str:
    try:
        return widget.__class__.__name__
    except AttributeError:
        return ""


def _probable_label_text(widget, *, label_map: Mapping[str, str] | None = None) -> str:
    """Best-effort derivation of an accessible name from sibling labels.

    Tries in order:
    1. Explicit ``label_map[objectName]`` entry.
    2. Widget's own :meth:`objectName` (converted to title-case).
    3. The ``toolTip`` or ``placeholderText`` when meaningful.
    """
    try:
        name = getattr(widget, "objectName", lambda: "")() or ""
    except (AttributeError, TypeError):
        name = ""
    if label_map and name and name in label_map:
        return label_map[name]
    if name:
        # "someSpin" → "Some spin"
        spaced = []
        for i, ch in enumerate(name):
            if i and ch.isupper() and name[i - 1].islower():
                spaced.append(" ")
            spaced.append(ch)
        return "".join(spaced).replace("_", " ").strip().capitalize()
    # Fallbacks
    for getter in ("toolTip", "placeholderText"):
        fn = getattr(widget, getter, None)
        if callable(fn):
            try:
                s = fn()
            except (RuntimeError, TypeError, ValueError):
                s = ""
            if s and len(s) < 120:
                return s
    return _cls_name(widget)


def apply_accessibility_defaults(
    root,
    *,
    label_map: Mapping[str, str] | None = None,
    focus_policy: str = "StrongFocus",
) -> int:
    """Walk ``root`` and fill missing accessibility metadata in place.

    For every input-class widget found:
    - if ``accessibleName()`` is empty, set it from the label map /
      object name / tooltip (see :func:`_probable_label_text`).
    - if ``focusPolicy()`` is ``NoFocus``, force it to
      :attr:`Qt.FocusPolicy.<focus_policy>`.

    Returns the number of widgets touched.
    """
    if root is None:
        return 0
    try:
        from PyQt6.QtCore import Qt
    except ImportError:
        return 0

    fp_target = getattr(Qt.FocusPolicy, focus_policy, Qt.FocusPolicy.StrongFocus)
    touched = 0
    try:
        # Use QWidget as fallback so we walk everything in the tree.
        from PyQt6.QtWidgets import QWidget

        children = root.findChildren(QWidget)
    except (ImportError, AttributeError, RuntimeError, TypeError):
        return 0

    for w in children:
        try:
            if _cls_name(w) not in _INPUT_CLASS_NAMES:
                continue
            # Accessible name
            has_name = False
            try:
                has_name = bool(w.accessibleName())
            except (AttributeError, RuntimeError, TypeError):
                pass
            if not has_name:
                try:
                    w.setAccessibleName(_probable_label_text(w, label_map=label_map))
                    touched += 1
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    pass
            # Focus policy
            try:
                if w.focusPolicy() == Qt.FocusPolicy.NoFocus:
                    w.setFocusPolicy(fp_target)
            except (AttributeError, RuntimeError, TypeError):
                pass
        except (AttributeError, RuntimeError, TypeError):
            continue
    return touched


def compute_tab_order(widgets: Iterable) -> list[tuple]:
    """Return a list of ``(prev, next)`` pairs suitable for ``QMainWindow.setTabOrder`` calls."""
    seq = [w for w in widgets if w is not None]
    return [(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]


def apply_tab_order(parent, widgets: Iterable) -> int:
    """Apply a deterministic tab order across ``widgets``.

    Returns the number of transitions configured. Silently ignores
    missing widgets.
    """
    pairs = compute_tab_order(widgets)
    if parent is None or not pairs:
        return 0
    try:
        from PyQt6.QtWidgets import QWidget  # noqa: F401 - ensures PyQt is importable
    except ImportError:
        return 0
    applied = 0
    for prev, nxt in pairs:
        try:
            parent.setTabOrder(prev, nxt)
            applied += 1
        except (AttributeError, RuntimeError, TypeError):
            pass
    return applied


__all__ = [
    "WCAG_AA_NORMAL",
    "WCAG_AA_LARGE",
    "WCAG_AAA_NORMAL",
    "WCAG_AAA_LARGE",
    "contrast_ratio",
    "passes_wcag_aa",
    "audit_palette",
    "apply_accessibility_defaults",
    "compute_tab_order",
    "apply_tab_order",
]
