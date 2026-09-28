"""

CERTUS METAL DEFAULTS

=====================

Default values shared by the METAL modules.

This module imports nothing, so the METAL computation code can read these
values without importing certus_metal_common, which pulls in PyQt6,
pyqtgraph and certus.ui. certus_metal_common re-exports every one of them
unchanged.

"""

# =============================================================================

# CONSTANTS (Shared Defaults)

# =============================================================================

DEFAULT_EM_MIN = 5

DEFAULT_EM_MAX = 50

DEFAULT_NUM_KNOTS = 5

DEFAULT_NK_MIN = 0.0

DEFAULT_NK_MAX = 10.0

DEFAULT_MIN_KNOT_DISTANCE = 20.0

DEFAULT_EXCEL_FILENAME = "metal_results.xlsx"


DEFAULT_POPSIZE = 15

DEFAULT_MAXITER = 800

DEFAULT_TOL = 0.005

DEFAULT_MUTATION_MIN = 0.5

DEFAULT_MUTATION_MAX = 1.0

DEFAULT_RECOMBINATION = 0.7

DEFAULT_UPDATING = "deferred"

DEFAULT_WORKERS = 1
