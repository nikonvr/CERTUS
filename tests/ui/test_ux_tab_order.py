"""The synthesis tab comes first, the promotional tab last (step T10 / 2.x).

Tab ORDER used to be checked by accident: the skeleton guard joined every tab
title into one signature, so any reordering broke the string. That same property
made ADDING a tab look like a removal, so the signature was split per tab on
2026-09-04 - and the accidental order coverage went with it.

Order is a real requirement, so it is asserted on purpose here instead:

  * a window that computes something must let the operator read the outcome
    first, not scroll past an argument for buying the software;
  * step T10 settled on option B - keep the promotional tab, put it last.

Reads the ordered titles the audit harness records (out["tab_titles"]), so it
measures one process per module like every other harness-backed guard.
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import _run_worker

#: The six modules that carried a promotional tab when step T10 was written.
#: Measured 2026-09-04: most no longer have one (T10 was applied as option A,
#: removal), so sweeping all eleven cost 11 workers for 2 real assertions.
CANDIDATES = [
    "CERTUS_DESIGN",
    "CERTUS_STRAT",
    "CERTUS_RE",
    "CERTUS_INDEX",
    "CERTUS_METAL_SINGLE",
    "CERTUS_METAL_BILAYER",
]

PROMOTIONAL = ("why certus", "about")
SYNTHESIS = ("synthesis", "overview", "synth")


@pytest.fixture(scope="module")
def tabs_by_module() -> dict[str, list[str]]:
    return {tag: _run_worker(tag, 1920, 1080).get("tab_titles", []) for tag in CANDIDATES}


@pytest.mark.parametrize("tag", CANDIDATES)
def test_promotional_tab_never_precedes_the_synthesis_tab(tag: str, tabs_by_module) -> None:
    """A sales pitch must not sit between the operator and the result."""
    titles = [t.lower() for t in tabs_by_module[tag]]
    promo = [i for i, t in enumerate(titles) if any(k in t for k in PROMOTIONAL)]
    synth = [i for i, t in enumerate(titles) if any(k in t for k in SYNTHESIS)]
    if not promo or not synth:
        pytest.skip(f"{tag} has no promotional or no synthesis tab")

    assert min(promo) > max(synth), (
        f"{tag}: promotional tab at index {min(promo)} precedes the synthesis tab "
        f"at {max(synth)} - tabs are {tabs_by_module[tag]}"
    )


@pytest.mark.parametrize("tag", CANDIDATES)
def test_promotional_tab_is_the_last_one(tag: str, tabs_by_module) -> None:
    """Option B of step T10: the promotional tab stays, at the end."""
    titles = [t.lower() for t in tabs_by_module[tag]]
    promo = [i for i, t in enumerate(titles) if any(k in t for k in PROMOTIONAL)]
    if not promo:
        pytest.skip(f"{tag} has no promotional tab")

    assert max(promo) == len(titles) - 1, (
        f"{tag}: the promotional tab is not last - tabs are {tabs_by_module[tag]}"
    )
