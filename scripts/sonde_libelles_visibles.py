"""LES CHAINES VUES PAR L'UTILISATEUR SONT-ELLES INTACTES ? — sonde de l'etape 3.0

    python scripts\\sonde_libelles_visibles.py
    python scripts\\sonde_libelles_visibles.py --detail

## Pourquoi cette sonde existe

Une passe a **efface les caracteres non-ASCII** des chaines visibles sans les remplacer, et
elle a laisse des cicatrices : un separateur retire laisse un **double espace**, un `λ` retire
laisse le mot **`lambda`**. L'etape 4.1 de `docs/archives/UX_PLAN.md` doit ramener
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
    # 🔴 Les deux FABRIQUES du depot. Sans elles, la sonde ne voyait aucun des 72 boutons
    # construits par la premiere, ni les neuf onglets de la seconde -- et elle annoncait
    # zero alors qu'un onglet portait encore une esperluette mangee et qu'un bouton
    # ecrivait le nom de la lettre grecque en toutes lettres.
    # 🔑 Un puits absent de cette liste est un angle mort SILENCIEUX, contrairement a
    # celui du controle F, qui se compte et s'affiche.
    "create_styled_button", "_add_plot_tab",
}

#: 🔴 L'INDEX de l'argument qui atteint l'ecran, quand ce n'est pas le premier.
#: La sonde parcourait TOUS les arguments : elle comptait donc la donnee metier de
#: `addItem(texte, donnee)` comme un libelle. `certus_index_spline_eventsextras_mixin.py`
#: porte `addItem("...", "lambda")`, et cette seconde chaine etait signalee comme un mot
#: a traduire -- or la renommer casse `_on_spectrum_x_mode_changed`.
INDEX_TEXTE = {"addTab": 1, "setTabText": 1, "insertItem": 1, "setItemText": 1, "_add_plot_tab": 1}

#: 🔑 CE QUE Qt FAIT REELLEMENT DE L'ESPERLUETTE, PUITS PAR PUITS. Mesure le 2026-09-07
#: en peignant le widget et en comparant sa largeur a celle du meme texte prive du signe.
#: ⚠️ Ce n'est PAS la meme propriete que `PUITS`, qui dit seulement ce qui atteint l'ecran.
#: Les confondre faisait compter 23 defauts la ou la mesure en designe 4, et prescrivait
#: 19 corrections FAUSSES : doubler le signe dans une infobulle l'y afficherait EN DOUBLE.
#:
#:     QPushButton 136 == 136   QCheckBox 146 == 146   QRadioButton 146 == 146
#:     QToolButton 136 == 136   QAction   136 == 136   addTab 50 == 50
#:     addItem     120 == 120                                          -> MANGEE
#:
#:     QLabel 132 != 122   CertusCard 138 != 129   QGroupBox 161 != 151
#:     setHorizontalHeaderLabels 144 != 134                            -> AFFICHEE
#:
#: 🔴 QGroupBox est contre-intuitif : c'est la mesure qui tranche, pas la documentation.
#: 🔴 Et la methode qui associe un libelle a son champ n'est appelee NULLE PART dans le
#: depot, donc aucun QLabel ne porte de raccourci.
MANGEURS = {"addTab", "setTabText", "addItem", "insertItem", "setItemText", "addAction"}
MANGEURS_CONSTRUCTEURS = {
    "QPushButton", "QCheckBox", "QRadioButton", "QToolButton", "QAction",
    # Les fabriques rendent l'une un bouton, l'autre un onglet : deux mangeurs.
    "create_styled_button", "_add_plot_tab",
}
AFFICHEURS = {
    "setToolTip", "setWindowTitle", "setStatusTip", "setWhatsThis", "setPlaceholderText",
    "setHorizontalHeaderLabels", "setVerticalHeaderLabels", "setHeaderLabels",
    "setAccessibleName", "setInformativeText", "setLabelText", "setSuffix", "setPrefix",
}
AFFICHEURS_CONSTRUCTEURS = {"QLabel", "QGroupBox", "CertusCard", "QTableWidgetItem", "QTreeWidgetItem"}

#: `setText` depend de son RECEVEUR, et l'AST ne le type pas : on lit donc son nom.
#: Mesure : un bouton mange le signe (136 == 136) la ou une etiquette et le corps d'une
#: boite de message l'affichent (270 != 260). 🔑 Ce qui n'est reconnu ni d'un cote ni de
#: l'autre est compte A PART : le ranger d'office serait la faute meme qu'on corrige ici.
RECEVEUR_MANGEUR = re.compile(r"(?:^|_)(?:btn|button)s?(?:_|$)", re.IGNORECASE)
RECEVEUR_AFFICHEUR = re.compile(
    r"(?:^|_)(?:lbl|label|progress|msg|message|title|status|hint|box|dlg|dialog)s?(?:_|$)",
    re.IGNORECASE,
)

#: Un trou laisse par un separateur : deux espaces ENTRE deux caracteres de texte.
#: Ni un alignement de debut de ligne, ni une indentation dans un bloc HTML.
TROU = re.compile(r"[A-Za-z0-9)\]]  +[A-Za-z0-9(\[]")

#: ⚠️ La borne de mot generique ne convient PAS ici. En mode str elle suit `isalnum()`,
#: qui rend vrai pour un chiffre en indice : le nom suivi d'un zero souscrit n'offrait
#: donc aucune frontiere et echappait au controle. Trois occurrences vivaient ainsi dans
#: `certus_strat_ui_layout.py`, invisibles pour la sonde. On borne sur les caracteres de
#: mot ASCII, ce qui laisse tranquilles les noms de champs a tiret bas.
MOT_LAMBDA = re.compile(r"(?<![A-Za-z_])lambda(?![A-Za-z_])", re.IGNORECASE)

EXCLUS = {"tests", "scripts", "build", "dist", "node_modules", "studies"}

#: 🔴 ET TOUT REPERTOIRE CACHE, ce qui n'etait PAS le cas et a fausse une mesure de
#: 60 %. La liste ci-dessus nommait `.git` et `.venv` un par un, donc elle ne disait
#: rien de `.claude/worktrees/`, ou une session parallele tient une COPIE du depot.
#: 📏 Mesure du 2026-09-07 : 578 fichiers sur 968 balayes venaient d'un autre arbre,
#: portant le code d'AVANT les corrections -- et les trois tests de comptage de
#: l'etape 3.0 ont echoue pour cette seule raison, en annonçant une regression qui
#: n'existait pas. C'est le piege n° 1 du §4 de `CLAUDE.md` : modifier un arbre et
#: en mesurer un autre, sans le moindre message d'erreur.
def _est_cache(chemin: Path) -> bool:
    return any(partie.startswith(".") for partie in chemin.parts)


def _est_emoji(texte: str) -> bool:
    """Un symbole hors du texte courant. TESTE caractere par caractere, jamais devine."""
    return any(
        ord(c) > 0x2000 and unicodedata.category(c) in ("So", "Sk") for c in texte
    )


def _sources() -> list[Path]:
    """Les sources de CET arbre -- ni un worktree voisin, ni un cache."""
    return sorted(
        p for p in RACINE.rglob("*.py")
        if not (EXCLUS & set(p.parts)) and not _est_cache(p.relative_to(RACINE))
    )


def _nom_appele(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _nom_receveur(node: ast.Call) -> str:
    """Le nom de l'objet sur lequel le puits est appele -- vide si l'AST ne le nomme pas."""
    cible = node.func.value if isinstance(node.func, ast.Attribute) else None
    if isinstance(cible, ast.Attribute):
        return cible.attr
    if isinstance(cible, ast.Name):
        return cible.id
    return ""


def _recolte_source(source: str) -> tuple[list[tuple[str, int, str, str]], int]:
    """Le coeur de la recolte, sur du texte -- pour que le controle negatif puisse MORDRE.

    Une logique qu'on ne peut exercer que sur le depot entier ne se verifie pas : la
    premiere version de cette sonde etait fausse et verte, faute d'un tel point d'entree.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return [], 0

    litterales: list[tuple[str, int, str, str]] = []
    aveugles = 0
    for node in ast.walk(arbre):
        if not isinstance(node, ast.Call):
            continue
        nom = _nom_appele(node)
        if nom not in PUITS and nom not in CONSTRUCTEURS:
            continue
        receveur = _nom_receveur(node)
        vise = INDEX_TEXTE.get(nom, 0)
        for i, arg in enumerate(node.args):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                # Un seul argument est le libelle ; les autres portent des donnees metier,
                # et les corriger casse la logique qui les compare.
                if i == vise:
                    litterales.append((arg.value, node.lineno, nom, receveur))
            elif isinstance(arg, ast.JoinedStr) or (
                isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add)
            ):
                aveugles += 1
    return litterales, aveugles


def _recolte(chemin: Path) -> tuple[list[tuple[str, int, str, str]], int]:
    """Idem, sur un fichier."""
    return _recolte_source(chemin.read_text(encoding="utf-8", errors="replace"))


def _mnemonique_actif(puits: str, receveur: str) -> bool | None:
    """Qt mangera-t-il l'esperluette ? Vrai, faux, ou None quand ce n'est PAS mesure.

    🔑 Le troisieme cas est le plus important des trois. Repondre vrai par defaut, c'est
    ce que faisait la version precedente : elle prescrivait alors de doubler le signe dans
    des infobulles, ou il se serait affiche EN DOUBLE.
    """
    if puits in MANGEURS or puits in MANGEURS_CONSTRUCTEURS:
        return True
    if puits in AFFICHEURS or puits in AFFICHEURS_CONSTRUCTEURS:
        return False
    if puits == "setText":
        if RECEVEUR_MANGEUR.search(receveur):
            return True
        if RECEVEUR_AFFICHEUR.search(receveur):
            return False
    return None


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
    indetermine: list[str] = []
    mot_lambda: list[str] = []
    emoji: list[str] = []
    aveugles = 0

    deux_defauts = 0
    for chemin in _sources():
        rel = chemin.relative_to(RACINE)
        litterales, borgnes = _recolte(chemin)
        aveugles += borgnes
        for texte, ligne, puits, receveur in litterales:
            marque = f"{rel}:{ligne}  {texte!r}"
            trou = _mutile(texte)
            # 🔴 Un `&` ne devient un raccourci que dans CERTAINS puits : il est affiche
            # tel quel dans une infobulle, un titre de fenetre, une etiquette et un cadre.
            amp = _esperluette_seule(texte) and _mnemonique_actif(puits, receveur)
            # ⚠️ Les deux categories ne s'excluent PAS. Une chaine peut porter un
            # separateur efface ET une esperluette -- deux correctifs sur la meme ligne.
            if trou:
                separateur.append(marque)
            if amp is True:
                mnemonique.append(marque)
            elif amp is None:
                indetermine.append(f"{marque}   [{puits} sur {receveur or '?'}]")
            if trou and amp is True:
                deux_defauts += 1
            if MOT_LAMBDA.search(texte):
                mot_lambda.append(marque)
            if _est_emoji(texte):
                emoji.append(marque)

    return {
        "separateur": separateur,
        "mnemonique": mnemonique,
        "indetermine": indetermine,
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
    # 🔴 Et le nom suivi d'un zero souscrit, que la borne de mot generique laissait passer.
    voit_lambda = voit_lambda and bool(MOT_LAMBDA.search("Center lambda\u2080 (nm):"))
    # ... sans mordre sur un nom de champ, qui n'est pas un libelle.
    voit_lambda = voit_lambda and not MOT_LAMBDA.search("(lambda_min + lambda_max) / 2")
    # La source d'un mnemonique n'a QUE des espaces simples : le trou nait au rendu.
    mnemo = "Substrate (n) & layer thickness"
    ne_confond_pas = _esperluette_seule(mnemo) and not _mutile(mnemo)
    # Et une entite HTML ne doit surtout pas etre prise pour un mnemonique.
    ignore_entite = not _esperluette_seule("<span>&#9646;</span> = Smart Delta")

    # 🔴 LE CONTROLE QUI MANQUAIT, ET SON ABSENCE A COUTE 19 CORRECTIONS FAUSSES.
    # Un puits qui affiche l'esperluette ne doit pas etre signale ; un puits qui la mange
    # doit l'etre ; un puits non mesure ne doit etre range NI d'un cote NI de l'autre.
    trie_les_puits = (
        _mnemonique_actif("setToolTip", "") is False
        and _mnemonique_actif("QLabel", "") is False
        and _mnemonique_actif("addTab", "") is True
        and _mnemonique_actif("setText", "stop_step2_btn") is True
        and _mnemonique_actif("setText", "lbl_status") is False
        and _mnemonique_actif("setText", "quelque_chose") is None
    )

    # 🔴 Et la donnee metier d'un `addItem` ne doit PAS etre prise pour un libelle.
    recoltees, _ = _recolte_source(
        'combo.addItem("Wavelength lambda (nm)", "lambda")\n'
        'tabs.addTab(page, "n & k")\n'
    )
    textes = [t for t, _ligne, _puits, _recv in recoltees]
    ignore_donnee = textes == ["Wavelength lambda (nm)", "n & k"]

    # 🔴 LE CONTROLE QUI MANQUAIT, ET SON ABSENCE A FAIT ANNONCER UNE FAUSSE
    # REGRESSION. Un repertoire cache peut contenir une copie entiere du depot ;
    # la balayer revient a mesurer un autre arbre que celui qu'on edite.
    hors_arbre = not any(_est_cache(p.relative_to(RACINE)) for p in _sources())

    return (
        voit_trou,
        voit_lambda,
        ne_confond_pas and ignore_entite,
        trie_les_puits,
        ignore_donnee and hors_arbre,
    )


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
    print("  🔴 Seuls les puits qui MANGENT le signe sont comptes ici — mesure le")
    print("     2026-09-07. Une infobulle, un titre de fenetre, une etiquette et un cadre")
    print("     l'affichent tel quel : y doubler l'esperluette la montrerait EN DOUBLE.")
    print(f"  🔴 {r['deux_defauts']} chaine(s) portent les DEUX defauts — A et B a la fois.")
    montre("mnemonique")
    if r["indetermine"]:
        print(f"\n  ⚠️ {len(r['indetermine'])} chaine(s) NON CLASSEES : le puits n'a pas ete")
        print("     mesure, ou le receveur de `setText` n'est pas reconnu. Elles ne sont NI")
        print("     un defaut NI un faux positif — c'est a toi de trancher, pas a la sonde.")
        montre("indetermine")

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
    voit_trou, voit_lambda, ne_confond_pas, trie_les_puits, ignore_donnee = _controle_negatif()
    print(f"  {'🟢' if voit_trou else '🔴'} il repere un double espace plante")
    print(f"  {'🟢' if voit_lambda else '🔴'} il repere un nom plante, indice compris,")
    print("       sans mordre sur un nom de champ a tiret bas")
    print(f"  {'🟢' if ne_confond_pas else '🔴'} il ne confond PAS une esperluette avec un trou")
    print(f"  {'🟢' if trie_les_puits else '🔴'} il sait quels puits MANGENT le signe, et laisse")
    print("       les autres NON CLASSES au lieu de les ranger d'office")
    print(f"  {'🟢' if ignore_donnee else '🔴'} il ne prend PAS la donnee metier d'un `addItem`")
    print("       pour un libelle")
    if not (voit_trou and voit_lambda and ne_confond_pas and trie_les_puits and ignore_donnee):
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
