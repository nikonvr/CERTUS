"""48-hour campaign driver for the RICL article (2026-11-05): one stage at a time, read from queue.txt.

queue.txt, one stage per line, re-read before every stage (stages may be added or edited while the driver runs):
    NAME ; MINUTES ; SCRIPT ARGS...        ({minutes} in the arguments is replaced by the granted minutes)
    WAIT ; FILE ; TEXT                     (wait until FILE contains TEXT, at most 4 h)
Lines starting with # are ignored. A stage whose NAME is in queue_done.txt is skipped. Every stage gets
min(MINUTES, time left - 15 min); OPENBLAS/MKL/NUMBA threads = 1 per process (each script runs its own pool).
usage: python orchestrate.py HOURS        outputs: orchestrate.log, queue_done.txt, {NAME}.out
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = HERE / "queue.txt"
DONE = HERE / "queue_done.txt"
LOG = HERE / "orchestrate.log"


def say(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as h:
        h.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def done_names() -> set[str]:
    if not DONE.exists():
        return set()
    return {line.split()[0] for line in DONE.read_text(encoding="utf-8").splitlines() if line.strip()}


def mark(name: str, note: str) -> None:
    with DONE.open("a", encoding="utf-8") as h:
        h.write(f"{name} {time.strftime('%Y-%m-%d %H:%M:%S')} {note}\n")


def next_stage():
    done = done_names()
    for k, line in enumerate(QUEUE.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(";", 2)]
        if len(parts) != 3:
            continue
        name = parts[0] if parts[0] != "WAIT" else f"WAIT@{k}"
        if name not in done:
            return name, parts[1], parts[2]
    return None


def main() -> None:
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 48.0
    deadline = time.time() + 3600.0 * hours
    say(f"driver start, {hours} h, until {time.strftime('%Y-%m-%d %H:%M', time.localtime(deadline))}")
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMBA_NUM_THREADS="1", PYTHONUNBUFFERED="1")
    while time.time() < deadline - 900:
        st = next_stage()
        if st is None:
            time.sleep(120)
            continue
        name, minutes, cmd = st
        if name.startswith("WAIT"):
            path, text = HERE / minutes, cmd
            say(f"{name}: waiting for '{text}' in {path.name}")
            t0 = time.time()
            while time.time() - t0 < 4 * 3600 and time.time() < deadline:
                if path.exists() and text in path.read_text(encoding="utf-8", errors="replace"):
                    break
                time.sleep(60)
            mark(name, "waited")
            say(f"{name}: done waiting")
            continue
        granted = min(float(minutes), (deadline - time.time()) / 60.0 - 15.0)
        if granted < 5:
            # audit 2026-11-07: stop instead of marking every remaining stage 'skipped' (a relaunch must still run them)
            say(f"{name}: less than 5 min left, driver stops here; the stage stays pending")
            break
        args = cmd.replace("{minutes}", f"{granted:.1f}").split()
        say(f"stage {name} start, {granted:.0f} min: {cmd}")
        t0 = time.time()
        with (HERE / f"{name}.out").open("a", encoding="utf-8") as out:
            rc = subprocess.run([sys.executable, *args], cwd=HERE, env=env, stdout=out, stderr=subprocess.STDOUT,
                                check=False).returncode
        mark(name, f"rc={rc} {(time.time() - t0) / 60:.1f} min")
        say(f"stage {name} end rc={rc} after {(time.time() - t0) / 60:.1f} min")
    say("driver end")


if __name__ == "__main__":
    main()
