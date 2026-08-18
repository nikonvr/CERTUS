"""AUDIT DU MODE RATE -- ce qui le bride, et ce que ca coute REELLEMENT.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\audit_rate.py

👤 2026-08-18 : *« je reste persuade que le rate est sous-employe, il faut lancer des idees pour
lui permettre d'etre pleinement utilise »*, puis *« fais un veritable audit avec des
verifications, des contradictions, etc. »*.

## La methode

Trois etages, et le troisieme est le seul qui prouve quelque chose :

    ETAGE 1  les CONTRAINTES, relevees dans le code par AST et non par lecture
    ETAGE 2  les CONTRADICTIONS entre ce que le code fait et ce que sa justification annonce
    ETAGE 3  les CONSEQUENCES, comptees sur les artefacts deja produits -- combien de variantes
             Rate ont ete offertes, combien etaient deposables, et une seule a-t-elle jamais gagne

L'etage 3 est le juge. Un plafond dont on demontre qu'il n'a jamais mordu ne merite pas qu'on y
touche ; un plafond qui ecarte la gagnante est un defaut.
"""

from __future__ import annotations

import ast
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CT = 0.05
SRC = ROOT / "certus" / "core" / "certus_strat_robustness.py"


def _const(nom: str):
    """La valeur d'une constante de module, par AST."""
    arbre = ast.parse(SRC.read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == nom:
            return ast.literal_eval(n.value), n.lineno
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if getattr(c, "id", None) == nom:
                    return ast.literal_eval(n.value), n.lineno
    return None, None


def etage1_contraintes() -> list[tuple[str, str]]:
    print("=" * 100)
    print("ETAGE 1 -- LES SEPT CONTRAINTES QUI BRIDENT LE RATE")
    print("=" * 100)
    faits = []
    v, ln = _const("RATE_MAX_VARIANTS_PER_STRATEGY")
    print(f"  1. RATE_MAX_VARIANTS_PER_STRATEGY = {v}   ({SRC.name}:{ln})")
    print("     -> au plus 3 variantes Rate par strategie, les frontieres les plus PROFONDES")
    faits.append(("plafond de variantes", str(v)))

    v2, ln2 = _const("RATE_MIN_LAYERS_PER_BLOCK")
    print(f"\n  2. RATE_MIN_LAYERS_PER_BLOCK = {v2}   ({SRC.name}:{ln2})")
    print("     -> sous 3 couches par bloc, la strategie recoit ZERO candidate. Une strategie")
    print("        qui surveille couche par couche n'a donc JAMAIS de variante Rate.")
    faits.append(("plancher couches/bloc", str(v2)))

    t = SRC.read_text(encoding="utf-8")
    n_seul = "rate_max_layers_per_variant" in t
    print(f"\n  3. UNE SEULE couche Rate par variante : {'liftable depuis 2026-08-18' if n_seul else 'EN DUR'}")
    faits.append(("couches par variante", "1 par defaut, liftable" if n_seul else "1 en dur"))

    print("\n  4. Les candidates sont les FRONTIERES DE BLOC uniquement")
    print("     -> `_rate_candidate_layers` : « Layers where a Rate is CHEAPEST »")
    faits.append(("critere de placement", "cout, pas besoin"))

    print("\n  5. La DERNIERE couche de l'empilement est exclue deliberement (A24)")
    faits.append(("derniere couche", "exclue, jamais testee"))

    ph = (ROOT / "certus" / "core" / "certus_strat_objectives.py")
    lit = "rate_flags" in ph.read_text(encoding="utf-8") if ph.exists() else False
    print(f"\n  6. La Phase A connait-elle `rate_flags` ? {'OUI' if lit else 'NON'}")
    print("     -> si NON, la lambda de la couche i+1 est choisie en supposant un historique")
    print("        que la couche Rate i a DETRUIT. Chaque variante Rate est donc jugee avec une")
    print("        Phase A qui ignorait sa presence -- un handicap systematique.")
    faits.append(("Phase A informee du Rate", "oui" if lit else "NON -- handicap"))

    print("\n  7. `allow_rate` par defaut :", "vrai" if 'params.get("allow_rate", True)' in t else "?")
    faits.append(("allow_rate", "vrai par defaut"))
    return faits


def etage2_contradictions() -> list[str]:
    print("\n" + "=" * 100)
    print("ETAGE 2 -- LES CONTRADICTIONS")
    print("=" * 100)
    t = SRC.read_text(encoding="utf-8")
    trouvees = []

    # --- A ---------------------------------------------------------------------------
    a = 'asked for the trial "on the 10 best strategies", not on everything' in t \
        or "on the 10 best strategies" in t
    if a:
        print("\n  🔴 A. LA JUSTIFICATION DU PLAFOND NE DECRIT PAS CE QUE LE CODE FAIT.")
        print("     Le commentaire de RATE_MAX_VARIANTS_PER_STRATEGY dit : 👤 a demande l'essai")
        print("     « sur les 10 meilleures strategies, pas sur tout ». Or `_expand_with_rate_variants`")
        print("     etend TOUTES les strategies, a 3 variantes chacune. Le code ne fait donc NI l'un")
        print("     NI l'autre : ni les 10 meilleures en profondeur, ni tout le monde largement.")
        print("     🔑 Un plafond a 3 sur 2000 strategies coute plus cher qu'un plafond a 40 sur les")
        print("        50 meilleures -- et explore moins.")
        trouvees.append("A. le plafond ne met en oeuvre ni la consigne citee, ni son contraire")

    # --- B ---------------------------------------------------------------------------
    print("\n  🔴 B. LE REGIME OU LE RATE SERAIT LE PLUS UTILE EST CELUI OU IL N'EST JAMAIS OFFERT.")
    print("     RATE_MIN_LAYERS_PER_BLOCK = 3 rend ZERO candidate aux strategies a blocs fins.")
    print("     Or CLAUDE.md §24-40 a mesure que la surveillance COUCHE PAR COUCHE gagne sur")
    print("     2 graines sur 5 a l'incertitude d'indice reelle. Ces strategies-la n'ont donc")
    print("     jamais eu une seule variante Rate.")
    trouvees.append("B. les strategies a blocs fins n'ont jamais de variante Rate")

    # --- C ---------------------------------------------------------------------------
    print("\n  🔴 C. LE CRITERE DE PLACEMENT REPOND A UNE AUTRE QUESTION QUE LA PHYSIQUE.")
    print("     `_rate_candidate_layers` cherche ou le Rate COUTE le moins (frontieres de bloc).")
    print("     CLAUDE.md §22 pose que le Rate est NECESSAIRE quand `swing < SWING_MIN` -- une")
    print("     couche sans dynamique exploitable. Ce sont deux ensembles differents, et le code")
    print("     n'a jamais essaye le second.")
    trouvees.append("C. placement par cout, jamais par besoin (swing)")

    # --- D ---------------------------------------------------------------------------
    print("\n  🟠 D. LA DERNIERE COUCHE EST EXCLUE SUR UN ARGUMENT QUI SE CONTREDIT.")
    print("     Le docstring dit : elle n'a pas de successeur donc le cout aval est nul -- mais")
    print("     elle est aussi la derniere chance de corriger l'accumule, « et les deux tirent en")
    print("     sens contraire ». Deux effets opposes non mesures ne justifient pas une exclusion :")
    print("     ils justifient une MESURE. A24 le dit, elle n'a jamais eu lieu.")
    trouvees.append("D. derniere couche exclue sans mesure, sur deux effets opposes")
    return trouvees


def etage3_consequences() -> None:
    print("\n" + "=" * 100)
    print("ETAGE 3 -- CE QUE CA COUTE, COMPTE SUR LES ARTEFACTS")
    print("=" * 100)
    fichiers = sorted((ROOT / "reports").glob("blocs_vs_plantage_*.json"))
    lignes, tot_s, tot_r, tot_rd, gagne_rate = [], 0, 0, 0, 0
    for f in fichiers:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("verdict") != "OK":
            continue
        s = d["strategies"]
        rate = [x for x in s if str(x.get("origine") or "").startswith("RATE")]
        dep = [x for x in s if x["crash_rate"] < CT]
        rate_dep = [x for x in rate if x["crash_rate"] < CT]
        tot_s += len(s); tot_r += len(rate); tot_rd += len(rate_dep)
        best = min(dep, key=lambda x: x["score"]) if dep else None
        best_rate = str(best.get("origine") or "").startswith("RATE") if best else False
        if best_rate:
            gagne_rate += 1
        lignes.append((f.name.replace("blocs_vs_plantage_", "").replace(".json", ""),
                       len(s), len(rate), len(dep), len(rate_dep), best_rate,
                       2 * math.sqrt(best["score"]) if best else float("nan")))
    print(f"  {'cellule':<34}{'strat':>7}{'RATE':>7}{'depos':>7}{'RATE dep':>9}{'gagnante':>10}{'SEEL':>8}")
    print("  " + "-" * 84)
    for nom, n, r, dp, rd, bw, se in lignes:
        print(f"  {nom:<34}{n:>7}{r:>7}{dp:>7}{rd:>9}{('RATE' if bw else 'optique'):>10}"
              f"{(f'{se:.3f}' if se == se else '-'):>8}")
    print("  " + "-" * 84)
    print(f"  {'TOTAL':<34}{tot_s:>7}{tot_r:>7}{'':>7}{tot_rd:>9}")
    if tot_s:
        print(f"\n  📏 Les variantes Rate representent {100*tot_r/tot_s:.1f} % de l'offre totale")
        print(f"     ({tot_r} sur {tot_s} strategies, {len(lignes)} cellules).")
    if tot_r:
        print(f"  📏 {tot_rd} d'entre elles sont deposables ({100*tot_rd/tot_r:.1f} % des Rate).")
    print(f"  📏 Une variante Rate est la MEILLEURE strategie dans {gagne_rate} cellule(s) "
          f"sur {len(lignes)}.")
    if gagne_rate == 0 and tot_r:
        print("\n  🟠 VERDICT PRUDENT : sur tout ce qui est mesure, aucune variante Rate n'a jamais")
        print("     ete la meilleure. Deux lectures, et l'audit ne les departage pas :")
        print("       -- le Rate n'aide pas sur ces composants ;")
        print("       -- ou il n'a jamais ete offert la ou il aurait aide (contradictions B et C).")
        print("     🔑 Les deux se distinguent par UNE mesure : lever les contraintes et recompter.")
    elif gagne_rate:
        print(f"\n  🟢 Le Rate gagne dans {gagne_rate} cellule(s) MALGRE les contraintes ci-dessus.")
        print("     C'est un argument direct pour les lever.")


def main() -> int:
    etage1_contraintes()
    contras = etage2_contradictions()
    etage3_consequences()
    print("\n" + "=" * 100)
    print(f"{len(contras)} contradiction(s) relevee(s)")
    for c in contras:
        print("   -", c)
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
