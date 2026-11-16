"""The phase B workers read the same complex indices as phase A (audit 2026-11-15, L4-m4).

``SharedIndicesManager`` stored the real parts in float32: k was dropped and n rounded to 1e-7 for every phase B
worker, while phase A computed with the complex index.
"""

from __future__ import annotations

from certus.utils.certus_data import SharedIndicesManager, SharedIndicesWorker


def test_the_shared_indices_keep_n_and_k_to_the_bit() -> None:
    clues = {
        500.0: {"H": 2.3456789012345 - 3.7e-5j, "L": 1.4868160123 - 1.0e-6j, "substrate": 1.4623 + 0j},
        550.0: {"H": 2.3301 - 2.0e-5j, "L": 1.4851 - 0j, "substrate": 1.4599 + 0j},
    }
    with SharedIndicesManager(clues) as manager, SharedIndicesWorker(manager.get_context_info()) as worker:
        got = worker.get(500.0)
        assert got["H"] == clues[500.0]["H"]
        assert got["L"] == clues[500.0]["L"]
        assert got["substrate"] == clues[500.0]["substrate"]
        assert worker.get(525.0)["H"].imag < 0.0
