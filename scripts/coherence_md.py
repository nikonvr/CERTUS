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
    # Ajoute le 2026-08-19 : une ligne qui dit qu'une chose N'EXISTE PAS ne la
    # prescrit evidemment pas. Sans ce marqueur, le controle E signalait le recit
    # de sa propre trouvaille.
    "n'existe pas", "n'existe **pas**", "inexecutable", "inexecutables",
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


def _fonction_englobante(f: Path, ligne: int) -> str | None:
    """Le nom de la fonction (ou classe) qui CONTIENT cette ligne, ou None."""
    try:
        arbre = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    meilleur = None
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fin = getattr(n, "end_lineno", None) or n.lineno
            if n.lineno <= ligne <= fin:
                # la plus INTERNE gagne : une methode plutot que sa classe
                if meilleur is None or n.lineno > meilleur[0]:
                    meilleur = (n.lineno, n.name)
    return meilleur[1] if meilleur else None


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


# --------------------------------------------------------------------------- #
#  EXTENSION DU 2026-08-19 -- 👤 : « lance l'extension »
#
#  🔑 LE PRINCIPE : ne PAS enumerer les faits a la main. Une liste ecrite a la main se
#  perime exactement comme les chiffres qu'elle surveille -- c'est ce qui est arrive a
#  « 2 450 tests » quatre fois de suite. Les deux balayages ci-dessous DECOUVRENT ce qu'il
#  y a a verifier, donc ils grandissent tout seuls quand un document cite un symbole de
#  plus.
# --------------------------------------------------------------------------- #

def _symboles_du_code() -> dict[str, set]:
    """Toute affectation `NOM = <litteral numerique>` dans `certus/`, module OU locale.

    ⚠️ Les locales comptent, et il le faut : `NPTS = 64` et `NPTS_PREV = 16` sont des
    variables de fonction dans le noyau, et ce sont pourtant deux des chiffres les plus
    cites du projet (§24-22). Se limiter aux constantes de module en manquerait la moitie.

    Un nom affecte a DEUX valeurs differentes est rendu tel quel : le comparateur le
    signalera comme ambigu plutot que de choisir, parce que choisir serait deviner.
    """
    out: dict[str, set] = {}
    for p in (ROOT / "certus").rglob("*.py"):
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(arbre):
            cible = val = None
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                cible, val = n.target.id, n.value
            elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                cible, val = n.targets[0].id, n.value
            if (cible and len(cible) > 3 and cible.upper() == cible
                    and isinstance(val, ast.Constant)
                    and isinstance(val.value, (int, float)) and not isinstance(val.value, bool)):
                out.setdefault(cible, set()).add(float(val.value))
    return out


def _profondeurs_par_mode() -> dict[str, dict[str, float]]:
    """La table `mode -> profondeurs`, lue dans les branches `if mode == ...` de l'interface.

    🔑 C'est la seule source de verite pour « fast = 50 tirages » etc., et ce document l'a
    ecrit faux au moins une fois (« 50 -> 150 tirages », retire le 2026-08-18).
    """
    p = ROOT / "certus" / "ui" / "certus_strat_ui_state.py"
    if not p.exists():
        return {}
    try:
        arbre = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {}
    out: dict[str, dict[str, float]] = {}

    def _lit(corps, cible: dict[str, float]) -> None:
        for st in corps:
            if (isinstance(st, ast.Assign) and len(st.targets) == 1
                    and isinstance(st.targets[0], ast.Subscript)
                    and isinstance(st.targets[0].slice, ast.Constant)
                    and isinstance(st.value, ast.Constant)
                    and isinstance(st.value.value, (int, float))):
                cible[str(st.targets[0].slice.value)] = float(st.value.value)

    for n in ast.walk(arbre):
        if not isinstance(n, ast.If) or not isinstance(n.test, ast.Compare):
            continue
        g = n.test.comparators[0] if n.test.comparators else None
        if not (isinstance(g, ast.Constant) and g.value in ("fast", "premium", "deep", "extreme")):
            continue
        # ⚠️ `premium` n'a PAS de branche a lui : c'est le `else` de la chaine, donc le mode
        # PAR DEFAUT. Le rater ferait croire que le triplet 50/150/300 n'est verifiable qu'aux
        # deux bouts -- alors que la valeur du milieu est dans le code, juste ailleurs.
        if g.value == "fast" and n.orelse:
            queue = n.orelse
            while len(queue) == 1 and isinstance(queue[0], ast.If):
                queue = queue[0].orelse
            if queue:
                _lit(queue, out.setdefault("premium", {}))
        d = out.setdefault(g.value, {})
        for st in n.body:
            if (isinstance(st, ast.Assign) and len(st.targets) == 1
                    and isinstance(st.targets[0], ast.Subscript)
                    and isinstance(st.targets[0].slice, ast.Constant)
                    and isinstance(st.value, ast.Constant)
                    and isinstance(st.value.value, (int, float))):
                d[str(st.targets[0].slice.value)] = float(st.value.value)
    return out


def _sweep_symboles(fichiers, sym) -> tuple[int, int]:
    """Les documents qui ecrivent `NOM = N` disent-ils la valeur du code ?

    Motifs reconnus : `NOM = 4`, **NOM** vaut 4, `NOM` a 4, NOM : 4.
    """
    n_ok = n_ko = n_nc = 0
    noms = "|".join(re.escape(k) for k in sorted(sym, key=len, reverse=True))
    rx = re.compile(r"`?\*{0,2}(" + noms + r")\*{0,2}`?\s*(?:=|vaut|:)\s*\*{0,2}"
                    r"(-?\d+(?:[.,]\d+)?)", re.I)
    for f in fichiers:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _est_correction(l):
                continue
            for m in rx.finditer(l):
                nom, brut = m.group(1), m.group(2).replace(",", ".")
                # 🔴 TROIS CONSTRUCTIONS QUE L'OUTIL NE SAIT PAS LIRE, et qui produisaient
                # SIX faux positifs a la premiere execution (2026-08-19) :
                #   « NPTS_PREV = **0** »   -> le 0 est le RESULTAT d'une multiplication
                #   « dp_top_k 20 → 100 »   -> une TRANSITION entre deux modes
                #   « dp_top_k = 20 / 40 / 100 » -> une LISTE par mode
                #   « phase_a_keep_limit ×4 »    -> un MULTIPLICATEUR
                # On les compte a part : ce ne sont NI des conformites NI des erreurs, et les
                # noyer dans l'un ou l'autre mentirait sur la couverture.
                autour = l[max(0, m.start() - 12): m.end() + 14]
                if re.search(r"→|->|×|\bx\s*\d|\d\s*/\s*\d|\(\s*i\s*[−-]", autour):
                    n_nc += 1
                    continue
                try:
                    x = float(brut)
                except ValueError:
                    continue
                ref = sym.get(nom)
                if not ref:
                    continue
                if len(ref) > 1:
                    print(f"  🟠 {nom:<30} {f.name}:{i} dit {brut} -- le code en porte "
                          f"PLUSIEURS : {sorted(ref)} (ambigu, a trancher a la main)")
                    continue
                r = next(iter(ref))
                if abs(x - r) < 1e-9 or (r and abs(x - r) / abs(r) < 0.005):
                    n_ok += 1
                else:
                    n_ko += 1
                    print(f"  🔴 {nom:<30} {f.name}:{i} dit {brut}, le CODE dit {r}")
    return n_ok, n_ko, n_nc


def _sweep_modes(fichiers, modes) -> tuple[int, int, int]:
    """« fast = 50 tirages », « deep = 300 » : les documents suivent-ils le code ?"""
    n_ok = n_ko = n_nc = 0
    for mode, d in sorted(modes.items()):
        for cle, ref in sorted(d.items()):
            rx = re.compile(re.escape(mode) + r".{0,80}?" + re.escape(cle)
                            + r".{0,20}?\*{0,2}(\d+)", re.I)
            for f in fichiers:
                for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if _est_correction(l):
                        continue
                    for m in rx.finditer(l):
                        autour = l[max(0, m.start() - 12): m.end() + 14]
                        if re.search(r"→|->|×|x\s*\d|\d\s*/\s*\d", autour):
                            n_nc += 1
                            continue
                        x = float(m.group(1))
                        if abs(x - ref) < 1e-9:
                            n_ok += 1
                        else:
                            n_ko += 1
                            print(f"  🔴 {mode}/{cle:<24} {f.name}:{i} dit {m.group(1)}, "
                                  f"le CODE dit {ref:g}")
    return n_ok, n_ko, n_nc


def main() -> int:
    fichiers = _md()
    tout_le_md = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in fichiers)
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
                # 🔑 UNE LIGNE QUI PORTE DEUX VALEURS DU MEME FAIT COMPARE, elle n'affirme
                # pas. Generalisation de la garde `_un_seul_composant` a tous les faits,
                # posee le 2026-08-19 apres un faux positif sur « prefere-t-on une fente de
                # 1 nm ... ou la fente NOMINALE ? ». Sans elle, chaque arbitrage ecrit dans
                # un dossier ressort comme une contradiction.
                if len({m.group(0).strip() for m in re.finditer(val, l)}) > 1:
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

    print("\n=== C. TOUT SYMBOLE DU CODE CITE `NOM = N` DANS UN .md ===")
    sym = _symboles_du_code()
    cites = {k for k in sym if re.search(r"\b" + re.escape(k) + r"\b", tout_le_md)}
    ok_s, ko_s, nc_s = _sweep_symboles(fichiers, {k: sym[k] for k in cites})
    n_pb += ko_s
    print(f"  {len(sym)} symboles numeriques dans certus/, {len(cites)} cites dans les .md.")
    print(f"  {'🟢' if ko_s == 0 else '🔴'} {ok_s} conforme(s) au code · {ko_s} en desaccord · "
          f"{nc_s} NON CONCLUANTE(S) (transition, liste, multiplicateur ou formule)")

    print("\n=== D. LES PROFONDEURS PAR MODE, lues dans l'interface ===")
    modes = _profondeurs_par_mode()
    # 🔑 LES DOCUMENTS N'ECRIVENT JAMAIS « deep = 300 » : ils ecrivent le TRIPLET
    # « N = 50 / 150 / 300 » et « dp_top_k = 20 / 40 / 100 ». Sans lire les triplets, ce
    # balayage rendait « 0 conforme, 0 en desaccord, 6 non concluantes » -- decoratif.
    ok_t = ko_t = 0
    rx3 = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})\s*/\s*(\d{1,4})")
    ordre = ("fast", "premium", "deep")
    for f in fichiers:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _est_correction(l):
                continue
            # 🔴 APPARIEMENT PAR PROXIMITE, et il le faut. Une seule ligne porte souvent DEUX
            # triplets — « $N = 50 / 150 / 300$ et `dp_top_k` = 20 / 40 / 100 » — et un
            # appariement naif les CROISE, produisant deux faux desaccords sur une ligne
            # parfaitement juste. Mesure du 2026-08-19 : 4 faux positifs sur 6.
            trios = [(m.start(), [float(x) for x in m.groups()]) for m in rx3.finditer(l)]
            if not trios:
                continue
            for cle in ("robustness_num_runs", "dp_top_k", "n_screen_runs", "consensus_num_runs",
                        "k_keep_survivors", "elite_rounds"):
                pos = l.find(cle)
                if pos < 0 and cle == "robustness_num_runs":
                    m_n = re.search(r"\bN\s*=", l)
                    pos = m_n.start() if m_n else -1
                if pos < 0:
                    continue
                # ⚠️ ET LA DISTANCE EST BORNEE. Sans borne, §24-26 de CLAUDE.md — qui dit
                # « a N = 150 » puis, deux cents caracteres plus loin, la suite d'IDENTIFIANTS
                # de strategies « 2228 / 2218 / 2228 » — appariait les deux et criait au
                # desaccord. Un triplet qui ne suit pas immediatement la cle ne la decrit pas.
                apres = [t for t in trios if pos <= t[0] <= pos + 40]
                if not apres:
                    continue
                trio = min(apres, key=lambda t: t[0] - pos)[1]
                att = [modes.get(md_, {}).get(cle) for md_ in ordre]
                if any(a is None for a in att):
                    continue
                if trio == att:
                    ok_t += 1
                else:
                    ko_t += 1
                    print(f"  🔴 {cle:<22} {f.name}:{i} dit {trio}, le CODE dit {att}")
    n_pb += ko_t
    print(f"  {'🟢' if ko_t == 0 else '🔴'} triplets fast/premium/deep : {ok_t} conforme(s), "
          f"{ko_t} en desaccord")
    ok_m, ko_m, nc_m = _sweep_modes(fichiers, modes)
    n_pb += ko_m
    for m, d in sorted(modes.items()):
        print(f"  {m:<9} " + " · ".join(f"{k}={v:g}" for k, v in sorted(d.items())))
    print(f"  {'🟢' if ko_m == 0 else '🔴'} {ok_m} conforme(s) · {ko_m} en desaccord · "
          f"{nc_m} non concluante(s)")

    # 🔴 LE CONTROLE QUI MANQUAIT, ET IL A COUTE LE PLUS CHER. Le 2026-08-19, une relecture
    # ligne a ligne a trouve que `.venv\\Scripts\\python.exe` -- prescrit par 47 commandes dans
    # 10 fichiers, dont la TOUTE PREMIERE du demarrage -- n'existait pas : le venv avait
    # demenage hors du depot. Un agent neuf echouait a son premier geste sans savoir pourquoi.
    # Aucun outil ne regardait si les commandes documentees s'EXECUTENT.
    print("\n=== E. LES INTERPRETEURS CITES DANS LES COMMANDES EXISTENT-ILS ? ===")
    rx_py = re.compile(r"([A-Za-z]:[\\/][^\s`\"']*?python\.exe|\.?[\\/]?[\w.-]*venv[\\/]"
                       r"[Ss]cripts[\\/]python\.exe)")
    vus_i: dict[str, list[str]] = {}
    for f in fichiers:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _est_correction(l):
                continue
            for m in rx_py.finditer(l):
                vus_i.setdefault(m.group(1).replace("\\\\", "\\"), []).append(f"{f.name}:{i}")
    ko_i = 0
    for chemin, ou in sorted(vus_i.items()):
        existe = Path(chemin.replace("\\", "/")).is_file()
        if not existe:
            ko_i += 1
            n_pb += 1
            print(f"  🔴 {chemin}  N'EXISTE PAS -- {len(ou)} citation(s), ex. {ou[0]}")
        else:
            print(f"  🟢 {chemin}  ({len(ou)} citation(s))")
    if not vus_i:
        print("  ·  aucun interpreteur cite")

    # 🔴 UN NUMERO DE LIGNE DANS LES BORNES PEUT POINTER SUR N'IMPORTE QUOI. Le controle A de
    # check_claude_md.py verifie que `fichier.py:N` existe et que N <= nombre de lignes. Il ne
    # verifie PAS que la ligne N contienne ce qu'on lui prete. 📏 Trouve le 2026-08-19 : le
    # renvoi `certus_strat_robustness.py:513`, cense designer `_rate_candidate_layers`,
    # pointait sur un `return` d'une autre fonction -- mes propres editions du jour l'avaient
    # decale de 83 lignes. Ici on verifie que le SYMBOLE cite sur la meme ligne du .md se
    # trouve bien a proximite (+/- 3 lignes) du numero annonce.
    print("\n=== F. UN `fichier.py:N` CITE A COTE D'UN SYMBOLE POINTE-T-IL DESSUS ? ===")
    rx_ref = re.compile(r"`([\w./\\-]+\.py):(\d{1,5})`")
    rx_sym = re.compile(r"`(_?[A-Za-z][\w]{4,})`")
    idx: dict[str, list[Path]] = {}
    for q in (ROOT / "certus").rglob("*.py"):
        idx.setdefault(q.name, []).append(q)
    n_ok = n_ko = n_sans = 0
    for f in fichiers:
        for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _est_correction(l):
                continue
            for m in rx_ref.finditer(l):
                cands = idx.get(Path(m.group(1).replace("\\", "/")).name, [])
                if not cands:
                    continue
                ln = int(m.group(2))
                # 🔴 LES SYMBOLES DOIVENT ETRE IMMEDIATEMENT AVANT LE RENVOI. Sans borne, une
                # ligne portant DEUX renvois -- « `_resolve_consensus_seeds`
                # (`consensus.py:111`) ... (`robustness.py:2162`) » -- fait apparier le second
                # avec le symbole du premier, et crie au faux. 3 des 13 signalements de la
                # premiere execution etaient de cette forme (2026-08-19).
                avant = l[max(0, m.start() - 90): m.start()]
                syms = [x.group(1) for x in rx_sym.finditer(avant)][-2:]
                syms = [x for x in syms if not x.endswith(".py")]
                if not syms:
                    n_sans += 1
                    continue
                src = cands[0].read_text(encoding="utf-8", errors="replace").splitlines()
                zone = "\n".join(src[max(0, ln - 4): ln + 3])
                # 🔑 UN RENVOI PEUT VISER L'INTERIEUR D'UNE FONCTION, et c'est legitime : on
                # cite souvent la LIGNE qui porte le comportement, pas le `def`. On accepte
                # donc aussi quand la ligne N tombe DANS la fonction nommee. Sans cette
                # tolerance, l'outil ferait « corriger » des renvois parfaitement justes --
                # 3 des 12 signalements de la premiere execution etaient de cette forme.
                englobante = _fonction_englobante(cands[0], ln)
                if any(sy in zone for sy in syms) or (englobante and englobante in syms):
                    n_ok += 1
                else:
                    vrai = [k + 1 for k, li in enumerate(src) if any(f"def {sy}" in li or f"{sy}:" in li or f"{sy} =" in li for sy in syms)]
                    n_ko += 1
                    print(f"  🔴 {f.name}:{i} — `{m.group(1)}:{ln}` ne porte pas {syms}"
                          + (f" (trouve ligne {vrai[0]})" if vrai else " (symbole introuvable)"))
    n_pb += n_ko
    print(f"  {'🟢' if n_ko == 0 else '🔴'} {n_ok} renvoi(s) confirme(s) · {n_ko} qui pointent "
          f"ailleurs · {n_sans} sans symbole cite a cote (non verifiables)")

    # 🔴 DEUX ENTREES DU §24 PORTAIENT LE NUMERO 49. J'ai ajoute la mienne le 2026-08-19 sans
    # verifier que 49 etait pris, et mon PROPRE controle l'a manque : il collectait les numeros
    # dans un SET, ou un doublon disparait en silence. Un renvoi « §24-49 » designe alors deux
    # constats differents, et le lecteur ne peut pas savoir lequel.
    print("\n=== G. LES ENTREES NUMEROTEES DU §24 SONT-ELLES UNIQUES ? ===")
    import collections as _c
    claude = ROOT / "CLAUDE.md"
    txt = claude.read_text(encoding="utf-8")
    try:
        bloc = txt[txt.index("## 24."): txt.index("## 25.")]
    except ValueError:
        bloc = ""
    nums = re.findall(r"^\|\s*(\d+)\s*\|", bloc, re.M)
    dups = {k: v for k, v in _c.Counter(nums).items() if v > 1}
    if dups:
        n_pb += len(dups)
        print(f"  🔴 numeros en double : {dups} — un renvoi « §24-N » y devient ambigu")
    else:
        print(f"  🟢 {len(nums)} entrees, {len(set(nums))} numeros distincts, aucun doublon")

    ok, det = _controle_negatif()
    print("\n=== H. CONTROLE NEGATIF -- l'outil sait-il seulement DETECTER ? ===")
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
