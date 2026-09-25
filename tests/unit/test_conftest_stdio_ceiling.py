"""The test process must not run out of C-runtime FILE* streams (Windows).

Measured 2026-09-25 with a probe counting free ``ucrtbase`` FILE* slots after each test: under
the offscreen platform, Qt's FreeType engine keeps font files open as FILE* streams. The first
DESIGN window took 253 of the default 512 slots, and the UI suite filled all 512 before
``test_u8_animations_onboarding_reports``, whose Excel export (lxml writes through ``fopen``)
then failed with ``OSError: [Errno 24] Too many open files``. Run alone, the same file passed.
``tests/conftest.py`` raises the ceiling to the C-runtime maximum.
"""

from __future__ import annotations

import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="the 512-stream default is a Windows C-runtime limit")
def test_c_runtime_stream_ceiling_is_raised() -> None:
    import ctypes

    ceiling = ctypes.cdll.ucrtbase._getmaxstdio()
    assert ceiling >= 2048, (
        f"C-runtime FILE* ceiling is {ceiling}: the offscreen font engine alone can exhaust 512 "
        "slots, and every later fopen (lxml, libxml2) then fails with 'Too many open files'"
    )
