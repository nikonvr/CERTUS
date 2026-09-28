"""CERTUS DESIGN changes directory to its own folder, not to certus/ui.

`main()` does `os.chdir(script_dir)`, and the log files are relative paths. CERTUS_DESIGN.py
computed its own `env` and `script_dir`, then three `import *` lines overwrote both with those of
certus_design_common: until 2026-09-28 DESIGN ran inside certus/ui, where its logs went
(certus/ui/certus_design.log, certus/ui/logs/). The module is a CertusFacadeModule whose own
dict is a copy of the module's globals, the ones `main()` reads.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_design_changes_directory_to_its_own_folder() -> None:
    import CERTUS_DESIGN

    assert Path(CERTUS_DESIGN.script_dir) == ROOT
    assert CERTUS_DESIGN.env["module_name"] == "CERTUS_DESIGN"
