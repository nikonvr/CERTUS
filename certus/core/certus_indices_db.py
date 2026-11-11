"""Where the indices database of the suite is: one function, under the programs that open it.

STRAT and FIELD read the same spreadsheet of refractive indices. The function that finds it lived in the STRAT
workers, so FIELD imported the worker module of another program for it. It is here, in the core; the STRAT workers
import it back under the name they always exposed.
"""

from pathlib import Path

from certus.core.certus_core import get_resource_path


def _resolve_strat_indices_db_path() -> str:
    """Return canonical indices DB path for STRAT, with legacy fallback."""

    preferred = str(Path(get_resource_path(str(Path("example") / "database_index" / "indices.xlsx"))).resolve())

    if Path(preferred).exists():
        return preferred

    legacy = str(Path(get_resource_path("clues.xlsx")).resolve())

    return legacy
