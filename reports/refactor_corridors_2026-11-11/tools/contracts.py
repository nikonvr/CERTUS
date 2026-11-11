"""Corridor refactoring, step 4 of a slice extraction: rewrites CONTRACTS in certus_index_spline_corridor_host.py from what the code reads, as the contract
test measures it, and says which names the protocols now lack or type for nothing.

    python reports/refactor_corridors_2026-11-11/tools/contracts.py
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "tests/unit")
sys.path.insert(0, ".")
import test_the_corridor_mixins_declare_what_they_read_on_the_window as t  # noqa: E402

HOST = Path("certus/ui/certus_index_spline_corridor_host.py")
raw = HOST.read_bytes()
crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n")
start = text.index("CONTRACTS: dict[str, tuple[str, ...]] = {")
head = text[:start]
order = [name for name in t.CONTRACTS if name in t.CORRIDOR_MIXINS] + sorted(set(t.CORRIDOR_MIXINS) - set(t.CONTRACTS))
lines = ["CONTRACTS: dict[str, tuple[str, ...]] = {"]
union: set[str] = set()
for name in order:
    names = sorted(t.required_by(t.CORRIDOR_MIXINS[name]))
    union |= set(names)
    before = set(t.CONTRACTS.get(name, ()))
    print(f"{name}: {len(names)} names ({len(before)} before; +{len(set(names) - before)} -{len(before - set(names))})")
    if not names:
        lines.append(f'    "{name}": (),')
        continue
    lines.append(f'    "{name}": (')
    body = ", ".join(f'"{n}"' for n in names) + ","
    lines += textwrap.wrap(body, width=112, initial_indent="        ", subsequent_indent="        ", break_long_words=False)
    lines.append("    ),")
lines.append("}")
HOST.write_bytes(((head + "\n".join(lines) + "\n").replace("\n", "\r\n") if crlf else head + "\n".join(lines) + "\n").encode("utf-8"))
typed = set().union(*(set(m) for m in t.protocol_members().values()))
print("read and not typed by a protocol:", sorted(union - typed))
print("typed and no longer read:", sorted(typed - union))
