"""At 1366x768 STRAT and the two METAL windows no longer fail the layout rules of the UX harness (audit UX A06, ETAT D61).

Measured 2026-10-02 at 1366x768 (`scripts/audit_ux_certus.py`):

    STRAT         plots 59.6 % of the window for the 65 % the harness asks; its "Design" page needed 525 px
                  because the stack table sat beside a 300 px grid of buttons (the code said so: "reaching 65 %
                  requires REORGANISING this panel, not resizing it")
    METAL SINGLE  the control panel needed 442 px and was given 394 (the label "Clear / Reset" was cut)
    METAL BILAYER 453 px for 394

Three causes, all shared components: the logo of the header has a width of its own that the header could not give
back (180 px, fixed), the reset button carried an icon beside a label that has its own symbol, and the STRAT stack
card laid its table beside its buttons. The ratchet (tests/ui/test_ux_ratchet.py) keeps each figure from getting
worse; this test states the rules themselves, which the ratchet does not: a panel that overflows, and plots under
65 %, are verdicts of the harness, not figures.
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import _run_worker, _verdicts

LAYOUT_RULES = ("plot area", "overflows", "hides")


@pytest.mark.parametrize("app", ["CERTUS_STRAT", "CERTUS_METAL_SINGLE", "CERTUS_METAL_BILAYER"])
def test_the_window_passes_the_layout_rules_at_1366x768(app) -> None:
    row = _run_worker(app, 1366, 768)
    assert "ERROR" not in row, row.get("ERROR")

    broken = [v for v in _verdicts(row) if any(rule in v for rule in LAYOUT_RULES)]

    assert not broken, f"{app} at 1366x768: {broken}"
