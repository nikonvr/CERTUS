import pytest
import numpy as np

# Import the main module to verify it is a valid facade (or the original file)
import CERTUS_INDEX

def test_certus_index_smoke_imports():
    """Verify that we can import the module and access its main components."""
    assert hasattr(CERTUS_INDEX, "IRGlobalObjective")
    assert hasattr(CERTUS_INDEX, "Phase23SplineObjective")
    assert hasattr(CERTUS_INDEX, "OptimizationConfig")
    assert hasattr(CERTUS_INDEX, "substrateMode")
    assert hasattr(CERTUS_INDEX, "CertusIndexApp")



def test_certus_index_substrate_mode():
    """Verify substrateMode enum."""
    assert CERTUS_INDEX.substrateMode.STANDARD.name == "STANDARD"
    assert CERTUS_INDEX.substrateMode.FROSTED_GLASS.name == "FROSTED_GLASS"
