"""ECRIRE UN ARTEFACT SANS JAMAIS EN DETRUIRE UN AUTRE.

🔴 POURQUOI CE MODULE EXISTE. `CLAUDE.md` interdit 3 : `reports/` porte les resultats
scientifiques de 👤 -- **33 fichiers suivis par git sur 226**, les 193 autres sont
IRRECUPERABLES. Or les sondes nomment leurs artefacts d'apres leurs parametres, si bien que
deux runs qui ne different que par un reglage NON present dans le nom s'ecrasent l'un l'autre.

📏 Ce defaut a deja coute des mesures a ce projet :

    « les coupures 28-52 ont ete perdues ainsi »  -- probe_blocs_vs_plantage.py, a propos de
                                                     TAIL_CUTS absent du nom de fichier

📏 Et il a failli recommencer le 2026-08-20, deux fois dans la meme heure :

  - le run de diagnostic prevu produisait exactement `blocs_vs_plantage_r75x2_deep_s042.json`,
    soit le nom de la REFERENCE de 8,26 Mo servant au controle C1 -- on aurait detruit la
    mesure a laquelle on voulait comparer ;
  - un run de controle sur le 35c a ete lance avant que la garde ne soit posee, et allait
    ecraser 215 Ko dates du 19 aout. Sauve a la main, de justesse.

🔑 RENOMMER PLUTOT QUE REFUSER. Un run de deux heures qui aboutit ne doit pas perdre son
resultat parce qu'un homonyme existe. L'horodatage rend la collision impossible, et la ligne
imprimee DIT ce qui s'est passe au lieu de le taire -- c'est le motif que `CLAUDE.md` denonce
partout : *ca ne produit pas d'erreur, ca produit un resultat plausible.*
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def chemin_libre(cible: Path, *, horodatage: str | None = None) -> tuple[Path, Path | None]:
    """Rend un chemin qui n'ecrase rien, et le chemin conserve s'il y a eu collision.

    Args:
        cible: le nom voulu.
        horodatage: suffixe a employer en cas de collision. `None` prend l'heure courante --
            l'argument existe pour que le test soit deterministe, jamais pour l'usage.

    Returns:
        `(chemin_a_ecrire, ancien_conserve)`. `ancien_conserve` vaut `None` s'il n'y avait
        pas de collision.
    """
    if not cible.exists():
        return cible, None
    stamp = horodatage or f"{datetime.now():%Y%m%d_%H%M%S}"
    libre = cible.with_name(f"{cible.stem}_{stamp}{cible.suffix}")
    # 🔴 Deux collisions dans la meme seconde restent possibles -- deux sondes lancees
    # ensemble par un pilote. On boucle plutot que de supposer.
    n = 1
    while libre.exists():
        libre = cible.with_name(f"{cible.stem}_{stamp}_{n}{cible.suffix}")
        n += 1
    return libre, cible


def ecrire_json(cible: Path, donnees: Any, *, racine: Path | None = None) -> Path:
    """Ecrit `donnees` en JSON sans jamais ecraser, et dit a voix haute ce qu'il fait.

    Returns:
        Le chemin REELLEMENT ecrit -- qui peut differer de `cible`.
    """
    ecrit, ancien = chemin_libre(cible)
    if ancien is not None:
        taille = ancien.stat().st_size
        quand = datetime.fromtimestamp(ancien.stat().st_mtime)
        print(f"\n🟠 {ancien.name} EXISTE DEJA ({taille} octets, {quand:%Y-%m-%d %H:%M}).")
        print(f"   L'artefact precedent est CONSERVE. Le nouveau va dans {ecrit.name}.")
    ecrit.write_text(json.dumps(donnees, indent=2, ensure_ascii=False), encoding="utf-8")
    ou = ecrit.relative_to(racine) if racine else ecrit
    print(f"\nconsigne dans {ou}")
    return ecrit
