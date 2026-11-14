"""A selector audit must see fixture calls and propagate pytest failures."""

import json
from pathlib import Path

import pytest

from scripts import verify_changed as vc


def test_a_failed_pytest_run_cannot_certify_the_graph(monkeypatch):
    def failed(command, env):
        Path(env["VERIFY_OUT"]).write_text(json.dumps({}), encoding="utf-8")
        return 1, "FAILED tests/test_example.py::test_example"

    monkeypatch.setattr(vc, "run_env", failed)
    assert vc.audit_calls(vc.Graph(files=[]), ["tests/test_example.py"]) == 1


@pytest.mark.parametrize("phase", ["setup", "teardown"])
@pytest.mark.parametrize("missing_edge", [False, True])
@pytest.mark.parametrize("workers", [1, 2])
def test_fixture_calls_are_compared_to_the_static_graph(tmp_path, monkeypatch, phase, missing_edge, workers):
    (tmp_path / "tests").mkdir()
    (tmp_path / "helper.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    before, after = ("helper.value()", "pass") if phase == "setup" else ("pass", "helper.value()")
    source = (
        "import pytest\nimport helper\n\n"
        f"@pytest.fixture\ndef resource():\n    {before}\n    yield\n    {after}\n\n"
        "def test_fixture(resource):\n    assert True\n"
    )
    (tmp_path / "tests/test_fixture.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(vc, "ROOT", tmp_path)
    graph = vc.build_graph(["helper.py", "tests/test_fixture.py"])
    if missing_edge:
        for key, edges in graph.edges.items():
            graph.edges[key] = {edge for edge in edges if edge[0] != "helper.py"}
    assert vc.audit_calls(graph, ["tests/test_fixture.py"], workers) == int(missing_edge)
