"""Shared launcher for the UX tests that measure a window in a subprocess.

Eight test modules spawn a dedicated process that builds a full Qt window and
prints a single marker line (rule 0.14: ``QApplication`` state is a process
global, so one process per window).

Such a process can also die **natively** -- Qt aborting mid-paint kills it
without unwinding Python, so nothing ever reaches stderr. Reading only stdout,
as these modules used to, turns that abort into ``assert []`` with an empty
stderr: a transient infrastructure fault then looks exactly like a UX
regression, and none of the eight call sites ever looked at ``returncode``.

Measured over five full passes: three runs failed that way, on three different
tests, each passing in isolation. ``0 failed`` is the only criterion this
project relies on, so a criterion that flips at random is the first thing to
repair.

This module makes the two cases distinguishable:

- a marker line is the only accepted result;
- a run that yields none is retried once, because the abort is transient, and
  the retry is reported as a warning -- never silently;
- if it happens twice, the failure names the exit status, so a reader can tell
  a native abort (a large unsigned Windows status, or a negative POSIX signal)
  from a worker that ran to completion and stayed silent.

The retry cannot hide a real defect: a worker that aborts every time still
fails, and says so with its exit status.
"""

from __future__ import annotations

import json
import subprocess
import warnings


def describe_exit_status(code: int | None) -> str:
    """Return a readable diagnosis of a subprocess exit status."""
    if code is None:
        return "no exit status"
    if code == 0:
        return "exit status 0"
    if code < 0:
        return f"killed by signal {-code}"
    unsigned = code & 0xFFFFFFFF
    if unsigned >= 0x80000000:
        # Windows surfaces a structured exception (access violation, abort...)
        # as a large unsigned status. Python never ran an except clause here.
        return f"native abort, exit status {unsigned:#010x}"
    return f"exit status {code}"


def run_ux_worker(
    cmd: list[str],
    marker: str,
    *,
    context: str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    attempts: int = 2,
) -> dict:
    """Run ``cmd`` and return the payload carried by its marker line.

    ``context`` names what is being measured; it only appears in the failure
    message. Raises :class:`AssertionError` when no attempt produced a marker.
    """
    proc = None
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        for line in (proc.stdout or "").splitlines():
            if line.startswith(marker):
                if attempt > 1:
                    warnings.warn(
                        f"{context}: worker produced no result on attempt "
                        f"{attempt - 1} ({describe_exit_status(proc.returncode)}), "
                        f"succeeded on attempt {attempt}",
                        stacklevel=2,
                    )
                return json.loads(line[len(marker) :])

    stderr = (proc.stderr or "").strip() if proc is not None else ""
    if not stderr:
        stderr = "<stderr empty: the process died without unwinding Python>"
    status = describe_exit_status(proc.returncode if proc is not None else None)
    raise AssertionError(f"{context}: worker produced no result in {attempts} attempts ({status}).\n{stderr}")
