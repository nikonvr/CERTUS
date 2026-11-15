"""Audit M-L4a, M-L4b, M-L4c: how RE reads a column header and decides percent against fraction (direct calls).

    python reports/audit_code_2026-11-15/preuves/p_lecture_mesures.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from certus.utils.certus_re_helpers import (  # noqa: E402
    _re_header_normalize_for_tokens,
    _re_measurement_values_are_percent,
    parse_re_column_header,
)

print("M-L4a: parse_re_column_header")
for h in ("R45p", "R 45 p", "R45s1f", "T0"):
    print(f"  {h!r:10} -> {parse_re_column_header(h)}")
print("M-L4b: _re_header_normalize_for_tokens and the parsed header")
for h in ("R 45 s sans arriere", "R 45 s sans arrière"):
    print(f"  {h!r:24} -> normalized {_re_header_normalize_for_tokens(h)!r} -> {parse_re_column_header(h)}")
print("M-L4c: _re_measurement_values_are_percent")
for label, vals in (("AR coating R in %, max 1.2", [0.4, 0.8, 1.2, 0.9]), ("R in %, max 4.5", [3.9, 4.5, 4.2]),
                    ("R as fraction, max 0.045", [0.039, 0.045, 0.042])):
    print(f"  {label:28} -> read as percent: {_re_measurement_values_are_percent(vals)}")
