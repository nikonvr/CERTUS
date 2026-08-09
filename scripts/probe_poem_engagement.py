"""Does POEM really commit, and on how many layers?

POEM (Arsac these 2025 eq. 2.2) remplace la cible absolue par une FRACTION entre deux points
turning points, reported on the extrema actually observed. It is the mechanism that produces
l'auto-compensation. Mais le noyau ne l'active QUE si trois conditions tiennent
(certus/physics/certus_strat_growth.py) :

    tp_a >= 0 et tp_b >= 0          deux points tournants trouves, le premier devant
                                    tomber sous idx_nom_stop
    |amp_nom| > SWING_MIN           amplitude entre les deux ancres > 0,04 en T
    |amp_real| > SWING_MIN          idem sur le signal reel

Otherwise: `target_level = target_nominal`, ABSOLUTE target, NO compensation.

Sur un dichroique monitore dans sa bande passante a ~95 % de T, rien ne garantit que le
signal sweeps 4 transmission points during one layer. If POEM rarely engages,
tout le mecanisme de compensation — et les trois quarts du travail de modele de la session du
4 aout — est dormant.

METHODE. Le noyau est en njit et ne renvoie pas `poem_ok` ; on ne peut pas l'observer de
l'exterieur. Ce script REPLIQUE la detection a l'identique (memes constantes, meme balayage,
same rule idx_nom_stop) on the real nominal stack of the example, propagating the same
TMM. It is a replication, therefore to be read as such: if it diverges from the nucleus, it is
qui a tort.

    .venv/Scripts/python.exe scripts/probe_poem_engagement.py

Does not write anything except reports/. Do not touch any production codes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "reports" / "probe_poem_engagement.json"

#Constants copied from certus_strat_growth.py — if they change there, this script is lying.
NPTS = 64
D_SCAN = 3.0
SWING_MIN = 0.04


def main() -> None:
    from PyQt6.QtWidgets import QApplication  # ordre de chargement des DLL, cf. bench

    _app = QApplication.instance() or QApplication(sys.argv[:1])
    import numpy as np

    from certus_physics import calculate_RT_vectorized_real_HL
    from certus.core.certus_core import get_refractive_clues_vectorized
    from certus.core.certus_strat_core import APP_CONTEXT  # noqa: F401

    cfg = json.loads((ROOT / "example/example_strat/JSON-strat-example.json").read_text("utf-8"))
    l0 = float(cfg["l0"])
    mult = [float(m) for m in cfg["stack_multipliers"]]
    scan_min, scan_max = float(cfg["scan_wl_min"]), float(cfg["scan_wl_max"])
    scan_step = float(cfg["scan_wl_step"])

    from certus.core.certus_core import MaterialDatabase  # type: ignore

    db = MaterialDatabase()
    wl_l0 = np.array([l0], dtype=np.float64)
    nH0 = complex(get_refractive_clues_vectorized(cfg["h_material_file"], wl_l0, db_instance=db)[0])
    nL0 = complex(get_refractive_clues_vectorized(cfg["l_material_file"], wl_l0, db_instance=db)[0])

    # epaisseurs physiques nominales : d_i = m_i * l0 / (4 n_i)
    d_nom = np.array(
        [m * l0 / (4.0 * (nH0.real if i % 2 == 0 else nL0.real)) for i, m in enumerate(mult)],
        dtype=np.float64,
    )
    n_layers = d_nom.size

    scan = np.arange(scan_min, scan_max + 1e-9, scan_step)
    print(f"empilement : {n_layers} couches, l0 = {l0} nm")
    print(f"nH({l0}) = {nH0.real:.4f}   nL({l0}) = {nL0.real:.4f}")
    print(f"balayage : {scan.size} longueurs d'onde de {scan_min} a {scan_max} au pas de {scan_step}")
    print()

    idx_nom_stop = int(round((NPTS - 1) / D_SCAN))

    rows = []
    for wl in scan:
        wl_arr = np.array([wl], dtype=np.float64)
        nH = get_refractive_clues_vectorized(cfg["h_material_file"], wl_arr, db_instance=db).astype(np.complex128)
        nL = get_refractive_clues_vectorized(cfg["l_material_file"], wl_arr, db_instance=db).astype(np.complex128)
        nS = get_refractive_clues_vectorized(cfg["substrate_choice"], wl_arr, db_instance=db).astype(np.complex128)

        for i in range(n_layers):
            dmax = D_SCAN * d_nom[i]
            ds = np.linspace(0.0, dmax, NPTS)
            T = np.empty(NPTS, dtype=np.float64)
            base = d_nom[:i]
            for k, dk in enumerate(ds):
                th = np.concatenate([base, [dk]])
                _, t = calculate_RT_vectorized_real_HL(wl_arr, nH, nL, nS, th)
                T[k] = float(np.asarray(t)[0])

            #all the extrema of the sweep, with their position relative to the stop
            extrema = []
            for k in range(1, NPTS - 1):
                dl = T[k] - T[k - 1]
                dr = T[k + 1] - T[k]
                if (dl > 1e-12 and dr < -1e-12) or (dl < -1e-12 and dr > 1e-12):
                    extrema.append(k)
            n_tp = sum(1 for k in extrema if k <= idx_nom_stop)

            # --- A. TEL QUE CODE ---------------------------------------------------
            # An extremum beyond idx_nom_stop is only taken if tp_b < 0, and it
            #then leaves tp_a = -1: it can NEVER serve as a usable anchor.
            tp_a = tp_b = -1
            for k in extrema:
                if k <= idx_nom_stop or tp_b < 0:
                    tp_a, tp_b = tp_b, k
            two_tp = tp_a >= 0 and tp_b >= 0
            amp = abs(T[tp_b] - T[tp_a]) if two_tp else 0.0

            # --- B. PRESCRIPTION ARSAC ---------------------------------------------
            # « If the current layer has less than two turning points, the VIRTUAL NEXT
            #turning points are used”. We therefore authorize the last extremum before
            #   l'arret et le PREMIER APRES a servir d'ancres — c'est ce que le
            #scanning at 3x the nominal thickness is expected to provide.
            before = [k for k in extrema if k <= idx_nom_stop]
            after = [k for k in extrema if k > idx_nom_stop]
            if len(before) >= 2:
                va, vb = before[-2], before[-1]
            elif before and after:
                va, vb = before[-1], after[0]
            elif len(after) >= 2:
                va, vb = after[0], after[1]
            else:
                va = vb = -1
            v_two = va >= 0 and vb >= 0
            v_amp = abs(T[vb] - T[va]) if v_two else 0.0

            rows.append(
                {
                    "wl": float(wl),
                    "layer": i,
                    "two_tp": bool(two_tp),
                    "amp": float(amp),
                    "poem_ok": bool(two_tp and amp > SWING_MIN),
                    "virtual_two_tp": bool(v_two),
                    "virtual_amp": float(v_amp),
                    "poem_ok_virtual": bool(v_two and v_amp > SWING_MIN),
                    "n_tp_in_nominal": int(n_tp),
                }
            )

    tot = len(rows)
    ok = sum(r["poem_ok"] for r in rows)
    no_tp = sum(1 for r in rows if not r["two_tp"])
    weak = sum(1 for r in rows if r["two_tp"] and not r["poem_ok"])
    amps = sorted(r["amp"] for r in rows if r["two_tp"])

    okv = sum(r["poem_ok_virtual"] for r in rows)
    print(f"couples (couche, lambda) evalues : {tot}")
    print(f"  A. POEM ENGAGE, tel que code .......... {ok:>6}  ({100*ok/tot:.1f} %)")
    print(f"  B. POEM ENGAGE, prescription Arsac .... {okv:>6}  ({100*okv/tot:.1f} %)")
    print(f"     -> gagnes par le point tournant virtuel : {okv-ok} ({100*(okv-ok)/tot:+.1f} pts)")
    print(f"  moins de deux ancres (A) .............. {no_tp:>6}  ({100*no_tp/tot:.1f} %)")
    print(f"  amplitude < {SWING_MIN} (A) ................. {weak:>6}  ({100*weak/tot:.1f} %)")
    if amps:
        q = lambda p: amps[min(len(amps) - 1, int(p * len(amps)))]  # noqa: E731
        print()
        print(f"  amplitude entre ancres : min {amps[0]:.4f}  p25 {q(.25):.4f}  "
              f"mediane {q(.5):.4f}  p75 {q(.75):.4f}  max {amps[-1]:.4f}")

    per_layer = {}
    for r in rows:
        per_layer.setdefault(r["layer"], []).append(r["poem_ok"])
    engaged = [(l, sum(v), len(v)) for l, v in sorted(per_layer.items())]
    print()
    print("  taux d'engagement par couche (echantillon) :")
    for l, k, n in engaged[:6] + engaged[len(engaged) // 2 : len(engaged) // 2 + 2] + engaged[-3:]:
        print(f"    couche {l:>2} : {k:>3}/{n}  ({100*k/n:.0f} %)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "n_pairs": tot,
                "poem_engaged": ok,
                "poem_engaged_pct": 100.0 * ok / tot,
                "fewer_than_two_anchors": no_tp,
                "amplitude_below_swing_min": weak,
                "swing_min": SWING_MIN,
                "per_layer": {str(l): {"ok": k, "n": n} for l, k, n in engaged},
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\necrit : {OUT}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
