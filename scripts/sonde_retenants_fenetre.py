"""QUI RETIENT UNE FENETRE FERMEE ? La sonde nomme le detenteur, pas le symptome.

`scripts/sonde_fenetres_fuient.py` MESURE la fuite : une `CertusREApp` fermee laisse 45
widgets de premier niveau vivants, et construire la suivante coute plus cher (D11). Elle ne dit
pas QUI les retient, et sans ce nom il n'y a rien a corriger.

Cette sonde-ci construit UNE fenetre, la ferme, lache sa derniere reference, puis remonte la
chaine de references avec `gc.get_referrers` jusqu'a un detenteur DURABLE -- un objet de
module, une classe, un cadre de pile. Elle classe ce qu'elle trouve :

    methode liee      un `self.methode` range quelque part (le motif attendu ici)
    cellule           une fermeture lexicale qui capture la fenetre
    dictionnaire      souvent le `__dict__` d'un autre objet : on remonte a son proprietaire
    liste / ensemble  un registre
    cadre de pile     la sonde elle-meme, ou la boucle d'evenements : a ignorer

    python scripts\\sonde_retenants_fenetre.py [fenetre] [profondeur]

`fenetre` vaut `re` (defaut) ou `strat`. `profondeur` borne la remontee (defaut 4).

⚠️ CE QU'ELLE NE PROUVE PAS. `gc.get_referrers` ne voit que le cote PYTHON. Une reference
detenue par le cote C++ de Qt -- un parent, une connexion de signal, le registre global des
`ViewBox` de pyqtgraph -- n'y apparait pas. Une fenetre sans aucun retenant Python ici, et
pourtant vivante, designe donc le cote Qt, ce qui est un resultat et non un echec.
"""

from __future__ import annotations

import gc
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FENETRES = {
    "re": ("CERTUS_RE", "CertusREApp"),
    "strat": ("certus.ui.certus_strat_ui", "CertusStratApp"),
}

#: Ce qu'on ne signale pas : la sonde est forcement dans la chaine.
_A_IGNORER = (types.FrameType,)


def _decrire(obj: object) -> str:
    """Une ligne qui NOMME l'objet, jamais son adresse."""
    t = type(obj).__name__
    if isinstance(obj, types.MethodType):
        prop = getattr(obj, "__self__", None)
        return f"methode liee  {type(prop).__name__}.{obj.__func__.__name__}"
    if isinstance(obj, types.FunctionType):
        return f"fonction      {obj.__module__}.{obj.__qualname__}"
    if isinstance(obj, types.CellType):
        return "cellule       (fermeture lexicale)"
    if isinstance(obj, dict):
        # Le cas le plus courant : le __dict__ d'un objet. On remonte a son proprietaire.
        proprios = [r for r in gc.get_referrers(obj) if getattr(r, "__dict__", None) is obj]
        if proprios:
            return f"attribut de   {type(proprios[0]).__name__} (son __dict__)"
        apercu = ", ".join(repr(k)[:28] for k in list(obj)[:3])
        return f"dictionnaire  {len(obj)} cles : {apercu}"
    if isinstance(obj, (list, tuple, set)):
        return f"{t:<13} de {len(obj)} elements"
    if isinstance(obj, types.ModuleType):
        return f"MODULE        {obj.__name__}  <- detenteur durable"
    return f"{t:<13} {str(obj)[:60]}"


def _remonter(cible: object, profondeur: int, vus: set[int], rang: int = 0) -> None:
    if rang >= profondeur:
        return
    for ref in gc.get_referrers(cible):
        if id(ref) in vus or isinstance(ref, _A_IGNORER):
            continue
        vus.add(id(ref))
        print("    " * (rang + 1) + "<- " + _decrire(ref))
        if isinstance(ref, (dict, types.CellType, list, tuple, set)):
            _remonter(ref, profondeur, vus, rang + 1)


def main(argv: list[str]) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")

    quelle = (argv[1] if len(argv) > 1 else "re").lower()
    profondeur = int(argv[2]) if len(argv) > 2 else 4
    if quelle not in FENETRES:
        print(f"fenetre inconnue : {quelle} — attendu {sorted(FENETRES)}")
        return 2

    import importlib

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv or ["sonde"])
    nom_module, nom_classe = FENETRES[quelle]
    classe = getattr(importlib.import_module(nom_module), nom_classe)

    avant = {id(w) for w in QApplication.topLevelWidgets()}
    fenetre = classe()
    fenetre.close()
    del fenetre
    gc.collect()
    app.processEvents()
    gc.collect()

    neufs = [w for w in QApplication.topLevelWidgets() if id(w) not in avant]
    print(f"fenetre : {nom_classe}")
    print(f"widgets de premier niveau APPARUS et encore vivants : {len(neufs)}")
    if not neufs:
        print("🟢 rien ne survit : cette fenetre ne fuit pas.")
        return 0

    par_classe: dict[str, int] = {}
    for w in neufs:
        par_classe[type(w).__name__] = par_classe.get(type(w).__name__, 0) + 1
    print("  " + ", ".join(f"{n}×{c}" for n, c in sorted(par_classe.items(), key=lambda kv: -kv[1])))

    # La fenetre elle-meme est le seul objet dont le retenant nous interesse : les 44 autres
    # sont ses enfants, tenus par elle du cote Qt.
    principale = next((w for w in neufs if type(w).__name__ == nom_classe), None)
    if principale is None:
        print()
        print(f"🔑 {nom_classe} lui-meme est DETRUIT : ce qui survit sont des orphelins Qt,")
        print("   donc le detenteur est du cote C++ (parent, connexion, registre pyqtgraph).")
        return 0

    print()
    print(f"chaine de references vers {nom_classe}, profondeur {profondeur} :")
    _remonter(principale, profondeur, {id(principale)})
    print()
    print("⚠️ Un detenteur du cote C++ de Qt n'apparait PAS ci-dessus (voir l'en-tete).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
