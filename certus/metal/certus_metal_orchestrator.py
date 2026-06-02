"""Metal orchestration scaffold (#55).

Centralizes the declarative job spec used by METAL single/bilayer workflows.
"""

from __future__ import annotations

from certus.metal.certus_metal_common import (
    METAL_BILAYER_SPEC,
    METAL_SINGLE_SPEC,
    MetalJobSpec,
)

__all__ = ["MetalJobSpec", "METAL_SINGLE_SPEC", "METAL_BILAYER_SPEC"]
