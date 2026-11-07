"""Keep Windows from idle-sleeping while the RICL campaign runs (2026-11-05).

SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED): no setting is changed; the request ends when this
process ends. It stops by itself when orchestrate.log reports "driver end", or after HOURS.
usage: python keep_awake.py HOURS     (stop it earlier by ending this python process)
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
LOG = Path(__file__).resolve().parent / "orchestrate.log"


def main() -> None:
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 49.0
    end = time.time() + 3600.0 * hours
    kernel = ctypes.windll.kernel32
    kernel.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        while time.time() < end:
            if LOG.exists() and "driver end" in LOG.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(300)
    finally:
        kernel.SetThreadExecutionState(ES_CONTINUOUS)


if __name__ == "__main__":
    main()
