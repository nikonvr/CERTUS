"""Reference du 75 couches aleatoire EN UNE SEULE CAMPAGNE, sur verre nu.

    .venv\Scripts\python.exe scripts\ref_r75.py

C'est la mesure manquante du 2026-08-15 : sans elle on ne peut pas dire si le random75 a
BESOIN d'un changement de verre temoin. Meme reglage que les sous-empilements du controle
negatif (fast, fente 2 nm, graine 42) pour que la comparaison soit legitime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import controle_negatif as CN  # noqa: E402

row = CN.mesurer("random75", 0, 75)
out = CN.cache_dir("random75") / "REFERENCE_0_75.json"
out.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(row, indent=2, ensure_ascii=False))
