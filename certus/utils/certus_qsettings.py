"""Every QSettings of CERTUS comes from here.

`QSettings(organization, application)` is the Windows registry. When CERTUS_CONFIG_DIR is set
-- the test suite sets it, and its subprocesses inherit it -- the same settings go to INI files
under that directory instead, so that no test run rewrites the user's window layouts, recent
files or fit options. Unset, this returns exactly `QSettings(organization, application)`: the
application does not change (C1).

Under CERTUS_CONFIG_DIR each PROCESS gets its own folder. One shared file made the UI tests
order-dependent: every window a test closed saved its geometry and splitters, and a window
measured later in a worker subprocess restored them (measured 2026-09-27: 10 UI tests failed in
the full suite and passed alone). A worker now starts from a first launch, whatever ran before.
The folder is named by a random token drawn once per process, not by the PID, which Windows
reuses.

`QSettings.setDefaultFormat` and `QSettings.setPath` cannot do this: the (organization,
application) constructor always uses the native format.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtCore import QSettings

_PROCESS_TOKEN = uuid.uuid4().hex


def certus_settings(organization: str, application: str) -> QSettings:
    """The settings of `application`, in the registry -- or under CERTUS_CONFIG_DIR if set."""
    from PyQt6.QtCore import QSettings

    override = os.environ.get("CERTUS_CONFIG_DIR", "").strip()
    if not override:
        return QSettings(organization, application)
    folder = Path(override) / "qsettings" / _PROCESS_TOKEN / organization
    folder.mkdir(parents=True, exist_ok=True)
    return QSettings(str(folder / f"{application}.ini"), QSettings.Format.IniFormat)
