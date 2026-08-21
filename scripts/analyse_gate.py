"""Read the GATE campaign artefacts and lay out the four questions it was built to answer.

    .venv\\Scripts\\python.exe scripts\\analyse_gate.py

Takes no argument, runs nothing, writes nothing. It reads `reports/probe_anchor_*.json`,
selects the runs by their RECORDED configuration -- never by their file name -- and prints
one block per question.

🔴 IT PRINTS NUMBERS AND THE TEST THAT GOES WITH EACH. It does not conclude: the four
verdicts below are mechanical comparisons, and every one of them has a reading that a
human must supply. In particular a `RESULT` gap under ~6 % means "indistinguishable at
this depth", never "equal" and never "better".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

#: 5 %, the physicist's "95 % of depositions complete". Quoted, never recomputed.
TOLERANCE = 0.05
#: 📏 The RESULT of the N=300, n_screen=10 run made on code carrying correctif 1 but
#: NOT correctif 2. G0 replays that configuration exactly, so C1 is an EQUALITY test.
C1_REFERENCE = "0.006151532415266679"

#: Monte-Carlo dispersion of a score at the working depth, from the 2026-08-11 campaign.
#: Two scores differing by less than sigma*sqrt(2) are indistinguishable.
INDISTINGUISHABLE_PCT = 8.5


def _load() -> list[dict]:
    out = []
    for p in sorted(REPORTS.glob("probe_anchor_noise_pipeline_*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(r, dict) or "config" not in r or "ranking" not in r:
            continue
        r["_path"] = p.name
        r["_bandpass"] = "bandpass" in p.name
        out.append(r)
    return out


def _pick(runs: list[dict], **want) -> dict | None:
    """The most recent run whose RECORDED configuration matches, on the dichroic."""
    hits = []
    for r in runs:
        if r["_bandpass"]:
            continue
        cfg = r["config"]
        if all(abs(float(cfg.get(k, -1)) - float(v)) < 1e-9 for k, v in want.items()):
            hits.append(r)
    return hits[-1] if hits else None


def _line(label: str, r: dict | None) -> str:
    if r is None:
        return f"  {label:<26} ABSENT"
    rk = r["ranking"]
    resc = sum(1 for e in rk if e.get("crash_eliminated"))
    k = float(r.get("seel", {}).get("fit_k") or 0.0)
    seel = rk[0]["score"] * k if rk and k else float("nan")
    return (f"  {label:<26} classees={len(rk):<5} repechees={resc:<5} "
            f"RESULT={r.get('result')!r:<24} SEEL={seel:.3f} nm")


def main() -> int:
    runs = _load()
    if not runs:
        print("Aucun artefact lisible dans reports/. Rien a analyser.")
        return 1

    # G0 et G3 partagent leur configuration a la porte pres : G0 EST le temoin de G3.
    s10off = _pick(runs, crash_gate_confidence=0.0, robustness_num_runs=300, n_screen_runs=10)
    s10on = _pick(runs, crash_gate_confidence=0.95, robustness_num_runs=300, n_screen_runs=10)
    off300 = _pick(runs, crash_gate_confidence=0.0, robustness_num_runs=300, n_screen_runs=25)
    on300 = _pick(runs, crash_gate_confidence=0.95, robustness_num_runs=300, n_screen_runs=25)
    on150 = _pick(runs, crash_gate_confidence=0.95, robustness_num_runs=150, n_screen_runs=25)
    on500 = _pick(runs, crash_gate_confidence=0.95, robustness_num_runs=500, n_screen_runs=25)

    print("=" * 78)
    print("G0 -- C1 : porte INACTIVE. Elle GOUVERNE tous les autres bras.")
    print("=" * 78)
    print(_line("G0.c1  scr=10 gate OFF", s10off))
    print(f"  ATTENDU : RESULT = {C1_REFERENCE}")
    if s10off is not None:
        got = str(s10off.get("result"))
        same = got == C1_REFERENCE
        print(f"  LU      : RESULT = {got}")
        print(f"  VERDICT : {'IDENTIQUE' if same else '🔴 DIFFERENT'}")
        if not same:
            print("            Le correctif a FUI dans le chemin neutre.")
            print("            AUCUN autre bras de cette campagne ne veut rien dire.")
            print("            ARRETE-TOI ICI et signale-le.")

    print()
    print("=" * 78)
    print("G1 -- porte ARMEE au point de fonctionnement.")
    print("=" * 78)
    print(_line("gate OFF, N=300", off300))
    print(_line("gate ON,  N=300", on300))
    if off300 and on300:
        d = len(on300["ranking"]) - len(off300["ranking"])
        print(f"  strategies classees : {d:+d}")
        print("  TEST : ce nombre doit etre >= 0. La borne inferieure est toujours SOUS")
        print("         l'estimation ponctuelle, donc la porte armee ne peut qu'AJOUTER.")
        print("         Un nombre negatif est un DEFAUT, pas un resultat.")
        try:
            a, b = float(off300["result"]), float(on300["result"])
            print(f"  ecart de RESULT : {(b - a) / a:+.2%}   "
                  f"(sous {INDISTINGUISHABLE_PCT:.1f} % = indiscernable, PAS 'egal')")
        except (TypeError, ValueError):
            pass

    print()
    print("=" * 78)
    print("G2 -- Piege 1 : le classement est-il devenu INSENSIBLE a la profondeur ?")
    print("=" * 78)
    for lab, r in (("gate ON, N=150", on150), ("gate ON, N=300", on300),
                   ("gate ON, N=500", on500)):
        print(_line(lab, r))
    got = [r for r in (on150, on300, on500) if r]
    if len(got) >= 2:
        n = [len(r["ranking"]) for r in got]
        rs = [sum(1 for e in r["ranking"] if e.get("crash_eliminated")) for r in got]
        print(f"  etendue de `classees` : {max(n) - min(n)}   de `repechees` : {max(rs) - min(rs)}")
        print("  TEST : avec la porte historique ces deux etendues valaient 147 et 64.")
        print("         Si elles ne se resserrent PAS nettement, la borne ne fait pas son")
        print("         travail -- et c'est le seul bras qui peut invalider le correctif.")

    print()
    print("=" * 78)
    print("G3 -- n_screen peut-il redescendre a 10 ?")
    print("=" * 78)
    print(_line("G0.c1      gate OFF", s10off) + "   <- le temoin, deja lu en G0")
    print(_line("G3.scr10on gate ON ", s10on))
    if s10off and s10on:
        d = len(s10on["ranking"]) - len(s10off["ranking"])
        print(f"  strategies classees : {d:+d}")
        print("  TEST : a 10 tirages, 1/10 = 10 % >= 5 %, donc UN seul plantage tuait la")
        print("         strategie -- et depuis le correctif d'heritage elle etait perdue")
        print("         pour toute la recherche. La borne ne peut pas tuer sur un tirage.")
        print("         Attendu : le bras ON classe PLUS, et sa gagnante ne se degrade pas.")

    print()
    print("=" * 78)
    print("A NE PAS FAIRE EN LISANT CE TABLEAU")
    print("=" * 78)
    print("  - conclure d'un ecart de RESULT sous 8,5 % : c'est du bruit Monte-Carlo ;")
    print("  - conclure sur le passe-bande : aucun bras de cette campagne n'y touche ;")
    print("  - lire `repechees` comme une mesure de qualite : c'est un COMPTE de")
    print("    strategies auxquelles le repli a rendu un score fini, et leur score n'est")
    print("    PAS un score de robustesse -- ne le moyenne jamais avec les autres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
