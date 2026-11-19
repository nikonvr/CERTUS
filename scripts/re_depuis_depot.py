r"""Ecrit le classeur RE (measurement, design, index) d'une reference de la base de depots (lot 2d, 2026-11-19).

    python scripts\re_depuis_depot.py sb2s3-silice
    python scripts\re_depuis_depot.py sb2s3-silice --out C:\chemin\sb2s3.xlsx

La reference vient de `example/database_depots/references_index.json` : ses voies mesurees, une couche (QWOT a la
longueur d'onde du milieu de la bande) sur son substrat, et ses n, k de Tauc-Lorentz-Urbach. Une reference normalisee
(T/T_sub) est refusee : RE modelise R et T absolus (`certus/utils/certus_depots_re.py`). Le classeur s'ouvre dans RE
(`load_reverse_engineering_from_path`, ou le bouton de chargement).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()  # the Numba cache keyed by the sources, before the first import that loads Numba
    from certus.utils.certus_depots_db import database_dir, load_catalogue
    from certus.utils.certus_depots_re import write_re_workbook

    references = {ref["nom"]: ref for ref in json.loads((database_dir() / "references_index.json").read_text(encoding="utf-8"))["references"]}
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reference", choices=sorted(references))
    ap.add_argument("--out", default=None, help="chemin du classeur (par defaut : reports/RE_depot_<reference>.xlsx)")
    a = ap.parse_args()
    target = Path(a.out) if a.out else ROOT / "reports" / f"RE_depot_{a.reference}.xlsx"
    catalogue = {entry["id"]: entry for entry in load_catalogue()}
    try:
        write_re_workbook(references[a.reference], catalogue, target)
    except ValueError as error:
        print(f"REFUS={error}")
        return 1
    print(f"CLASSEUR_RE={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
