"""Sonde : les 10 longueurs d'onde retenues par bloc sont-elles dix fois la meme ?

`_dp_kernel` ne considere que les 10 meilleures lambda par bloc
(certus/physics/certus_strat_dp.py:117), et `_compute_valid_blocks_kernel` les choisit par
COUT CROISSANT, sans aucune contrainte de separation spectrale (:71-85).

Si cout(lambda) est une fonction lisse de lambda, ces dix candidats sont dix points voisins
du MEME minimum local. On ne garderait alors pas dix strategies : on echantillonnerait dix
fois la meme, avant de depenser dessus le budget Monte-Carlo — la seule etape qui mesure la
reponse spectrale.

Cette sonde intercepte le kernel au premier appel, sans rien changer au calcul, et mesure :
  - l'etendue spectrale des 10 retenues, bloc par bloc ;
  - combien de « regions » distinctes elles couvrent a differents seuils de separation ;
  - la courbe cout(lambda) de quelques couches, pour juger de sa regularite.

    .venv/Scripts/python.exe scripts/probe_block_wls.py

N'ecrit rien dans le depot hors reports/. Ne modifie aucun comportement.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402  (fixe ROOT, chdir et sys.path)

OUT = ROOT / "reports" / "probe_block_wls.json"
PROBE: dict = {"captured": False}


def _clusters(wls: list[float], sep: float) -> int:
    """Nombre de groupes separes d'au moins `sep` nm."""
    if not wls:
        return 0
    s = sorted(wls)
    n = 1
    ref = s[0]
    for w in s[1:]:
        if w - ref >= sep:
            n += 1
            ref = w
    return n


def install_probe() -> None:
    import numpy as np

    import certus.core.certus_strat_ranking as R

    original = R._compute_valid_blocks_kernel

    def patched(layer_wls, layer_costs, valid_mask, num_layers, top_k, max_W):
        block_costs, block_wls, block_counts = original(
            layer_wls, layer_costs, valid_mask, num_layers, top_k, max_W
        )
        if PROBE["captured"]:
            return block_costs, block_wls, block_counts
        PROBE["captured"] = True

        # --- ce que la DP voit reellement : les 10 premieres de chaque bloc -------
        per_block = []
        for i in range(num_layers):
            for j in range(i + 1, num_layers + 1):
                cnt = int(block_counts[i, j])
                if cnt <= 1:
                    continue
                take = min(10, cnt)
                wls = [float(block_wls[i, j, b]) for b in range(take)]
                costs = [float(block_costs[i, j, b]) for b in range(take)]
                per_block.append(
                    {
                        "i": i,
                        "j": j,
                        "len": j - i,
                        "count_total": cnt,
                        "n_used": take,
                        "wls": wls,
                        "span_nm": max(wls) - min(wls),
                        "clusters_5nm": _clusters(wls, 5.0),
                        "clusters_10nm": _clusters(wls, 10.0),
                        "clusters_20nm": _clusters(wls, 20.0),
                        "cost_first": costs[0],
                        "cost_last": costs[-1],
                        "cost_spread_rel": (
                            (costs[-1] - costs[0]) / costs[0] if costs[0] > 0 else float("nan")
                        ),
                    }
                )

        # --- la courbe cout(lambda) de quelques couches ---------------------------
        curves = {}
        for l in (0, 1, 12, 24, 36, num_layers - 1):
            if l < 0 or l >= num_layers:
                continue
            pts = []
            for w in range(max_W):
                if valid_mask[l, w]:
                    pts.append((float(layer_wls[l, w]), float(layer_costs[l, w])))
            pts.sort()
            curves[str(l)] = {
                "n_valid": len(pts),
                "wl": [p[0] for p in pts],
                "cost": [p[1] for p in pts],
            }

        # --- agregats --------------------------------------------------------------
        spans = [b["span_nm"] for b in per_block]
        c20 = [b["clusters_20nm"] for b in per_block]
        full = [b for b in per_block if b["n_used"] == 10]
        spans_full = [b["span_nm"] for b in full]
        c20_full = [b["clusters_20nm"] for b in full]

        def _stats(v):
            if not v:
                return None
            s = sorted(v)
            n = len(s)
            return {
                "n": n,
                "min": s[0],
                "p25": s[n // 4],
                "median": s[n // 2],
                "p75": s[(3 * n) // 4],
                "max": s[-1],
                "mean": sum(s) / n,
            }

        PROBE["result"] = {
            "num_layers": int(num_layers),
            "top_k": int(top_k),
            "max_W": int(max_W),
            "n_blocks_valid": len(per_block),
            "n_blocks_with_10": len(full),
            "span_nm_all": _stats(spans),
            "span_nm_only_full10": _stats(spans_full),
            "clusters_20nm_all": _stats(c20),
            "clusters_20nm_only_full10": _stats(c20_full),
            "curves": curves,
            "sample_blocks": per_block[:40],
        }
        return block_costs, block_wls, block_counts

    R._compute_valid_blocks_kernel = patched
    B.emit("sonde installee sur _compute_valid_blocks_kernel")


def main() -> None:
    B.qapp()
    B.autoanswer_dialogs(True)
    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")

    if "result" in PROBE:
        r = PROBE["result"]
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
        B.emit(f"PROBE_WRITTEN={OUT}")
        B.emit(f"PROBE_BLOCS_VALIDES={r['n_blocks_valid']}  AVEC_10={r['n_blocks_with_10']}")
        s = r["span_nm_only_full10"] or r["span_nm_all"]
        if s:
            B.emit(
                "PROBE_SPAN_NM (blocs a 10 candidats) "
                f"min={s['min']:.1f} p25={s['p25']:.1f} median={s['median']:.1f} "
                f"p75={s['p75']:.1f} max={s['max']:.1f}"
            )
        c = r["clusters_20nm_only_full10"] or r["clusters_20nm_all"]
        if c:
            B.emit(
                "PROBE_REGIONS_20NM sur 10 candidats "
                f"min={c['min']} median={c['median']} max={c['max']} mean={c['mean']:.2f}"
            )
    else:
        B.emit("PROBE_JAMAIS_APPELEE — le kernel n'a pas ete atteint")

    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
