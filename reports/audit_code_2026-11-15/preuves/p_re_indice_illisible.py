"""Audit M-L6g: what RE's 'index' sheet parser makes of an n cell it cannot read.

Calls the real `CertusREExcelMixin._parse_re_index` (with the real `_reconstruct_lambda_list`) on an in-memory sheet
whose n1 column holds a decimal-comma string, "1,52", as a French-locale workbook can store it.
    python reports/audit_code_2026-11-15/preuves/p_re_indice_illisible.py
"""

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from certus.ui.certus_re_excel_mixin import CertusREExcelMixin  # noqa: E402
from certus.ui.certus_re_table_mixin import CertusRETableMixin  # noqa: E402


class Window(CertusREExcelMixin, CertusRETableMixin):
    def __init__(self):
        self.logger = logging.getLogger("audit")


class Sheet:
    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, values_only=True):
        return iter(self.rows)


rows = [("lambda", "n1", "k1", "n2", "k2"),
        (500.0, 2.35, 0.0, 1.46, 0.0),
        (600.0, "2,30", 0.0, 1.46, 0.0),   # decimal comma stored as text
        (700.0, 2.28, 0.0, "1,45", 0.0)]
logging.basicConfig(level=logging.WARNING, format="    log %(levelname)s: %(message)s")
wls, n1, k1, n2, k2 = Window()._parse_re_index(Sheet(rows))
for i, w in enumerate(wls):
    print(f"lambda={w:.0f} nm : n1={n1[i]:.2f} (cell {rows[i + 1][1]!r}) | n2={n2[i]:.2f} (cell {rows[i + 1][3]!r})")
