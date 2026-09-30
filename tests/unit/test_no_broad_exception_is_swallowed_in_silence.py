"""A broad `except` in `certus/` leaves a trace: it never swallows an error in silence.

The audit of 2026-09-29 counted 74 handlers of `except Exception:` (or a bare `except:`) whose body did nothing (`pass`,
`continue`). Each one is a place where a failure disappears: a toast that did not show, a handler that did not flush, an
objective that raised in the middle of an optimisation, and nobody, later, can say whether it happened once or ten thousand
times. All 74 now write a DEBUG record with the traceback (`logging.getLogger("CERTUS").debug(..., exc_info=True)`), which
costs nothing when the level is higher and is exactly what a session with `--log-level DEBUG` needs; the behaviour is
unchanged, the error is still swallowed.

The scan is the definition of `scripts/metrics.py` (`arch.except_avales`): a handler of `Exception`, `BaseException` or
nothing, whose body only holds `pass`, `continue` or a constant. Narrowing a handler to the exceptions it really expects
is better than logging it, and is done case by case; a NEW silent one fails here.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: (file -> why a silent broad handler may stay). Empty: none has a reason a DEBUG record would not serve.
ALLOWED: dict[str, str] = {}


def _silent_broad_handlers(tree: ast.AST) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            kind = handler.type
            broad = kind is None or (isinstance(kind, ast.Name) and kind.id in ("Exception", "BaseException"))
            silent = all(
                isinstance(stmt, ast.Pass | ast.Continue)
                or (isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant))
                for stmt in handler.body
            )
            if broad and silent:
                lines.append(handler.lineno)
    return lines


def _offenders() -> dict[str, list[int]]:
    found = {}
    for path in sorted((ROOT / "certus").rglob("*.py")):
        lines = _silent_broad_handlers(ast.parse(path.read_text(encoding="utf-8-sig", errors="replace")))
        if lines:
            found[path.relative_to(ROOT).as_posix()] = lines
    return found


def test_no_broad_exception_handler_of_certus_does_nothing() -> None:
    offenders = {f: lines for f, lines in _offenders().items() if f not in ALLOWED}

    assert not offenders, (
        "a broad `except` that does nothing makes an error disappear. Narrow it to the exceptions it expects, or write "
        f'`logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)`: {offenders}'
    )


def test_every_allowed_file_still_has_one() -> None:
    stale = sorted(set(ALLOWED) - set(_offenders()))

    assert not stale, f"these no longer swallow anything in silence: remove them from ALLOWED: {stale}"


def test_the_scan_sees_every_way_of_swallowing_and_only_those() -> None:
    silent = ast.parse(
        "try:\n    f()\nexcept Exception:\n    pass\n"
        "try:\n    f()\nexcept BaseException:\n    pass\n"
        "try:\n    f()\nexcept:\n    pass\n"
        "for x in y:\n    try:\n        f()\n    except Exception:\n        continue\n"
        "try:\n    f()\nexcept Exception:\n    'a reason, said in a string'\n"
        "try:\n    f()\nexcept Exception:\n    ...\n"
    )
    not_silent = ast.parse(
        "try:\n    f()\nexcept Exception:\n    log.debug('x', exc_info=True)\n"
        "try:\n    f()\nexcept ValueError:\n    pass\n"
        "try:\n    f()\nexcept (OSError, ValueError):\n    pass\n"
        "try:\n    f()\nexcept Exception:\n    raise\n"
        "try:\n    f()\nexcept Exception:\n    x = 1\n"
    )

    assert len(_silent_broad_handlers(silent)) == 6
    assert _silent_broad_handlers(not_silent) == []
