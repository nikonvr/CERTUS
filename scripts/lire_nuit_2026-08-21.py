"""LIRE LE BATCH DE LA NUIT DU 2026-08-21, et appliquer la regle de decision ECRITE D'AVANCE.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_nuit_2026-08-21.py

## 🔑 CE QUE CE SCRIPT FAIT, ET POURQUOI IL EXISTE SEPAREMENT DU BATCH

La regle de decision de la question de fond est ecrite en **§8.2ter de
`docs/REPRENDRE_ICI.md`**, AVANT la mesure, precisement pour ne pas etre reinterpretee selon le
resultat. Ce script l'applique mecaniquement.

    r75x2 NU (sans rampes), graines 101 et 202

    les DEUX trouvent   -> la graine 42 est MALCHANCEUSE. Le multiseed de GENERATION est la
                           reponse produit : union sur K graines, faisabilite exigee sur TOUTES.
    UNE SEULE trouve    -> la recherche reussit ~1 fois sur 2. Meme conclusion, K plus grand.
    AUCUNE ne trouve    -> la graine 77 est CHANCEUSE. 🔴 Mais NE CONCLUS PAS que la
                           decouverte autonome est impossible : la QUEUE RATE trouve seule a
                           2 nm, SEEL 0,67-0,69 (CHANTIER_RATE.md §3bis). L'enonce juste est
                           « aucune voie autonome n'atteint 0,57 EN PUR OPTIQUE ». Reponse
                           produit : les rampes pour 0,57, la queue Rate pour un niveau
                           degrade mais autonome. CE N'EST PAS UN ECHEC.

📌 Le contexte, a garder en tete : sur `r75x2` a 2 nm on ne dispose que de DEUX graines mesurees
nues -- la 77 rend 547 deposables, la 42 en rend ZERO sur 1617.

## 🔴 IL REFUSE DE CONCLURE SUR DU PARTIEL, ET C'EST LE PLUS IMPORTANT

📏 Lecon du 2026-08-21 : un analyseur qui conclut sur des donnees incompletes avait rendu un
verdict sur UN SEUL nombre de blocs degenere. Ici :

  - un artefact manquant ou de verdict non-OK **suspend** le verdict, il ne compte pas pour zero
  - un artefact **sans le detail des blocs** est ecarte -- c'est le troisieme etat, « a remesurer »
  - la regle ne s'applique QUE si les DEUX graines nues ont un artefact exploitable
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

#: 👤 La porte : 95 % des depositions doivent se terminer.
TOLERANCE = 0.05

#: Les quatre mesures de la nuit. `(composant, graine, role)`.
ATTENDUES = [
    ("r75x2", 101, "nu"),
    ("r75x2", 202, "nu"),
    ("r75x2-2nm", 101, "livree"),
    ("r75x2-2nm", 202, "livree"),
]

#: Les trois repere deja acquis, pour situer ce que la nuit rend.
REPERES = {
    "graine 42, config livree": 0.5676,
    "graine 77, nu (source)": 0.5692,
    "graine 101, config livree (journal du 21/08)": 0.5707,
}


def _artefact(composant: str, graine: int) -> Path | None:
    """Le plus recent artefact `deep` de ce couple. Le nom canonique ne suffit pas."""
    motif = f"blocs_vs_plantage_{composant}_deep_s{graine:03d}*.json"
    cands = sorted(
        (ROOT / "reports").glob(motif), key=lambda q: q.stat().st_mtime, reverse=True
    )
    return cands[0] if cands else None


def _lire(chemin: Path) -> dict:
    """Rend un etat explicite. `None` n'est pas une reponse, c'est une absence de reponse."""
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"etat": "ILLISIBLE", "detail": f"{type(e).__name__}"}
    if d.get("verdict") != "OK":
        return {"etat": "VERDICT_NON_OK", "detail": str(d.get("verdict"))}
    st = d.get("strategies") or []
    if not st:
        return {"etat": "VIDE", "detail": "aucune strategie"}
    if not all(s.get("blocs") for s in st):
        # 🔴 Le troisieme etat : ni sterile, ni fecond -- A REMESURER.
        return {"etat": "SANS_PLANS", "detail": f"{len(st)} strategies, blocs manquants"}
    dep = [s for s in st if (s.get("crash_rate") or 1.0) <= TOLERANCE]
    scores = [s["score"] for s in dep if isinstance(s.get("score"), (int, float))]
    return {
        "etat": "OK",
        "n_strats": len(st),
        "n_dep": len(dep),
        "seel": 2.0 * math.sqrt(min(scores)) if scores else None,
        "blocs_dep": sorted({s.get("n_blocs") for s in dep}),
        "crash_min": min((s.get("crash_rate") or 1.0) for s in dep) if dep else None,
        "fichier": chemin.name,
    }


def main() -> int:
    print("=" * 78)
    print("BATCH DE LA NUIT DU 2026-08-21 -- LECTURE")
    print("=" * 78)
    res: dict[tuple[str, int], dict] = {}
    for comp, graine, role in ATTENDUES:
        a = _artefact(comp, graine)
        if a is None:
            res[(comp, graine)] = {"etat": "ABSENT", "detail": "aucun artefact"}
        else:
            res[(comp, graine)] = _lire(a)
        r = res[(comp, graine)]
        tete = f"{comp:<11} graine {graine:>3} ({role})"
        if r["etat"] != "OK":
            print(f"  🟠 {tete} : {r['etat']} -- {r.get('detail', '')}")
            continue
        seel = f"{r['seel']:.4f} nm" if r["seel"] is not None else "aucun score"
        print(f"  {'🟢' if r['n_dep'] else '🔴'} {tete} : {r['n_strats']:>5} strategies · "
              f"{r['n_dep']:>4} deposables · meilleur SEEL {seel}")
        if r["n_dep"]:
            print(f"       blocs porteurs {r['blocs_dep']} · crash min {r['crash_min']:.2%}")
        print(f"       {r['fichier']}")

    # ── LA REGLE DE DECISION, appliquee mecaniquement ─────────────────────
    print()
    print("=" * 78)
    print("LA QUESTION DE FOND -- regle ecrite AVANT la mesure (§8.2ter de REPRENDRE_ICI.md)")
    print("=" * 78)
    nus = [res[("r75x2", g)] for g in (101, 202)]
    exploitables = [r for r in nus if r["etat"] == "OK"]

    if len(exploitables) < 2:
        print("  🟠 VERDICT SUSPENDU. La regle exige les DEUX graines nues exploitables.")
        for g, r in zip((101, 202), nus):
            print(f"     graine {g} : {r['etat']}")
        print("  🔴 Ne compte PAS un artefact manquant comme un zero : c'est une absence de")
        print("     donnee, pas un resultat. C'est la lecon de l'analyseur du 2026-08-21, qui")
        print("     avait conclu sur un seul nombre de blocs degenere.")
    else:
        trouvent = [g for g, r in zip((101, 202), nus) if r["n_dep"] > 0]
        if len(trouvent) == 2:
            print("  🟢 LES DEUX GRAINES NUES TROUVENT.")
            print("     -> la graine 42 est MALCHANCEUSE.")
            print("     -> le MULTISEED DE GENERATION est la reponse produit : union sur K")
            print("        graines, faisabilite exigee sur TOUTES -- ce n'est pas du seed")
            print("        hacking, c'est une exigence de robustesse PLUS FORTE qu'aujourd'hui.")
            print("     -> K peut etre petit.")
        elif len(trouvent) == 1:
            print(f"  🟠 UNE SEULE TROUVE (graine {trouvent[0]}).")
            print("     -> la recherche reussit environ une fois sur deux.")
            print("     -> meme conclusion : multiseed de generation, mais K plus grand.")
        else:
            print("  🔴 AUCUNE DES DEUX NE TROUVE.")
            print("     -> la graine 77 est CHANCEUSE, pas la 42 malchanceuse.")
            print()
            print("     🔴 NE CONCLUS PAS « la decouverte autonome est impossible ».")
            print("        C'est ce que cette sortie disait, et c'etait FAUX : la QUEUE RATE")
            print("        trouve seule a 2 nm, SEEL 0,6717 en premium et 0,6859 en deep, sans")
            print("        aucune rampe (CHANTIER_RATE.md §3bis, mesure du 2026-08-20).")
            print()
            print("     La conclusion correcte est :")
            print("        aucune voie autonome n'atteint le niveau de 0,57 EN PUR OPTIQUE ;")
            print("        la seule qui trouve sans rampe plafonne a 0,67-0,69, soit +18 %.")
            print()
            print("     -> pour le niveau de 0,57 : `scripts/generer_rampes.py`")
            print("     -> pour un niveau degrade mais AUTONOME : la queue Rate")
            print("     CE N'EST PAS UN ECHEC : une bibliotheque de rampes plus une procedure")
            print("     scriptee pour en fabriquer est une reponse produit legitime.")
            print()
            print("     ⚠️ Et le contexte qui borne tout : a la resolution NATIVE de ce fichier")
            print("        (1 nm), le pur optique rend 277 deposables a SEEL 0,6248. Tout ce")
            print("        travail decrit le composant tourne a LA MOITIE de sa resolution.")

    # ── LE CHIFFRE LIVRE, situe parmi les reperes ─────────────────────────
    print()
    print("=" * 78)
    print("LE CHIFFRE LIVRE -- convergence entre realisations")
    print("=" * 78)
    for nom, v in REPERES.items():
        print(f"  {nom:<46} SEEL {v:.4f} nm")
    neufs = [(g, res[("r75x2-2nm", g)]) for g in (101, 202)]
    for g, r in neufs:
        if r["etat"] == "OK" and r["seel"] is not None:
            print(f"  {'graine ' + str(g) + ', config livree (cette nuit)':<46} "
                  f"SEEL {r['seel']:.4f} nm")
    tous = list(REPERES.values()) + [
        r["seel"] for _g, r in neufs if r["etat"] == "OK" and r["seel"] is not None
    ]
    if len(tous) >= 2:
        etendue = (max(tous) - min(tous)) / min(tous)
        print(f"\n  etendue sur {len(tous)} realisations : {etendue:.2%}")
        print("  ⚠️ a comparer au bruit de 2,59 % sur une DIFFERENCE de SEEL (§24-26). En")
        print("     dessous, les realisations sont INDISCERNABLES -- c'est le resultat voulu.")
        if etendue > 0.0259:
            print("  🔴 ETENDUE SUPERIEURE AU BRUIT : les realisations ne convergent PAS.")
            print("     Le chiffre livre depend alors de la graine, et il faut le republier")
            print("     comme une fourchette et non comme une valeur.")

    print()
    print("=" * 78)
    print("CE QUE CETTE LECTURE NE DIT PAS")
    print("=" * 78)
    print("  Tout porte sur `r75x2` a 2 nm -- UN empilement, UNE fente. 👤 a fixe ce perimetre")
    print("  le 2026-08-21 (« on reste sur le 75cx2 »). Aucune affirmation de GENERALITE n'est")
    print("  permise : voir §8.2bis de docs/REPRENDRE_ICI.md pour les formulations autorisees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
