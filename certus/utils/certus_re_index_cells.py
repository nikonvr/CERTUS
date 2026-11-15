"""Read one optical-index column of RE's 'index' sheet without ever inventing a value.

Audit 2026-11-15, M-L6g: a cell "2,30" (decimal comma stored as text) used to become n = 1.5 without a message, and
the reverse engineering ran on a wrong stack. Here a decimal comma is read; a cell that still cannot be read, or an
empty cell where emptiness is not allowed, raises ValueError naming the column and the data row.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def index_column_values(
    rows: Sequence[tuple], col_idx: int | None, n_rows: int, default: float, name: str, empty_ok: bool
) -> np.ndarray:
    """Values of column ``col_idx`` over the first ``n_rows`` data rows.

    A missing column (``col_idx is None``) gives ``default`` everywhere. An empty cell gives ``default`` when
    ``empty_ok`` (k: no absorption), and raises otherwise (n: no guess).
    """

    if col_idx is None:
        return np.full(n_rows, default, dtype=np.float64)

    out = np.empty(n_rows, dtype=np.float64)

    for i in range(n_rows):
        row = rows[i]
        v = row[col_idx] if len(row) > col_idx else None
        if v is None or (isinstance(v, str) and not v.strip()):
            if not empty_ok:
                raise ValueError(f"'index' sheet: empty {name} cell on data row {i + 1}.")
            out[i] = default
            continue
        if isinstance(v, str):
            s = v.strip()
            v = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s
        try:
            out[i] = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"'index' sheet: unreadable {name} value {v!r} on data row {i + 1}.") from None

    return out
