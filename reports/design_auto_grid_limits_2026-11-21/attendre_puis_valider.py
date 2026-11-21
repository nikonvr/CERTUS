"""Attend la fin de la campagne 24 h (12:30 passées et plus aucun de ses processus), puis valide, une étape après l'autre.

1. `scripts/validate_parallel.py` sans son étape ruff (le dossier non suivi de la campagne la ferait échouer) ;
2. ruff sur l'arbre, ce dossier exclu (accord de 👤 le 2026-11-21) ;
3. `scripts/c1_diff.py HEAD`.

Sortie : `validation.txt` à côté de ce script. Abandon (sans rien lancer) si la campagne tourne encore à `--limite`.

    python reports\\design_auto_grid_limits_2026-11-21\\attendre_puis_valider.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMPAIGN = "RICL_campagne24h_2026-11-20"
SCRIPTS = ("orch.py", "res_needle.py", "cis_res_needle.py", "memetic_fixed.py", "relink.py", "smooth.py", "massclean.py",
           "native_design.py", "adaptive_res.py", "cis_adaptive.py", "curve_compare.py")


def pythons() -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from orient import foreign_pythons

    return [cmd for _pid, cmd in foreign_pythons()]


def campaign_processes() -> list[str]:
    """The campaign's scripts are run from its folder by name (`python.exe orch.py --hours 24`); their pool workers die
    with them."""
    return [cmd for cmd in pythons() if CAMPAIGN in cmd or any(f" {s} " in f" {cmd} " for s in SCRIPTS)
            or " pytest " in f" {cmd} "]  # nor a test run of someone else, which a parallel validation would disturb


def run(out, title: str, command: list[str]) -> int:
    out.write(f"\n=== {title} ({dt.datetime.now():%Y-%m-%d %H:%M}) ===\n$ {' '.join(command)}\n")
    out.flush()
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    text = (done.stdout or "") + (done.stderr or "")
    out.write("\n".join(line for line in text.splitlines()[-60:]) + f"\ncode de sortie : {done.returncode}\n")
    out.flush()
    return done.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debut", default="12:30", help="heure avant laquelle rien n'est lancé")
    parser.add_argument("--limite", default="23:30", help="heure d'abandon si la campagne tourne encore")
    args = parser.parse_args()
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time.fromisoformat(args.debut))
    limit = dt.datetime.combine(today, dt.time.fromisoformat(args.limite))
    with (HERE / "validation.txt").open("w", encoding="utf-8") as out:
        while True:
            now = dt.datetime.now()
            busy = campaign_processes()
            if now >= start and not busy:
                break
            if now >= limit:
                out.write(f"ABANDON {now:%H:%M} : la campagne tourne encore ({len(busy)} processus)\n")
                return 3
            time.sleep(300)
        others = pythons()
        out.write(f"campagne finie, départ {dt.datetime.now():%Y-%m-%d %H:%M} ; autres python : {len(others)}\n")
        out.writelines(f"  {cmd[:160]}\n" for cmd in others)
        code = run(out, "validate_parallel sans ruff", [sys.executable, "scripts/validate_parallel.py", "--only", "docs",
                                                         "oracle", "unit", "ui", "rest", "performance"])
        code |= run(out, "ruff, dossier de la campagne exclu", [sys.executable, "-m", "ruff", "check", ".",
                                                                 "--extend-exclude", f"reports/{CAMPAIGN}"])
        code |= run(out, "c1_diff HEAD", [sys.executable, "scripts/c1_diff.py", "HEAD"])
        out.write(f"\nFIN {dt.datetime.now():%H:%M}, code global {code}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
