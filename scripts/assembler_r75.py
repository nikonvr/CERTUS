"""ASSEMBLAGE DU 75 COUCHES ALEATOIRE + test HORS ECHANTILLON de la regle de sensibilite.

    .venv\\Scripts\\python.exe scripts\\assembler_r75.py

🔑 POURQUOI CE COMPOSANT ET PAS UN AUTRE. Le random75 (graine 2026) n'a ni cavite, ni
miroir, ni periodicite. Une regle qui aurait besoin de la STRUCTURE du design ne doit donc
RIEN y prevoir. 👤 : *« on se fout du fait que cela soit un multicavite, je cherche une
strategie generale »*. C'est le seul des quatre composants qui teste vraiment cette exigence.

CE QU'ON MESURE ICI, et c'est UNE question, pas deux :

    la sensibilite S(p-1) de la couche GELEE par le changement de temoin
    predit-elle le SEEL de la piece assemblee ?

Sur le 99c la correlation vaut r = +0,69. Sur le 48c et le 35c elle tombe a +0,25 et +0,20.
Deux lectures restent possibles et ce script les separe :

    (a) la regle a besoin d'un fort CONTRASTE de sensibilite entre couches -- le 99c en a
        un (facteur 11), les petits composants non ;
    (b) le +0,69 du 99c etait une coincidence sur 18 points.

Le random75 a un contraste de 11x comme le 99c mais AUCUNE structure. Si (a) est vraie, la
correlation doit y reapparaitre. Si (b) est vraie, elle doit rester plate.

🔴 CE QUE CE SCRIPT NE FAIT PAS : refaire des tirages. Il concatene ceux qui sont en cache,
tirage par tirage, exactement comme `classer_partitions.py`. La regle 1 de la methode
d'assemblage validee (§25.8) : refaire un tirage introduit un alea neuf et detruit ce qu'on
mesure -- les erreurs COMMISES, sans compensation croisee.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CACHE = ROOT / "reports" / "controle_random75"
FULL = "example/example_strat/JSON-strat-random75.json"
N = 75
DELTA = 0.051          # resolution en SEEL a N=50


def charger() -> dict[tuple[int, int], np.ndarray]:
    out = {}
    for f in CACHE.glob("i_*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        th = CACHE / f"th_{r['a']:03d}_{r['b']:03d}.npy"
        if r["verdict"] == "DEPOSABLE" and th.exists():
            out[(r["a"], r["b"])] = np.load(th)
    return out


def main() -> int:
    import bench_examples as Bx
    from certus.core.certus_strat_robustness import _index_stream_seed
    from certus.physics.certus_opt_tmm import arange_inclusive
    from certus.physics.certus_strat_batch import compute_batch_rmse
    from certus.physics.certus_tmm_hl import calculate_RT_vectorized_real_HL
    from certus.utils.certus_strat_service import (
        get_refractive_clues_vectorized,
        get_refractive_index,
    )
    from CERTUS_STRAT import CertusStratApp

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / FULL))
    prm = app.collect_params()
    db = prm.get("materials_db_instance") or prm.get("materials_db")

    wl = arange_inclusive(prm["wl_range"][0], prm["wl_range"][1], float(prm["wl_step"]))
    nH = np.asarray(get_refractive_clues_vectorized(prm["nH_id"], wl, db_instance=db), dtype=np.complex128)
    nL = np.asarray(get_refractive_clues_vectorized(prm["nL_id"], wl, db_instance=db), dtype=np.complex128)
    nS = np.asarray(get_refractive_clues_vectorized(prm["nSub_id"], wl, db_instance=db), dtype=np.complex128)

    l0 = float(prm["l0"])
    mult = [float(e) for e in str(prm["stack_string"]).split(",") if e.strip()]
    nH0 = get_refractive_index(prm["nH_id"], l0, db_instance=db)
    nL0 = get_refractive_index(prm["nL_id"], l0, db_instance=db)
    nom = np.array([(m * l0) / (4.0 * np.real(nH0 if i % 2 == 0 else nL0))
                    for i, m in enumerate(mult)], dtype=np.float64)
    _, T_nom = calculate_RT_vectorized_real_HL(wl, nH, nL, nS, nom)
    parity = np.arange(N) % 2 == 0
    mat = np.where(parity[np.newaxis, :], nH[:, np.newaxis], nL[:, np.newaxis])
    vide = np.empty(0, dtype=np.complex128)
    seed_idx = _index_stream_seed(42, 1)
    corr = float(prm.get("index_corridor", 0.0) or 0.0)

    def seel_of(th: np.ndarray) -> float:
        rmse = compute_batch_rmse(th, wl.astype(np.float64), vide, vide,
                                  nS.astype(np.complex128), T_nom, mat, None,
                                  corr, seed_idx, float(wl[0]), float(wl[-1]))
        return 2.0 * math.sqrt(float(np.percentile(rmse, 95)))

    # 🔴 CONTROLE OBLIGATOIRE (regle 5) : concatener les NOMINALES doit rendre le design
    # complet. Sans lui l'assemblage peut etre faux sans que rien ne le signale.
    ctrl = max(abs(np.concatenate([nom[:40], nom[40:]]) - nom))
    print(f"controle d'assemblage (nominales concatenees vs design) : ecart {ctrl:.3e}\n")

    # SENSIBILITE S(i) : de combien le spectre bouge quand la couche i SEULE bouge.
    #
    # 🔴 DEUX DEFINITIONS, ET ELLES NE DONNENT PAS LE MEME CLASSEMENT. §25.10 a mesure le
    # 99c, le 48c et le 35c avec une perturbation de **1 nm ABSOLU**. Une premiere version
    # de ce script utilisait **1 % RELATIF**, ce qui pondere par l'epaisseur nominale et
    # n'est donc PAS la meme grandeur. Comparer un r calcule sur l'une aux r de l'autre
    # serait une faute. Les deux sont donc calculees, et c'est **S_nm** qui se compare aux
    # trois reperes existants.
    def sensibilite(mode: str) -> np.ndarray:
        S = np.zeros(N)
        for i in range(N):
            p = nom.copy()
            p[i] += 1.0 if mode == "nm" else 0.01 * nom[i]
            _, T = calculate_RT_vectorized_real_HL(wl, nH, nL, nS, p)
            S[i] = float(np.sqrt(np.mean((T - T_nom) ** 2)))
        return S

    S = sensibilite("nm")          # 🔑 la definition de reference, comparable a §25.10
    S_rel = sensibilite("rel")     # l'autre, gardee pour montrer qu'elle differe
    print(f"S (1 nm absolu)  : min {S.min():.3e}  max {S.max():.3e}  contraste {S.max()/S.min():.1f}x")
    print(f"S (1 % relatif)  : min {S_rel.min():.3e}  max {S_rel.max():.3e}  contraste {S_rel.max()/S_rel.min():.1f}x")
    print(f"correlation entre les deux definitions : {np.corrcoef(S, S_rel)[0,1]:+.3f}\n")

    cache = charger()
    res = []
    for p in range(20, 56, 2):
        if (0, p) in cache and (p, N) in cache:
            th = np.concatenate([cache[(0, p)], cache[(p, N)]], axis=1)
            if th.shape[1] != N:
                continue
            res.append({"p": p, "seel": seel_of(th),
                        "S_gelee": float(S[p - 1]), "S_gelee_rel": float(S_rel[p - 1])})

    if not res:
        print("aucune position complete en cache.")
        return 0
    res.sort(key=lambda r: r["seel"])
    best = res[0]["seel"]

    print("=" * 72)
    print(f"{len(res)} positions de changement de verre temoin assemblees")
    print("=" * 72)
    print("\n  rang   position   SEEL     ecart    S(p-1) de la couche GELEE")
    for k, r in enumerate(res, 1):
        ec = (r["seel"] - best) / best
        tag = "= " if ec <= DELTA else "  "
        print(f"  {k:4d}   0-{r['p']:<2d}/{r['p']}-75   {r['seel']:.3f}  {tag}{ec:+6.1%}   {r['S_gelee']:.3e}")

    y = np.array([r["seel"] for r in res])

    def correle(cle: str) -> tuple[float, float]:
        x = np.array([r[cle] for r in res])
        rp = float(np.corrcoef(x, y)[0, 1])
        rs = float(np.corrcoef(np.argsort(np.argsort(x)),
                               np.argsort(np.argsort(y)))[0, 1])
        return rp, rs

    rp_nm, rs_nm = correle("S_gelee")
    rp_rel, rs_rel = correle("S_gelee_rel")

    ex = [r for r in res if (r["seel"] - best) / best <= DELTA]
    print(f"\n{len(ex)} positions a EGALITE avec la premiere (ecart <= {DELTA:.1%})")
    print(f"etendue : {best:.3f} -> {res[-1]['seel']:.3f} nm ({(res[-1]['seel']-best)/best:+.1%})")
    print("\n" + "=" * 72)
    print("TEST HORS ECHANTILLON DE LA REGLE DE SENSIBILITE")
    print("=" * 72)
    print(f"  [REF] S en 1 nm ABSOLU (comparable a 25.10) : Pearson {rp_nm:+.3f}  Spearman {rs_nm:+.3f}")
    print(f"        S en 1 % relatif  (NON comparable)    : Pearson {rp_rel:+.3f}  Spearman {rs_rel:+.3f}")
    print(f"  reperes en 1 nm absolu : 99c +0,69 | 48c +0,25 | 35c +0,20")
    print("\n  [INFO] Avec 18 points et 11 a egalite, |r| < 0,47 n'est pas distinguable de zero")
    print("         au seuil de 5 %. Lis le signe et l'amplitude ensemble, jamais le signe seul.")

    out = CACHE / "ASSEMBLAGE_r75.json"
    out.write_text(json.dumps({
        "positions": res,
        "pearson_S_nm": rp_nm, "spearman_S_nm": rs_nm,
        "pearson_S_rel": rp_rel, "spearman_S_rel": rs_rel,
        "contraste_S_nm": float(S.max() / S.min()),
        "contraste_S_rel": float(S_rel.max() / S_rel.min()),
        "n_positions": len(res), "n_ex_aequo": len(ex),
        "seuil_significativite_5pct": 0.468,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nconsigne dans {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
