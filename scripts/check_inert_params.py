"""Traque les PARAMETRES INERTES : poses et jamais lus, ou lus et jamais poses.

    .venv\\Scripts\\python.exe scripts\\check_inert_params.py

POURQUOI CE SCRIPT EXISTE. Le 2026-08-15, deux defauts de cette famille ont ete trouves en
une matinee, et aucun des deux ne produisait d'erreur :

  * `--mode fast` du balayage multi-temoins ne s'appliquait pas. `collect_params` lit la
    combo box et en deduit le budget ; ecrire `params["execution_mode"]` APRES ne changeait
    que l'etiquette. Un run PREMIUM complet s'est affiche comme « fast ».
  * `witness_reset_layers` et la fente figee n'atteignaient jamais le solveur, parce que
    `run_workflow` rappelle `collect_params()` en interne et jette le dictionnaire modifie.
    Deux batchs « sans coupure » et « coupure en 32 » ont rendu des scores BIT-IDENTIQUES.

Et le depot en portait deja un, documente : `fast_auto_blocks` est pose par `collect_params`
et JOURNALISE par le worker, alors qu'aucun code ne le lit -- un bouton mort dont le journal
affirme le contraire.

🔴 C'EST LE MODE DE DEFAILLANCE DOMINANT DU PROJET : pas une exception, pas un plantage,
juste un resultat plausible obtenu avec une configuration qui n'est pas celle qu'on croit.

CE QU'IL CHERCHE :

  A. POSES, JAMAIS LUS -- une cle ecrite dans un dict de parametres (ou presente dans une
     configuration d'exemple) qu'aucun `.get("cle")` ne lit nulle part. Le reglage n'a
     aucun effet, et rien ne le dit.

  B. LUS, JAMAIS POSES -- une cle lue avec un defaut, que personne n'ecrit jamais. Le
     defaut s'applique toujours : la fonctionnalite existe sur le papier et pas en vrai.

Ni l'un ni l'autre n'est automatiquement une faute -- une cle peut etre lue depuis un JSON
utilisateur, ou posee pour un consommateur externe. Le script rend une LISTE A EXAMINER,
pas un verdict.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SRC = [ROOT / "certus", ROOT / "scripts", ROOT / "tests"]

#: Cles techniques qui n'ont rien a voir avec un reglage physique.
IGNORE = {
    "logger", "materials_db", "gui_parent", "stop_requested", "progress_signal",
    "show_plots", "reality_sim_params", "type", "name", "value", "id", "path",
    "config", "data", "results", "params", "self", "cls", "kwargs", "args",
}

WRITE_PATS = [
    re.compile(r"""params(?:_out|_safe|_consensus)?\[["'](\w+)["']\]\s*="""),
    re.compile(r"""\bp2\[["'](\w+)["']\]\s*="""),
    re.compile(r"""\bconfig\[["'](\w+)["']\]\s*="""),
]
READ_PATS = [
    re.compile(r"""\.get\(\s*["'](\w+)["']"""),
    re.compile(r"""params\[["'](\w+)["']\]"""),
    re.compile(r"""\bos\.environ\.get\(\s*["'](\w+)["']"""),
]


def py_files() -> list[Path]:
    out: list[Path] = []
    for base in SRC:
        if base.exists():
            out += [p for p in base.rglob("*.py")
                    if "__pycache__" not in str(p) and ".venv" not in str(p)]
    return out


def scan() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    writes: dict[str, list[str]] = defaultdict(list)
    reads: dict[str, list[str]] = defaultdict(list)
    for f in py_files():
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(ROOT))
        for i, line in enumerate(txt.splitlines(), 1):
            for pat in WRITE_PATS:
                for k in pat.findall(line):
                    writes[k].append(f"{rel}:{i}")
            for pat in READ_PATS:
                for k in pat.findall(line):
                    reads[k].append(f"{rel}:{i}")
    return writes, reads


def config_keys() -> dict[str, list[str]]:
    """Cles presentes dans les configurations d'exemple livrees."""
    out: dict[str, list[str]] = defaultdict(list)
    for f in (ROOT / "example").rglob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, dict):
            for k in d:
                out[k].append(str(f.relative_to(ROOT)))
    return out


def main() -> int:
    writes, reads = scan()
    cfg = config_keys()

    #: Une cle n'est INERTE que si personne ne la lit NULLE PART -- ni en source, ni en test.
    posed_unread = {k: v for k, v in writes.items()
                    if k not in reads and k not in IGNORE and len(k) > 3}
    # Les cles prefixees par `_` sont de la documentation dans le gabarit JSON, pas des
    # reglages : les compter serait du bruit, et un controle bruyant cesse d'etre lu.
    cfg_unread = {k: v for k, v in cfg.items()
                  if k not in reads and k not in IGNORE and len(k) > 3
                  and not k.startswith("_")}
    # Lues avec un defaut mais jamais ecrites nulle part, ni en code ni en configuration.
    read_unwritten = {k: v for k, v in reads.items()
                      if k not in writes and k not in cfg and k not in IGNORE
                      and len(k) > 6 and not k.startswith(("_", "test"))}

    print("=" * 78)
    print("A. POSES DANS UN DICT DE PARAMETRES, JAMAIS LUS : %d" % len(posed_unread))
    print("=" * 78)
    for k, v in sorted(posed_unread.items()):
        print("  %-34s pose en %s" % (k, ", ".join(v[:3])))

    print("\n" + "=" * 78)
    print("B. PRESENTS DANS UNE CONFIG D'EXEMPLE, JAMAIS LUS : %d" % len(cfg_unread))
    print("=" * 78)
    for k, v in sorted(cfg_unread.items()):
        print("  %-34s dans %d fichier(s), ex. %s" % (k, len(v), Path(v[0]).name))

    print("\n" + "=" * 78)
    print("C. LUS AVEC UN DEFAUT, JAMAIS ECRITS : %d  (le defaut s'applique TOUJOURS)" % len(read_unwritten))
    print("=" * 78)
    for k, v in sorted(read_unwritten.items())[:40]:
        print("  %-34s lu en %s" % (k, ", ".join(v[:2])))

    total = len(posed_unread) + len(cfg_unread)
    print("\n" + "=" * 78)
    print("A EXAMINER : %d" % total)
    print("Aucun n'est automatiquement une faute. Mais chacun est un reglage dont")
    print("PERSONNE ne garantit qu'il fait quelque chose.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
