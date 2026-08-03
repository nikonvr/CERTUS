#!/usr/bin/env python3
"""
Script pour remplacer automatiquement 'from typing import *' par des imports explicites.
Ce script traite uniquement les imports typing qui sont sûrs à corriger automatiquement.
"""

import re
from pathlib import Path
from typing import Dict, Set

# Mapping des fichiers avec leurs imports typing détectés
TYPING_FIXES = {
    "certus/physics/certus_optimizers.py": ["Callable", "TYPE_CHECKING"],
    # Autres fichiers nécessitent analyse manuelle car script a retourné TODO
}


def fix_typing_import(filepath: Path, symbols: list[str]) -> bool:
    """Remplace 'from typing import *' par imports explicites."""
    content = filepath.read_text(encoding="utf-8")

    # Pattern pour trouver 'from typing import *'
    pattern = r"^from typing import \*$"

    if not re.search(pattern, content, re.MULTILINE):
        print(f"[SKIP] Pas de 'from typing import *' dans {filepath}")
        return False

    # Créer la nouvelle ligne d'import
    if len(symbols) <= 5:
        new_import = f"from typing import {', '.join(sorted(symbols))}"
    else:
        imports = ",\n    ".join(sorted(symbols))
        new_import = f"from typing import (\n    {imports}\n)"

    # Remplacer
    new_content = re.sub(pattern, new_import, content, flags=re.MULTILINE)

    if new_content == content:
        print(f"[ERREUR] Remplacement echoue pour {filepath}")
        return False

    # Écrire le fichier modifié
    filepath.write_text(new_content, encoding="utf-8")
    print(f"[OK] {filepath}: from typing import * -> {new_import.split('import')[1].strip()[:50]}")
    return True


def main():
    fixed_count = 0

    for filepath_str, symbols in TYPING_FIXES.items():
        filepath = Path(filepath_str)
        if not filepath.exists():
            print(f"[ERREUR] Fichier non trouve: {filepath}")
            continue

        if fix_typing_import(filepath, symbols):
            fixed_count += 1

    print(f"\n[STATS] {fixed_count}/{len(TYPING_FIXES)} fichiers corriges")


if __name__ == "__main__":
    main()
