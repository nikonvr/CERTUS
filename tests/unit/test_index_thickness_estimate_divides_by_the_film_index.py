"""The thickness pre-estimate of INDEX divides the optical path by the index of the film (audit 2026-11-15, M-L5g).

The fringes of a spectrum give the optical path 2 n d of the *film*. ``_auto_detect_from_file`` divided it by a rough
index of the *substrate* (3.5 on silicon, 1.5 on fused silica): a SiO2 film of 500 nm on a silicon wafer was estimated
at 190 nm and the thickness bounds written for the fit, [100, 380] nm, excluded the true thickness. The divisor is now
the index at 550 nm of the starting parameters of the model.

The spectra come from ``tests/oracle/tmm_reference.py``, which shares no code with ``certus.physics``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))

from tmm_reference import rt_stack  # noqa: E402

from certus.ui.certus_index_ui_events import CertusIndexEventsMixin  # noqa: E402


class _Combo:
    def __init__(self, items: list[str]) -> None:
        self.items, self.i = list(items), 0

    def findText(self, text: str) -> int:
        return self.items.index(text) if text in self.items else -1

    def setCurrentIndex(self, i: int) -> None:
        self.i = i

    def currentText(self) -> str:
        return self.items[self.i]


class _Spin:
    def __init__(self) -> None:
        self.v: float | None = None

    def setValue(self, v: float) -> None:
        self.v = v

    def value(self) -> float | None:
        return self.v


class _Window:
    pass


CASES = [  # film index, thickness (nm), substrate index, file name that selects the substrate, measured column
    pytest.param(1.46, 500.0, 3.88, "sio2_on_wafer.csv", "R", id="SiO2 500 nm on Si"),
    pytest.param(1.46, 1000.0, 3.88, "sio2_on_wafer.csv", "R", id="SiO2 1000 nm on Si"),
    pytest.param(2.10, 500.0, 3.88, "ta2o5_on_wafer.csv", "R", id="Ta2O5 500 nm on Si"),
    pytest.param(2.30, 500.0, 1.46, "tio2_on_fusedsilica.csv", "T", id="TiO2 500 nm on SiO2"),
]


@pytest.mark.parametrize(("n_film", "d_nm", "n_sub", "file_name", "column"), CASES)
def test_the_thickness_bounds_contain_the_true_thickness(n_film, d_nm, n_sub, file_name, column) -> None:
    lam = np.linspace(400.0, 1000.0, 601)
    rt = np.array([rt_stack(w, [complex(n_film)], [d_nm], 1.0 + 0j, complex(n_sub)) for w in lam])
    win = _Window()
    win.cb_sub = _Combo(["N-BK7", "SiO2", "Si", "Al2O3"])
    win.sb_dmin, win.sb_dmax = _Spin(), _Spin()
    win.logger = logging.getLogger("test")
    win.target_data = pd.DataFrame({"lambda": lam, column: rt[:, 0] if column == "R" else rt[:, 1]})

    CertusIndexEventsMixin._auto_detect_from_file(win, file_name)

    assert win.sb_dmin.v is not None, "no thickness bounds were written"
    assert win.sb_dmax.v is not None
    assert win.sb_dmin.v <= d_nm <= win.sb_dmax.v, (
        f"true thickness {d_nm:.0f} nm outside [{win.sb_dmin.v:.0f}, {win.sb_dmax.v:.0f}] nm "
        f"(estimate {win._estimated_thickness_nm:.0f} nm)"
    )
