"""One quantity, one precision (plan UX, 4.6).

DESIGN uses seven different float formats. **That is not the defect** - a
thickness in nanometres and a refractive index have no reason to share a number
of decimals, and forcing them to would be worse.

The defect is the same quantity rendered two ways. 📏 Measured 2026-09-08:
``best_rmse``, ``best_mc`` and ``best_fab`` - the same three fields of the same
record - are written with six decimals in the text report and **five** in the
table built from it, both in ``certus_design_ui_plot``. The operator reads
``0.002733`` in one view and ``0.00273`` in the other, and has no way to know it
is the same number.

⚠️ This guard does NOT rule on how many decimals an RMSE deserves. That is a
scientific question - ``CLAUDE.md`` §24-26 measured a Monte-Carlo dispersion of
about 6 %, which six decimals plainly overstate - and it belongs to the project
owner, not to a consistency check. All this asserts is that the answer is the
same everywhere.

Two contexts are excluded on purpose:

- **file names** (``base_name = f"..._RMSE_{v:.5f}"``): renaming artefacts has
  effects outside the interface;
- ``rmse_per_n * 1000``, which is a different quantity on a different scale.
"""

from __future__ import annotations

import pathlib
import re

import pytest

#: The screen-facing modules of DESIGN.
SOURCES = sorted(pathlib.Path("certus/ui").glob("certus_design_ui_*.py"))

#: ``{ <expression> :.Nf }`` inside an f-string.
FORMAT = re.compile(r"\{([^{}:]{1,80}?):\.(\d)f\}")

#: Quantities we can name without guessing, and the identifiers that carry them.
QUANTITIES = {
    "RMSE": ("best_rmse", "best_mc", "best_fab", "rmse_val", "best_overall_rmse"),
    "minimum layer thickness": ("dmin_r", "dmin_m", "dmin_f", "dmin_rmse", "dmin_mc", "dmin_fab"),
}

#: Contexts where a different precision is legitimate.
EXCLUDED_SUBSTRINGS = ("base_name", "rmse_per_n")


def _sites(quantity: str) -> list[tuple[str, int, int, str]]:
    """Every ``(file, line, precision, expression)`` formatting that quantity."""
    names = QUANTITIES[quantity]
    out: list[tuple[str, int, int, str]] = []
    for path in SOURCES:
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(bad in line for bad in EXCLUDED_SUBSTRINGS):
                continue
            for expr, digits in FORMAT.findall(line):
                if any(name in expr for name in names):
                    out.append((path.name, lineno, int(digits), expr.strip()))
    return out


def test_the_sources_are_there():
    """Contrôle négatif : no file, no finding, and every test below is vacuous."""
    assert len(SOURCES) >= 5, f"only {len(SOURCES)} DESIGN module(s) found"


@pytest.mark.parametrize("quantity", sorted(QUANTITIES))
def test_the_quantity_is_actually_formatted_somewhere(quantity: str):
    """Contrôle négatif, per quantity: an empty list would pass for free."""
    assert len(_sites(quantity)) >= 4, f"{quantity}: only {len(_sites(quantity))} formatting site(s) found"


@pytest.mark.parametrize("quantity", sorted(QUANTITIES))
def test_one_quantity_is_shown_with_one_precision(quantity: str):
    sites = _sites(quantity)
    precisions = sorted({p for _f, _l, p, _e in sites})
    if len(precisions) > 1:
        detail = "\n".join(
            f"      {f}:{ln}  .{p}f  on {e}" for f, ln, p, e in sorted(sites, key=lambda s: (s[2], s[0], s[1]))
        )
        pytest.fail(
            f"{quantity} is shown with {len(precisions)} different precisions {precisions} - "
            f"the same value reads differently depending on the view:\n{detail}"
        )
