"""Corridor refactoring, step 3 of a slice extraction: the manifest scripts/refactor_guard.py reads, from the move specification.

    python reports/refactor_corridors_2026-11-11/tools/manifest.py SPEC.json PHASE "sentence" compat_stem:CompatClass [compat_stem:CompatClass ...]

`added_attributes` lists, for each compatibility class that inherits the slice, the moved methods it did not define.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

M = "certus.ui.certus_index_spline_"

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
phase, sentence, compat = sys.argv[2], sys.argv[3], sys.argv[4:]
target = f"{M}{Path(spec['target']).stem.replace('certus_index_spline_', '')}:{spec['class']}"
manifest = {
    "phase": f"{phase} - {sentence}",
    "new_classes": [target],
    "moved_methods": [{"name": name, "from": f"{M}{stem}:{klass}", "to": target} for stem, klass, name in spec["methods"]],
    "added_attributes": sorted(
        f"{M}{c}.{name}" for c in compat for stem, klass, name in spec["methods"] if f"{stem}:{klass}" != c
    ),
}
out = Path(f"reports/refactor_corridors_2026-11-11/manifests/phase_{phase}.json")
out.write_bytes((json.dumps(manifest, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
print(out, len(manifest["moved_methods"]), "moved,", len(manifest["added_attributes"]), "added attributes")
