"""CERTUS bootstrap helpers."""

from __future__ import annotations

from certus.core.certus_runtime import build_runtime, CertusRuntime, setup_numba_cache, set_num_threads
from certus.core.certus_logging import setup_logging, get_logger, handle_exception


def bootstrap_app(*args, **kwargs):
    return build_runtime(*args, **kwargs)
