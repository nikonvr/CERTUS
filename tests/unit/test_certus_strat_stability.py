from __future__ import annotations

from pathlib import Path

from certus.utils.certus_strat_stability import load_stability_reference, run_reference_audit, summarize_stability_reference


def test_reference_stability_json_reports_same_best_strategy(tmp_path: Path) -> None:
    ref = load_stability_reference(Path("example/example_strat/JSON-strat-example-verification.json"))
    summary = summarize_stability_reference(ref)

    assert summary.strategies_count_baseline == 60
    assert summary.strategies_count_perturbed == 60
    assert summary.same_best_strategy_id is True
    assert summary.same_best_origin is True
    assert summary.best_strategy_id_baseline == 48108
    assert summary.best_strategy_id_perturbed == 48108
    assert summary.best_origin_baseline == "THICKNESS²"
    assert summary.best_origin_perturbed == "THICKNESS²"
    assert summary.top5_overlap == 5
    assert summary.top5_jaccard == 1.0
    assert summary.is_stable is True

    out_md = tmp_path / "audit.md"
    summary_2 = run_reference_audit(Path("example/example_strat/JSON-strat-example-verification.json"), out_md)
    assert summary_2 == summary
    text = out_md.read_text(encoding="utf-8")
    assert "STRAT stability audit report" in text
    assert "Stable best strategy: **yes**" in text
    assert "Top 5 overlap: **5/5**" in text


def test_stability_robustness_with_malformed_input(tmp_path: Path) -> None:
    # Test with baseline/perturbed as None or missing, and malformed top5
    payload = {
        "baseline": None,
        "stability_seed_plus_1": {
            "strategies_count": 10,
            "top5": [
                None,
                "not-a-dict",
                {"id": "invalid-id"},
                {"id": 42, "origin": "TEST", "score": 0.5}
            ]
        },
        "same_best_strategy_id": False,
        "same_best_origin": False
    }

    summary = summarize_stability_reference(payload)
    assert summary.strategies_count_baseline == 0
    assert summary.strategies_count_perturbed == 10
    assert summary.is_stable is False
    assert summary.top5_overlap == 0

    out_md = tmp_path / "audit_malformed.md"
    from certus.utils.certus_strat_stability import build_markdown_report
    report = build_markdown_report(payload, summary)
    assert "STRAT stability audit report" in report
    assert "Stable best strategy: **no**" in report

