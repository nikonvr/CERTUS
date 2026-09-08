"""LE COUT DE CONSTRUIRE UNE FENETRE CROIT-IL AVEC CE QUI TRAINE DERRIERE ?

🔴 LA QUESTION, ET POURQUOI ELLE COMPTE. `tests/ui/test_ux_re_stop_when_idle.py`
coute 6,5 s lance seul et ~9 min a l'interieur de la suite -- un facteur ~80,
reproduit sur deux passes. La fixture `qapp` de `tests/ui/conftest.py` est de
portee SESSION : une seule `QApplication` sert les 798 tests, et rien ne nettoie
les fenetres entre eux.

    L'hypothese : une fenetre fermee n'est PAS detruite. `close()` ne supprime
    que si `WA_DeleteOnClose` est pose. Si quelque chose garde une reference --
    une connexion de signal, un registre de module, une fermeture lexicale --
    les fenetres s'accumulent dans `topLevelWidgets()`. Or appliquer une feuille
    de style repolit l'arbre : plus il y a de fenetres vivantes, plus chaque
    construction coute.

🔑 CE QUE CETTE SONDE MESURE, et ce qu'elle ne mesure pas. Elle construit N fois
la meme fenetre, chronometre chaque construction, et compte les widgets de
premier niveau vivants. Elle ne prouve rien sur la SUITE de tests : elle repond
a la question amont, *« construire coute-t-il plus cher quand il en traine
d'autres ? »*. Si la duree est plate et le compte stable, l'hypothese tombe et
il faut chercher ailleurs -- ce qui est un resultat, pas un echec.

⚠️ Une duree sans sa machine ne vaut rien (§11-1). La sonde imprime le processeur
et le nombre de coeurs avec ses chiffres.

    python scripts/sonde_fenetres_fuient.py [fenetre] [repetitions]

`fenetre` vaut `re` (defaut) ou `strat`. Ce sont les deux que le test construit.
"""

from __future__ import annotations

import gc
import os
import platform
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


FENETRES = {
    "re": ("CERTUS_RE", "CertusREApp"),
    "strat": ("certus.ui.certus_strat_ui", "CertusStratApp"),
}


def _machine() -> str:
    return (
        f"{platform.processor() or platform.machine()} · {os.cpu_count()} coeurs logiques · {platform.python_version()}"
    )


def main(argv: list[str]) -> int:
    # La console Windows par defaut est en cp1252 : sans cela, la sonde meurt sur
    # son propre verdict au lieu de le rendre.
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")

    quelle = (argv[1] if len(argv) > 1 else "re").lower()
    repetitions = int(argv[2]) if len(argv) > 2 else 8

    if quelle not in FENETRES:
        print(f"fenetre inconnue : {quelle} — attendu {sorted(FENETRES)}")
        return 2

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv or ["sonde"])

    import importlib

    nom_module, nom_classe = FENETRES[quelle]
    classe = getattr(importlib.import_module(nom_module), nom_classe)

    print(f"machine : {_machine()}")
    print(f"fenetre : {nom_classe} · {repetitions} constructions successives")
    print(f"fils vivants avant la premiere : {threading.active_count()}")
    print()
    print(f"{'#':>3}  {'construction (s)':>16}  {'fermeture (s)':>13}  {'widgets':>8}  {'fils':>5}")
    print("-" * 56)

    premieres: list[float] = []
    for i in range(1, repetitions + 1):
        gc.collect()
        app.processEvents()

        debut = time.perf_counter()
        fenetre = classe()
        cout_construction = time.perf_counter() - debut

        debut = time.perf_counter()
        fenetre.close()
        del fenetre
        gc.collect()
        app.processEvents()
        cout_fermeture = time.perf_counter() - debut

        vivants = len(QApplication.topLevelWidgets())
        fils = threading.active_count()
        premieres.append(cout_construction)
        print(f"{i:>3}  {cout_construction:>16.3f}  {cout_fermeture:>13.3f}  {vivants:>8}  {fils:>5}")

    print()
    noms: dict[str, int] = {}
    for fil in threading.enumerate():
        cle = re.sub(r"[-_]?\d+$", "", fil.name) or fil.name
        noms[cle] = noms.get(cle, 0) + 1
    print("fils encore vivants, par nom : " + ", ".join(f"{n}×{c}" for n, c in sorted(noms.items())))

    classes: dict[str, int] = {}
    for widget in QApplication.topLevelWidgets():
        classes[type(widget).__name__] = classes.get(type(widget).__name__, 0) + 1
    print()
    print("widgets de 1er niveau encore vivants, par classe :")
    for nom, combien in sorted(classes.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {combien:>5} × {nom}")

    print()
    if len(premieres) >= 4:
        tete = sum(premieres[:2]) / 2
        queue = sum(premieres[-2:]) / 2
        facteur = queue / tete if tete > 0 else float("inf")
        print(f"deux premieres : {tete:.3f} s · deux dernieres : {queue:.3f} s · facteur {facteur:.2f}")
        if facteur < 1.3:
            print("🟢 le cout NE croit PAS : l'hypothese d'accumulation ne tient pas sur cette fenetre.")
        else:
            print("🔴 le cout CROIT avec ce qui traine derriere -- l'accumulation est reelle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
