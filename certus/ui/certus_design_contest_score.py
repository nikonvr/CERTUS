"""DESIGN window: the score of the OIC 2025 contest, Problem B.1, for the design on display.

DESIGN solves B.1 as a component specification (R_s = 1 at the three lines, T_s = T_p = 1 elsewhere, in a cube of
index 1.80 at 45 degrees; example/example_design/JSON-design-OIC2025-B1.json). This button gives the contest score
of the current design, which the specification does not minimize directly: the score is a proxy for the component.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def oic2025_b1_report(ui: Any) -> str | None:
    """The score of the current design and whether it keeps the rules, as one line; None without a design."""
    from certus.core.certus_contest_scores import oic2025_b1_score

    stack = ui._get_front_stack()
    ep = getattr(ui, "ep_current", None)
    if not stack or ep is None or len(ep) != len(stack):
        return None
    score, legal = oic2025_b1_score(ui._get_materials(), [layer.mat for layer in stack], np.asarray(ep, dtype=float))
    rules = "within the contest rules" if legal else "OUTSIDE the contest rules (100 layers, 20 um, contest materials)"
    return (
        f"OIC 2025 B.1 score: {score.total:.6f} = contrast term {score.contrast_term:.6f} + "
        f"{score.n_rs_at_least_99}/{score.n_ts_at_least_99} points with Rs/Ts >= 99 % "
        f"({len(stack)} layers, {float(np.sum(ep)):.1f} nm; {rules})"
    )


def show_oic2025_b1_score(ui: Any) -> None:
    """Button handler: log the score of the current design."""
    line = oic2025_b1_report(ui)
    if line is None:
        ui.log("OIC 2025 B.1 score: no design to score.", "WARNING")
        return
    ui.log(line, "SUCCESS")
