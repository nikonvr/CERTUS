"""
CERTUS STRAT Context - Dependency Injection Container
=====================================================
Part of CERTUS Suite (Refactoring 2026)

Replaces global variables with a proper context object for testability
and maintainability.
"""

from __future__ import annotations

import multiprocessing as mp
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass


@dataclass
class StratContext:
    """
    Context container for STRAT calculationations.

    Replaces global variables with injectable dependencies for:
    - Material database
    - Statistics queues
    - Live preview queue
    - Thread-local buffers

    Usage:
        >>> ctx = StratContext(material_db=my_db)
        >>> with ctx.activate():
        ...     # All functions use ctx implicitly
        ...     pass

        # Or explicit passing:
        >>> calculate_RT_normal_real(..., ctx=ctx)
    """

    # Material database (RobustMaterialDatabase or MaterialDatabase)
    material_db: Any | None = None

    # Multiprocessing queues for stats
    stats_queue: mp.Queue | None = None
    live_queue: mp.Queue | None = None

    # Thread-local buffer for SP stats batching
    sp_buffer: int = field(default=0, repr=False)
    sp_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # App-level context dictionary (legacy compatibility)
    app_context: dict[str, Any] = field(default_factory=dict)

    # Cached arrays
    wavelengths: np.ndarray | None = None
    clues_cache: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize thread lock if not provided."""
        if self.sp_lock is None:
            self.sp_lock = threading.Lock()

    # --- Singleton pattern for global access ---
    _current: "StratContext" | None = None

    @classmethod
    def get_current(cls) -> "StratContext" | None:
        """Get the current active context (if any)."""
        return cls._current

    @classmethod
    def set_current(cls, ctx: "StratContext" | None):
        """Set the current active context."""
        cls._current = ctx

    def activate(self) -> "StratContextManager":
        """
        Activate this context as the current global context.

        Returns:
            Context manager for use with 'with' statement
        """
        return StratContextManager(self)

    # --- Material Database Access ---

    def get_refractive_index(self, mat_id: str, wl: float) -> complex:
        """
        Get refractive index for material at wavelength.

        Args:
            mat_id: Material identifier ('H', 'L', 'substrate', etc.)
            wl: Wavelength in nm

        Returns:
            Complex refractive index (n + ik)
        """
        if self.material_db is not None:
            return self.material_db.get_refractive_index(mat_id, wl)

        # Fallback to certus_physics
        from certus_physics import get_refractive_index as physics_get_ri

        return physics_get_ri(mat_id, wl, self.app_context.get("materials_db"))

    def get_refractive_clues_vectorized(self, mat_id: str, wls: np.ndarray) -> np.ndarray:
        """Get refractive clues for material at multiple wavelengths.

        Args:
            mat_id: Material identifier
            wls: Array of wavelengths in nm

        Returns:
            Array of complex refractive clues"""
        if self.material_db is not None:
            return self.material_db.get_refractive_clues_vectorized(mat_id, wls)

        # Fallback to certus_physics
        from certus_physics import (
            get_refractive_clues_vectorized as physics_get_ri_vec,
        )

        return physics_get_ri_vec(mat_id, wls, self.app_context.get("materials_db"))

    # --- Statistics Emission ---

    def emit_stat(self, counter_type: str, increment: int = 1):
        """
        Emit a statistics update.

        Uses batching for 'SP' (spectrum) counter to reduce queue pressure.

        Args:
            counter_type: 'SP' (spectrum), 'MS' (monte carlo), 'MCS' (micro step)
            increment: Count to add
        """
        if counter_type == "SP":
            with self.sp_lock:
                self.sp_buffer += increment
                if self.sp_buffer >= 500:
                    to_send = self.sp_buffer
                    self.sp_buffer = 0
                else:
                    return
        else:
            to_send = increment

        if self.stats_queue is not None:
            try:
                self.stats_queue.put((counter_type, to_send))
            except (BrokenPipeError, OSError):
                pass

    def flush_stats(self):
        """Flush any buffered SP stats."""
        with self.sp_lock:
            if self.sp_buffer > 0 and self.stats_queue is not None:
                try:
                    self.stats_queue.put(("SP", self.sp_buffer))
                    self.sp_buffer = 0
                except (BrokenPipeError, OSError):
                    pass

    # --- Queue Initialization ---

    def init_queues(self):
        """Initialize multiprocessing queues."""
        self.stats_queue = mp.Queue()
        self.live_queue = mp.Queue()

    def worker_init(self):
        """
        Initialize context for worker process.

        Called in ProcessPoolExecutor initializer.
        """
        # Set as current context for this process
        StratContext.set_current(self)

    # --- Cache Management ---

    def clear_cache(self):
        """Clear cached clues."""
        self.clues_cache.clear()
class StratContextManager:
    """Context manager for StratContext activation."""

    def __init__(self, ctx: StratContext):
        self.ctx = ctx
        self.previous: StratContext | None = None

    def __enter__(self) -> StratContext:
        self.previous = StratContext.get_current()
        StratContext.set_current(self.ctx)
        return self.ctx

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        StratContext.set_current(self.previous)
        return False


# =============================================================================
# HELPER FUNCTIONS (for gradual migration)
# =============================================================================


def get_context() -> StratContext:
    """
    Get current STRAT context, creating default if needed.

    Returns:
        Current StratContext instance
    """
    ctx = StratContext.get_current()
    if ctx is None:
        ctx = StratContext()
        StratContext.set_current(ctx)
    return ctx

