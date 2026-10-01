"""The slow tier: `pytest -m "not slow"` runs the tests that take less than a second (audit v2, plan S3.3).

156 test functions of `tests/unit` out of some 4 200 take 85 % of the 15 minutes 39 the suite lasts (measured warm on 2026-10-01). They are listed in
`tests/slow_tests.json` and marked `slow` at collection by `tests/conftest.py`, so that nobody has to put a marker on that many tests and keep it true.
The list is rewritten from a `--durations` log by `scripts/refresh_slow_tests.py`.

The logic is here, in a module of its own, because a conftest cannot be imported from a test: the hook in `conftest.py` is one line and what it does is tested.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

LIST = Path(__file__).with_name("slow_tests.json")


def slow_test_ids(path: Path = LIST) -> frozenset[str]:
    """The test functions listed as slow ('tests/unit/test_x.py::test_y', 'tests/unit/test_x.py::TestC::test_y'); none if the list is absent or unreadable."""
    try:
        return frozenset(json.loads(path.read_text(encoding="utf-8"))["tests"])
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()


def is_slow(nodeid: str, slow: frozenset[str]) -> bool:
    """A parametrized test is slow when its function is, whatever its parameters: the list keeps the duration of the worst instance."""
    return nodeid.split("[", 1)[0] in slow


def mark_slow(items: Iterable[Any], slow: frozenset[str], marker: Any) -> int:
    """Add `marker` to the items whose function is in `slow`; the number marked."""
    marked = 0
    for item in items:
        if is_slow(item.nodeid, slow):
            item.add_marker(marker)
            marked += 1
    return marked
