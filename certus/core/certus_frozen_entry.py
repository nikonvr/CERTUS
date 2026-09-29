"""Entry point of the frozen CERTUS suite: the hub, or one of its modules.

`certus_hub.spec` freezes the suite into ONE executable, `CERTUS_HUB.exe`. The hub used to start a
module by running `<folder>/CERTUS_DESIGN.exe`, an executable the build never produced: from the
frozen hub, every card ended in "Could not start". In the frozen suite `sys.executable` is that one
executable, so the hub starts a module with

    CERTUS_HUB.exe --run-module CERTUS_DESIGN [file]

and this entry runs the module the way `python CERTUS_DESIGN.py [file]` would: the same
`__main__`, and the same `sys.argv` (the modules read `sys.argv[1]` as the file to open, so the
flag and the name must not stay in it). Without the flag it runs the hub.

Only the modules of the hub catalog can be named: the flag is not a way to run any module.

The script PyInstaller starts is `tools/frozen_entry.py`, which only calls `main` (and why it is
not this file: see its docstring).
"""

from __future__ import annotations

import datetime
import os
import runpy
import sys
import tempfile
import traceback
from pathlib import Path

from certus.core.certus_hub_config import HUB_APP_CATALOG, RUN_MODULE_FLAG

HUB_MODULE = "CERTUS_HUB"

#: Exit code of a command line that names no module of the catalog (the one `argparse` uses).
USAGE_ERROR = 2

#: Where a frozen start-up failure is written, next to the executable (a `.log`, like the others).
STARTUP_LOG = "certus_frozen_startup.log"


def catalog_modules() -> tuple[str, ...]:
    """Names (script stems) of the modules the hub can start, in the order of the catalog."""
    return tuple(Path(str(item["script"])).stem for item in HUB_APP_CATALOG)


def record_startup_failure(name: str) -> Path | None:
    """Append the exception being handled to `STARTUP_LOG`; return the file, or None if none was written.

    A windowed executable has no console: an exception that ended a module at start-up left only
    the bootloader's "Unhandled exception in script" box, without the exception in it. From the
    sources the traceback goes to the terminal, so this is for the frozen build only.
    """
    if not getattr(sys, "frozen", False):
        return None
    text = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {name}\n{traceback.format_exc()}\n"
    for folder in (Path(sys.executable).resolve().parent, Path(tempfile.gettempdir())):
        try:
            with (folder / STARTUP_LOG).open("a", encoding="utf-8") as handle:
                handle.write(text)
            return folder / STARTUP_LOG
        except OSError:
            continue
    return None


def ensure_standard_streams() -> None:
    """Give `sys.stdout` and `sys.stderr` a stream when the executable has no console.

    A windowed executable has none: both are None, and code that reconfigures or writes to them
    raises. `scripts/orchestre_multigraine.py` does at import, so STRAT could not start.
    """
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _run(name: str) -> None:
    ensure_standard_streams()
    try:
        runpy.run_module(name, run_name="__main__", alter_sys=True)
    except Exception:
        record_startup_failure(name)
        raise


def main(argv: list[str] | None = None) -> int:
    """Run the hub, or the module named after `--run-module`; return the exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] != [RUN_MODULE_FLAG]:
        _run(HUB_MODULE)
        return 0

    modules = catalog_modules()
    if len(args) < 2 or args[1] not in modules:
        named = args[1] if len(args) > 1 else "nothing"
        print(f"{RUN_MODULE_FLAG}: {named!r} is not a CERTUS module ({', '.join(modules)})", file=sys.stderr)
        return USAGE_ERROR

    name = args[1]
    sys.argv = [f"{name}.py", *args[2:]]
    _run(name)
    return 0
