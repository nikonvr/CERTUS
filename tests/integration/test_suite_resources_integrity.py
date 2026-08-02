import pytest
from pathlib import Path

def test_static_resources_integrity():
    """
    Test that critical static resources exist in the project directory.
    Missing icons or data files can cause ungraceful app crashes.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    
    # List of critical resources relative to the root directory
    critical_resources = [
        "certus.ico",
        "certus.svg",
        "certus2.svg",
        "data/materials_v1.json"
    ]
    
    for resource in critical_resources:
        resource_path = root_dir / resource
        assert resource_path.exists(), f"Missing critical resource: {resource} at {resource_path}"
