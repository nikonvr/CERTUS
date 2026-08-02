import pytest
import json
from pathlib import Path

def get_all_json_files():
    """Retrieve all JSON files from the 'example' directory."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    example_dir = root_dir / "example"
    
    if not example_dir.exists():
        return []
        
    # Get all .json files recursively
    return list(example_dir.rglob("*.json"))

JSON_FILES = get_all_json_files()

@pytest.mark.parametrize("json_file", JSON_FILES, ids=lambda x: x.name)
def test_config_json_validation(json_file):
    """
    Test that all example JSON configuration files are well-formed.
    This prevents broken configs from crashing applications on load.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert isinstance(data, (dict, list)), "JSON file must contain a dict or list"
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON file {json_file.name}: {e}")
    except Exception as e:
        pytest.fail(f"Failed to read {json_file.name}: {e}")
