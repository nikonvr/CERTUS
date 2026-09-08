"""Table headers must not be force-uppercased: in optics, case is a quantity.

CLAUDE.md fixes the complex refractive index as ``n_hat = n - ik``. Upper-case
``N`` therefore denotes the *complex* index, and ``K`` is not the extinction
coefficient ``k``. A stylesheet that upper-cases every header turns the column
holding the real index into the symbol of another physical quantity -- the
reader cannot tell which one is displayed. The same collision hits ``T``/``t``
and ``R``/``r``.

This is not a cosmetic rule on a metrology tool: it is a correctness rule.

Two stylesheet layers reach a table header, and the defect lived in the second
one -- the theme sheet never upper-cased anything, the premium overrides applied
on top of it did. A guard that read only the theme would have seen nothing, so
this one checks every layer.
"""

from __future__ import annotations

import re

import pytest

# Each entry: (label, callable returning a Qt stylesheet).
STYLESHEET_LAYERS = ("theme", "premium overrides")

_HEADER_BLOCK = re.compile(r"QHeaderView::section[^{]*\{(?P<body>[^}]*)\}", re.DOTALL)


def _layer(name: str) -> str:
    if name == "theme":
        from certus.ui.certus_theme import get_standard_stylesheet

        return get_standard_stylesheet()
    from certus.utils.certus_ux import build_premium_overrides

    return build_premium_overrides()


@pytest.mark.parametrize("layer", STYLESHEET_LAYERS)
def test_no_layer_force_uppercases_table_headers(layer: str) -> None:
    blocks = _HEADER_BLOCK.findall(_layer(layer))
    assert blocks, f"{layer}: no QHeaderView::section block found - has the selector moved?"

    offenders = [b.strip() for b in blocks if "uppercase" in b.replace(" ", "").lower()]
    assert not offenders, (
        f"{layer}: a QHeaderView::section rule upper-cases every table header.\n"
        f"In optics that changes the quantity displayed: the real index n reads as N, "
        f"which denotes the complex index n_hat = n - ik.\n"
        f"Offending rule(s): {offenders}"
    )


def test_the_guard_would_catch_an_upper_casing_rule() -> None:
    """Negative control: the detection must actually bite.

    Without this, a future refactor could silently break the regex above and
    leave a guard that passes on everything.
    """
    faulty = "QHeaderView::section { font-weight: 600; text-transform: uppercase; }"
    blocks = _HEADER_BLOCK.findall(faulty)
    assert blocks, "the regex no longer recognises a QHeaderView::section block"
    assert any("uppercase" in b.replace(" ", "").lower() for b in blocks)
