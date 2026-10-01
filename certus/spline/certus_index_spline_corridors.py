#!/usr/bin/env python3

"""
CERTUS-INDEX-SPLINE Corridors and Export Module.

Since S5.3 (2026-10-01) this module is the FACADE of the corridor mixins, which live in their own modules (every name is still
importable from here, and `CERTUS_INDEX_SPLINE` still proxies attribute reads to this module):

- certus_index_spline_corridor_common   constants and the log-k axis helper
- certus_index_spline_corridor_worker   _CorridorWorkerMixin: what the window does when a corridor worker is done
- certus_index_spline_corridor_tab      _CorridorTabMixin: the corridor tab (inherited by _CorridorWorkerMixin)
- certus_index_spline_corridor_data     _DataMixin: the n / k and thickness tables and their previews
- certus_index_spline_corridor_gen      _CorridorGenMixin: corridors from a partial grid, manual selection, the corridor table
- certus_index_spline_corridor_ui       the one place where these modules import the interface layer (certus.ui)
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

# What moved out is imported back here: the window class takes the three mixins from this module and the tests read these names.
from certus.spline.certus_index_spline_corridor_common import (
    _CORRIDOR_K_TAB_MIN_HALF_WIDTH,
    _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN,
    _DEFAULT_CORRIDOR_RMSE_DELTA,
    _SCRIPT_DIR,
    _apply_fixed_log_k_axis,
)
from certus.spline.certus_index_spline_corridor_data import (
    _DataMixin,
)
from certus.spline.certus_index_spline_corridor_gen import (
    _CorridorGenMixin,
)
from certus.spline.certus_index_spline_corridor_worker import (
    _CorridorWorkerMixin,
)


# Helper structures originally defined in CERTUS_INDEX_SPLINE


