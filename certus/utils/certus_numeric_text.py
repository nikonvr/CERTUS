"""Reading a number the operator typed."""

from __future__ import annotations

import math

# Space, no-break space, narrow no-break space, thin space: the separators of thousands.
_SPACES = (" ", "\u00a0", "\u202f", "\u2009")


def parse_decimal(text: str) -> float:
    """Return the finite number written in ``text``.

    The decimal comma is read as a decimal point, since it is the natural way to write 1550.5 on
    a French keyboard, and spaces are ignored. Nothing else is guessed: an empty text, a text
    with several commas, one that has both a comma and a point, and anything that is not
    finite (``nan``, ``inf``) raise ``ValueError``, so that the caller can tell the operator
    instead of substituting a value he never typed.
    """
    cleaned = str(text).strip()
    for space in _SPACES:
        cleaned = cleaned.replace(space, "")
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    value = float(cleaned)
    if not math.isfinite(value):
        raise ValueError(f"not a finite number: {text!r}")
    return value
