"""LES CHAINES VUES PAR L'UTILISATEUR SONT-ELLES INTACTES ? — sonde de l'etape 3.0

    C:\\envs\\certus\\Scripts\\python.exe scripts\\sonde_libelles_visibles.py
    C:\\envs\\certus\\Scripts\\python.exe scripts\\sonde_libelles_visibles.py --detail

## Pourquoi cette sonde existe

Une passe a **efface les caracteres non-ASCII** des chaines visibles sans les remplacer, et
elle a laisse des cicatrices : un separateur retire laisse un **double espace**, un `λ` retire
laisse le mot **`lambda`**. L'etape 3.0 de `docs/GEMINI_UX_TOP1_2026-09-04.md` doit ramener
ces comptes a zero.

🔴 **ET CE N'EST PAS COSMETIQUE.** `certus/metal/certus_metal_common.py` affiche
*« percentage or 01 scale accepted »* : **« 01 scale » ne veut rien dire**, la lecture evidente
etant `0-1 scale`. Le separateur portait du sens, donc son retrait a produit une **consigne
fausse a l'utilisateur**.

## Ce qu'elle mesure, et pourquoi la distinction compte

⚠️ **Tous les doubles espaces ne sont PAS des mutilations.** Dans un `QPushButton`, un
`QCheckBox` ou un `QLabel` avec buddy, `&` est le prefixe **mnemonique** : Qt le retire de
l'affichage et fabrique un raccourci sur le caractere suivant. `"... (n) & layer ..."` rend
donc `"... (n)  layer ..."` a l'ecran alors que la source est intacte.

**Les deux cas ont des correctifs opposes** — doubler l'esperluette, ou retablir le
separateur — et ils sont du **meme ordre de grandeur**. Les confondre produirait autant de
corrections fausses que de justes. La sonde les separe donc, et ne les additionne jamais.

## Sa limite, mesuree et non pas seulement avouee

Elle ne voit que les chaines **litterales** passees a un puits Qt connu. Un libelle construit
par f-string ou par concatenation lui echappe. **Ce n'est pas une supposition** : le controle F
compte les arguments non litteraux des memes puits, et affiche l'angle mort en clair. Un
garde-fou qui exigerait `== 0` sans dire ce qu'il ne regarde pas serait un faux ami.

## Code de sortie

`0` si les deux compteurs de mutilation sont a zero, `1` sinon. **Tant que l'etape 3.0 n'est
pas faite, cette sonde DOIT sortir en 1** — c'est sa preuve d'utilite.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

# 🔴 LA CONSOLE WINDOWS EST EN cp1252, ET CETTE SONDE IMPRIME DES PASTILLES.
#
# Sans ces deux lignes, `UnicodeEncodeError` leve **a la fin**, en ecrivant la synthese,
# c'est-a-dire APRES que la mesure a ete calculee : le run a l'air complet et rien n'est
# garde. C'est la regle de `tests/unit/test_scripts_console_cp1252.py`, ecrite apres que ce
# defaut a detruit l'artefact d'un run de cinquante minutes.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

RACINE = Path(__file__).resolve().parents[1]
SQUELETTE = RACINE / "tests" / "ui" / "ux_skeleton.json"

#: Les appels Qt dont un argument chaine atteint l'ecran.
#: ⚠️ Cette liste est le PERIMETRE de la sonde. L'allonger elargit la mesure ; c'est voulu,
#: et c'est la seule facon honnete de reduire l'angle mort du controle F.
PUITS = {
    "setText", "setWindowTitle", "setToolTip", "addItem", "addTab", "setTitle",
    "setPlaceholderText", "setHorizontalHeaderLabels", "setVerticalHeaderLabels",
    "setStatusTip", "setWhatsThis", "setLabelText", "setAccessibleName",
    "setSuffix", "setPrefix", "addAction", "setItemText", "insertItem",
    "setHeaderLabels", "setTabText", "setInformativeText",
}
CONSTRUCTEURS = {
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox", "QAction",
    "QToolButton", "QTableWidgetItem", "QTreeWidgetItem", "CertusCard",
}

#: Un trou laisse par un separateur : deux espaces ENTRE deux caracteres de texte.
#: Ni un alignement de debut de ligne, ni une indentation dans un bloc HTML.
TROU = re.compile(r"[A-Za-z0-9)\]]  +[A-Za-z0-9(\[]")
MOT_LAMBDA = re.compile(r"\blambda\b", re.IGNORECASE)

EXCLUS = {"tests", "scripts", "build", "dist", "node_modules", "studies", ".git", ".venv"}


def _est_emoji(texte: str) -> bool:
    """Un symbole hors du texte courant. TESTE caractere par caractere, jamais devine."""
    return any(
        ord(c) > 0x2000 and unicodedata.category(c) in ("So", "Sk") for c in texte
    )


def _sources() -> list[Path]:
    return sorted(
        p for p in RACINE.rglob("*.py") if not (EXCLUS & set(p.parts))
    )


def _nom_appele(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _recolte(chemin: Path) -> tuple[list[tuple[str, int]], int]:
    """Rend les chaines litterales atteignant un puits, et le compte des arguments NON litteraux.

    Le second nombre est l'angle mort, et il est rendu pour etre affiche -- pas pour etre tu.
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return [], 0

    litterales: list[tuple[str, int]] = []
    aveugles = 0
    for node in ast.walk(arbre):
        if not isinstance(node, ast.Call):
            continue
        nom = _nom_appele(node)
        if nom not in PUITS and nom not in CONSTRUCTEURS:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                litterales.append((arg.value, node.lineno))
            elif isinstance(arg, ast.JoinedStr) or (
                isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add)
            ):
                aveugles += 1
    return litterales, aveugles


#: Une entite HTML (`&amp;`, `&#9646;`) n'est PAS un mnemonique : Qt la rend telle quelle.
ENTITE_HTML = re.compile(r"&[A-Za-z]+;|&#\d+;")


def _esperluette_seule(texte: str) -> bool:
    """Un `&` qui deviendra un mnemonique Qt — donc invisible, et porteur d'un raccourci.

    🔑 CONTRE-INTUITIF, ET C'EST CE QUI A FAIT ECHOUER LA PREMIERE VERSION DE CETTE SONDE.
    La source d'un mnemonique ne contient **aucun** double espace : elle ecrit
    `"(n) & layer"`, avec des espaces simples. Le double espace n'existe qu'**au rendu**,
    quand Qt retire le `&`. Chercher un trou dans la source ne pouvait donc rien trouver --
    le controle negatif G3 l'a refute au premier lancement.
    """
    reste = ENTITE_HTML.sub("", texte).replace("&&", "")
    return "&" in reste


def _mutile(texte: str) -> bool:
    """Un trou laisse par un separateur retire, dans la source elle-meme."""
    return bool(TROU.search(texte))


def _balaye() -> dict:
    separateur: list[str] = []
    mnemonique: list[str] = []
    mot_lambda: list[str] = []
    emoji: list[str] = []
    aveugles = 0

    deux_defauts = 0
    for chemin in _sources():
        rel = chemin.relative_to(RACINE)
        litterales, borgnes = _recolte(chemin)
        aveugles += borgnes
        for texte, ligne in litterales:
            marque = f"{rel}:{ligne}  {texte!r}"
            trou = _mutile(texte)
            amp = _esperluette_seule(texte)
            # ⚠️ Les deux categories ne s'excluent PAS. Une chaine peut porter un
            # separateur efface ET une esperluette -- deux correctifs sur la meme ligne.
            if trou:
                separateur.append(marque)
            if amp:
                mnemonique.append(marque)
            if trou and amp:
                deux_defauts += 1
            if MOT_LAMBDA.search(texte):
                mot_lambda.append(marque)
            if _est_emoji(texte):
                emoji.append(marque)

    return {
        "separateur": separateur,
        "mnemonique": mnemonique,
        "lambda": mot_lambda,
        "emoji": emoji,
        "aveugles": aveugles,
        "deux_defauts": deux_defauts,
    }


def _recouvrement_squelette() -> tuple[int, int, dict[str, int]] | None:
    """Combien d'entrees du cliquet une correction de libelle obligerait a regenerer ?

    🔑 C'est le VRAI multiplicateur de risque de l'etape 3.0, et l'etape ne le nommait pas :
    `ux_skeleton.json` stocke le TEXTE LITTERAL, sous la forme `'QPushButton|Detach plot'`.
    """
    if not SQUELETTE.exists():
        return None
    donnees = json.loads(SQUELETTE.read_text(encoding="utf-8"))
    total = 0
    touchees = 0
    par_module: dict[str, int] = {}
    for module, entrees in donnees.items():
        total += len(entrees)
        n = sum(
            1
            for e in entrees
            if TROU.search(e) or MOT_LAMBDA.search(e) or _est_emoji(e)
        )
        if n:
            par_module[module] = n
        touchees += n
    return total, touchees, par_module


def _controle_negatif() -> tuple[bool, bool, bool]:
    """L'outil sait-il seulement detecter ? Sinon il rassure sans rien garder.

    ⚠️ Le troisieme cas est celui qui compte. Une premiere version classait
    `"Substrate (n) & layer thickness"` en `separateur`, donc elle aurait prescrit de
    retablir un tiret la ou il faut DOUBLER l'esperluette -- une correction fausse, produite
    par un outil vert.
    """
    voit_trou = _mutile("Optical Profiles  n(lambda)")
    voit_lambda = bool(MOT_LAMBDA.search("n(lambda) and ln k(lambda)"))
    # La source d'un mnemonique n'a QUE des espaces simples : le trou nait au rendu.
    mnemo = "Substrate (n) & layer thickness"
    ne_confond_pas = _esperluette_seule(mnemo) and not _mutile(mnemo)
    # Et une entite HTML ne doit surtout pas etre prise pour un mnemonique.
    ignore_entite = not _esperluette_seule("<span>&#9646;</span> = Smart Delta")
    return voit_trou, voit_lambda, ne_confond_pas and ignore_entite


def _tete(titre: str) -> None:
    print(f"\n=== {titre} ===")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument(
        "--detail", action="store_true", help="liste chaque chaine au lieu du compte seul"
    )
    args = parseur.parse_args()

    r = _balaye()

    def montre(cle: str, limite: int = 8) -> None:
        entrees = r[cle]
        for e in entrees if args.detail else entrees[:limite]:
            print(f"    {e}")
        if not args.detail and len(entrees) > limite:
            print(f"    ... et {len(entrees) - limite} autres (--detail)")

    def fichiers(cle: str) -> int:
        return len({e.split(":", 1)[0] for e in r[cle]})

    _tete("A. SEPARATEUR EFFACE — un double espace dans un libelle")
    print(f"  {len(r['separateur'])} chaine(s), {fichiers('separateur')} fichier(s)")
    print("  correctif : RETABLIR le separateur (le meme partout : U+00B7 ou U+2014)")
    montre("separateur")

    _tete("B. ESPERLUETTE MANGEE PAR Qt — ressemble a A, correctif OPPOSE")
    print(f"  {len(r['mnemonique'])} chaine(s), {fichiers('mnemonique')} fichier(s)")
    print("  correctif : DOUBLER l'esperluette (`&&`), ou la remplacer par « et » / « · »")
    print("  🔑 Qt en fait un raccourci sur le caractere suivant. Suivi d'une espace, il")
    print("     fabrique Alt+Space, qui est le menu de fenetre de Windows.")
    print("  ⚠️ La SOURCE d'un mnemonique n'a que des espaces simples : le double espace")
    print("     n'apparait qu'au RENDU. Ne le cherche donc jamais dans le fichier.")
    print(f"  🔴 {r['deux_defauts']} chaine(s) portent les DEUX defauts — A et B a la fois.")
    montre("mnemonique")

    _tete("C. `lambda` ECRIT EN TOUTES LETTRES au lieu de λ")
    print(f"  {len(r['lambda'])} chaine(s), {fichiers('lambda')} fichier(s)")
    print("  ⚠️ Seulement dans les chaines VUES : ni variables, ni cles JSON, ni `lambda:`.")
    montre("lambda")

    _tete("D. EMOJI DANS UN LIBELLE — perimetre de l'etape 3.5, pas de la 3.0")
    print(f"  {len(r['emoji'])} chaine(s), {fichiers('emoji')} fichier(s)")
    print("  ⚠️ Ne compte QUE ce qui atteint un widget. Les emoji des journaux de")
    print("     `certus/core/` et `certus/workers/` sont HORS perimetre : ne pas y toucher.")
    montre("emoji")

    _tete("E. RECOUVREMENT AVEC LE CLIQUET — ce qu'une correction obligerait a regenerer")
    recouvrement = _recouvrement_squelette()
    if recouvrement is None:
        print(f"  ⚠️ {SQUELETTE} absent — recouvrement non mesurable")
    else:
        total, touchees, par_module = recouvrement
        part = (100.0 * touchees / total) if total else 0.0
        print(f"  {touchees} entree(s) sur {total} — soit {part:.0f} % du squelette")
        print("  🔴 `ux_skeleton.json` stocke le TEXTE LITTERAL des libelles. Toute")
        print("     correction casse donc le garde-fou de l'etape 1.3 lui-meme.")
        print("     Regenere-le DANS LE MEME changement, et colle le diff (regle 0.15).")
        for module, n in sorted(par_module.items(), key=lambda kv: -kv[1]):
            print(f"      {n:4}  {module}")

    _tete("F. ANGLE MORT — ce que cette sonde ne voit PAS")
    print(f"  {r['aveugles']} argument(s) NON litteraux passes aux memes puits Qt")
    print("  (f-string ou concatenation). Un libelle construit ainsi echappe aux")
    print("  controles A a D. 🔑 Un « 0 » en A et C ne vaut donc que POUR LES LITTERAUX.")
    print(f"  Perimetre : {len(PUITS)} methodes + {len(CONSTRUCTEURS)} constructeurs.")

    _tete("G. CONTROLE NEGATIF — l'outil sait-il seulement DETECTER ?")
    voit_trou, voit_lambda, ne_confond_pas = _controle_negatif()
    print(f"  {'🟢' if voit_trou else '🔴'} il repere un double espace plante")
    print(f"  {'🟢' if voit_lambda else '🔴'} il repere un `lambda` plante")
    print(f"  {'🟢' if ne_confond_pas else '🔴'} il ne confond PAS une esperluette avec un trou")
    if not (voit_trou and voit_lambda and ne_confond_pas):
        print("  🔴 LA SONDE NE MORD PAS. Ne crois aucun compte ci-dessus.")
        return 2

    a_corriger = len(r["separateur"]) + len(r["lambda"])
    print("\n" + "=" * 88)
    if a_corriger:
        print(f"  {a_corriger} chaine(s) a corriger pour l'etape 3.0.")
        print("  ⚠️ Les esperluettes de B ne sont PAS comptees ici : autre correctif.")
    else:
        print("  🟢 0 chaine a corriger — l'etape 3.0 est faite, POUR LES LITTERAUX (voir F).")
    print("=" * 88)
    return 1 if a_corriger else 0


if __name__ == "__main__":
    sys.exit(main())
