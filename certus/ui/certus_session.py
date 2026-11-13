"""The session of a window, kept on disk so that a power cut loses nothing (U12 A, decision Q40 of the corridor plan).

A window that changed its configuration writes it here every minute; a close that goes to its end erases it. A session
file found at the opening is therefore the trace of a window that did not close: the window offers to resume it. No
computation is saved or resumed here (that is U12 B): only what the window's own `_collect_config` returns, the same
dictionary its "Save" writes, given back to its own `_apply_config`.

Where: under CERTUS_CONFIG_DIR when it is set (the test suite sets it), else in the user's application data, never in
a working folder nor next to the application (its folder is a public repository).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from certus.utils.certus_atomic_io import atomic_open

SESSION_FORMAT = 1


def sessions_dir() -> Path:
    override = os.environ.get("CERTUS_CONFIG_DIR", "").strip()
    if override:
        return Path(override) / "sessions"
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "CERTUS" / "sessions"


def session_path(app_name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(app_name)) or "CERTUS"
    return sessions_dir() / f"{safe}.json"


def write_session(app_name: str, config: dict[str, Any]) -> Path:
    """Write the session of `app_name` atomically: a cut during the write leaves the previous one whole."""
    path = session_path(app_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"format": SESSION_FORMAT, "app": str(app_name), "saved_at": datetime.now().isoformat(timespec="seconds"), "config": config}
    with atomic_open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=1, default=str)
    return path


def read_session(app_name: str) -> dict[str, Any] | None:
    """The session left by `app_name`, or None when there is none or it cannot be trusted (another format, another
    window, not a dictionary). A session that cannot be read is never half applied."""
    path = session_path(app_name)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(record, dict)
        or record.get("format") != SESSION_FORMAT
        or record.get("app") != str(app_name)
        or not isinstance(record.get("config"), dict)
    ):
        return None
    return record


def clear_session(app_name: str) -> None:
    try:
        session_path(app_name).unlink()
    except FileNotFoundError:
        pass
