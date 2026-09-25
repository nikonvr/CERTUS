"""Regenere `tests/ui/ux_skeleton.json`, le cliquet de l'etape 1.2.

🔴 IL STOCKE LE TEXTE LITTERAL DES LIBELLES, sous la forme `'QPushButton|Run'`. Toute
correction de libelle le casse donc -- c'est mesure : 67 entrees sur 487, soit 14 %, pour
la seule etape 3.0. Le dossier `GEMINI_UX_TOP1` demande de le regenerer DANS LE MEME
changement que la correction, et d'en coller le diff (regle 0.15).

🔑 CE SCRIPT MONTRE LE DIFF AVANT D'ECRIRE, et n'ecrit qu'avec `--ecrire`. Une regeneration
muette transforme le cliquet en presse-bouton : il rendrait vert n'importe quelle
disparition de controle, qui est precisement ce qu'il surveille.

⚠️ Il instancie eleven fenetres Qt en sous-processus. Sur cette plateforme, `QSvgRenderer`
peut faire aborter le processus (voir `certus_icons.py::_qsvg_stack_known_unstable`) :
`_run_worker` reessaie trois fois, et un module qui echoue quand meme est SIGNALE et son
entree LAISSEE INTACTE, jamais videe.

Usage :
    python scripts/regenerer_squelette.py            # montre le diff, n'ecrit rien
    python scripts/regenerer_squelette.py --ecrire   # ecrit apres avoir montre le diff
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

from scripts.audit_ux_certus import MODULES, _run_worker  # noqa: E402

SQUELETTE = RACINE / "tests" / "ui" / "ux_skeleton.json"


def _releve(tag: str) -> tuple[str, list[str] | None, str]:
    """Rend (module, controles, message). `None` = le releve a echoue, on ne touche a rien."""
    ligne = _run_worker(tag, 1920, 1080)
    if "ERROR" in ligne:
        return tag, None, str(ligne.get("ERROR"))[:120]
    controles = ligne.get("skeleton")
    if not controles:
        return tag, None, "releve vide"
    # 🔴 NE PAS TRIER. Le fichier garde l'ordre d'apparition des controles dans la fenetre ;
    # le reordonner produit un diff de 700 lignes pour deux libelles corriges, et un diff
    # qu'on ne peut pas lire ne prouve rien -- c'est la regle 0.15 rendue inoperante.
    return tag, list(controles), f"stable={ligne.get('skeleton_stable')}"


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument(
        "--ecrire", action="store_true", help="ecrit le fichier apres avoir montre le diff"
    )
    args = parseur.parse_args()

    reference: dict[str, list[str]] = json.loads(SQUELETTE.read_text(encoding="utf-8"))

    # Chaque releve est un sous-processus : les lancer de front ne fausse rien et divise
    # l'attente par le nombre de coeurs.
    with ThreadPoolExecutor(max_workers=len(MODULES)) as pool:
        releves = list(pool.map(_releve, MODULES))

    echecs, total_ajouts, total_retraits = [], 0, 0
    nouveau = dict(reference)

    for tag, controles, note in sorted(releves):
        avant = set(reference.get(tag, []))
        if controles is None:
            echecs.append(f"{tag} : {note}")
            continue
        apres = set(controles)
        ajouts, retraits = sorted(apres - avant), sorted(avant - apres)
        total_ajouts += len(ajouts)
        total_retraits += len(retraits)
        nouveau[tag] = controles

        if not ajouts and not retraits:
            print(f"  {tag:22} inchange ({len(apres)} controles)")
            continue
        print(f"\n  {tag:22} {len(avant)} -> {len(apres)} controles   [{note}]")
        for c in retraits:
            print(f"      - {c}")
        for c in ajouts:
            print(f"      + {c}")

    print("\n" + "=" * 84)
    print(f"  {total_retraits} entree(s) retiree(s), {total_ajouts} ajoutee(s).")
    if echecs:
        print("  🔴 RELEVE ECHOUE, entree LAISSEE INTACTE :")
        for e in echecs:
            print(f"      {e}")
        print("  ⚠️ Relance : trois tentatives ont deja eu lieu par module.")
    print("=" * 84)

    if not args.ecrire:
        print("\n  Rien n'a ete ecrit. Relis le diff, puis relance avec --ecrire.")
        return 1 if (total_ajouts or total_retraits or echecs) else 0

    if echecs:
        print("\n  🔴 REFUS D'ECRIRE : un releve a echoue, le fichier serait partiel.")
        return 2

    SQUELETTE.write_text(
        json.dumps(nouveau, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\n  🟢 {SQUELETTE.relative_to(RACINE)} reecrit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
