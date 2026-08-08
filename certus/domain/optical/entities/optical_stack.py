"""
CERTUS Domain - OpticalStack Aggregate Root

Aggregate root for an optical layer stack.
Manages domain invariants and emits domain events.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import uuid4

from certus.domain.optical.entities import Layer
from certus.domain.optical.value_objects import Wavelength


@dataclass
class OpticalStack:
    """
    Multilayer optical stack (Aggregate Root).

    Invariants:
    - At least 1 layer (substrate)
    - All thicknesses > 0
    - Layer order preserved

    Events emitted:
    - LayerAdded
    - LayerRemoved
    - StackValidated
    """

    stack_id: str = field(default_factory=lambda: str(uuid4()))
    layers: List[Layer] = field(default_factory=list)
    _events: List[dict] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Initial validation."""
        if not isinstance(self.layers, list):
            raise TypeError("layers must be a list")

    def add_layer(self, layer: Layer, position: Optional[int] = None) -> None:
        """
        Add a layer to the stack.

        Args:
            layer: Layer to add
            position: Position in stack (None = end)

        Raises:
            TypeError: If layer is not a Layer
            ValueError: If position is invalid
        """
        if not isinstance(layer, Layer):
            raise TypeError(f"Expected Layer, got {type(layer)}")

        if position is None:
            self.layers.append(layer)
            position = len(self.layers) - 1
        else:
            if not (0 <= position <= len(self.layers)):
                raise ValueError(f"Invalid position {position} for stack of {len(self.layers)} layers")
            self.layers.insert(position, layer)

        # Emit domain event
        self._events.append(
            {
                "type": "LayerAdded",
                "stack_id": self.stack_id,
                "layer_material": layer.material_id,
                "position": position,
            }
        )

    def remove_layer(self, position: int) -> Layer:
        """
        Remove a layer from the stack.

        Args:
            position: Index of the layer to remove

        Returns:
            Removed Layer

        Raises:
            ValueError: If position is invalid
            ValueError: If attempting to remove the last layer
        """
        if not (0 <= position < len(self.layers)):
            raise ValueError(f"Invalid position {position} for stack of {len(self.layers)} layers")

        if len(self.layers) <= 1:
            raise ValueError("Cannot remove last layer from stack (minimum 1 layer)")

        layer = self.layers.pop(position)

        # Emit domain event
        self._events.append(
            {
                "type": "LayerRemoved",
                "stack_id": self.stack_id,
                "layer_material": layer.material_id,
                "position": position,
            }
        )

        return layer

    def get_layer(self, position: int) -> Layer:
        """
        Retrieve a layer by position.

        Args:
            position: Index of the layer

        Returns:
            Layer at this position

        Raises:
            IndexError: If position is out of bounds
        """
        return self.layers[position]

    def layer_count(self) -> int:
        """Number of layers in the stack."""
        return len(self.layers)

    def total_thickness(self) -> float:
        """
        Total physical thickness of the stack (nm).

        Returns:
            Sum of thicknesses of all layers
        """
        return sum(layer.thickness.nm for layer in self.layers)

    def total_optical_thickness(self, wavelength: Wavelength) -> float:
        """
        Total optical thickness at a wavelength (nm).

        Args:
            wavelength: Reference wavelength

        Returns:
            Sum of optical thicknesses n*d
        """
        return sum(layer.optical_thickness_at(wavelength) for layer in self.layers)

    def has_absorbing_layers(self, threshold: float = 1e-6) -> bool:
        """
        Check if the stack contains absorbing layers.

        Args:
            threshold: Detection threshold for k

        Returns:
            True if at least one layer has k > threshold
        """
        return any(layer.is_absorbing(threshold) for layer in self.layers)

    def validate(self) -> bool:
        """
        Validate stack invariants.

        Returns:
            True if all invariants are satisfied

        Raises:
            ValueError: If an invariant is violated
        """
        if len(self.layers) == 0:
            raise ValueError("Stack must have at least 1 layer")

        for i, layer in enumerate(self.layers):
            if layer.thickness.nm <= 0:
                raise ValueError(f"Layer {i} has invalid thickness: {layer.thickness.nm}")

        # Emit validation event
        self._events.append(
            {
                "type": "StackValidated",
                "stack_id": self.stack_id,
                "layer_count": len(self.layers),
                "total_thickness": self.total_thickness(),
            }
        )

        return True

    def get_events(self) -> List[dict]:
        """
        Retrieve emitted domain events.

        Returns:
            List of events (copy)
        """
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear domain events after publication."""
        self._events.clear()

    def __len__(self) -> int:
        """Number of layers (len() support)."""
        return len(self.layers)

    def __getitem__(self, position: int) -> Layer:
        """Access by index (stack[i] support)."""
        return self.layers[position]


    def __str__(self) -> str:
        return f"OpticalStack({len(self.layers)} layers, {self.total_thickness():.1f}nm total)"

    def __repr__(self) -> str:
        return f"OpticalStack(stack_id='{self.stack_id}', layers={len(self.layers)})"
