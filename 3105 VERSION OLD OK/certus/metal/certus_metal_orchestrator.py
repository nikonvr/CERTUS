"""Metal orchestration scaffold (#55).

Depends on #26 deduplication for full functional routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


MetalJobKind = Literal["single", "bilayer"]


@dataclass(frozen=True)
class MetalJobSpec:
    """Declarative job spec for METAL workflows."""

    kind: MetalJobKind
    payload: dict[str, Any]


