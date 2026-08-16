"""Orchestrateur automatique de la session 2026-08-16 (Postes 1 à 9)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LOG_DIR = ROOT / "reports" / "logs_orchestrateur"
LOG_DIR.mkdir(parents=True, exist_ok=True)

ENV = dict(os.environ)
ENV["CERTUS_BENCH_TIMEOUT_S"] = "5400"
ENV["QT_QPA_PLATFORM"] = "offscreen"


def run_cmd(cmd: list[str], log_name: str) -> int:
    log_path = LOG_DIR / log_name
    print(f"\n[ORCHESTRATEUR] >> {' '.join(cmd)}")
    print(f"               Log: {log_path.name}")
    t0 = time.perf_counter()
    with open(log_path, "w", encoding="utf-8") as f:
        res = subprocess.run(cmd, cwd=str(ROOT), env=ENV, stdout=f, stderr=subprocess.STDOUT, text=True)
    dur = round(time.perf_counter() - t0, 1)
    print(f"[ORCHESTRATEUR] << Code {res.returncode} en {dur} s")
    return res.returncode


def poste1_bilan() -> None:
    print("\n" + "=" * 78)
    print("BILAN DU POSTE 1 : Les 5 verdicts en mode premium")
    print("=" * 78)
    p_verif = ROOT / "reports" / "verif_66_vs_68"
    for iv in [(0, 66), (0, 76), (0, 78), (22, 78), (34, 99)]:
        a, b = iv
        f = p_verif / f"i_{a:03d}_{b:03d}_premium.json"
        if f.exists():
            r = json.loads(f.read_text(encoding="utf-8"))
            print(f"  [{a:2d},{b:2d}) : verdict {r.get('verdict'):<16s} | {r.get('n_deposables')}/{r.get('n_strats')} deposables | plantage min {r.get('crash_min')}% | SEEL {r.get('seel')}")
        else:
            print(f"  [{a:2d},{b:2d}) : EN ATTENTE")


def poste4_echelle_premium() -> None:
    print("\n" + "=" * 78)
    print("POSTE 4 : Série d'échelle x1.5 en mode premium")
    print("=" * 78)
    run_cmd([str(PYTHON), "scripts/serie_echelle_r75.py", "--facteur", "1.5", "--mode", "premium"], "poste4_x1.5_premium.log")
    run_cmd([str(PYTHON), "scripts/serie_echelle_r75.py", "--etat"], "poste4_etat.log")


def poste5_margin_ab() -> None:
    print("\n" + "=" * 78)
    print("POSTE 5 : A/B test du classement par la marge (use_margin_ranking)")
    print("=" * 78)
    run_cmd([str(PYTHON), "scripts/test_margin_ranking.py", "--composant", "48c", "--mode", "off"], "poste5_48c_off.log")
    run_cmd([str(PYTHON), "scripts/test_margin_ranking.py", "--composant", "48c", "--mode", "on"], "poste5_48c_on.log")
    run_cmd([str(PYTHON), "scripts/test_margin_ranking.py", "--composant", "35c", "--mode", "off"], "poste5_35c_off.log")
    run_cmd([str(PYTHON), "scripts/test_margin_ranking.py", "--composant", "35c", "--mode", "on"], "poste5_35c_on.log")
    run_cmd([str(PYTHON), "scripts/test_margin_ranking.py", "--etat"], "poste5_etat.log")


def poste6_campagne_premium_5shards() -> None:
    print("\n" + "=" * 78)
    print("POSTE 6 : Grande campagne premium (6 shards en parallèle sur 8 cœurs)")
    print("=" * 78)
    t0 = time.perf_counter()
    n_shards = 6
    procs = []
    for i in range(n_shards):
        log_path = ROOT / "reports" / f"premium_shard_{i}.log"
        f = open(log_path, "w", encoding="utf-8")
        cmd = [str(PYTHON), "scripts/campagne_intervalles.py", "--vague", "3", "--hi", "99", "--shard", f"{i}/{n_shards}", "--mode", "premium"]
        print(f"  > Lancement Shard {i}/{n_shards} -> {log_path.name}")
        p = subprocess.Popen(cmd, cwd=str(ROOT), env=ENV, stdout=f, stderr=subprocess.STDOUT)
        procs.append((i, p, f))

    for i, p, f in procs:
        p.wait()
        f.close()
        print(f"  < Shard {i}/{n_shards} terminé avec code {p.returncode}")

    dur_h = round((time.perf_counter() - t0) / 3600.0, 2)
    print(f"\nGrande campagne premium terminée en {dur_h} h.")


def poste7_comparer_fast_premium() -> None:
    print("\n" + "=" * 78)
    print("POSTE 7 : Classement et comparaison fast / premium")
    print("=" * 78)
    run_cmd([str(PYTHON), "scripts/classer_partitions.py", "--mode", "premium", "--hi", "99"], "poste7_classement_premium.log")


def main() -> int:
    print("================================================================================")
    print("DÉMARRAGE DE LA SESSION AUTOMATISÉE COMPLETE (POSTES 1 À 7)")
    print("================================================================================")

    # 1. Bilan Poste 1
    poste1_bilan()

    # 4. Poste 4
    poste4_echelle_premium()

    # 5. Poste 5
    poste5_margin_ab()

    # 6. Poste 6 : Grande campagne premium
    poste6_campagne_premium_5shards()

    # 7. Poste 7 : Reclasser
    poste7_comparer_fast_premium()

    print("\n================================================================================")
    print("SESSION AUTOMATISÉE TERMINÉE AVEC SUCCÈS")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
