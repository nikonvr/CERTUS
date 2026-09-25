"""Classe les couleurs ecrites en dur -- l'instrument de l'etape 3.10.

🔴 CE N'EST PAS UN OUTIL DE REECRITURE, ET L'ETAPE DIT POURQUOI. Router un hexadecimal
vers un jeton est un changement de COMPORTEMENT : la valeur d'un jeton change avec le
theme, donc l'affirmation « cet element doit suivre le theme » se prend site par site.
Cette sonde CLASSE et COMPTE ; elle ne prescrit que la ou le classement est certain.

🔑 Trois choses qu'elle separe, et que le cliquet de l'etape 1.3 confond :

  - un hexadecimal dans un COMMENTAIRE ou une DOCSTRING n'est pas de la dette : c'est de
    la documentation. Le cliquet le compte pourtant, ce qui a deja fait passer sa valeur
    de 315 a 316 pour une simple phrase d'explication (§1 de `CLAUDE.md`).
  - un hexadecimal dans du HTML EXPORTE doit rester independant du theme : un rapport
    enregistre ne change pas de couleur parce que l'operateur a bascule en sombre.
  - qu'une valeur COINCIDE avec un jeton ne dit pas qu'elle EST ce jeton. La meme valeur
    sert de texte clair dans un module et de fond sombre dans un autre.

Code de sortie : 0 si rien n'est classe « a router », 1 sinon, 2 si le controle negatif
ne mord plus -- pour qu'on ne prenne jamais le silence de la sonde pour un resultat.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

# ⚠️ La protection d'encodage precede tout `print`, faute de quoi un libelle non ASCII
# fait lever la console Windows APRES que la mesure a ete calculee : le run a l'air
# complet et rien n'est garde. C'est la regle de `tests/unit/test_scripts_console_cp1252.py`.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")

#: Les fichiers qui DEFINISSENT la palette. Meme liste que le cliquet de l'etape 1.3 --
#: elle vit ici en second exemplaire parce qu'importer un module de `tests/` depuis
#: `scripts/` inverserait la dependance ; le controle F la compare a celle du cliquet.
FICHIERS_PALETTE = {"certus_theme.py", "certus_theme_config.py", "certus_hub_config.py"}

#: Marqueurs de HTML destine a un FICHIER, donc a survivre au theme de l'application.
MARQUEURS_HTML = (
    "<html", "<!doctype", "<div", "<table", "<body", "<style>", "<tr", "<td", "<th",
    "<p ", "<h1", "<h2", "<span", "style=",
)

#: Marqueurs d'une feuille de style Qt : la couleur y habille un widget, donc elle DOIT
#: suivre le theme. C'est le seul cas ou la sonde se permet de prescrire.
MARQUEURS_QSS = ("background", "color:", "border", "gridline", "selection-", "stop:")

#: Marqueurs d'un tracé : pyqtgraph et matplotlib recoivent une couleur qui n'est ni du
#: QSS ni du HTML. Elle devrait suivre le theme aussi, mais par les jetons de COURBE.
MARQUEURS_TRACE = ("mkPen", "mkBrush", "setPen", "setBrush", "setColor", "setBackground",
                   "plot(", "addLine", "InfiniteLine", "LinearRegionItem", "TextItem")


def _fichiers() -> list[Path]:
    """Le meme perimetre que le cliquet : la racine et tout `certus/`, hors tests."""
    fichiers = sorted(RACINE.glob("CERTUS_*.py"))
    fichiers += sorted(p for p in (RACINE / "certus").rglob("*.py") if "tests" not in p.parts)
    return fichiers


def _lignes_de_prose(source: str) -> set[int]:
    """Les lignes ou un hexadecimal n'est PAS du code : commentaire ou docstring.

    🔑 On passe par `tokenize`, pas par une expression reguliere : un `#` vit aussi dans
    une chaine de couleur, donc chercher « la ligne commence par un diese » se trompe sur
    les deux sens a la fois.
    """
    prose: set[int] = set()
    try:
        jetons = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return prose

    precedent = None
    for jeton in jetons:
        if jeton.type == tokenize.COMMENT:
            prose.update(range(jeton.start[0], jeton.end[0] + 1))
        elif jeton.type == tokenize.STRING and precedent in (
            None, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
        ):
            # Une chaine en position d'instruction est une docstring -- ou une chaine
            # laissee la sans effet, ce qui revient au meme pour la dette.
            prose.update(range(jeton.start[0], jeton.end[0] + 1))
        if jeton.type not in (tokenize.NL, tokenize.COMMENT):
            precedent = jeton.type
    return prose


def _lignes_de_balisage(source: str) -> set[int]:
    """Les lignes qui vivent dans une chaine portant du BALISAGE -- donc un document.

    🔴 CE CONTROLE ETAIT FAIT LIGNE PAR LIGNE, ET C'ETAIT FAUX. Une couleur de rapport
    s'ecrit `color: #...` exactement comme une couleur de widget ; ce qui les distingue est
    l'ouverture du document, quatre-vingts lignes plus haut. On classe donc par chaine
    litterale entiere : si le bloc porte du balisage, tout ce qu'il contient est un
    document, qui doit rester independant du theme de l'application.
    """
    balisage: set[int] = set()
    try:
        jetons = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return balisage
    for jeton in jetons:
        if jeton.type != tokenize.STRING:
            continue
        minuscule = jeton.string.lower()
        if any(m in minuscule for m in MARQUEURS_HTML):
            balisage.update(range(jeton.start[0], jeton.end[0] + 1))
    return balisage


def _jetons_du_theme() -> dict[str, list[str]]:
    """Valeur -> noms de jetons qui la portent. Lu dans les fichiers de palette."""
    par_valeur: dict[str, list[str]] = {}
    motif = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*[\"'](#[0-9a-fA-F]{3,8})[\"']")
    # 🔴 Chercher depuis la RACINE balaierait aussi `.claude/worktrees/`, ou une session
    # parallele tient une copie du depot : on lirait alors la palette d'un AUTRE arbre que
    # celui qu'on edite. C'est le piege n° 1 du projet, et il est silencieux -- les jetons
    # sont ressortis en double au premier lancement, ce qui l'a rendu visible par chance.
    candidats = [p for nom in FICHIERS_PALETTE for p in (RACINE / "certus").rglob(nom)]
    for chemin in candidats:
        for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
            trouve = motif.match(ligne)
            if trouve:
                par_valeur.setdefault(trouve.group(2).lower(), []).append(trouve.group(1))
    return par_valeur


def _classe(ligne_texte: str, en_prose: bool, en_balisage: bool = False) -> str:
    """Le contexte d'un hexadecimal, ou `indetermine` quand rien ne tranche.

    `en_balisage` vient du BLOC, pas de la ligne : c'est ce qui separe la couleur d'un
    rapport enregistre de celle d'un widget, et les deux s'ecrivent pareil.
    """
    if en_prose:
        return "prose"
    if en_balisage:
        return "html"
    minuscule = ligne_texte.lower()
    if any(m in minuscule for m in MARQUEURS_HTML):
        return "html"
    if any(m in ligne_texte for m in MARQUEURS_TRACE):
        return "trace"
    if any(m in minuscule for m in MARQUEURS_QSS):
        return "qss"
    return "indetermine"


def balaye() -> dict:
    par_valeur = _jetons_du_theme()
    trouvailles: list[dict] = []
    for chemin in _fichiers():
        if chemin.name in FICHIERS_PALETTE:
            continue
        source = chemin.read_text(encoding="utf-8", errors="replace")
        prose = _lignes_de_prose(source)
        balisage = _lignes_de_balisage(source)
        for numero, ligne in enumerate(source.splitlines(), start=1):
            for valeur in HEX.findall(ligne):
                trouvailles.append({
                    "fichier": chemin.relative_to(RACINE).as_posix(),
                    "ligne": numero,
                    "valeur": valeur.lower(),
                    "classe": _classe(ligne, numero in prose, numero in balisage),
                    "jetons": par_valeur.get(valeur.lower(), []),
                    "texte": ligne.strip()[:100],
                })
    return {"trouvailles": trouvailles, "par_valeur": par_valeur}


def _controle_negatif() -> tuple[bool, bool, bool, bool]:
    """La sonde sait-elle seulement DETECTER ? Un harnais toujours vert ne prouve rien."""
    voit_prose = 1 in _lignes_de_prose('# la couleur primaire vaut #0f62fe\nx = 1\n')
    voit_code = 2 not in _lignes_de_prose('# rien\nx = "#0f62fe"\n')
    # Une docstring de module doit etre vue comme de la prose, sur TOUTES ses lignes.
    docstring = _lignes_de_prose('"""ligne une\nla couleur #0f62fe\n"""\nx = 1\n')
    voit_docstring = {1, 2, 3} <= docstring
    # Et le classement doit distinguer les contextes qui commandent des decisions opposees.
    trie = (
        _classe('self.setStyleSheet("background: #ffffff;")', False) == "qss"
        and _classe('pen = pg.mkPen("#a855f7")', False) == "trace"
        and _classe('quelque_chose = "#123456"', False) == "indetermine"
    )
    # 🔴 LE CONTROLE QUI MANQUAIT, ET SON ABSENCE A FAIT PRESCRIRE FAUX SUR 26 SITES.
    # Une couleur de rapport est ecrite comme une couleur de widget ; ce qui les separe
    # est l'ouverture du document, souvent tres loin au-dessus. Le controle porte donc
    # sur une chaine MULTI-LIGNE, seule forme qui exerce la vraie logique.
    rapport = (
        'def rendre():\n'
        '    return """<!DOCTYPE html>\n'
        '<html><head><style>h1 {{ font-size: 2em; }}</style></head><body>\n'
        '<table><tr><td style="color: #1e293b">valeur</td></tr></table>\n'
        '</body></html>"""\n'
    )
    lignes_html = _lignes_de_balisage(rapport)
    voit_le_bloc = 4 in lignes_html
    # ... et il ne doit pas prendre une feuille de style Qt pour un document.
    feuille = 'def f():\n    return """QPushButton {{ color: #ffffff; }}"""\n'
    ne_confond_pas_qss = 2 not in _lignes_de_balisage(feuille)
    return voit_prose, voit_code, voit_docstring, trie, voit_le_bloc, ne_confond_pas_qss


def _tete(titre: str) -> None:
    print(f"\n=== {titre} ===")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--detail", action="store_true", help="liste chaque site")
    parseur.add_argument("--fichier", help="ne montrer qu'un fichier (chemin partiel)")
    args = parseur.parse_args()

    r = balaye()
    tout = r["trouvailles"]
    if args.fichier:
        tout = [t for t in tout if args.fichier in t["fichier"]]

    par_classe = Counter(t["classe"] for t in tout)

    _tete("A. CE QUE LE CLIQUET COMPTE, ET CE QUI EST VRAIMENT DE LA DETTE")
    print(f"  {len(tout)} hexadecimal(aux) hors des fichiers de palette")
    print("  🔴 Le cliquet de l'etape 1.3 les compte AU NIVEAU DU TEXTE, donc il compte")
    print("     aussi ceux qui expliquent un defaut dans un commentaire. Repartition :")
    for classe, libelle in (
        ("qss", "feuille de style Qt   -> DOIT suivre le theme, c'est de la dette"),
        ("trace", "courbe ou trace       -> doit suivre le theme, par les jetons de courbe"),
        ("html", "HTML exporte          -> ne DOIT PAS suivre le theme, ce n'est PAS de la dette"),
        ("prose", "commentaire/docstring -> documentation, ce n'est PAS de la dette"),
        ("indetermine", "indetermine           -> a lire, la sonde ne tranche pas"),
    ):
        print(f"      {par_classe.get(classe, 0):4}  {libelle}")

    _tete("B. LES VALEURS QUI COINCIDENT AVEC UN JETON")
    avec = [t for t in tout if t["jetons"] and t["classe"] in ("qss", "trace")]
    print(f"  {len(avec)} site(s) portent une valeur qui EXISTE comme jeton")
    print("  ⚠️ Coincider n'est pas etre. La meme valeur sert de texte en mode clair dans")
    print("     un module et de fond en mode sombre dans un autre : router sur la valeur")
    print("     seule serait faux deux fois sur trois. Le jeton propose est une PISTE.")
    ambigus = {v: j for v, j in r["par_valeur"].items() if len(j) > 1}
    if ambigus:
        print(f"  🔴 {len(ambigus)} valeur(s) portent PLUSIEURS noms de jetons -- pour celles-la,")
        print("     la valeur ne designe meme pas un jeton unique :")
        for valeur, noms in sorted(ambigus.items())[:6]:
            print(f"      {valeur}  ->  {', '.join(noms)}")

    _tete("C. PAR FICHIER — l'etape se fait fichier par fichier, pas en une passe")
    par_fichier: dict[str, Counter] = {}
    for t in tout:
        par_fichier.setdefault(t["fichier"], Counter())[t["classe"]] += 1
    entetes = ("qss", "trace", "html", "prose", "indetermine")
    print(f"  {'fichier':52} {'qss':>4} {'trace':>6} {'html':>5} {'prose':>6} {'indet':>6}")
    for fichier, compte in sorted(par_fichier.items(), key=lambda kv: -sum(kv[1].values()))[:20]:
        cases = "".join(f"{compte.get(c, 0):>6}" for c in entetes)
        print(f"  {fichier[-52:]:52}{cases}")

    if args.detail:
        _tete("D. DETAIL")
        for t in sorted(tout, key=lambda x: (x["fichier"], x["ligne"])):
            piste = f"  ~ {'/'.join(t['jetons'])}" if t["jetons"] else ""
            print(f"  [{t['classe']:11}] {t['fichier']}:{t['ligne']}  {t['valeur']}{piste}")
            print(f"                {t['texte']}")

    _tete("E. CONTROLE NEGATIF — la sonde sait-elle seulement DETECTER ?")
    (voit_prose, voit_code, voit_docstring, trie, voit_le_bloc,
     ne_confond_pas_qss) = _controle_negatif()
    print(f"  {'🟢' if voit_prose else '🔴'} elle voit un hexadecimal plante dans un commentaire")
    print(f"  {'🟢' if voit_code else '🔴'} elle ne prend PAS une ligne de code pour de la prose")
    print(f"  {'🟢' if voit_docstring else '🔴'} elle voit TOUTES les lignes d'une docstring, pas seulement")
    print("       la premiere")
    print(f"  {'🟢' if trie else '🔴'} elle distingue feuille de style, trace et indetermine")
    print(f"  {'🟢' if voit_le_bloc else '🔴'} elle voit une couleur de document ecrite LOIN sous")
    print("       l'ouverture du document -- le defaut qui lui faisait prescrire faux")
    print(f"  {'🟢' if ne_confond_pas_qss else '🔴'} et elle ne prend PAS une feuille de style Qt pour")
    print("       un document")
    if not (voit_prose and voit_code and voit_docstring and trie and voit_le_bloc
            and ne_confond_pas_qss):
        print("  🔴 LA SONDE NE MORD PAS. Ne crois aucun compte ci-dessus.")
        return 2

    _tete("F. CONTROLE CROISE — la sonde et le cliquet voient-ils la MEME chose ?")
    try:
        sys.path.insert(0, str(RACINE / "tests" / "ui"))
        from test_ux_design_system import THEME_FILES, count_hex_outside_theme

        du_cliquet = count_hex_outside_theme()
        meme_liste = set(THEME_FILES) == FICHIERS_PALETTE
        print(f"  cliquet : {du_cliquet}   sonde : {len(r['trouvailles'])}")
        print(f"  {'🟢' if du_cliquet == len(r['trouvailles']) else '🔴'} les deux comptes concordent")
        print(f"  {'🟢' if meme_liste else '🔴'} les deux exemptent les MEMES fichiers de palette")
        if not meme_liste:
            print(f"      cliquet : {sorted(THEME_FILES)}")
            print(f"      sonde   : {sorted(FICHIERS_PALETTE)}")
    except ImportError as erreur:
        print(f"  ⚠️ cliquet illisible ({erreur}) -- controle croise non fait")

    a_router = par_classe.get("qss", 0) + par_classe.get("trace", 0)
    print("\n" + "=" * 88)
    print(f"  {a_router} site(s) classes A ROUTER, {par_classe.get('indetermine', 0)} a lire soi-meme.")
    print(f"  {par_classe.get('html', 0) + par_classe.get('prose', 0)} ne sont PAS de la dette,")
    print("  et le cliquet les compte pourtant.")
    print("=" * 88)
    return 1 if a_router else 0


if __name__ == "__main__":
    sys.exit(main())
