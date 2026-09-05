"""Test d'intégrité et de validité de tous les fichiers de configuration JSON d'exemple."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_DIR = ROOT / "example"


def get_all_example_json_files() -> list[Path]:
    """Récupère l'ensemble des fichiers JSON dans example/."""
    return sorted(list(EXAMPLE_DIR.glob("**/*.json")), key=lambda p: p.as_posix())


@pytest.mark.parametrize("json_path", get_all_example_json_files(), ids=lambda p: p.relative_to(EXAMPLE_DIR).as_posix())
def test_example_json_is_valid_utf8_and_parsable(json_path: Path) -> None:
    """Vérifie que chaque fichier JSON d'exemple est encodé en UTF-8 valide et se parse sans erreur."""
    assert json_path.exists(), f"File {json_path} does not exist"
    assert json_path.stat().st_size > 0, f"File {json_path} is empty"

    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert isinstance(data, (dict, list)), f"Root of {json_path.name} must be a dict or list, got {type(data)}"

    # Vérifications ciblées par module
    parent_dir = json_path.parent.name
    if parent_dir == "example_design" and isinstance(data, dict):
        # Doit contenir des informations de design optique
        has_stack = any(k in data for k in ("stack", "layers", "stack_string", "materials", "l0"))
        assert has_stack, f"{json_path.name} in example_design missing stack/materials keys"

    elif parent_dir == "example_strat" and isinstance(data, dict):
        # Doit contenir des paramètres de stratégie ou un rapport de benchmark/sweep
        has_strat = any(
            k in data
            for k in (
                "stack_multipliers",
                "stack_string",
                "l0",
                "materials",
                "strategies",
                "runs",
                "sweep",
                "config",
                "summary",
                "baseline",
            )
        )
        assert has_strat, f"{json_path.name} in example_strat missing strategy or benchmark keys"
