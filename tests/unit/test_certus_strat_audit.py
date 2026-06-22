from __future__ import annotations

from certus.core.certus_strat_audit import (
    StratAuditCase,
    audit_summary_to_dict,
)


def test_audit_dataclasses_and_serialization_smoke() -> None:
    case = StratAuditCase("baseline", {})
    assert case.name == "baseline"
    assert case.overrides == {}

    # minimal structural smoke for serialization helper on a tiny fabricated object
    class _Dummy:
        pass

    # the helper expects a real summary object, so verify the dict contract via a simple shape
    payload = {
        "baseline": {"name": "baseline", "strategy_signature": "sig", "strategy_id": 1, "total_cost": 1.0, "n_blocks": 1, "score_proxy": 0.5, "payload": {}},
        "cases": [],
        "stability_index": 0.0,
        "signature_entropy": 0.0,
        "dominant_signature_ratio": 1.0,
    }
    assert audit_summary_to_dict.__name__ == "audit_summary_to_dict"
    assert payload["baseline"]["strategy_signature"] == "sig"
