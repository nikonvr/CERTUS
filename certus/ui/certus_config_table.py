"""One declarative table per window for the settings its configuration file saves and loads back.

Each row names the JSON key, the window attribute that holds the widget (a dotted path for a widget inside a panel),
how the value is read and written, and the value saved when the window has no such widget. ``collect_table`` and
``apply_table`` read the same rows, so a setting can no longer be saved without being loaded back, or shown without
being saved: the four defects of that class found by the audit of 2026-11-15 (M-L5b, M-L6d) came from two hand-written
lists that drifted apart.

A key missing from a loaded file, or saved as ``None``, leaves its widget as it is.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# How a widget value is read and written.
#   float, int : a spin box, value() / setValue()
#   bool       : a check box or radio button; ``off_widget`` is checked instead when the value is false
#   text       : a combo box by its displayed text; an unknown text leaves the combo as it is
#   data       : a combo box by its item data; an unknown value leaves the combo as it is
#   index      : a combo box by its position
#   line       : a line edit, text() / setText()
KINDS = ("float", "int", "bool", "text", "data", "index", "line")


@dataclass(frozen=True)
class ConfigField:
    """One saved setting: its JSON key, its widget, how it is read and written, its value without the widget."""

    key: str
    widget: str
    kind: str
    default: Any = None
    off_widget: str | None = None
    applies: Callable[[Mapping[str, Any]], bool] | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind!r} for the configuration key {self.key!r}")


def resolve_widget(owner: object, path: str) -> Any:
    """The widget at ``path`` (``"panel.spin"``) on ``owner``, or ``None`` when one step is missing."""
    obj: Any = owner
    for name in path.split("."):
        obj = getattr(obj, name, None)
        if obj is None:
            return None
    return obj


def read_field(owner: object, field: ConfigField) -> Any:
    """The value of one row as it is saved; the row default when the window has no such widget."""
    w = resolve_widget(owner, field.widget)
    if w is None:
        return field.default
    kind = field.kind
    if kind == "float":
        return float(w.value())
    if kind == "int":
        return int(w.value())
    if kind == "bool":
        return bool(w.isChecked())
    if kind == "text":
        return w.currentText()
    if kind == "data":
        return w.currentData()
    if kind == "index":
        return int(w.currentIndex())
    return w.text()


def write_field(owner: object, field: ConfigField, value: Any) -> bool:
    """Put ``value`` into the widget of one row; ``False`` when there is no widget or the combo has no such item."""
    w = resolve_widget(owner, field.widget)
    if w is None:
        return False
    kind = field.kind
    if kind == "float":
        w.setValue(float(value))
    elif kind == "int":
        w.setValue(int(value))
    elif kind == "bool":
        off = resolve_widget(owner, field.off_widget) if field.off_widget else None
        if value or off is None:
            w.setChecked(bool(value))
        else:
            off.setChecked(True)
    elif kind in ("text", "data"):
        idx = w.findText(str(value)) if kind == "text" else w.findData(value)
        if idx < 0:
            return False
        w.setCurrentIndex(idx)
    elif kind == "index":
        w.setCurrentIndex(int(value))
    else:
        w.setText(str(value))
    return True


def collect_table(owner: object, table: Iterable[ConfigField]) -> dict[str, Any]:
    """The saved values of every row, in the order of the table."""
    return {field.key: read_field(owner, field) for field in table}


def apply_table(owner: object, table: Iterable[ConfigField], config: Mapping[str, Any]) -> None:
    """Load every row present in ``config``, in the order of the table; a missing or ``None`` key changes nothing."""
    for field in table:
        value = config.get(field.key)
        if value is None:
            continue
        if field.applies is not None and not field.applies(config):
            continue
        write_field(owner, field, value)


def table_widgets(table: Iterable[ConfigField]) -> set[str]:
    """The widget paths a table saves, radio partners included."""
    out: set[str] = set()
    for field in table:
        out.add(field.widget)
        if field.off_widget:
            out.add(field.off_widget)
    return out
