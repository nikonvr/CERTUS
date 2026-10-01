"""The CI runs `tools/bench_kernels.py` and keeps its report (audit v2, plan S7.5: "JSON, artefact de CI, seuil relatif +30 %").

The workflows are read as text, like `test_github_workflows_are_hardened.py`: PyYAML is not a dependency, and what is checked (a step, a path, a line of
`uses:`) needs no parser. What is pinned:

    the Ubuntu job runs the tool with the committed baseline and writes the report to the file the next step uploads
    the file the CI uploads is the file the tool is asked to write, and the baseline it compares with is a file of the repository
    the upload is pinned to a commit like every other action (the hardening test checks it too), and runs even when the benchmark step fails
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def _steps() -> list[str]:
    """The text of each step of the workflow, in order."""
    text = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    return re.split(r"\n(?=      - name: )", text)


def _step_running(command: str) -> str:
    found = [step for step in _steps() if command in step]
    assert len(found) == 1, f"{len(found)} step(s) mention {command!r}"
    return found[0]


def test_the_ubuntu_job_runs_the_benchmark_tool_with_the_committed_baseline():
    step = _step_running("tools/bench_kernels.py")
    assert "--baseline tests/performance/kernel_baseline.json" in step
    assert (ROOT / "tests" / "performance" / "kernel_baseline.json").is_file()
    assert (ROOT / "tools" / "bench_kernels.py").is_file()


def test_the_report_the_tool_writes_is_the_file_the_next_step_uploads():
    run = _step_running("tools/bench_kernels.py")
    written = re.search(r"--json (\S+)", run)
    assert written, "the benchmark step does not ask for a JSON report"
    upload = _step_running("actions/upload-artifact")
    assert f"path: {written.group(1)}" in upload


def test_the_upload_runs_even_when_the_benchmark_fails_and_is_pinned_to_a_commit():
    upload = _step_running("actions/upload-artifact")
    assert "if: always()" in upload
    assert re.search(r"upload-artifact@[0-9a-f]{40} # v\d", upload)


def test_the_benchmark_step_comes_after_the_tests_it_must_not_disturb():
    names = [step for step in _steps() if "- name:" in step]
    order = [next(line for line in step.splitlines() if "- name:" in line).strip() for step in names]
    last_tests = max(i for i, name in enumerate(order) if "Le reste de tests/" in name)
    benchmark = next(i for i, step in enumerate(names) if "tools/bench_kernels.py" in step)
    assert benchmark > last_tests  # a benchmark that shared the machine with a test run would measure the test run
