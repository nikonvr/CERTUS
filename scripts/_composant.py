"""CHARGER UN COMPOSANT SANS JAMAIS CALCULER SUR UN AUTRE (D105).

🔴 POURQUOI CE MODULE EXISTE. `CertusStratApp.load_configuration` rend `False` quand le fichier est absent ou refuse, et
laisse la fenetre sur sa configuration par defaut (une pile de 46 couches). Les 23 appels de `scripts/` n'en lisaient pas le
retour : un rejeu de `probe_blocs_vs_plantage.py r75x0.5`, le 2026-10-12, dans un clone qui n'avait pas
`reports/serie_echelle_r75/cfg_x0.5.json`, a calcule quatre heures sur cette pile par defaut -- verdict `OK`, 2 743 strategies,
aucun message. *Ca ne produit pas d'erreur, ca produit un resultat plausible.*

🔑 Le helper arrete le script, en disant pourquoi, plutot que de laisser un calcul tourner sur ce qui n'a pas ete demande.
`tests/unit/test_the_scripts_read_what_load_configuration_returns.py` echoue si un appel nu reapparait.

Ce module n'importe rien d'autre que la bibliotheque standard : un script peut l'importer avant d'avoir cree la `QApplication`
(l'ordre de chargement des DLL compte sur Windows, `bench_examples.py` piege 3). Il est embarque dans le gel avec `_artefact.py`,
que `probe_blocs_vs_plantage.py` importe quand STRAT demarre.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def charger_configuration(app: Any, chemin: str | Path) -> None:
    """Charge le fichier de composant `chemin` dans la fenetre STRAT `app`, ou arrete le script en disant pourquoi.

    Raises:
        SystemExit: le fichier est absent, ou `load_configuration` l'a refuse (retour `False`) -- la fenetre est alors restee sur
            sa configuration par defaut, et rien ne doit etre calcule dessus.
    """
    fichier = Path(chemin)
    if not fichier.is_file():
        raise SystemExit(f"fichier de composant introuvable : {fichier} -- rien n'est calcule sur la configuration par defaut")
    if not app.load_configuration(str(fichier)):
        raise SystemExit(
            f"load_configuration a refuse {fichier} : la fenetre est restee sur sa configuration par defaut, rien n'est calcule"
        )
