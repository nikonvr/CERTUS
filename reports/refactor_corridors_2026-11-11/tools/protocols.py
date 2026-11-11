"""Corridor refactoring, step 5 of a slice extraction: brings the protocols of certus_index_spline_corridor_host.py in line with CONTRACTS.

    python reports/refactor_corridors_2026-11-11/tools/protocols.py

Removes the members no contract names any more. Adds a stub, in IndexSplineRunHost and in sorted place, for each method
of the window that a contract names and no protocol types; the signature is the window's. An attribute that lacks a type
is only reported: its type is a decision.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "tests/unit")
sys.path.insert(0, ".")
import test_the_corridor_mixins_declare_what_they_read_on_the_window as t  # noqa: E402

HOST = Path("certus/ui/certus_index_spline_corridor_host.py")
text = HOST.read_bytes().decode("utf-8").replace("\r\n", "\n")
typed = set().union(*(set(m) for m in t.protocol_members().values()))
contracted = set().union(*(set(names) for names in t.CONTRACTS.values()))

for name in sorted(typed - contracted):
    found = re.findall(rf"^    (?:def {re.escape(name)}\(.*|{re.escape(name)}: .*)\n", text, flags=re.M)
    assert len(found) == 1, (name, found)
    text = text.replace(found[0], "")
    print("removed ", found[0].strip()[:120])


def stub(name: str) -> str:
    func = inspect.unwrap(getattr(t.CertusIndexSplineApp, name))
    signature = inspect.signature(func)
    parts, star_done = [], False
    for p in signature.parameters.values():
        piece = p.name if p.annotation is p.empty else f"{p.name}: {p.annotation}"
        if p.default is not p.empty:
            piece += " = ..."
        if p.kind is p.VAR_POSITIONAL:
            piece, star_done = "*" + piece, True
        elif p.kind is p.VAR_KEYWORD:
            piece = "**" + piece
        elif p.kind is p.KEYWORD_ONLY and not star_done:
            parts.append("*")
            star_done = True
        parts.append(piece)
    returns = "" if signature.return_annotation is signature.empty else f" -> {signature.return_annotation}"
    if "self" not in signature.parameters:
        return f"    @staticmethod\n    def {name}({', '.join(parts)}){returns}: ...\n"
    return f"    def {name}({', '.join(parts)}){returns}: ...\n"


start = text.index("class IndexSplineRunHost(Protocol):")
end = text.index("class IndexSplineViewHost(Protocol):")
block = text[start:end]
for name in sorted(contracted - typed):
    if not callable(inspect.getattr_static(t.CertusIndexSplineApp, name, None)) and not isinstance(
        inspect.getattr_static(t.CertusIndexSplineApp, name, None), staticmethod
    ):
        print("ATTRIBUTE needs a type:", name)
        continue
    new = stub(name)
    defs = [m for m in re.finditer(r"^    def (\w+)\(.*\n", block, flags=re.M)]
    after = [m for m in defs if m.group(1) < name]
    at = after[-1].end() if after else defs[0].start()
    block = block[:at] + new + block[at:]
    print("added   ", new.strip()[:140])
text = text[:start] + block + text[end:]
HOST.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
