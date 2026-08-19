"""COHERENCE DE TOUS LES .md — le meme fait porte-t-il la meme valeur partout ?

    C:\\envs\\certus\\Scripts\\python.exe scripts\\coherence_md.py

👤 2026-08-19 : *« refais une passe de verification de coherence parfaite et totale de tous
les fichiers md »*.

## Ce que cet outil fait, et ce qu'aucun autre ne faisait

`check_claude_md.py` verifie **un** fichier et ne juge aucune phrase. Le balayage de renvois
verifie que les **liens** existent. Aucun des deux ne repond a la question qui a produit la
quasi-totalite des contradictions de ce depot :

    « le SEEL du 99c vaut 0,782 dans un fichier et 0,81 dans un autre »

C'est le defaut que `CLAUDE.md` §1 decrit — *« un fait, un seul endroit »* — et il se detecte
mecaniquement : pour chaque grandeur nommee, on releve TOUTES les valeurs citees dans TOUS les
.md, et on signale les desaccords.

## 🔑 ET LA VALEUR DE REFERENCE VIENT DU CODE QUAND ELLE EXISTE

Comparer les documents entre eux ne dit que s'ils sont d'accord, pas s'ils ont raison. Les
constantes de calcul sont donc lues dans les **sources**, et un document qui s'en ecarte est
signale meme si tous les autres le repetent.

## Ce qu'il ne peut PAS faire

Il ne comprend pas les phrases. Un chiffre cite pour dire *« cette valeur etait fausse »* lui
ressemble a une affirmation -- d'ou la liste `CONTEXTES_DE_CORRECTION` : une ligne qui porte
l'un de ces marqueurs est un RECIT de correction, pas une prescription, et elle est ecartee.
C'est exactement la lecon du 2026-08-19 sur le controle L de `verifier_affirmations.py`, qui
attrapait ses propres commentaires d'explication.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Une ligne portant l'un de ces marqueurs RACONTE une correction : le chiffre qu'elle cite est
#: celui qu'on retire, pas celui qu'on prescrit. L'ignorer evite un deluge de faux positifs.
CONTEXTES_DE_CORRECTION = (
    "périmé", "perime", "retiré", "retire", "faux", "réfuté", "refute", "corrigé", "corrige",
    "disait", "annonçait", "annoncait", "était", "etait", "ancien", "jusqu'au", "historique",
    "n'est plus", "ne correspondait", "portait", "avant correctif", "CADUQUE", "SUPPRIMÉE",
    "obsolète", "obsolete", "~~",
    # 🔑 Ajoutes le 2026-08-19 : une ligne qui se DECLARE non comparable, ou qui parle d'un
    # score de REPLI, n'affirme pas une performance. Les deux marqueurs sont poses a la main
    # par l'auteur, ce qui est le bon niveau : l'outil ne devine pas, il obeit a une marque.
    "non comparable", "score de repli", "non comparables",
)

#: (nom lisible, motif de CONTEXTE, motif de VALEUR, valeur de reference ou None)
#: 🔴 La valeur de reference est lue dans le CODE quand c'est possible -- voir `_du_code`.
#: 4e champ : motif d'EXCLUSION. Une ligne qui le porte parle d'AUTRE CHOSE que le fait
#: verifie -- typiquement la CIBLE a atteindre plutot que la valeur atteinte. Sans lui,
#: l'outil signale un desaccord entre deux grandeurs qui n'ont jamais eu a etre egales, et
#: un controleur qui crie toujours finit ignore.
FAITS: list[tuple[str, str, str, str]] = [
    ("SEEL du 48c",            r"48\s*(?:couches|c\b)|JSON-strat-example",  r"0,(\d{3})\s*nm", r"cible"),
    ("SEEL du 35c",            r"35\s*(?:couches|c\b)|bandpass-3cav",       r"0,(\d{3})\s*nm", r"cible"),
    ("SEEL du 75c",            r"random75`|75\s*couches",                   r"0,(\d{3})\s*nm", r"cible"),
    ("SEEL du 99c multi-temoins", r"99c|99\s*couches|5cav-99c",             r"0,(\d{2,3})\s*nm", r"cible|repli"),
    ("cible posee par le physicien", r"cible.{0,30}👤|👤.{0,30}cible",      r"0,(\d{3})\s*nm", r""),
    ("cadence machine",        r"cadence|4\s*Hz",                           r"(\d)\s*Hz", r""),
    ("pas d'echantillonnage machine", r"0,125\s*nm|un point tous les",      r"0,(\d{3})\s*nm", r""),
    ("amplitude du bruit de lecture", r"bruit de lecture|±0,05|A = 5e-4",   r"5e-(\d)", r""),
    ("fente nominale",         r"fente nominale|résolution du monochromateur", r"(\d)\s*nm", r""),
    ("objectif de rendement (👤)", r"95\s*% des d[ée]p[oô]ts|objectif du physicien", r"(\d{2})\s*%", r""),
]

#: Constantes lues dans le CODE : (nom lisible, fichier, nom de la constante, motif dans les .md)
DU_CODE: list[tuple[str, str, str, str]] = [
    ("RATE_MIN_LAYER",   "certus/core/certus_strat_robustness.py",  "RATE_MIN_LAYER",   r"RATE_MIN_LAYER"),
    ("RATE_TURN_NM",     "certus/physics/certus_strat_growth.py",   "RATE_TURN_NM",     r"RATE_TURN_NM"),
    ("RATE_MIN_LAYERS_PER_BLOCK", "certus/core/certus_strat_robustness.py",
     "RATE_MIN_LAYERS_PER_BLOCK", r"RATE_MIN_LAYERS_PER_BLOCK"),
    ("RATE_MAX_VARIANTS_PER_STRATEGY", "certus/core/certus_strat_robustness.py",
     "RATE_MAX_VARIANTS_PER_STRATEGY", r"RATE_MAX_VARIANTS_PER_STRATEGY"),
    ("RATE_SWING_MIN_DEFAULT", "certus/core/certus_strat_robustness.py",
     "RATE_SWING_MIN_DEFAULT", r"RATE_SWING_MIN_DEFAULT|dynamics_threshold"),
    ("PHOTOMETRIC_CURVATURE_AMP", "certus/physics/certus_strat_growth.py",
     "PHOTOMETRIC_CURVATURE_AMP", r"photometric_curvature_amp|PHOTOMETRIC_CURVATURE_AMP"),
]


def _md() -> list[Path]:
    fs = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md"))
    return [f for f in fs if f.exists()]


#: Une ligne qui nomme PLUSIEURS composants COMPARE, elle n'affirme pas une valeur unique.
#:
#: 🔴 IL FAUT COMPTER DES COMPOSANTS, PAS DES MOTIFS -- premiere version faite et corrigee le
#: 2026-08-19. Elle listait `dichro` et `48\s*c` cote a cote, si bien qu'une ligne parfaitement
#: saine comme « | dichroique `JSON-strat-example` | 48 | **0,173 nm** | » comptait DEUX
#: composants et se faisait ecarter. L'outil n'examinait alors que **2 lignes sur 9** pour le
#: 48c, et son « valeur unique » ne prouvait presque rien. C'est le controle negatif qui l'a
#: revele -- exactement ce pour quoi il existe.
_COMPOSANTS = {
    "48c": (r"48\s*c", r"JSON-strat-example", r"dichro"),
    "35c": (r"35\s*c", r"bandpass-3cav", r"3\s*cavit"),
    "75c": (r"75\s*c", r"random75"),
    "99c": (r"99\s*c", r"5cav-99c", r"5\s*cavit"),
}


def _un_seul_composant(ligne: str) -> bool:
    vus = {nom for nom, motifs in _COMPOSANTS.items()
           if any(re.search(m, ligne, re.I) for m in motifs)}
    return len(vus) <= 1


def _est_correction(ligne: str) -> bool:
    bas = ligne.lower()
    return any(m.lower() in bas for m in CONTEXTES_DE_CORRECTION)


def _du_code(fichier: str, nom: str):
    """La valeur d'une constante, lue par AST dans la source -- jamais par grep."""
    p = ROOT / fichier
    if not p.exists():
        return None
    try:
        arbre = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    for n in arbre.body:
        cible = None
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            cible, val = n.target.id, n.value
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            cible, val = n.targets[0].id, n.value
        if cible == nom and isinstance(val, ast.Constant):
            return val.value
    return None


def _controle_negatif() -> tuple[bool, str]:
    """Plante une contradiction VOLONTAIRE et verifie que l'outil la voit.

    🔑 CLAUDE.md : *« un harnais dont tous les tests passent toujours ne prouve rien »*. Un
    controleur qui rend 0 sur un depot sain et 0 sur un depot faux ne mesure rien du tout.
    On ecrit donc un fichier temporaire qui affirme un SEEL faux pour le 48c, on relance la
    detection, et on exige qu'elle ECHOUE. Le fichier est retire dans tous les cas.
    """
    faux = ROOT / "docs" / "_CONTROLE_NEGATIF_TEMPORAIRE.md"
    faux.write_text("| dichroique 48 couches | **0,999 nm** |\n", encoding="utf-8")
    try:
        vues = set()
        for f in _md():
            for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not re.search(r"48\s*(?:couches|c)|JSON-strat-example", l):
                    continue
                if _est_correction(l) or not _un_seul_composant(l) or re.search(r"cible", l, re.I):
                    continue
                for m in re.finditer(r"0,(\d{3})\s*nm", l):
                    vues.add(m.group(0).strip())
        return (len(vues) > 1, f"{len(vues)} valeurs vues : {sorted(vues)}")
    finally:
        faux.unlink(missing_ok=True)


def main() -> int:
    fichiers = _md()
    n_pb = 0
    print("=" * 96)
    print(f"COHERENCE DES {len(fichiers)} FICHIERS .md")
    print("=" * 96)

    print("\n=== A. LES CONSTANTES DU CODE, ET CE QUE LES DOCUMENTS EN DISENT ===")
    print("  (la reference vient de la SOURCE : un document qui s'en ecarte a tort, meme seul)")
    for lib, src, cst, motif in DU_CODE:
        ref = _du_code(src, cst)
        if ref is None:
            print(f"  🟠 {lib:<34} constante INTROUVABLE dans {src}")
            n_pb += 1
            continue
        ecarts = []
        for f in fichiers:
            for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if not re.search(motif, l) or _est_correction(l):
                    continue
                for v in re.findall(r"\*\*(\d+(?:[.,]\d+)?)\*\*|`(\d+(?:[.,]\d+)?)`", l):
                    t = (v[0] or v[1]).replace(",", ".")
                    try:
                        x = float(t)
                    except ValueError:
                        continue
                    if abs(x - float(ref)) > 1e-9 and abs(x - float(ref)) / max(1e-9, abs(float(ref))) > 0.01:
                        ecarts.append(f"{f.name}:{i} dit {t}")
        if ecarts:
            n_pb += len(ecarts)
            print(f"  🔴 {lib:<34} code = {ref} | {len(ecarts)} ecart(s) : {ecarts[:3]}")
        else:
            print(f"  🟢 {lib:<34} code = {ref} | aucun document ne le contredit")

    print("\n=== B. LES GRANDEURS PHYSIQUES : le meme fait, plusieurs valeurs ? ===")
    for lib, ctx, val, excl in FAITS:
        vues: dict[str, list[str]] = {}
        for f in fichiers:
            for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if not re.search(ctx, l) or _est_correction(l):
                    continue
                # 🔴 Sans cette garde, « SEEL 0,583 sur 35c et 0,173 sur 48c » declenche DEUX
                # faux positifs. Une ligne qui compare n'affirme pas.
                if lib.startswith("SEEL") and not _un_seul_composant(l):
                    continue
                if excl and re.search(excl, l, re.I):
                    continue
                for m in re.finditer(val, l):
                    vues.setdefault(m.group(0).strip(), []).append(f"{f.name}:{i}")
        if len(vues) > 1:
            n_pb += 1
            detail = " | ".join(f"{k} ({len(v)}x, ex. {v[0]})" for k, v in sorted(vues.items())[:4])
            print(f"  🟠 {lib:<32} {len(vues)} valeurs : {detail}")
        elif vues:
            k = next(iter(vues))
            print(f"  🟢 {lib:<32} valeur unique {k} ({len(vues[k])} citation(s))")
        else:
            print(f"  ·  {lib:<32} aucune citation trouvee")

    ok, det = _controle_negatif()
    print("\n=== C. CONTROLE NEGATIF -- l'outil sait-il seulement DETECTER ? ===")
    if ok:
        print(f"  🟢 contradiction plantee DETECTEE ({det}) -- l'outil mord")
    else:
        n_pb += 1
        print(f"  🔴 contradiction plantee NON DETECTEE ({det}) -- LE HARNAIS EST CASSE,")
        print("     et son « 0 point a instruire » ne veut plus rien dire.")

    print("\n" + "=" * 96)
    print(f"  {n_pb} point(s) a instruire.")
    print("  ⚠️ Un signalement n'est PAS une erreur : c'est une phrase a LIRE. L'outil ne")
    print("     comprend pas le francais, il rapproche un mot et un nombre.")
    print("=" * 96)
    return 0 if n_pb == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
