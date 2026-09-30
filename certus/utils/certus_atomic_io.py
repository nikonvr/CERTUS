"""Write a file so that it is either the old one or the complete new one, never half of one.

An export that dies in the middle (a full disk, an exception in the writer, the process killed) used to leave a truncated
file at the very path the user had chosen, over the copy that was there. `atomic_open` writes to a sibling temporary file
and moves it over the target only when the `with` block has ended without an error: `os.replace` is atomic on one
volume, on Windows as on POSIX, and the temporary file lives next to the target for that reason.

Nothing here imports the rest of CERTUS, so that any layer can use it.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any

_WRITE_MODES = ("w", "wb")


@contextlib.contextmanager
def atomic_open(
    path: str | os.PathLike[str],
    mode: str = "w",
    *,
    encoding: str | None = "utf-8",
    newline: str | None = None,
) -> Iterator[IO[Any]]:
    """`open(path, mode)` for writing ("w" or "wb"), with the guarantee above.

    On an error inside the block, or when the file cannot be moved over the target, the target is left as it was and the
    temporary file is removed; the error goes on its way. `encoding` and `newline` are those of `open` (ignored in binary).
    """
    if mode not in _WRITE_MODES:
        raise ValueError(f"atomic_open writes whole files: mode must be one of {_WRITE_MODES}, not {mode!r}")
    target = Path(path)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    binary = "b" in mode
    try:
        with open(temporary, mode, encoding=None if binary else encoding, newline=None if binary else newline) as handle:
            yield handle
            handle.flush()
            with contextlib.suppress(OSError):  # a file system without fsync is not a reason to lose the export
                os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise
