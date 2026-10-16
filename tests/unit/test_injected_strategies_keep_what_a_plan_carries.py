"""An injected plan keeps what it carries besides its blocks: the layers laid by Rate, the slit, the testglass swaps.

`_resolve_injected_strategies` rebuilt each plan from its blocks alone, so a plan exported with `rate_layers`, a slit of its own
or testglass swaps entered the search as a pure optical plan: the injection of a Rate plan (task A9) silently evaluated
something else than what was handed over (reports/STRAT_Rate_expertise_2026-10-13.md, "Limite de routage"). The keys are the ones
the children of ELITE already keep, `_INHERITED_KEYS`, so the two routes cannot drift apart.
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_consensus import _INHERITED_KEYS
from certus.workers.certus_strat_workers import _resolve_injected_strategies as resolve

BLOCKS = [{"start": 0, "end": 10, "wavelength": 562.0}, {"start": 10, "end": 20, "wavelength": 476.0}]
CARRIED = {
    "rate_layers": [9, 10, 11],
    "monochromator_resolution_nm": 2.0,
    "witness_reset_layers": [5],
}


def _plan(**extra) -> dict:
    return {"nom": "carrier", "blocs": [dict(b) for b in BLOCKS], **extra}


def test_the_carried_keys_are_the_ones_the_children_inherit() -> None:
    assert set(CARRIED) == set(_INHERITED_KEYS)


@pytest.mark.parametrize("key", _INHERITED_KEYS)
def test_a_plan_keeps_each_key_it_carries(key: str) -> None:
    out = resolve({"injected_strategies": [_plan(**{key: CARRIED[key]})]})

    assert out[0][key] == CARRIED[key]


def test_the_carried_values_are_copies_not_the_callers_objects() -> None:
    source = _plan(**CARRIED)

    out = resolve({"injected_strategies": [source]})
    out[0]["rate_layers"].append(99)

    assert source["rate_layers"] == [9, 10, 11]


def test_a_plan_without_them_enters_exactly_as_before() -> None:
    out = resolve({"injected_strategies": [_plan()]})

    assert not set(_INHERITED_KEYS) & set(out[0])
    assert out[0]["blocks"] == BLOCKS


@pytest.mark.parametrize("empty", [None, []])
def test_an_empty_value_is_not_carried(empty) -> None:
    out = resolve({"injected_strategies": [_plan(rate_layers=empty)]})

    assert "rate_layers" not in out[0]
