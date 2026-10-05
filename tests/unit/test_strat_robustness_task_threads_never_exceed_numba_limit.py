"""The robustness task asks Numba for 2 or 4 threads; a process limited to 1 (the frozen build) must not crash on it."""

import os
import subprocess
import sys
import textwrap


def _run(code: str, threads: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "NUMBA_NUM_THREADS": threads, "NUMBA_DISABLE_JIT": "1"}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=env, capture_output=True, text=True, timeout=300)


def test_task_thread_request_survives_a_one_thread_numba():
    r = _run(
        """
        import numba
        import certus.core.certus_strat_robustness_task as m
        try:
            m._test_strategy_robustness_task({"blocks": []}, 0, [0.0], 1, [1.0], None, {}, None, None, None, None, None, None)
        except ValueError as e:
            assert "number of threads" not in str(e), e
        except Exception:
            pass
        assert numba.get_num_threads() == 1
        """,
        "1",
    )
    assert r.returncode == 0, r.stderr[-800:]


def test_task_asks_four_threads_on_a_big_machine_and_two_otherwise():
    r = _run(
        """
        import os
        from certus.core.certus_strat_robustness_task import task_numba_threads
        os.cpu_count = lambda: 16
        assert task_numba_threads() == 4
        os.cpu_count = lambda: 8
        assert task_numba_threads() == 2
        """,
        "8",
    )
    assert r.returncode == 0, r.stderr[-800:]
