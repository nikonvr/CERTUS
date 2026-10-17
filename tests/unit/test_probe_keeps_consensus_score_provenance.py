"""The real probe export must distinguish consensus samples from a base score."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import probe_blocs_vs_plantage as probe  # noqa: E402


def _export(monkeypatch: pytest.MonkeyPatch, rows: list[dict], post_report: dict | None = None) -> dict:
    """Exercise mesurer's export without opening Qt or starting a scientific worker."""
    class App:
        def __init__(self):
            self.widgets = {}
            self.worker = object()

        def collect_params(self):
            return {"robustness_num_runs": 300, "consensus_num_runs": 300}

        def run_workflow(self, workflow):
            assert workflow == 23
            self.collect_params()
            self.collect_params()

    bench = ModuleType("bench_examples")
    bench.qapp = lambda: None
    bench.autoanswer_dialogs = lambda answer: None
    bench.wait_for = lambda worker: {"final_results": {"all_strategies_results": rows,
                                   **({"rate_post_refinement": post_report} if post_report is not None else {})}}
    strat = ModuleType("CERTUS_STRAT")
    strat.CertusStratApp = App
    component = ModuleType("_composant")
    component.charger_configuration = lambda app, path: None
    for name, module in (("bench_examples", bench), ("CERTUS_STRAT", strat), ("_composant", component)):
        monkeypatch.setitem(sys.modules, name, module)
    for name in ("CERTUS_PROBE_OVERRIDES", "CERTUS_PROBE_TAG", "CERTUS_CONSENSUS_SEEDS"):
        monkeypatch.delenv(name, raising=False)
    return probe.mesurer("r75x0.5", "deep", seed=101)


@pytest.mark.parametrize("samples", [1, 3])
def test_consensus_metadata_and_both_scores_survive_the_actual_export(monkeypatch, samples):
    meta = {"mode": "mean_std", "mean": 0.02, "std": 0.01, "worst": 0.03,
            "seeds": [41, 42, 43], "n_samples": samples}
    row = {"strategy": {"strategy_id": 71, "blocks": [{"start": 0, "end": 5, "wavelength": 613.0}],
                        "rate_layers": [4, 3], "witness_reset_layers": [0, 3]},
           "robustness_score": 0.0235, "robustness_score_base": 0.019,
           "robustness_score_consensus": 0.0235, "robustness_consensus_meta": meta,
           "crash_rate": 0.0}
    before = copy.deepcopy(row)

    exported = _export(monkeypatch, [row])
    kept = exported["strategies"][0]

    assert exported["verdict"] == "OK"
    assert kept["score"] == 0.0235
    assert kept["robustness_score_base"] == 0.019
    assert kept["robustness_score_consensus"] == 0.0235
    assert kept["robustness_consensus_meta"] == meta
    assert kept["witness_reset_layers"] == [0, 3]
    assert kept["rate_layers"] == [3, 4]
    assert row == before
    kept["robustness_consensus_meta"]["seeds"].append(44)
    kept["witness_reset_layers"].append(4)
    assert row == before


def test_missing_consensus_metadata_is_not_inferred_from_deep_or_declared_depth(monkeypatch):
    rows = [{"strategy": {"strategy_id": sid, "blocks": []}, "robustness_score": score}
            for sid, score in ((3, 0.031), (1, 0.025))]

    exported = _export(monkeypatch, rows)

    assert exported["profondeur"] == {"robustness_num_runs": 300, "consensus_num_runs": 300}
    assert [row["id"] for row in exported["strategies"]] == [3, 1]
    assert [row["score"] for row in exported["strategies"]] == [0.031, 0.025]
    for row in exported["strategies"]:
        assert row["robustness_score_base"] is None
        assert row["robustness_score_consensus"] is None
        assert row["robustness_consensus_meta"] is None
        assert row["witness_reset_layers"] is None


def test_automatic_refinement_ledger_survives_export_without_aliasing(monkeypatch):
    report = {"new_proposals": 305, "stages": [{"records": [{"status": "incomplete_consensus"}]}],
              "consensus_seeds": [41, 42, 43]}
    rows = [{"strategy": {"strategy_id": 9, "blocks": []}, "robustness_score": 0.02}]
    exported = _export(monkeypatch, rows, report)
    assert exported["rate_post_refinement"] == report
    exported["rate_post_refinement"]["consensus_seeds"].append(44)
    assert report["consensus_seeds"] == [41, 42, 43]
    assert "rate_post_refinement" not in _export(monkeypatch, rows)
