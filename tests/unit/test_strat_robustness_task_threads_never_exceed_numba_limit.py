"""The robustness task asks Numba for 2 threads; a process limited to 1 (the frozen build) must not crash on it."""

import subprocess
import sys
import textwrap


def test_task_thread_request_survives_a_one_thread_numba():
    code = textwrap.dedent(
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
        """
    )
    env = {**__import__("os").environ, "NUMBA_NUM_THREADS": "1", "NUMBA_DISABLE_JIT": "1"}
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
