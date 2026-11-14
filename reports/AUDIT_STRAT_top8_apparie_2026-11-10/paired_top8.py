"""Paired test of the top of STRAT's final ranking, from the draws captured by capture_final_ranking.py.

The draws are common to all plans (C2), so the uncertainty that matters between two plans is the one of their
DIFFERENCE on the same draws, not the sum of their individual uncertainties.

    python reports/AUDIT_STRAT_top8_apparie_2026-11-10/paired_top8.py

Reads final_ranking_draws.npz and final_ranking_meta.json next to this file; prints, writes nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
TOP = 8
STEP_NM = 0.01  # SEEL_EQUALITY_STEP_NM of certus/core/certus_strat_ranking.py
B, CHUNK, SPLITS = 4000, 100, 2000


def score_of(x):
    """The native score on (..., levels, draws): the max over the noise levels of the P95 of the RMSE."""
    return np.percentile(x, 95, axis=-1).max(axis=-1)


def seel(s):
    return 2.0 * np.sqrt(s)


def main() -> None:
    with np.load(HERE / "final_ranking_draws.npz") as z:
        rmse_all, stopped_all, noise_all, rank_all = z["rmse"], z["stopped"], z["noise_level"], z["rank"]
    meta = json.loads((HERE / "final_ranking_meta.json").read_text(encoding="utf-8"))
    ranking = meta["ranking"]
    print(f"classement final : {meta['n_ranked']} plans, dont {meta['n_with_draws']} avec leurs tirages")
    print("provenance :", str(meta.get("provenance", "absente"))[:400])

    # Keep the plans drawn like the first ranked one: same levels, same number of draws at every level.
    n_per = (~np.isnan(rmse_all)).sum(axis=-1)
    first = int(np.argmin(rank_all))
    same = np.all(n_per == n_per[first], axis=1) & np.all(np.isclose(noise_all, noise_all[first]), axis=1)
    keep = np.flatnonzero(same)
    keep = keep[np.argsort(rank_all[keep])]
    n = int(n_per[first].min())
    if not np.all(n_per[first] == n) or n < 20:
        print(f"ARRET : tirages par niveau = {n_per[first].tolist()}, analyse impossible")
        return
    R = rmse_all[keep][:, :, :n]  # (plans, levels, draws), in ranking order
    stp = stopped_all[keep][:, :, :n]
    ranks = rank_all[keep]
    levels = noise_all[first]
    S = R.shape[0]
    top_n = min(TOP, S)
    print(
        f"plans retenus : {S} (N = {n} tirages, niveaux = {levels.tolist()}) ; écartés pour tirages différents : {int((~same).sum())}"
    )
    print(f"rangs officiels des {top_n} premiers retenus : {ranks[:top_n].tolist()}")

    p95 = np.percentile(R, 95, axis=-1)
    sc = p95.max(axis=1)
    official = np.array([float(ranking[r]["result"].get("robustness_score", np.nan)) for r in ranks])
    fin = np.isfinite(official) & (official > 0)
    if fin.any():
        dev = np.abs(sc[fin] / official[fin] - 1.0)
        print(
            f"contrôle : mon score contre robustness_score, écart relatif max {dev.max():.2e} sur {int(fin.sum())} plans (non finis : {int((~fin).sum())})"
        )

    print("\n--- le haut du classement officiel (SEEL = 2*sqrt(score)) ---")
    for i in range(min(12, S)):
        it = ranking[ranks[i]]
        crashed = [int((stp[i, j] == 1).sum()) if np.all(stp[i, j] >= 0) else -1 for j in range(len(levels))]
        print(
            f"#{ranks[i] + 1:<3d} id={it['strategy'].get('strategy_id', '?')} origine={str(it['strategy'].get('origin', '?'))[:26]:26s} "
            f"blocs={len(it['blocks'])} P95/niveau={np.round(p95[i], 5).tolist()} SEEL={seel(sc[i]):.4f} nm "
            f"crash_rate={it['result'].get('crash_rate', '?')} arrêts/niveau={crashed}"
        )
    best = float(seel(sc).min())
    print(
        f"plans dans la classe d'égalité (SEEL <= meilleur + {STEP_NM} nm) : {int((seel(sc) <= best + STEP_NM).sum())} sur {S}"
    )
    print(
        f"niveau qui décide le score (fréquence de l'argmax par niveau) : {np.round(np.bincount(p95.argmax(axis=1), minlength=len(levels)) / S, 2).tolist()}"
    )
    print(
        f"P95 par niveau rapporté au niveau médian, moyenne des {top_n} premiers : {np.round((p95[:top_n] / p95[:top_n, [len(levels) // 2]]).mean(axis=0), 3).tolist()}"
    )

    print(f"\n--- tirages communs : corrélation des RMSE par tirage (si indépendants : +-{1 / np.sqrt(n):.2f}) ---")
    iu = np.triu_indices(top_n, 1)
    for j, lv in enumerate(levels):
        c = np.corrcoef(R[:top_n, j, :])[iu]
        print(
            f"niveau {lv:g} : Pearson entre les {top_n} premiers, moyenne {c.mean():+.3f} (min {c.min():+.3f}, max {c.max():+.3f})"
        )
    mid = len(levels) // 2
    call = np.corrcoef(R[:, mid, :])[np.triu_indices(S, 1)]
    print(
        f"tous les {S} plans, niveau {levels[mid]:g} : moyenne {call.mean():+.3f}, médiane {np.median(call):+.3f}, min {call.min():+.3f}"
    )
    if len(levels) > 1:
        across = [np.corrcoef(R[s, j], R[s, j + 1])[0, 1] for s in range(top_n) for j in range(len(levels) - 1)]
        print(
            f"même plan, niveaux voisins : moyenne {np.mean(across):+.3f} (les niveaux partagent-ils leurs tirages ?)"
        )

    rng = np.random.default_rng(20261110)
    sp = np.empty((B, S))  # paired: the same resampled draws for every plan and level
    for b0 in range(0, B, CHUNK):
        idx = rng.integers(0, n, size=(CHUNK, n))
        sp[b0 : b0 + CHUNK] = score_of(R[:, :, idx].transpose(2, 0, 1, 3))
    su = np.empty((B, top_n))  # unpaired: independent resampling per plan
    for q in range(top_n):
        idx = rng.integers(0, n, size=(B, n))
        su[:, q] = score_of(R[q][:, idx].transpose(1, 0, 2))

    print(f"\n--- incertitude d'un score seul (bootstrap, {top_n} premiers) ---")
    print("écart-type relatif du score :", np.round(su.std(axis=0) / sc[:top_n], 3).tolist())
    print("écart-type du SEEL (nm)     :", np.round(seel(su).std(axis=0), 4).tolist())

    print("\n--- écart au 1er officiel : non apparié contre apparié (SEEL, nm) ---")
    for q in range(1, top_n):
        d = seel(sc[q]) - seel(sc[0])
        du = seel(su[:, q]) - seel(su[:, 0])
        dp = seel(sp[:, q]) - seel(sp[:, 0])
        d2 = R[q, mid] ** 2 - R[0, mid] ** 2
        z2 = d2.mean() / (d2.std(ddof=1) / np.sqrt(n)) if d2.std() > 0 else 0.0
        lo, hi = np.percentile(dp, [2.5, 97.5])
        zu = d / du.std() if du.std() > 0 else 0.0
        zp = d / dp.std() if dp.std() > 0 else 0.0
        print(
            f"#{ranks[q] + 1}-#{ranks[0] + 1}: écart {d:+.4f} | sigma non apparié {du.std():.4f} (z={zu:+.2f}) | sigma apparié {dp.std():.4f} (z={zp:+.2f}) "
            f"| IC95 apparié [{lo:+.4f}, {hi:+.4f}] | P(bat le 1er) {np.mean(dp < 0):.2f} "
            f"| RMSE^2 moyen apparié au niveau {levels[mid]:g} : {d2.mean() / np.mean(R[0, mid] ** 2):+.1%} (z={z2:+.2f})"
        )

    print("\n--- la classe d'égalité vue du 1er par le score : écart apparié à quelques rangs ---")
    order = np.argsort(sc)
    for r_ in sorted({8, 12, 16, 20, 30, 40, 60, S - 1} & set(range(1, S))):
        s = order[r_]
        d = seel(sc[s]) - seel(sc[order[0]])
        dp = seel(sp[:, s]) - seel(sp[:, order[0]])
        zp = d / dp.std() if dp.std() > 0 else 0.0
        print(
            f"  rang par score {r_ + 1:3d} : écart {d:+.4f} nm, sigma apparié {dp.std():.4f}, z={zp:+.2f}, P(bat le 1er) {np.mean(dp < 0):.2f}"
        )

    print("\n--- qui gagne quand on retire les tirages (bootstrap apparié, tous les plans retenus) ---")
    win = np.bincount(sp.argmin(axis=1), minlength=S) / B
    for s in np.argsort(-win)[:8]:
        print(
            f"  rang officiel #{ranks[s] + 1} (id={ranking[ranks[s]]['strategy'].get('strategy_id', '?')}, {len(ranking[ranks[s]]['blocks'])} blocs) : gagne {win[s]:.1%}"
        )
    print(
        f"plans qui gagnent au moins une fois : {int((win > 0).sum())} | gagnant hors des {top_n} premiers officiels : {1 - win[:top_n].sum():.1%}"
    )
    rk = np.argsort(np.argsort(sp, axis=1), axis=1)
    print(
        f"P(rester dans les {top_n} meilleurs scores) pour chacun des {top_n} premiers :",
        np.round((rk[:, :top_n] < top_n).mean(axis=0), 2).tolist(),
    )

    print(f"\n--- biais de sélection : choisir sur une moitié des tirages, juger sur l'autre ({SPLITS} partages) ---")
    same_best, rho_top, rho_all, s_a, s_b = 0, [], [], np.zeros(top_n), np.zeros(top_n)
    for _ in range(SPLITS):
        perm = rng.permutation(n)
        a, b = score_of(R[:, :, perm[: n // 2]]), score_of(R[:, :, perm[n // 2 :]])
        ta = np.argsort(a)[:top_n]
        same_best += int(np.argmin(b[ta]) == 0)
        if np.std(b[ta]) > 0:
            rho_top.append(stats.spearmanr(np.arange(top_n), b[ta]).statistic)
        rho_all.append(stats.spearmanr(a, b).statistic)
        s_a += seel(a[ta])
        s_b += seel(b[ta])
    print(
        f"le 1er de la moitié A est le meilleur des {top_n} sur la moitié B : {same_best / SPLITS:.1%} (hasard : {1 / top_n:.1%})"
    )
    print(
        f"Spearman du rang A contre le score B, dans les {top_n} premiers de A : {np.mean(rho_top):+.3f} | sur les {S} plans : {np.mean(rho_all):+.3f}"
    )
    print("SEEL moyen par rang A, moitié A (nm) :", np.round(s_a / SPLITS, 4).tolist())
    print("SEEL moyen par rang A, moitié B (nm) :", np.round(s_b / SPLITS, 4).tolist())


if __name__ == "__main__":
    main()
