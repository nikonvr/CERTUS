"""Ou en sont les batchs, et est-ce que ca progresse ou est-ce qu'on tape dans le vide ?

    .venv\\Scripts\\python.exe scripts\\avancement.py

👤 2026-08-15 : *« je veux juste pouvoir interroger l'avancement et les resultats partiels
pour sentir si cela progresse ou si on tape dans le vide »*.

Ce script ne mesure rien. Il lit ce qui est deja ecrit et repond a trois questions :
ou en est-on, qu'a-t-on trouve, et est-ce que ca va quelque part.

🔴 IL DIT AUSSI QUAND IL NE FAUT PAS LIRE LES CHIFFRES. Sur un composant dont toutes les
strategies plantent, le solveur rend quand meme un score -- la pire RMSE finie de la moins
mauvaise des eliminees. Comparer deux positions de changement de temoin sur des scores de
repli, c'est comparer deux facons d'echouer. Le verdict FALLBACK est donc affiche avant le
SEEL, et pas apres.
"""

from __future__ import annotations


import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "reports" / "testglass_sweep_99c.tsv"


def rows() -> list[dict]:
    if not TSV.exists():
        return []
    lines = [line.rstrip("\n").split("\t") for line in open(TSV, encoding="utf-8")]
    if len(lines) < 2:
        return []
    head = lines[0]
    return [dict(zip(head, r)) for r in lines[1:] if len(r) == len(head)]


def running() -> list[str]:
    """Les solveurs en vie, et le CPU qu'ils ont consomme."""
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,UserModeTime"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    live = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 2 and p[0].isdigit() and p[1].isdigit() and int(p[0]) > 0:
            cpu_s = int(p[0]) / 1e7 if int(p[0]) > int(p[1]) else int(p[1]) / 1e7
            if cpu_s > 30:
                live.append(f"PID {p[1] if int(p[0]) > int(p[1]) else p[0]} -- {cpu_s / 60:.0f} min de CPU")
    return live


def main() -> int:
    rs = rows()
    print("=" * 78)
    print("AVANCEMENT DU CHANGEMENT DE VERRE TEMOIN")
    print("=" * 78)

    live = running()
    print(f"\nsolveur(s) en cours : {', '.join(live) if live else 'aucun'}")
    print(f"batchs ecrits       : {len(rs)}")

    if not rs:
        print("\nRien encore. Le premier batch ecrit sa ligne des qu'il finit.")
        return 0

    # Le 99 couches uniquement : c'est le seul ou le changement de temoin est en jeu.
    c99 = [r for r in rs if r.get("n_strats") and int(r.get("n_blocks", 0) or 0) >= 0
           and json.loads(r["config"]).get("robustness_num_runs")
           and float(r.get("rmse_p95") or 0) > 0.1]
    base = next((r for r in c99 if r["tag"] == "nocut"), None)

    print("\n" + "-" * 78)
    print("%-12s %-9s %-20s %-6s %-6s %-8s %s" %
          ("changement", "verdict", "RMSE", "SEEL", "blocs", "plantage", "vs reference"))
    print("-" * 78)
    for r in sorted(c99, key=lambda x: (x["tag"] != "nocut", x["tag"])):
        delta = ""
        if base and r is not base:
            try:
                d = (float(r["rmse_p95"]) - float(base["rmse_p95"])) / float(base["rmse_p95"]) * 100
                delta = f"{d:+.2f} %"
            except (ValueError, ZeroDivisionError):
                delta = "?"
        print("%-12s %-9s %-20s %-6s %-6s %-8s %s" %
              (r["tag"], r["verdict"], r["rmse_p95"][:18], r["seel_nm"],
               r["n_blocks"], r["crash_pct"] + " %", delta))

    # 🔴 La lecture, et elle prime sur les chiffres ci-dessus.
    print("\n" + "=" * 78)
    fallback = [r for r in c99 if r["verdict"] == "FALLBACK"]
    if len(fallback) == len(c99) and c99:
        print("🔴 TOUTES LES LIGNES SONT DES SCORES DE REPLI (plantage >= 5 %).")
        print()
        print("   Aucune strategie ne survit, sur aucune position. Les RMSE ci-dessus")
        print("   classent des facons d'echouer, pas des qualites de fabrication :")
        print("   les comparer entre elles n'apprend RIEN sur le SEEL.")
        print()
        print("   Ce qu'il faut regarder a la place, tant que c'est le cas :")
        print("     - le taux de plantage BAISSE-t-il ? c'est la seule progression reelle")
        print("     - la cible est < 5 %. Sous ce seuil, et seulement la, le SEEL compte")
        best = min(c99, key=lambda r: float(r["crash_pct"] or 100))
        print(f"\n   meilleur plantage atteint : {best['crash_pct']} % ({best['tag']})")
        if float(best["crash_pct"] or 100) >= 100:
            print("   ⚠️ toujours a 100 % : le changement de temoin, seul, ne suffit pas")
            print("      -> voir P0 de CLAUDE.md 25.7 : passer par la marge ou la continuation")
    elif fallback:
        print(f"⚠️ {len(fallback)} ligne(s) sur {len(c99)} sont des scores de repli : ne les")
        print("   compare pas aux lignes OK, elles ne mesurent pas la meme chose.")
    else:
        print("✅ Aucune ligne en repli : les SEEL sont comparables entre eux.")
        if base:
            better = [r for r in c99 if r is not base
                      and float(r["rmse_p95"]) < float(base["rmse_p95"])]
            print(f"   {len(better)} position(s) font mieux que la reference sans changement.")
            print("   ⚠️ Un changement est un degre de liberte gratuit : rejoue le gagnant")
            print("      sur une AUTRE GRAINE avant d'y croire.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
