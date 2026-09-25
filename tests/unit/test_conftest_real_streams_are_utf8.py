"""The encoding guard of ``tests/conftest.py`` must cover the REAL streams, not only pytest's.

``numba.core.errors.ColorShell`` calls ``colorama.init()``, which wraps whatever ``sys.stdout``
is at that moment. On a cold numba cache this happens while pytest's capture is suspended,
i.e. while ``sys.stdout`` is the real stream -- cp1252 on Windows when the output is
redirected to a file or a pipe. A later print of a non-Latin-1 character then raises
``UnicodeEncodeError`` and fails a test whose assertions all passed.

Measured 2026-09-25: ``test_gradient_vs_fd.py::test_design_gradient`` failed that way on the
first, cold-cache pass (547 s), while printing the success mark of a gradient check that had
passed; it passes in isolation. A pytest plugin logging ``sys.stdout`` around every test saw a
colorama wrapper around the cp1252 stream at the start of a test only when the numba cache
was cold. Reconfiguring ``sys.__stdout__`` / ``sys.__stderr__`` closes the window whatever
wraps them later.
"""

from __future__ import annotations

import sys

import pytest


@pytest.mark.parametrize("name", ["__stdout__", "__stderr__"])
def test_real_stream_is_utf8(name: str) -> None:
    stream = getattr(sys, name)
    if stream is None or not hasattr(stream, "reconfigure"):
        pytest.skip(f"sys.{name} is absent or cannot be reconfigured")
    encoding = (stream.encoding or "").lower().replace("-", "").replace("_", "")
    assert encoding == "utf8", (
        f"sys.{name} is encoded in {stream.encoding!r}: a colorama wrapper installed by numba "
        "on a cold cache would make any non-Latin-1 print fail a passing test"
    )
