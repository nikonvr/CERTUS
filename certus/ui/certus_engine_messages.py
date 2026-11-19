"""What a window says while its computing engine prepares, and once it is ready.

The windows said "Compiling JIT kernels...", "Waiting for JIT compilation..." and "System ready. JIT Warmup
complete.": the vocabulary of the implementation, and nothing about what the operator may do meanwhile, nor when a
computation can start (UX audit 2026-11-18, item 5). One place holds the words, so every window says the same.
"""

from __future__ import annotations

#: Shown from the opening of the window until the engine is ready.
ENGINE_PREPARING = (
    "Preparing the computing engine: you can load a measurement or a configuration meanwhile; "
    "computing starts once it is ready."
)

#: Logged when a computation is asked for before the engine is ready (it is retried until then).
ENGINE_WAITING = "The computing engine is still preparing: this computation will start by itself once it is ready."

#: The status once the engine is ready.
ENGINE_READY = "Ready to compute."

#: The notice of the same moment.
ENGINE_READY_TOAST = "Ready: computations can start."
