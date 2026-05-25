from __future__ import annotations

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
nodeids_file = root / "_pytest_nodeids.txt"

if not nodeids_file.exists():
    raise SystemExit("Missing _pytest_nodeids.txt")

nodeids = [line.strip() for line in nodeids_file.read_text(encoding="utf-8").splitlines() if line.strip()]

for batch_start in range(0, len(nodeids), 100):
    batch = nodeids[batch_start:batch_start + 100]
    print(f"\n=== BATCH {batch_start // 100 + 1} / {((len(nodeids) - 1) // 100) + 1} ===")
    cmd = [sys.executable, "-m", "pytest", "-q", "--cov-fail-under=0", *batch]
    proc = subprocess.run(cmd, cwd=root)
    print(f"=== BATCH EXIT {proc.returncode} ===")
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
