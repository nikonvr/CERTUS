"""`open_file_explorer` reports the error of the OS, not a NameError.

`import subprocess` sat inside three branches of the function, while the `except (OSError, subprocess.SubprocessError)`
of the folder branch (`os.startfile`) names it before any of them has run. When `os.startfile` failed, Python raised
UnboundLocalError instead of logging the OSError and raising it again, as the other branches do.
"""

from __future__ import annotations

import logging
import os
import sys

import pytest

from certus.ui.certus_io_ui import open_file_explorer


@pytest.mark.unit
def test_a_failing_startfile_is_logged_and_raised_as_the_os_error(tmp_path, monkeypatch, caplog) -> None:
    def refuse(_path: str) -> None:
        raise OSError("no application is associated with this folder")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", refuse, raising=False)

    with caplog.at_level(logging.ERROR), pytest.raises(OSError, match="no application"):
        open_file_explorer(str(tmp_path))

    assert "Failed to open Windows explorer" in caplog.text
