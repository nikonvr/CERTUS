"""Reads the campaign and answers the questions it was designed to answer.

    .venv\\Scripts\\python.exe scripts\\analyse_campagne.py

Reads only `reports/probe_anchor_noise_pipeline_*.json`. No bench time, and it can be
run WHILE the campaign is still going -- every run is identified by the `config` block
it carries, so a partial campaign simply answers fewer questions.

🔴 TWO RULES IT ENFORCES, because both have already produced plausible and wrong tables:

  * A ranking is read from `ranking` / `winner`, NEVER from `strategies`. The latter is
    a bounded sample kept in capture order.
  * `RESULT` is the WORST of three noise levels; the per-strategy figures are at the
    NOMINAL level. They are never put in the same comparison.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPORTS = Path(r"C:\dev\gemini\reports")
NEUTRAL = {
    "index_corridor": 0.0, "affine_scale_amp": 0.0, "affine_offset_amp": 0.0,
    "poem_enabled": True, "phase_a_level_margin_factor": 1.66, "dp_yield_weight": 0.0,
    "robustness_num_runs": 150, "n_screen_runs": 25, "k_keep_survivors": 10,
    "robustness_seed": 42,
}


def load() -> list[dict]:
    """Reports from the CURRENT code only.

    🔴 A report written before 2026-08-10 carries neither `ranking` nor `seel`, and its
    corridor runs used the monitoring-span normalisation -- which handed a grouped
    strategy up to 21x the specified corridor. Those numbers are void. They also sit in
    `reports/` under the very same file names, so an analyser that took everything
    would silently blend invalid figures into a fresh campaign and produce a table that
    reads perfectly. The absence of `ranking` is the marker, and it is exact: it was
    added by the same commit that fixed the normalisation.
    """
    out, skipped = [], 0
    for path in sorted(REPORTS.glob("probe_anchor_noise_pipeline_*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict) or not d.get("config"):
            continue
        if "ranking" not in d:
            skipped += 1
            continue
        d["_file"] = path.name
        out.append(d)
    if skipped:
        print(f"⚠️  {skipped} rapport(s) d'avant le correctif de normalisation ignore(s) : "
              "leurs chiffres de corridor sont invalides.")
    return out


def differs(run: dict, *keys: str) -> bool:
    """True when the run differs from the neutral reference ONLY on `keys`."""
    cfg = run["config"]
    for k, v in NEUTRAL.items():
        got = cfg.get(k, v)
        same = (got is v) if isinstance(v, bool) else abs(float(got) - float(v)) < 1e-12
        if k in keys:
            continue
        if not same:
            return False
    return True


def pick(runs: list[dict], key: str, value) -> dict | None:
    for r in runs:
        got = r["config"].get(key)
        ok = (got is value) if isinstance(value, bool) else (
            got is not None and abs(float(got) - float(value)) < 1e-12)
        if ok and differs(r, key):
            return r
    return None


def seel(run: dict) -> str:
    v = (run.get("seel") or {}).get("result_seel_nm")
    return f"{v:.1f} nm" if isinstance(v, (int, float)) else "—"


def winner(run: dict) -> tuple:
    w = run.get("winner") or {}
    return (w.get("id"), w.get("n_blocks"), tuple(w.get("wavelengths") or []))


def clopper_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """Upper 95 % bound on a rate from k events in n trials. Rule of three when k = 0."""
    if n <= 0:
        return float("nan")
    if k == 0:
        return 3.0 / n
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        tail = sum(math.comb(n, i) * mid**i * (1 - mid) ** (n - i) for i in range(k + 1))
        lo, hi = (mid, hi) if tail > alpha else (lo, mid)
    return (lo + hi) / 2


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> int:
    runs = load()
    ref = next((r for r in runs if differs(r)), None)
    print(f"{len(runs)} rapports lus.  Reference : {'trouvee' if ref else 'ABSENTE'}")
    if ref:
        print(f"  RESULT = {ref['result']}   SEEL = {seel(ref)}   gagnante = {winner(ref)}")

    # --- D1 ------------------------------------------------------------------
    section("D1 -- LE CORRIDOR, sur la normalisation CORRIGEE")
    pts = []
    for c in (0.001, 0.0025, 0.005, 0.01):
        r = pick(runs, "index_corridor", c)
        if r and ref:
            pts.append((c, r["result"] / ref["result"], seel(r)))
            print(f"  corridor {c:<7.4f} x{pts[-1][1]:>6.2f}   SEEL {pts[-1][2]:>8s}")
    if len(pts) >= 2:
        xs = [math.log(c) for c, _, _ in pts]
        ys = [math.log(v) for _, v, _ in pts]
        n = len(xs)
        sx, sy = sum(xs), sum(ys)
        slope = (n * sum(x * y for x, y in zip(xs, ys)) - sx * sy) / (n * sum(x * x for x in xs) - sx * sx)
        print(f"\n  exposant log-log : {slope:.3f}   (1 = lineaire, 0.5 = racine)")
    off = next((r for r in runs if r["config"].get("poem_enabled") is False
                and abs(float(r["config"].get("index_corridor", 0)) - 0.005) < 1e-12), None)
    on = pick(runs, "index_corridor", 0.005)
    if off and on and ref:
        print(f"\n  corridor 0.005 POEM actif : x{on['result']/ref['result']:.2f}")
        print(f"  corridor 0.005 POEM coupe : RESULT {off['result']:.6f}")
        print("  (protection = rapport des couts ; il faut le run POEM-off a corridor 0)")

    # --- D2 ------------------------------------------------------------------
    section("D2 -- COMBIEN DE TIRAGES ? convergence du classement")
    print("  Sobol est emboite et la Phase A ne bouge pas : les ids SONT comparables ici.")
    print(f"\n  {'N':>6s} {'RESULT':>20s} {'SEEL':>9s} {'gagnante':>10s} {'top-5 identique au N precedent':>32s}")
    prev_top = None
    for N in (25, 50, 100, 150, 300, 600, 1200):
        r = ref if N == 150 else pick(runs, "robustness_num_runs", N)
        if not r:
            continue
        rk = r.get("ranking") or []
        top = tuple(x.get("id") for x in rk[:5])
        stable = "—" if prev_top is None else ("OUI" if top == prev_top else "non")
        wid = (r.get("winner") or {}).get("id", "—")
        print(f"  {N:>6d} {r['result']:>20.15f} {seel(r):>9s} {str(wid):>10s} {stable:>32s}")
        prev_top = top
    print("\n  Certification : borne haute a 95 % sur le plantage de la gagnante")
    for N in (25, 150, 600, 1200):
        r = ref if N == 150 else pick(runs, "robustness_num_runs", N)
        w = (r or {}).get("winner") or {}
        ok, tot = w.get("n_runs_ok"), w.get("n_runs_total")
        if isinstance(ok, int) and isinstance(tot, int) and tot:
            print(f"    N={N:>5d}  {tot-ok}/{tot} plantages  ->  <= {100*clopper_upper(tot-ok, tot):.2f} %")

    # --- D3 ------------------------------------------------------------------
    section("D3 -- L'ELIMINATION perd-elle quelque chose ?")
    base_w = winner(ref) if ref else None
    for key, values in (("n_screen_runs", (10, 50, 100)), ("k_keep_survivors", (30,))):
        for v in values:
            r = pick(runs, key, v)
            if r:
                same = "IDENTIQUE" if winner(r) == base_w else "*** DIFFERENTE ***"
                print(f"  {key}={v:<4d}  gagnante {same}   SEEL {seel(r)}")
    print("\n  Si la gagnante ne change jamais, le screening a 25 ne perd rien.")
    print("  Si elle change, il ecarte sur une statistique qui ne voit pas la cible.")

    # --- D4 ------------------------------------------------------------------
    section("D4 -- LES GRAINES : la conclusion est-elle stable ?")
    for s in (42, 77, 101, 202):
        r = ref if s == 42 else pick(runs, "robustness_seed", s)
        if r:
            print(f"  graine {s:>4d} : RESULT {r['result']:.9f}   SEEL {seel(r):>9s}   gagnante {winner(r)[:2]}")
    cons = next((r for r in runs if r["config"].get("enable_consensus_ranking") is True), None)
    if cons:
        print(f"\n  consensus multi-graines : RESULT {cons['result']:.9f}   SEEL {seel(cons)}")

    # --- D5 ------------------------------------------------------------------
    section("D5 -- LES BOUTONS MESURES INERTES le sont-ils encore ?")
    for key, val, nom in (("phase_a_level_margin_factor", 3.33, "marge Phase A"),
                          ("dp_yield_weight", 200.0, "dp_yield_weight")):
        r = pick(runs, key, val)
        if r and ref:
            identique = r["result"] == ref["result"]
            verdict = "*** TOUJOURS INERTE (bit-identique) ***" if identique else "agit"
            print(f"  {nom:<18s} {val:>7} -> {verdict}")
    print("\n  Un bouton bit-identique n'est pas mal calibre : il n'atteint pas le calcul.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
