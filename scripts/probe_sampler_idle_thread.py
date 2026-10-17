"""DOES A THREAD THAT WAITS ON A QUEUE COST ANYTHING, AND HOW DOES THE BENCH SAMPLER COUNT IT?

ETAT section 6 listed "17 % of the profile in the statistics consumer's wait" as the last way to speed STRAT up at
identical bits. The profile came from the sampler of `scripts/bench_examples.py` (`start_sampler`), which records the
frame of EVERY live thread at every tick. `StatsConsumerWorker.run` (certus/workers/certus_strat_workers.py) spends
its life in `stats_queue.get(timeout=0.1)`: the sampler then finds it in its wait at every tick, whether or not it
takes anything from the computation.

This probe runs a fixed numpy computation on the main thread, with and without such a waiting thread, under the same
sampling algorithm, and prints the computation's duration and each thread's share of the samples. Run it on an idle
machine: a loaded one measures the load.

    python scripts/probe_sampler_idle_thread.py [repetitions]
"""

from __future__ import annotations

import collections
import queue
import sys
import threading
import time

import numpy as np


def work() -> float:
    """A fixed computation on the main thread; returns its duration in seconds."""
    a = np.random.default_rng(0).random((400, 400))
    t0 = time.perf_counter()
    for _ in range(40):
        a = np.linalg.inv(a @ a.T + np.eye(400))
    return time.perf_counter() - t0


def consumer(q: queue.Queue, stop: threading.Event) -> None:
    """The loop of `StatsConsumerWorker.run`: wait on the queue with a 0.1 s timeout, until stopped."""
    while not stop.is_set():
        try:
            if q.get(timeout=0.1) is None:
                break
        except queue.Empty:
            continue


def sampled(with_consumer: bool) -> tuple[float, dict[str, float]]:
    """Duration of `work`, and the share of sampler ticks at which each tagged thread was found (in %)."""
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    th = None
    if with_consumer:
        th = threading.Thread(target=consumer, args=(q, stop), name="consumer")
        th.start()
    counts: collections.Counter = collections.Counter()
    ticks = [0]
    done = threading.Event()
    me: list = [None]

    def loop() -> None:  # the algorithm of scripts/bench_examples.py::start_sampler
        me[0] = threading.get_ident()
        while not done.wait(0.005):
            ticks[0] += 1
            for tid in sys._current_frames():
                if tid == me[0]:
                    continue
                counts["MAIN" if tid == threading.main_thread().ident else "WAITING"] += 1

    sampler = threading.Thread(target=loop, daemon=True)
    sampler.start()
    dt = work()
    done.set()
    stop.set()
    q.put(None)
    if th is not None:
        th.join()
    return dt, {k: round(100.0 * v / max(ticks[0], 1), 1) for k, v in counts.items()}


def main() -> None:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    for rep in range(reps):
        for with_consumer in (False, True):
            dt, share = sampled(with_consumer)
            print(f"rep {rep}: waiting thread={with_consumer}: computation {dt:.3f} s; share of ticks per thread {share}")


if __name__ == "__main__":
    main()
