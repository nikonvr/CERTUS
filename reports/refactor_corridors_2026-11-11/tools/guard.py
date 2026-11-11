"""Corridor refactoring: the guard, with every manifest of the finished phases.

    python reports/refactor_corridors_2026-11-11/tools/guard.py [--full]

Takes a snapshot of this tree in a temporary file and compares it with the reference snapshot of Phase 0, with all the
manifests of `manifests/`. Expected last line: `GUARD=OK`. The reference was taken under Python 3.15.2: bytecode belongs
to one Python version, and the guard refuses to compare two.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
GUARD = str(ROOT / "scripts" / "refactor_guard.py")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        new = str(Path(folder) / "snapshot.json")
        taken = subprocess.call([sys.executable, GUARD, "snapshot", "--out", new], cwd=ROOT)
        if taken != 0:
            sys.exit(taken)
        manifests = [arg for path in sorted((HERE / "manifests").glob("phase_*.json")) for arg in ("--manifest", str(path))]
        reference = str(HERE / "reference_snapshot.json")
        sys.exit(subprocess.call([sys.executable, GUARD, "compare", reference, new, *manifests, *sys.argv[1:]], cwd=ROOT))
