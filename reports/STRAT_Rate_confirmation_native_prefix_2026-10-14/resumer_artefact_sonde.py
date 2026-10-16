"""RESUME D'UN ARTEFACT DE SONDE -- ce que les rapports du 2026-10-12 comptent, au meme endroit et de la meme facon.

    python scripts\\resumer_artefact_sonde.py reports\\blocs_vs_plantage_r75x0.5_deep_s101_....json [autre.json ...]

Pour chaque artefact de `scripts/probe_blocs_vs_plantage.py` : le commit et la configuration qui l'ont produit, le nombre de strategies et de
deposables (plantage inferieur a 5 % au pire des trois niveaux de bruit), le meilleur SEEL (2 racine(score), le score affiche par le logiciel),
puis les deposables par CLASSE de plan et la forme du meilleur plan.

Les classes : `optique pur` (aucune couche au Rate), `queue` (le Rate va de sa premiere couche a la derniere), `mixte` (de l'optique apres du
Rate : au moins deux paquets de Rate, ou un paquet qui ne va pas jusqu'au bout). Les paquets de Rate et d'optique du meilleur plan sont
numerotes a partir de 1, comme le tableau de l'interface (« L18-L75 »).

Ce que ce resume ne fait pas : il ne compare pas deux artefacts et ne dit pas si un ecart est reel (a 150 tirages la dispersion d'un meilleur
SEEL est de l'ordre de 6 %, ETAT section 2) ; il lit l'artefact, rien d'autre.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path
from typing import Any

#: Un plan est deposable quand son plantage, au pire des trois niveaux de bruit, est sous ce seuil (la porte de plantage de STRAT).
SEUIL_PLANTAGE = 0.05


def seel(score: float) -> float:
    """Le SEEL affiche par le logiciel : 2 racine(score), en nm d'erreur d'epaisseur equivalente par couche."""
    return 2.0 * math.sqrt(score)


def paquets(indices: Any) -> list[tuple[int, int]]:
    """Les paquets de couches consecutives d'un ensemble d'indices (a partir de 0), comme (premiere, derniere)."""
    runs: list[list[int]] = []
    for i in sorted({int(x) for x in indices or []}):
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return [(a, b) for a, b in runs]


def en_couches(runs: list[tuple[int, int]]) -> str:
    """Des paquets en numerotation de 1 : [(17, 74)] -> « L18-L75 »."""
    return ", ".join(f"L{a + 1}" if a == b else f"L{a + 1}-L{b + 1}" for a, b in runs) or "aucun"


def classe(rate_layers: Any, n_couches: int) -> str:
    """`optique pur`, `queue` ou `mixte` pour un jeu de couches Rate."""
    couches = sorted({int(i) for i in rate_layers or []})
    if not couches:
        return "optique pur"
    return "queue" if couches == list(range(couches[0], n_couches)) else "mixte"


def nombre_de_couches(strategies: list[dict[str, Any]]) -> int:
    """Le nombre de couches du composant : la fin du dernier bloc de n'importe quelle strategie."""
    for s in strategies:
        blocs = s.get("blocs")
        if isinstance(blocs, list) and blocs:
            return max(int(b["end"]) for b in blocs if isinstance(b, dict) and "end" in b)
    return 0


def forme_du_plan(s: dict[str, Any], n_couches: int) -> str:
    """La forme d'un plan : ses paquets de Rate, ses fenetres d'optique, ses blocs."""
    rate = paquets(s.get("rate_layers"))
    optique = paquets(sorted(set(range(n_couches)) - {i for a, b in rate for i in range(a, b + 1)}))
    blocs = ", ".join(f"{b['start'] + 1}-{b['end']} a {b['wavelength']:g} nm" for b in s.get("blocs") or [])
    return f"Rate {en_couches(rate)} ; optique {en_couches(optique)} ; {int(s.get('n_blocs', 0))} blocs ({blocs})"


def resumer(artefact: dict[str, Any]) -> dict[str, Any]:
    """Les nombres d'un artefact : une valeur par ligne du resume, sans mise en forme."""
    strategies = artefact.get("strategies") or []
    n_couches = nombre_de_couches(strategies)
    deposables = [s for s in strategies if float(s.get("crash_rate", 1.0)) < SEUIL_PLANTAGE]
    par_classe: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for s in deposables:
        par_classe[classe(s.get("rate_layers"), n_couches)].append(s)
    classes = {}
    for nom, plans in sorted(par_classe.items()):
        meilleur = min(plans, key=lambda s: float(s["score"]))
        classes[nom] = {"plans": len(plans), "meilleur_seel": seel(float(meilleur["score"])), "meilleur": meilleur}
    meilleur_global = min(deposables, key=lambda s: float(s["score"])) if deposables else None
    prov = artefact.get("provenance") or {}
    return {
        "composant": artefact.get("composant"),
        "mode": artefact.get("mode"),
        "graine": artefact.get("seed"),
        "commit": str(prov.get("git_commit", ""))[:8],
        "arbre_modifie": bool(prov.get("git_dirty")),
        "surcharges": (artefact.get("config") or {}).get("overrides"),
        "n_couches": n_couches,
        "strategies": len(strategies),
        "deposables": len(deposables),
        "plantage_minimal": min((float(s.get("crash_rate", 1.0)) for s in strategies), default=None),
        "meilleur_seel": None if meilleur_global is None else seel(float(meilleur_global["score"])),
        "meilleur": meilleur_global,
        "classes": classes,
        "paquets_de_rate": dict(sorted(collections.Counter(len(paquets(s.get("rate_layers"))) for s in deposables).items())),
    }


def texte(r: dict[str, Any]) -> str:
    """Le resume d'un artefact, en clair."""
    lignes = [
        f"{r['composant']} | {r['mode']} | graine {r['graine']} | commit {r['commit']}{' (arbre modifie)' if r['arbre_modifie'] else ''}"
        f" | surcharges {r['surcharges'] or 'aucune'}",
        f"  {r['strategies']} strategies, {r['deposables']} deposables (plantage < {SEUIL_PLANTAGE:.0%}), plantage minimal "
        + ("-" if r["plantage_minimal"] is None else f"{r['plantage_minimal']:.2%}"),
    ]
    if r["meilleur"] is None:
        lignes.append("  aucun deposable : pas de meilleur SEEL a rapporter")
        return "\n".join(lignes)
    lignes.append(f"  meilleur SEEL {r['meilleur_seel']:.4f} nm : {forme_du_plan(r['meilleur'], r['n_couches'])}")
    for nom, c in r["classes"].items():
        lignes.append(f"  {nom:12s} {c['plans']:6d} plans, meilleur SEEL {c['meilleur_seel']:.4f} nm")
    lignes.append("  paquets de Rate par plan deposable : " + ", ".join(f"{k} : {v}" for k, v in r["paquets_de_rate"].items()))
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resume d'un ou plusieurs artefacts de scripts/probe_blocs_vs_plantage.py")
    parser.add_argument("artefacts", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for chemin in args.artefacts:
        print(texte(resumer(json.loads(chemin.read_text(encoding="utf-8")))))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
