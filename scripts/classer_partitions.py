"""Assemble toutes les partitions depuis le cache d'intervalles et les classe.

    .venv\\Scripts\\python.exe scripts\\classer_partitions.py

Aucun run. Tout sort du cache produit par `campagne_intervalles.py` : les epaisseurs
simulees de chaque intervalle sont concatenees tirage par tirage, et la piece de 99 couches
est notee par `compute_batch_rmse`, le code de production.

🔴 CE QUE CE CLASSEMENT EST, ET CE QU'IL N'EST PAS.

C'est une BORNE SUPERIEURE. Chaque intervalle a jusqu'a 306 strategies deposables et la
campagne n'a garde QUE LA MEILLEURE -- meilleure au sens de son propre sous-spectre, qui
n'est pas celui du produit final. Une erreur benigne sur un intervalle isole peut etre
catastrophique si la couche concernee se trouve etre un espaceur de cavite dans l'empilement
complet. Le vrai optimum demanderait de garder les k meilleures par intervalle et d'assembler
les combinaisons.

⚠️ UNE SEULE GRAINE. Le classement ci-dessous est un CRIBLAGE, pas un verdict : le premier
est necessairement celui dont le bruit a eu le plus de chance. Son SEEL est biaise vers le
bas par construction. Seule une re-evaluation sur 3 a 5 graines independantes, dont on prend
la moyenne, donne un score defendable.

🔑 UNITE DE DECISION : la resolution relative d'un score vaut 6 % a N=150 et suit 1/sqrt(N),
donc 10,4 % a N=50, soit **5,1 % en SEEL**. Deux partitions separees de moins que ca sont A
EGALITE, pas classees.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from itertools import combinations
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

CACHE_BASE = ROOT / "reports" / "intervalles_99c"
FULL = "example/example_strat/JSON-strat-bandpass-5cav-99c.json"
N = 99


SEED = 42


def _suffixe_graine(seed: int) -> str:
    """Vide a la graine de reference -- meme convention que campagne_intervalles.py."""
    return "" if seed == SEED else f"_s{seed:03d}"


def charger(cache_dir: Path, seed: int = SEED) -> dict[tuple[int, int], dict]:
    """Les intervalles deposables d'UNE graine.

    🔴 Le filtre sur la graine n'est pas cosmetique. Le glob `i_*.json` ramene aussi les
    mesures des autres graines, et assembler une partition depuis des tranches tirees sur
    des bruits differents rend un SEEL qui ressemble a un resultat sans en etre un.
    Les entrees d'avant l'exposition de `--graine` n'ont pas de champ `seed` : elles
    valent SEED par construction, puisque la valeur etait codee en dur.
    """
    out = {}
    suf = _suffixe_graine(seed)
    for f in cache_dir.glob("i_*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r.get("seed", SEED) != seed:
            continue
        th = cache_dir / f"th_{r['a']:03d}_{r['b']:03d}{suf}.npy"
        if r["verdict"] == "DEPOSABLE" and th.exists():
            r["th"] = np.load(th)
            out[(r["a"], r["b"])] = r
    return out


def partitions(lo: int = 20, hi: int = 60) -> list[tuple[tuple[int, int], ...]]:
    res = []
    for k in (1, 2, 3):
        for cuts in combinations(range(2, N, 2), k):
            b = [0, *cuts, N]
            ps = tuple((b[i], b[i + 1]) for i in range(len(b) - 1))
            if all(lo <= y - x <= hi for x, y in ps):
                res.append(ps)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Classement des partitions assemblées du 99 couches.")
    ap.add_argument("--lo", type=int, default=20, help="Nombre minimal de couches par témoin (défaut: 20)")
    ap.add_argument("--hi", type=int, default=60, help="Nombre maximal de couches par témoin (défaut: 60)")
    ap.add_argument("--mode", default="fast", choices=("fast", "premium", "deep"), help="Mode du cache à lire")
    ap.add_argument("--cache-dir", default=None, help="Chemin du dossier de cache")
    ap.add_argument("--max-crash", type=float, default=0.05, help="Taux maximal de tirages plantés toléré (défaut: 0.05)")
    ap.add_argument("--graine", type=int, default=SEED,
                    help=f"graine de robustesse a classer (défaut: {SEED}). Le cache peut porter "
                         f"plusieurs graines cote a cote ; on n'assemble JAMAIS des tranches "
                         f"venant de graines differentes")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else (ROOT / "reports" / ("intervalles_99c" if args.mode == "fast" else f"intervalles_99c_{args.mode}"))
    delta = 0.030 if args.mode == "premium" else 0.051

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
    # 🔴 La graine de la realisation d'indice DOIT etre celle qui a servi a mesurer les
    # tranches. C'est la contrainte C2 : croissance et notation voient la meme realisation,
    # sinon on note un filtre qui n'a jamais existe. Elle valait 42 en dur, ce qui etait
    # juste tant qu'une seule graine existait dans le cache.
    seed_idx = _index_stream_seed(args.graine, 1)
    corr = float(prm.get("index_corridor", 0.0) or 0.0)

    cache = charger(cache_dir, args.graine)
    print(f"{len(cache)} intervalles deposables en cache ({cache_dir.name}), graine {args.graine}.\n")

    res = []
    manquants = 0
    rejetes_crash = 0
    all_partitions = partitions(lo=args.lo, hi=args.hi)

    for ps in all_partitions:
        if not all(p in cache for p in ps):
            manquants += 1
            continue
        th = np.concatenate([cache[p]["th"] for p in ps], axis=1)
        if th.shape[1] != N:
            continue

        # 🔑 Contrôle des tirages plantés (th > 1e5 nm)
        is_crashed_run = np.any(th > 1e5, axis=1)
        cum_crash_rate = float(np.mean(is_crashed_run))
        n_crashed = int(np.sum(is_crashed_run))

        if cum_crash_rate > args.max_crash:
            rejetes_crash += 1
            continue

        rmse = compute_batch_rmse(th, wl.astype(np.float64), vide, vide,
                                  nS.astype(np.complex128), T_nom, mat, None,
                                  corr, seed_idx, float(wl[0]), float(wl[-1]))
        p95 = float(np.percentile(rmse, 95))
        res.append({
            "parts": ps, "n_temoins": len(ps),
            "seel": 2.0 * math.sqrt(p95), "rmse": p95,
            "faible": min(cache[p]["n_deposables"] for p in ps),
            "crash_rate": cum_crash_rate,
            "n_crashed": n_crashed,
        })

    if not res:
        print("aucune partition complete et saine en cache pour l'instant.")
        return 0
    res.sort(key=lambda r: r["seel"])
    best = res[0]["seel"]

    print("=" * 86)
    print(f"{len(res)} partitions assemblees  ({manquants} incompletes, {rejetes_crash} rejetees car plantages > {args.max_crash:.1%})")
    print(f"Bornes par temoin : [{args.lo}, {args.hi}] couches  (cache: {cache_dir.name})")
    print("=" * 86)
    print(f"\nmeilleur SEEL {best:.3f} nm | cible 0,300 nm | resolution +/-{delta:.1%}\n")
    print("  rang  temoins  partition                       SEEL     ecart   min dep  plantages")
    for i, r in enumerate(res[:15], 1):
        ec = (r["seel"] - best) / best
        tag = "= " if ec <= delta else "  "
        pp = " ".join(f"{a}-{b}" for a, b in r["parts"])
        print(f"  {i:4d}  {r['n_temoins']:5d}    {pp:<30} {r['seel']:.3f}  {tag}{ec:+6.1%}   {r['faible']:5d}    {r['crash_rate']*100:4.1f}%")

    ex = [r for r in res if (r["seel"] - best) / best <= delta]
    print(f"\n{len(ex)} partitions a EGALITE avec la premiere (ecart <= {delta:.1%}).")
    print(f"etendue totale : {best:.3f} -> {res[-1]['seel']:.3f} nm "
          f"({(res[-1]['seel'] - best) / best:+.1%})")
    for k in (2, 3, 4):
        s = [r for r in res if r["n_temoins"] == k]
        if s:
            print(f"  meilleur a {k} temoins : {min(r['seel'] for r in s):.3f} nm  ({len(s)} partitions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

