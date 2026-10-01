"""CERTUS INDEX finds its sapphire table, example/sapphire fresnel.xlsx.

The path was built from the folder of the module that reads it: once certus_index_core moved
into certus/core (c2b1030, 2026-05-27) it named certus/core/example/sapphire fresnel.xlsx,
which does not exist, and every import warned "Sapphire substrate reference unavailable". The
fit itself never depended on it: the worker treats every substrate but silicon as transparent.
The table feeds the run log and the export summary.
"""

from __future__ import annotations

from pathlib import Path


def test_the_sapphire_table_is_read() -> None:
    import certus.core.certus_index_core as core

    assert Path(core._SAPPHIRE_DATA_FILE).is_file(), core._SAPPHIRE_DATA_FILE
    assert core._SAPPHIRE_WLS is not None
    assert len(core._SAPPHIRE_WLS) > 0
