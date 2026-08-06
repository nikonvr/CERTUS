"""
CERTUS STRAT Context - Dependency Injection Container
=====================================================
Part of CERTUS Suite (Refactoring 2026)

Replaces global variables with a proper context object for testability
and maintainability.

Also contains pure utility classes (PlotCache, ThreadSafeCounter) extracted
from CERTUS_STRAT.py to isolate non-Qt logic.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
import threading
import time
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


# --- Extracted helper constants & functions from CERTUS_STRAT ---

SYM_MISSING_DISTANCE = 999.0
FAST_AUTO_BLOCKS_DIVIDER_PRESETS = (
    (20.0, 12.0),  # compact
    (12.0, 6.0),   # balanced
    (8.0, 4.0),    # extended
    (6.0, 2.5),    # very_extended
)


def _clamp01(val: float) -> float:
    return max(0.0, min(1.0, float(val)))


def _compute_local_extrema_symmetry_score(
    dist_prev: float,
    dist_next: float,
    window_ot: float,
) -> float:
    window = max(1e-6, float(window_ot))
    d_prev = float(dist_prev)
    d_next = float(dist_next)
    if d_prev >= SYM_MISSING_DISTANCE and d_next >= SYM_MISSING_DISTANCE:
        return 0.0
    nearest = min(d_prev, d_next)
    proximity = _clamp01(1.0 - min(nearest, window) / window)
    if d_prev >= SYM_MISSING_DISTANCE or d_next >= SYM_MISSING_DISTANCE:
        balance = 0.0
    else:
        denom = max(d_prev + d_next, 1e-9)
        balance = _clamp01(1.0 - abs(d_prev - d_next) / denom)
    return 0.65 * proximity + 0.35 * balance


def _build_symmetry_bonus_map(
    raw_results_thickness: dict[int, list[dict[str, float]]],
    num_layers: int,
    window_ot: float,
) -> dict[int, dict[float, float]]:
    bonus_map: dict[int, dict[float, float]] = {}
    for i in range(num_layers):
        layer_items = raw_results_thickness.get(i, [])
        if not layer_items:
            continue
        layer_bonus: dict[float, float] = {}
        for cand in layer_items:
            wl = float(cand.get("wl", -1.0))
            if wl <= 0.0:
                continue
            s_start = _compute_local_extrema_symmetry_score(
                cand.get("ext_prev_start", SYM_MISSING_DISTANCE),
                cand.get("ext_next_start", SYM_MISSING_DISTANCE),
                window_ot,
            )
            s_end = _compute_local_extrema_symmetry_score(
                cand.get("ext_prev_end", SYM_MISSING_DISTANCE),
                cand.get("ext_next_end", SYM_MISSING_DISTANCE),
                window_ot,
            )
            layer_bonus[wl] = max(s_start, s_end)
        if layer_bonus:
            bonus_map[i] = layer_bonus
    return bonus_map


def _build_layer_importance_map(
    raw_results_thickness: dict[int, list[dict[str, float]]],
    num_layers: int,
) -> dict[int, float]:
    raw_scores: dict[int, float] = {}
    max_dyn = 0.0
    for i in range(num_layers):
        layer_items = raw_results_thickness.get(i, [])
        if not layer_items:
            continue
        dyn_values = [float(c.get("dynamics", 0.0)) for c in layer_items if np.isfinite(c.get("dynamics", 0.0))]
        if not dyn_values:
            continue
        score = float(np.percentile(np.array(dyn_values, dtype=np.float64), 75))
        raw_scores[i] = max(0.0, score)
        max_dyn = max(max_dyn, raw_scores[i])
    if max_dyn <= 1e-12:
        return {i: 0.0 for i in raw_scores}
    return {i: _clamp01(v / max_dyn) for i, v in raw_scores.items()}


def _compute_blocks_range_contractual(
    num_layers: int,
    div_start: float,
    div_end: float,
    dense: bool = False,
) -> list[int]:
    if num_layers <= 0:
        return []
    min_blocks = max(1, int(num_layers / max(1.0, float(div_start))))
    max_blocks = max(min_blocks, int(num_layers / max(1.0, float(div_end))))
    selected = {1, 2, min_blocks, max_blocks, num_layers}
    if dense:
        selected.update(range(min_blocks, max_blocks + 1))
    blocks_range = sorted([b for b in selected if 1 <= b <= num_layers], reverse=True)
    if not blocks_range:
        blocks_range = [1]
    return blocks_range


def _compute_blocks_range_for_params(
    num_layers: int,
    params: dict[str, Any],
    dense: bool = False,
) -> list[int]:
    # 🔴 MODE FAST SUPPRIME (2026-08-05) — decision du physicien : « interdit le mode
    # fast, je veux un mode vraiment semblable a la realite et j'ai tout mon temps ».
    #
    # Une branche `if execution_mode == "fast" and fast_auto_blocks` remplacait ici la
    # plage contractuelle par une union de FAST_AUTO_BLOCKS_DIVIDER_PRESETS calculee a
    # `dense=False` — alors que l'appelant demande `dense=True`. C'etait le SECOND effet
    # de `fast`, moins visible que la division des budgets Monte-Carlo mais tout aussi
    # nocif : on explorait moins de decoupages.
    #
    # `collect_params` ramene deja execution_mode a "premium" et le retire de l'IHM ;
    # la branche est supprimee ici pour que le chemin programmatique (tests headless,
    # appels directs) ne puisse pas la reactiver en posant params a la main.
    div_start = float(params.get("iter_divider_start", 10.0))
    div_end = float(params.get("iter_divider_end", 3.0))
    return _compute_blocks_range_contractual(num_layers, div_start, div_end, dense=dense)


def _validate_strategy_blocks_contract(
    strategy: dict[str, Any],
    num_layers: int,
    expected_n_blocks: int | None = None,
) -> tuple[bool, str]:
    if not isinstance(strategy, dict):
        return False, "strategy is not a dict"
    blocks = strategy.get("blocks", [])
    if not isinstance(blocks, list) or len(blocks) == 0:
        return False, "missing/empty blocks"
    try:
        n_blocks = int(strategy.get("n_blocks", len(blocks)))
    except (TypeError, ValueError):
        return False, "n_blocks is not an integer"
    if expected_n_blocks is not None:
        try:
            expected_n_blocks_int = int(expected_n_blocks)
        except (TypeError, ValueError):
            return False, "expected_n_blocks is invalid"
        if n_blocks != expected_n_blocks_int:
            return False, f"n_blocks mismatch (expected {expected_n_blocks_int}, got {n_blocks})"
    if len(blocks) != n_blocks:
        return False, f"len(blocks)={len(blocks)} != n_blocks={n_blocks}"
    cursor = 0
    blocks_sorted = []
    for blk in blocks:
        if not isinstance(blk, dict):
            return False, "block item is not a dict"
        try:
            start = int(blk.get("start", -1))
            end = int(blk.get("end", -1))
            wl = float(blk.get("wavelength", np.nan))
            blk_num = int(blk.get("num_layers", end - start))
        except (TypeError, ValueError):
            return False, "block field type invalid"
        if not np.isfinite(wl):
            return False, "block wavelength is not finite"
        blocks_sorted.append((start, end, wl, blk_num))
    blocks_sorted.sort(key=lambda item: item[0])
    for i, (start, end, _wl, blk_num) in enumerate(blocks_sorted):
        if start != cursor:
            return False, f"non contiguous coverage at block {i} (start={start}, cursor={cursor})"
        if start < 0 or end <= start or end > num_layers:
            return False, f"invalid bounds at block {i} ({start}, {end})"
        if blk_num != (end - start):
            return False, f"num_layers mismatch at block {i} ({blk_num} vs {end - start})"
        cursor = end
    if cursor != num_layers:
        return False, f"incomplete coverage (covered up to {cursor}, expected {num_layers})"
    return True, ""


def _augment_solution_cost_with_sym(
    sol: dict[str, Any],
    sym_bonus_map: dict[int, dict[float, float]] | None,
    layer_importance_map: dict[int, float] | None,
    sym_weight: float,
    same_wl_bonus: float,
    continuity_weight: float,
    adaptive_same_wl: bool,
) -> tuple[float, float, int]:
    base_cost = float(sol.get("cost", 0.0))
    blocks_info = sol.get("blocks_info", [])
    if not blocks_info:
        return base_cost, 0.0, 0
    total_sym = 0.0
    total_layers = 0
    for start, end, wl in blocks_info:
        wlf = float(wl)
        for l in range(int(start), int(end)):
            total_layers += 1
            if sym_bonus_map:
                total_sym += float(sym_bonus_map.get(l, {}).get(wlf, 0.0))
    mean_sym = (total_sym / total_layers) if total_layers > 0 else 0.0
    same_wl_kept = 0
    continuity_gain = 0.0
    prev = None
    for start, end, wl in sorted(blocks_info, key=lambda x: int(x[0])):
        wlf = float(wl)
        if prev is not None and abs(wlf - prev) <= 1e-3:
            same_wl_kept += 1
            if adaptive_same_wl:
                boundary_layer = int(max(0, int(start) - 1))
                importance = 0.0
                if layer_importance_map is not None:
                    importance = float(layer_importance_map.get(boundary_layer, 0.0))
                continuity_gain += float(same_wl_bonus) * (1.0 + float(continuity_weight) * importance)
            else:
                continuity_gain += float(same_wl_bonus)
        prev = wlf
    if not adaptive_same_wl:
        continuity_gain = float(same_wl_bonus) * same_wl_kept
    augmented = base_cost - float(sym_weight) * mean_sym - float(continuity_gain)
    return float(max(0.0, augmented)), float(mean_sym), int(same_wl_kept)


def _origin_family(origin_raw: Any) -> str:
    origin = str(origin_raw or "").upper().strip()
    if not origin:
        return "UNKNOWN"
    return origin.split("(")[0].strip()


def _parse_origin_priority_map(
    raw_value: Any,
) -> dict[str, int]:
    default_map = {
        "SYM": 0,
        "SMART_MERGE_SYM": 1,
        "THICKNESS²": 2,
        "THICKNESS2": 2,
        "THICKNESS": 3,
        "SMART_MERGE_THICKNESS2": 4,
        "SMART_MERGE_THICKNESS": 5,
        "SMART_MERGE_MIXED": 6,
    }
    if isinstance(raw_value, dict):
        out = {}
        for k, v in raw_value.items():
            try:
                out[str(k).upper().strip()] = int(v)
            except (TypeError, ValueError):
                continue
        return out if out else default_map
    if isinstance(raw_value, str) and ":" in raw_value:
        out = {}
        for part in raw_value.split(","):
            token = part.strip()
            if ":" not in token:
                continue
            k, v = token.split(":", 1)
            try:
                out[str(k).upper().strip()] = int(v.strip())
            except (TypeError, ValueError):
                continue
        return out if out else default_map
    return default_map


def _origin_priority_from_map(origin: str, priority_map: dict[str, int]) -> int:
    fam = _origin_family(origin)
    if fam in priority_map:
        return int(priority_map[fam])
    for key, val in priority_map.items():
        if key and key in fam:
            return int(val)
    return 999


def _apply_family_diversity(
    ordered_results: list[dict[str, Any]],
    top_k: int,
    max_per_family: int,
) -> list[dict[str, Any]]:
    if top_k <= 0 or max_per_family <= 0 or not ordered_results:
        return ordered_results
    k = min(int(top_k), len(ordered_results))
    selected: list[tuple[int, dict[str, Any]]] = []
    deferred: list[tuple[int, dict[str, Any]]] = []
    used_clues = set()
    counts: dict[str, int] = {}
    for idx, item in enumerate(ordered_results):
        fam = _origin_family(item.get("strategy", {}).get("origin", "UNKNOWN"))
        used = counts.get(fam, 0)
        if len(selected) < k and used < max_per_family:
            selected.append((idx, item))
            used_clues.add(idx)
            counts[fam] = used + 1
        else:
            deferred.append((idx, item))
    for idx, item in deferred:
        if len(selected) >= k:
            break
        selected.append((idx, item))
        used_clues.add(idx)
    diversified_head = [item for _idx, item in selected]
    tail = [item for idx, item in enumerate(ordered_results) if idx not in used_clues]
    return diversified_head + tail


def _blocks_signature(blocks: list[dict[str, Any]]) -> tuple:
    sig = []
    for blk in blocks:
        try:
            start = int(blk.get("start", 0))
            end = int(blk.get("end", 0))
            wl = round(float(blk.get("wavelength", 0.0)), 6)
            sig.append((start, end, wl))
        except (TypeError, ValueError):
            continue
    return tuple(sig)


def _strategy_signature(strategy: dict[str, Any]) -> tuple:
    if not isinstance(strategy, dict):
        return tuple()
    try:
        n_blocks = int(strategy.get("n_blocks", len(strategy.get("blocks", []))))
    except (TypeError, ValueError):
        n_blocks = len(strategy.get("blocks", []))
    return (n_blocks, _blocks_signature(strategy.get("blocks", [])))


def _strategy_id_sort_token(strategy_id: Any) -> tuple:
    text = str(strategy_id)
    try:
        return (0, int(text))
    except (TypeError, ValueError):
        return (1, text)


def _extract_rmse_p95_for_noise(result_item: dict[str, Any], target_noise: float) -> float:
    try:
        results = result_item.get("results_per_noise", [])
        if not results:
            return float("inf")
        best = min(results, key=lambda r: abs(float(r.get("noise_level", 0.0)) - float(target_noise)))
        return float(best.get("rmse_p95", best.get("rmse_mean", np.inf)))
    except Exception:
        return float("inf")


def _dedupe_preserve_order_int(values: list[int]) -> list[int]:
    deduped: list[int] = []
    seen: set[int] = set()
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def _default_consensus_seeds(
    *,
    base_seed: int,
    consensus_seed_stride: int,
    consensus_num_seeds: int,
) -> list[int]:
    return [base_seed + i * consensus_seed_stride for i in range(consensus_num_seeds)]


def _resolve_consensus_top_k(params: dict[str, Any]) -> int:
    return max(1, int(params.get("consensus_top_k", 12)))


def _resolve_consensus_num_seeds(params: dict[str, Any]) -> int:
    return max(1, int(params.get("consensus_num_seeds", 1)))


def _resolve_consensus_seed_stride(params: dict[str, Any]) -> int:
    return max(1, int(params.get("consensus_seed_stride", 1)))


def _resolve_consensus_num_runs(params: dict[str, Any], *, num_runs: int) -> int:
    return max(1, int(params.get("consensus_num_runs", num_runs)))


# =============================================================================
# PURE UTILITY CLASSES (extracted from CERTUS_STRAT.py)
# These classes have no Qt dependency and live here for testability.
# CERTUS_STRAT.py imports and re-exports them for backward compatibility.
# =============================================================================


class PlotCache:
    """
    Intelligent caching system using SHA256 hashes of data content.

    Prevents re-rendering identical plots.
    """

    def __init__(self, _max_size_mb: int = 200) -> None:
        self.cache: dict = {}
        self.max_size_items = 20  # Keep last 20 plots

    def get_hash(self, data_obj: Any) -> Any:
        """Compute a stable hash for *data_obj* (dict or arbitrary object)."""
        try:
            if isinstance(data_obj, dict):
                # Filter out heavy non-serializable objects
                serializable = {
                    k: v
                    for k, v in data_obj.items()
                    if isinstance(v, (str, int, float, list, dict, bool, type(None)))
                }
                data_str = json.dumps(serializable, sort_keys=True, separators=(",", ":"))
            else:
                data_str = str(data_obj)
            return hashlib.sha256(data_str.encode("utf-8")).hexdigest()
        except (TypeError, AttributeError, UnicodeEncodeError) as e:
            logging.debug("PlotCache.get_hash failed: %s", e)
            return str(time.time())  # Fallback

    def get(self, key: Any) -> Any:
        """Return cached item for *key*, promoting it to MRU position."""
        if key in self.cache:
            # Move to end (LRU style) by deleting and re-inserting
            val = self.cache.pop(key)
            self.cache[key] = val
            return val
        return None

    def put(self, key: Any, item: Any) -> None:
        """Store *item* under *key*, evicting the oldest entry when full."""
        self.cache[key] = item
        if len(self.cache) > self.max_size_items:
            # Remove oldest (FIFO) — dict preserves insertion order
            first_key = next(iter(self.cache))
            del self.cache[first_key]


class ThreadSafeCounter:
    """Thread-safe counter replacing global dictionary."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self.signal: Any = None

    def increment(self) -> int:
        """Increment counter and return new value."""
        with self._lock:
            self._count += 1
            return self._count

    def reset(self) -> None:
        """Reset counter to zero."""
        with self._lock:
            self._count = 0

    def set_signal(self, signal: Any) -> None:
        """Attach a Qt signal (or any callable) for live notifications."""
        with self._lock:
            self.signal = signal
