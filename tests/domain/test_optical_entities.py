"""
Property-Based Tests for Domain Entities (Layer, OpticalStack)

Tests exhaustifs avec Hypothesis.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, assume, settings

from certus.domain.optical.entities import Layer, OpticalStack
from certus.domain.optical.value_objects import (
    Thickness,
    RefractiveIndex,
    Wavelength,
)


# ============================================================================
# Layer Entity Tests
# ============================================================================


@given(
    material=st.text(min_size=1, max_size=20),
    thickness_nm=st.floats(min_value=1.0, max_value=1000.0),
    n=st.floats(min_value=1.0, max_value=4.0),
    k=st.floats(min_value=0.0, max_value=0.5),
)
@settings(max_examples=100, deadline=1000)
def test_layer_creation_valid(material, thickness_nm, n, k):
    """Property: Valid inputs should create valid Layer."""
    layer = Layer(material, Thickness(thickness_nm), RefractiveIndex(n, k))

    assert layer.material_id == material
    assert layer.thickness.nm == pytest.approx(thickness_nm)
    assert layer.refractive_index.n == pytest.approx(n)
    assert layer.refractive_index.k == pytest.approx(k)


@given(
    thickness_nm=st.floats(min_value=1.0, max_value=1000.0),
    n=st.floats(min_value=1.0, max_value=4.0),
    wl_nm=st.floats(min_value=400.0, max_value=700.0),
)
@settings(max_examples=100, deadline=1000)
def test_layer_optical_thickness(thickness_nm, n, wl_nm):
    """Property: Optical thickness = n × d."""
    layer = Layer("Test", Thickness(thickness_nm), RefractiveIndex(n, 0.0))
    wl = Wavelength(wl_nm)

    opt_thickness = layer.optical_thickness_at(wl)
    expected = thickness_nm * n

    assert np.isclose(opt_thickness, expected, rtol=1e-10)


@given(
    wl_nm=st.floats(min_value=400.0, max_value=700.0),
    n=st.floats(min_value=1.5, max_value=3.0),
)
@settings(max_examples=50, deadline=1000)
def test_layer_quarter_wave(wl_nm, n):
    """Property: Layer with d=λ/(4n) is quarter-wave."""
    qwot_thickness = wl_nm / (4 * n)
    layer = Layer("QWOT", Thickness(qwot_thickness), RefractiveIndex(n, 0.0))
    wl = Wavelength(wl_nm)

    assert layer.is_quarter_wave_at(wl, tolerance=0.01)


def test_layer_rejects_empty_material():
    """Property: Empty material_id must be rejected."""
    with pytest.raises(ValueError):
        Layer("", Thickness(50.0), RefractiveIndex(1.5, 0.0))


# ============================================================================
# OpticalStack Aggregate Tests
# ============================================================================


@given(n_layers=st.integers(min_value=1, max_value=20))
@settings(max_examples=50, deadline=2000)
def test_stack_add_layers(n_layers):
    """Property: Stack can hold N layers."""
    stack = OpticalStack()

    for i in range(n_layers):
        layer = Layer(f"Mat{i}", Thickness(50.0), RefractiveIndex(1.5 + i * 0.1, 0.0))
        stack.add_layer(layer)

    assert stack.layer_count() == n_layers
    assert len(stack) == n_layers


@given(
    n_layers=st.integers(min_value=2, max_value=10),
    remove_pos=st.integers(min_value=0, max_value=9),
)
@settings(max_examples=50, deadline=2000)
def test_stack_remove_layer(n_layers, remove_pos):
    """Property: Removing layer decreases count by 1."""
    assume(remove_pos < n_layers)

    stack = OpticalStack()
    for i in range(n_layers):
        stack.add_layer(Layer(f"Mat{i}", Thickness(50.0), RefractiveIndex(1.5, 0.0)))

    initial_count = stack.layer_count()
    stack.remove_layer(remove_pos)

    assert stack.layer_count() == initial_count - 1


def test_stack_cannot_remove_last_layer():
    """Property: Cannot remove last layer (minimum 1)."""
    stack = OpticalStack()
    stack.add_layer(Layer("Only", Thickness(50.0), RefractiveIndex(1.5, 0.0)))

    with pytest.raises(ValueError, match="Cannot remove last layer"):
        stack.remove_layer(0)


@given(thicknesses=st.lists(st.floats(min_value=10.0, max_value=200.0), min_size=1, max_size=10))
@settings(max_examples=50, deadline=2000)
def test_stack_total_thickness(thicknesses):
    """Property: Total thickness = sum of individual thicknesses."""
    stack = OpticalStack()

    for i, t in enumerate(thicknesses):
        stack.add_layer(Layer(f"Mat{i}", Thickness(t), RefractiveIndex(1.5, 0.0)))

    expected_total = sum(thicknesses)
    assert np.isclose(stack.total_thickness(), expected_total, rtol=1e-10)


@given(n_layers=st.integers(min_value=1, max_value=10))
@settings(max_examples=50, deadline=2000)
def test_stack_emits_events(n_layers):
    """Property: Adding N layers emits N LayerAdded events."""
    stack = OpticalStack()

    for i in range(n_layers):
        stack.add_layer(Layer(f"Mat{i}", Thickness(50.0), RefractiveIndex(1.5, 0.0)))

    events = stack.get_events()
    layer_added_events = [e for e in events if e["type"] == "LayerAdded"]

    assert len(layer_added_events) == n_layers


def test_stack_validation():
    """Property: Valid stack passes validation."""
    stack = OpticalStack()
    stack.add_layer(Layer("Test", Thickness(50.0), RefractiveIndex(1.5, 0.0)))

    assert stack.validate() is True

    events = stack.get_events()
    validation_events = [e for e in events if e["type"] == "StackValidated"]
    assert len(validation_events) > 0


def test_stack_indexing():
    """Property: Stack supports indexing like a list."""
    stack = OpticalStack()
    layer1 = Layer("First", Thickness(50.0), RefractiveIndex(1.5, 0.0))
    layer2 = Layer("Second", Thickness(100.0), RefractiveIndex(2.0, 0.0))

    stack.add_layer(layer1)
    stack.add_layer(layer2)

    assert stack[0].material_id == "First"
    assert stack[1].material_id == "Second"
    assert stack.get_layer(0).material_id == "First"


@given(n_layers=st.integers(min_value=1, max_value=10))
@settings(max_examples=30, deadline=2000)
def test_stack_has_absorbing_layers(n_layers):
    """Property: Stack correctly detects absorbing layers."""
    stack = OpticalStack()

    # Add transparent layers
    for i in range(n_layers - 1):
        stack.add_layer(Layer(f"Trans{i}", Thickness(50.0), RefractiveIndex(1.5, 0.0)))

    # Add one absorbing layer
    stack.add_layer(Layer("Absorbing", Thickness(50.0), RefractiveIndex(1.5, 0.1)))

    assert stack.has_absorbing_layers(threshold=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
