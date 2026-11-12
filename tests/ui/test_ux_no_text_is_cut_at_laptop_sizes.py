"""No text of the eleven windows is cut at 1366x768 nor at 1440x900 (U3).

Measured on 2026-11-12 with `scripts/audit_ux_certus.py::clipped_texts`, the window as it opens, one process per module:
19 texts were cut at 1440x900 and 20 at 1366x768.

    INDEX SPLINE  8  two steps of the workflow guide in a column of 119 px ("Substrate (n) & layer thickness" asks for
                     199), two card titles, "Nominal thickness (nm):" (138 px for 78), the hint under the run buttons,
                     two labels of the progress widget
    STRAT         9  the emojis of the welcome page, 26 and 27 px wide in boxes of 24 and 25
    DESIGN        2  the headers "λ min (nm)" and "λ max (nm)" of the targets table, in columns of 63 px
    RE            1  the header "n@lambda₀" of the stack table, 83 px for 54

None is left. This test holds the count at zero for every window, at both sizes. It reads `clipped` only: a text that is
whole but eats the padding of its widget (`tight`) is a lesser defect and is not held here. What the window does not show
when it opens (another tab, a collapsed panel) is not measured.
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker

SIZES = ((1366, 768), (1440, 900))


@pytest.mark.parametrize(("width", "height"), SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
@pytest.mark.parametrize("app", sorted(MODULES))
def test_no_text_of_the_window_is_cut(app, width, height) -> None:
    row = _run_worker(app, width, height)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["clipped"] == [], f"{app} at {width}x{height} cuts {len(row['clipped'])} text(s)"
