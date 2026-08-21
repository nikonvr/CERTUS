"""LE PLANTAGE VARIE-T-IL AVEC LE BRUIT, ET DANS LE BON SENS ?

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_plantage_vs_sigma.py <artefact.json>

## 🔴 POURQUOI CETTE SONDE EXISTE — une anomalie MESUREE, pas soupconnee

📏 Le 2026-08-21, sur l'artefact d'acceptation de `r75x2` a 2 nm (1810 strategies, graine 42) :

    sur les 197 deposables   :  125 DECROISSANTES ·  61 croissantes ·   11 plates
    sur les 1810 strategies  :  532 DECROISSANTES ·  61 croissantes · 1217 plates

**8,7 contre 1 dans le mauvais sens.** Le taux de plantage DECROIT quand le bruit croit, et ce
n'est pas du bruit de comptage : c'est systematique.

⚠️ J'avais d'abord ecarte l'anomalie par un argument de Poisson -- « 5 plantages contre 1 et 1
sur 300 tirages, donc a la limite de la statistique de comptage ». **Retire.** C'etait
substituer un raisonnement sur le bruit au test que le Piege 1 prescrit, et `CLAUDE.md` §7 dit
que ce projet a deja paye trois fois pour cela.

## 🔑 CE QUE CETTE SONDE FAIT, ET CE QU'ELLE NE FAIT PAS

Elle **lit un artefact deja produit** et classe chaque strategie selon le sens de variation de
son `crash_rate` avec le niveau de bruit. Elle ne relance aucun calcul : les trois niveaux
(0,5x, 1x, 2x du nominal) sont deja dans `crash_rates_by_noise`.

🔴 **Elle ne dit donc PAS pourquoi.** Elle etablit l'ampleur et la systematicite, et elle
separe les causes possibles autant que la donnee le permet -- rien de plus. Un candidat
mecanique existe et reste a tester : le seuil d'hysteresis vaut `tp_hysteresis_factor x A` ; si
`A` suit le multiplicateur de bruit, le detecteur devient plus CONSERVATEUR quand le bruit
croit, fabrique moins de faux points tournants, et `TP_MISCOUNT` -- 79 % des plantages mesures
(§24-36) -- recule. **A mesurer, pas a conclure.**

## ⚠️ CE QUE L'ANOMALIE CHANGE, EXACTEMENT

La porte de plantage prend le **maximum** des trois niveaux. Un taux publie vient donc du niveau
**le plus severe**, quel qu'il soit -- lecture conservatrice. **Le verdict « deposable » n'est
pas menace : il est pessimiste.** Ce qui est perdu est la comprehension du mode d'echec, et cela
touche toute mesure de plantage du projet, murs a 100 % compris.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

#: La porte de 👤 : 95 % des depositions doivent se terminer.
TOLERANCE = 0.05


def _sens(taux: list[float]) -> str:
    """Le sens de variation, du bruit le plus faible au plus fort."""
    if taux[0] < taux[-1]:
        return "croissant"
    if taux[0] > taux[-1]:
        return "DECROISSANT"
    return "plat"


def _lire(chemin: Path) -> list[dict]:
    d = json.loads(chemin.read_text(encoding="utf-8"))
    return d.get("strategies") or []


def analyser(strats: list[dict]) -> None:
    par_niveau: dict[str, list[float]] = {}
    sens_tous: Counter = Counter()
    sens_dep: Counter = Counter()
    # 🔑 On separe les strategies MURES (100 % partout) des autres : une strategie qui plante
    # toujours ne peut pas varier, et la compter en « plat » noierait le signal.
    n_mur = 0

    for s in strats:
        r = s.get("crash_rates_by_noise") or {}
        if len(r) < 2:
            continue
        cles = sorted(r, key=float)
        taux = [float(r[k]) for k in cles]
        for k in cles:
            par_niveau.setdefault(k, []).append(float(r[k]))
        if all(t >= 0.999 for t in taux):
            n_mur += 1
            continue
        sens_tous[_sens(taux)] += 1
        if (s.get("crash_rate") or 0.0) <= TOLERANCE:
            sens_dep[_sens(taux)] += 1

    print("=" * 78)
    print("A. LE TAUX MOYEN CROIT-IL AVEC LE BRUIT ?")
    print("=" * 78)
    print(f"  {'niveau':>10} {'n':>6} {'moyenne':>10} {'median':>10}")
    for k in sorted(par_niveau, key=float):
        v = sorted(par_niveau[k])
        med = v[len(v) // 2]
        print(f"  {k:>10} {len(v):>6} {sum(v)/len(v):>10.4f} {med:>10.4f}")
    niveaux = sorted(par_niveau, key=float)
    if len(niveaux) >= 2:
        a, b = par_niveau[niveaux[0]], par_niveau[niveaux[-1]]
        moy_a, moy_b = sum(a) / len(a), sum(b) / len(b)
        verdict = "🟢 CROISSANT, attendu" if moy_b > moy_a else "🔴 DECROISSANT, ANOMALIE"
        print(f"\n  {verdict} : {moy_a:.4f} (bruit {niveaux[0]}) -> {moy_b:.4f} "
              f"(bruit {niveaux[-1]})")

    print()
    print("=" * 78)
    print("B. STRATEGIE PAR STRATEGIE -- les murs a 100 % sont ECARTES")
    print("=" * 78)
    print(f"  murs a 100 % ecartes : {n_mur}")
    tot = sum(sens_tous.values())
    for nom, n in sens_tous.most_common():
        print(f"  {nom:>14} {n:>6}  ({n/tot:.1%} des {tot} qui varient)")
    if sens_tous["DECROISSANT"] and sens_tous["croissant"]:
        rap = sens_tous["DECROISSANT"] / sens_tous["croissant"]
        print(f"\n  rapport DECROISSANT / croissant = {rap:.2f}")
        if rap > 2.0:
            print("  🔴 SYSTEMATIQUE. Le Piege 1 s'applique : une grandeur de bruit qui ne")
            print("     croit pas avec le bruit designe l'ALGORITHME, pas le phenomene.")
        else:
            print("  🟠 les deux sens coexistent : pas de conclusion tiree d'ici.")

    if sens_dep:
        print()
        print("=" * 78)
        print(f"C. ET SUR LES DEPOSABLES SEULES (crash_max <= {TOLERANCE:.0%})")
        print("=" * 78)
        t = sum(sens_dep.values())
        for nom, n in sens_dep.most_common():
            print(f"  {nom:>14} {n:>6}  ({n/t:.1%})")

    print()
    print("=" * 78)
    print("D. CONTROLE NEGATIF -- la sonde sait-elle DETECTER ?")
    print("=" * 78)
    faux = [
        ("croissant", [0.01, 0.02, 0.05]),
        ("DECROISSANT", [0.05, 0.02, 0.01]),
        ("plat", [0.03, 0.03, 0.03]),
    ]
    ok = all(_sens(v) == attendu for attendu, v in faux)
    print(f"  trois profils plantes, tous reconnus : {'🟢 oui' if ok else '🔴 NON'}")
    if not ok:
        for attendu, v in faux:
            print(f"     {v} -> {_sens(v)} (attendu {attendu})")

    print()
    print("=" * 78)
    print("🔴 CE QUE CETTE SONDE NE DIT PAS")
    print("=" * 78)
    print("  Elle etablit l'ampleur et la systematicite. Elle ne dit RIEN de la cause.")
    print("  Candidat a tester : le seuil d'hysteresis vaut tp_hysteresis_factor x A ; si A")
    print("  suit le multiplicateur de bruit, le detecteur devient plus conservateur quand le")
    print("  bruit croit. A MESURER, pas a conclure.")
    print()
    print("  La porte prend le MAXIMUM des niveaux : un taux publie vient du niveau le plus")
    print("  severe. Le verdict « deposable » n'est pas menace -- il est pessimiste.")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage : probe_plantage_vs_sigma.py <artefact.json>")
        print("\nartefacts disponibles, les plus recents :")
        for f in sorted(
            (ROOT / "reports").glob("blocs_vs_plantage_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:8]:
            print(f"   {f.relative_to(ROOT)}")
        return 2
    chemin = Path(sys.argv[1])
    if not chemin.is_absolute():
        chemin = ROOT / chemin
    if not chemin.is_file():
        print(f"🔴 {chemin} introuvable.")
        return 2
    strats = _lire(chemin)
    if not strats:
        print(f"🔴 {chemin.name} ne porte aucune strategie.")
        return 1
    print(f"\n{chemin.name} -- {len(strats)} strategies\n")
    analyser(strats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
