"""Corridor refactoring, step 6 of a slice extraction: points the `born_in` entries of the corridor state table, and any other
`stem:Class.method` reference of the group, to the new place of the methods.

    python reports/refactor_corridors_2026-11-11/tools/born_in.py SPEC.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target_stem = Path(spec["target"]).stem.replace("certus_index_spline_", "")
path = Path("certus/ui/certus_index_spline_corridor_state.py")
text = path.read_bytes().decode("utf-8")
count = 0
for stem, klass, name in spec["methods"]:
    old, new = f"{stem}:{klass}.{name}", f"{target_stem}:{spec['class']}.{name}"
    count += text.count(old)
    text = text.replace(old, new)
path.write_bytes(text.encode("utf-8"))
print(f"corridor_state: {count} reference(s) repointed")
