"""D85: the RE warmup must reach the end, or the first real RE computation compiles the kernels it was meant to.

It built its indices with the wavelengths first, where a real run has the layers first, and stopped on
`IndexError: index 2 is out of bounds for axis 0 with size 2` in `_global_evaluate_oblique_physics`, which its own
`except Exception` swallowed (measured on 2026-10-03, and again on 2026-10-06). The except stays: a warmup must never
take an application down. What it swallows is now nothing.
"""

from __future__ import annotations

import logging

import certus.core.certus_re_objectives as objectives


def test_the_re_warmup_swallows_nothing(caplog):
    with caplog.at_level(logging.DEBUG, logger="CERTUS"):
        objectives._warmup_re_physics()

    swallowed = [r for r in caplog.records if r.exc_info and "Silenced exception" in r.getMessage()]
    assert swallowed == [], swallowed[0].exc_info[1] if swallowed else None
