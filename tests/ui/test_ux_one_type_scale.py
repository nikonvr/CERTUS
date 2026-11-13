"""One body size, nothing under the scale, and no window gains a size (U9).

Measured on 2026-11-13 (`scripts/audit_ux_certus.py::font_sizes`, 1440x900, visible texts at opening): DESIGN and RE
wrote their body at 11 pt and the nine other windows at 10 pt; METAL painted its header at 6.0 and 5.2 pt. Decision
Q34 of the corridor plan: the body is Typography.BODY (10 pt) everywhere. The HUB is a page of tiles, not of body text.
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, _run_worker

#: Distinct sizes painted at opening, measured on 2026-11-13 after the body was unified: a ceiling, lowered as U9 goes.
SIZES_CEILING = {
    "CERTUS_DESIGN": 6,
    "CERTUS_FIELD": 6,
    "CERTUS_HUB": 6,
    "CERTUS_INDEX": 6,
    "CERTUS_INDEX_SPLINE": 6,
    "CERTUS_METAL_BILAYER": 6,
    "CERTUS_METAL_SINGLE": 5,
    "CERTUS_RE": 7,
    "CERTUS_SMOOTHER": 4,
    "CERTUS_STRAT": 8,
    "CERTUS_SUBSTRATE_INDEX": 4,
}
NOT_BODY_TEXT = frozenset({"CERTUS_HUB"})


@pytest.mark.parametrize("app", sorted(MODULES))
def test_the_window_keeps_to_the_scale(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")
    sizes = {float(k): v for k, v in row["font_sizes"]["sizes"].items()}
    scale = row["font_sizes"]["scale"]

    assert min(sizes) >= scale["CAPTION"], f"{app} paints a text under the smallest size of the scale: {sizes}"
    assert len(sizes) <= SIZES_CEILING[app], f"{app} paints {len(sizes)} sizes, ceiling {SIZES_CEILING[app]}: {sizes}"
    if app not in NOT_BODY_TEXT:
        body = max(sizes, key=sizes.get)
        assert body == scale["BODY"], f"{app} writes its body at {body} pt, not at BODY ({scale['BODY']}): {sizes}"
