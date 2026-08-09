#!/usr/bin/env python3
"""
Script to replace wildcard imports with explicit imports.

Usage:
    python scripts/fix_wildcard_imports.py certus/physics/certus_material_db.py
    python scripts/fix_wildcard_imports.py certus/ --dry-run
"""

import ast
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple
import re


class WildcardImportFixer:
    """Parses and fixes wildcard imports in a Python file."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = filepath.read_text(encoding="utf-8")
        self.tree = ast.parse(self.content, filename=str(filepath))

    def find_wildcard_imports(self) -> List[Tuple[int, str]]:
        """Find all wildcard imports with their line."""
        wildcards = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    module = node.module or ""
                    wildcards.append((node.lineno, module))
        return wildcards

    def find_used_names(self) -> Set[str]:
        """Finds all names used in the code."""
        used = set()

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                # For calls like QWidget.show(), we want QWidget
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        return used

    def get_typing_symbols(self) -> Set[str]:
        """Commonly used typing symbols."""
        return {
            "Any",
            "Dict",
            "List",
            "Tuple",
            "Set",
            "Optional",
            "Union",
            "Callable",
            "Iterable",
            "Iterator",
            "Sequence",
            "Mapping",
            "TypeVar",
            "Generic",
            "Protocol",
            "TypedDict",
            "Literal",
            "Final",
            "ClassVar",
            "cast",
            "overload",
            "TYPE_CHECKING",
        }

    def suggest_explicit_imports(self, module: str, used_names: Set[str]) -> str:
        """Suggests explicit imports for a given module."""

        if module == "typing":
            # For typing, we suggest the common symbols used
            typing_symbols = self.get_typing_symbols()
            candidates = sorted(typing_symbols & used_names)
            if candidates:
                if len(candidates) <= 5:
                    return f"from typing import {', '.join(candidates)}"
                else:
                    # Multi-ligne pour plus de 5 imports
                    imports = ",\n    ".join(candidates)
                    return f"from typing import (\n    {imports}\n)"

        elif module.startswith("PyQt6"):
            # For PyQt6, we list the widgets/classes used
            candidates = sorted(
                name for name in used_names if name.startswith("Q") or name in {"Qt", "pyqtSignal", "pyqtSlot"}
            )
            if candidates:
                if len(candidates) <= 5:
                    return f"from {module} import {', '.join(candidates)}"
                else:
                    imports = ",\n    ".join(candidates)
                    return f"from {module} import (\n    {imports}\n)"

        #For other modules, we suggest a manual analysis
        return f"# TODO: Analyser manuellement les symboles utilisés depuis {module}"

    def generate_fixes(self) -> Dict[str, List[str]]:
        """Generates suggested fixes."""
        wildcards = self.find_wildcard_imports()
        if not wildcards:
            return {}

        used_names = self.find_used_names()
        fixes = {}

        for lineno, module in wildcards:
            suggestion = self.suggest_explicit_imports(module, used_names)
            if lineno not in fixes:
                fixes[lineno] = []
            fixes[lineno].append(f"Ligne {lineno}: from {module} import *")
            fixes[lineno].append(f"  -> {suggestion}")

        return fixes


def process_file(filepath: Path, dry_run: bool = True) -> None:
    """Processes a file and displays suggested corrections."""
    try:
        fixer = WildcardImportFixer(filepath)
        fixes = fixer.generate_fixes()

        if not fixes:
            return

        print(f"\n{'=' * 80}")
        print(f"Fichier: {filepath}")
        print(f"{'=' * 80}")

        for lineno in sorted(fixes.keys()):
            for line in fixes[lineno]:
                print(line)

        if not dry_run:
            print("\n[ATTENTION] Mode --apply non implemente. Corrections manuelles requises.")
            print("   Raison: Necessite analyse semantique complete pour eviter les bugs.")

    except SyntaxError as e:
        print(f"[ERREUR] Erreur de syntaxe dans {filepath}: {e}")
    except Exception as e:
        print(f"[ERREUR] Erreur lors du traitement de {filepath}: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv or "--apply" not in sys.argv

    if dry_run:
        print("[ANALYSE] MODE DRY-RUN: Analyse uniquement, aucune modification\n")

    if target.is_file():
        process_file(target, dry_run)
    elif target.is_dir():
        python_files = list(target.rglob("*.py"))
        print(f"[DOSSIER] Traitement de {len(python_files)} fichiers Python...\n")

        stats = {"total": 0, "with_wildcards": 0}
        for filepath in sorted(python_files):
            try:
                fixer = WildcardImportFixer(filepath)
                fixes = fixer.generate_fixes()
                if fixes:
                    stats["with_wildcards"] += 1
                    process_file(filepath, dry_run)
                stats["total"] += 1
            except Exception as exc:  # noqa: BLE001 - outil de maintenance, on continue
                # Un `except:` nu avalait AUSSI KeyboardInterrupt et SystemExit : l'outil
                #became impossible to interrupt. And the silent `pass` hid what
                #files had failed, on a script whose role is precisely to
                # reecrire des imports en masse.
                stats.setdefault("failed", []).append((str(filepath), repr(exc)))

        print(f"\n{'=' * 80}")
        print(f"[STATS] STATISTIQUES")
        print(f"{'=' * 80}")
        print(f"Fichiers analyses: {stats['total']}")
        print(f"Fichiers avec wildcard imports: {stats['with_wildcards']}")
        print(f"Taux: {stats['with_wildcards'] / stats['total'] * 100:.1f}%")
    else:
        print(f"[ERREUR] Chemin invalide: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
