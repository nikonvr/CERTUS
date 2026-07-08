"""
CERTUS Domain - OpticalStack Aggregate Root

Aggregate root pour un stack de couches optiques.
Gère les invariants métier et émet des domain events.
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
    Stack de couches optiques (Aggregate Root).

    Invariants:
    - Au moins 1 couche (substrate)
    - Toutes les épaisseurs > 0
    - Ordre des couches préservé

    Events émis:
    - LayerAdded
    - LayerRemoved
    - StackValidated
    """

    stack_id: str = field(default_factory=lambda: str(uuid4()))
    layers: List[Layer] = field(default_factory=list)
    _events: List[dict] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Validation initiale."""
        if not isinstance(self.layers, list):
            raise TypeError("layers must be a list")

    def add_layer(self, layer: Layer, position: Optional[int] = None) -> None:
        """
        Ajoute une couche au stack.

        Args:
            layer: Couche à ajouter
            position: Position dans le stack (None = fin)

        Raises:
            TypeError: Si layer n'est pas un Layer
            ValueError: Si position invalide
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
        Retire une couche du stack.

        Args:
            position: Index de la couche à retirer

        Returns:
            Layer retirée

        Raises:
            ValueError: Si position invalide
            ValueError: Si tentative de retirer la dernière couche
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
        Récupère une couche par position.

        Args:
            position: Index de la couche

        Returns:
            Layer à cette position

        Raises:
            IndexError: Si position hors limites
        """
        return self.layers[position]

    def layer_count(self) -> int:
        """Nombre de couches dans le stack."""
        return len(self.layers)

    def total_thickness(self) -> float:
        """
        Épaisseur totale physique du stack (nm).

        Returns:
            Somme des épaisseurs de toutes les couches
        """
        return sum(layer.thickness.nm for layer in self.layers)

    def total_optical_thickness(self, wavelength: Wavelength) -> float:
        """
        Épaisseur optique totale à une longueur d'onde (nm).

        Args:
            wavelength: Longueur d'onde de référence

        Returns:
            Somme des épaisseurs optiques n×d
        """
        return sum(layer.optical_thickness_at(wavelength) for layer in self.layers)

    def has_absorbing_layers(self, threshold: float = 1e-6) -> bool:
        """
        Vérifie si le stack contient des couches absorbantes.

        Args:
            threshold: Seuil de détection k

        Returns:
            True si au moins une couche a k > threshold
        """
        return any(layer.is_absorbing(threshold) for layer in self.layers)

    def validate(self) -> bool:
        """
        Valide les invariants du stack.

        Returns:
            True si tous les invariants sont respectés

        Raises:
            ValueError: Si un invariant est violé
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
        Récupère les domain events émis.

        Returns:
            Liste des events (copie)
        """
        return self._events.copy()

    def clear_events(self) -> None:
        """Efface les domain events après publication."""
        self._events.clear()

    def __len__(self) -> int:
        """Nombre de couches (support len())."""
        return len(self.layers)

    def __getitem__(self, position: int) -> Layer:
        """Accès par index (support stack[i])."""
        return self.layers[position]

    def __str__(self) -> str:
        return f"OpticalStack({len(self.layers)} layers, {self.total_thickness():.1f}nm total)"

    def __repr__(self) -> str:
        return f"OpticalStack(stack_id='{self.stack_id}', layers={len(self.layers)})"
