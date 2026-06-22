"""CERTUS runtime helpers extracted from the core module."""

from __future__ import annotations

from dataclasses import dataclass
import os
import logging

from certus.core.certus_logging import setup_logging


@dataclass(frozen=True)
class CertusRuntime:
    logger: logging.Logger
    cache_dir: str
    n_cores: int


def setup_numba_cache() -> str:
    return os.environ.get("NUMBA_CACHE_DIR", "")


def _resolve_n_cores(n_cores: int | None) -> int:
    resolved = os.cpu_count() or 1 if n_cores is None else n_cores
    return max(1, int(resolved))


def set_num_threads(n_cores: int | None = None) -> int:
    n_cores = _resolve_n_cores(n_cores)
    s_cores = str(n_cores)
    for env_var in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ.setdefault(env_var, s_cores)
    return n_cores


def build_runtime(*, log_file: str | None = None, level: int | None = None, n_cores: int | None = None) -> CertusRuntime:
    cache_dir = setup_numba_cache()
    resolved_n_cores = set_num_threads(n_cores)
    logger = setup_logging(log_file=log_file, level=level)
    return CertusRuntime(logger=logger, cache_dir=cache_dir, n_cores=resolved_n_cores)
