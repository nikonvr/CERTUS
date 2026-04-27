"""DTO boundaries for CERTUS_STRAT workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _copy_legacy_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    return dict(params)


@dataclass(frozen=True)
class WorkerThreadRequest:
    """DTO boundary for STRAT WorkerThread payload."""

    step: int = 0
    params: dict[str, Any] = field(default_factory=dict)
    opti_results: dict[str, Any] | None = None
    timing_logger: Any = None

    @staticmethod
    def from_legacy(
        *,
        step: int,
        params: dict[str, Any] | None,
        opti_results: dict[str, Any] | None = None,
        timing_logger: Any = None,
    ) -> "WorkerThreadRequest":
        return WorkerThreadRequest(
            step=int(step),
            params=_copy_legacy_params(params),
            opti_results=dict(opti_results) if isinstance(opti_results, dict) else opti_results,
            timing_logger=timing_logger,
        )


@dataclass(frozen=True)
class WorkerThreadResult:
    """DTO boundary for STRAT WorkerThread output payload."""

    nominal_results: dict[str, Any] | None = None
    seel_data: dict[str, Any] | None = None
    opti_results: dict[str, Any] | None = None
    final_results: dict[str, Any] | None = None

    @staticmethod
    def for_step_0(nominal_results: dict[str, Any], seel_data: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult(
            nominal_results=dict(nominal_results),
            seel_data=dict(seel_data),
        )

    @staticmethod
    def for_step_2(opti_results: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult(opti_results=dict(opti_results))

    @staticmethod
    def for_step_3(final_results: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult(final_results=dict(final_results))

    @staticmethod
    def for_step_23(
        *,
        opti_results: dict[str, Any],
        final_results: dict[str, Any],
    ) -> "WorkerThreadResult":
        return WorkerThreadResult(
            opti_results=dict(opti_results),
            final_results=dict(final_results),
        )

    @staticmethod
    def for_step_33(
        *,
        opti_results: dict[str, Any],
        final_results: dict[str, Any],
    ) -> "WorkerThreadResult":
        return WorkerThreadResult(
            opti_results=dict(opti_results),
            final_results=dict(final_results),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.nominal_results is not None:
            out["nominal_results"] = self.nominal_results
        if self.seel_data is not None:
            out["seel_data"] = self.seel_data
        if self.opti_results is not None:
            out["opti_results"] = self.opti_results
        if self.final_results is not None:
            out["final_results"] = self.final_results
        return out
