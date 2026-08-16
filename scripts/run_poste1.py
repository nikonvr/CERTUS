"""Lance les 4 intervalles restants pour le Poste 1 en mode premium en parallèle."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT = ROOT / "scripts" / "verif_66_vs_68.py"
OUT = ROOT / "reports" / "verif_66_vs_68"

INTERVALLES = [(0, 76), (0, 78), (22, 78), (34, 99)]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["CERTUS_BENCH_TIMEOUT_S"] = "5400"
    env["QT_QPA_PLATFORM"] = "offscreen"

    procs = []
    print(f"=== POSTE 1 : Lancement de {len(INTERVALLES)} intervalles en mode premium ===")
    t0 = time.perf_counter()

    for a, b in INTERVALLES:
        iv_str = f"{a},{b}"
        log_file = OUT / f"run_{a:03d}_{b:03d}_premium.log"
        print(f"  > Démarrage [{a},{b}) -> log: {log_file.name}")
        f_log = open(log_file, "w", encoding="utf-8")
        p = subprocess.Popen(
            [str(PYTHON), str(SCRIPT), "--intervalle", iv_str, "--mode", "premium"],
            cwd=str(ROOT),
            env=env,
            stdout=f_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(((a, b), p, f_log, log_file))

    for (a, b), p, f_log, log_file in procs:
        p.wait()
        f_log.close()
        dur = round(time.perf_counter() - t0, 1)
        print(f"  < Terminé [{a},{b}) (code {p.returncode}) après {dur} s")

    print(f"\nTous les runs du Poste 1 sont terminés en {round(time.perf_counter() - t0, 1)} s.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
