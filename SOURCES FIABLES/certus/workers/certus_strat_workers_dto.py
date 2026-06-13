"""DTO boundaries for CERTUS_STRAT workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from collections.abc import Mapping
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from certus.utils.certus_data import TimingLogger


class _MappingBase(BaseModel, Mapping):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None

    def __iter__(self):
        keys = list(self.__class__.model_fields.keys())
        if self.model_extra:
            keys.extend(self.model_extra.keys())
        return iter(keys)

    def __len__(self) -> int:
        return len(self.__class__.model_fields) + (len(self.model_extra) if self.model_extra else 0)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def _eq_mapping(self, other: Any) -> bool:
        if isinstance(other, dict):
            self_dict = {k: v for k, v in self.items() if v is not None}
            other_dict = {k: v for k, v in other.items() if v is not None}
            return self_dict == other_dict
        return False


class StratParamsDTO(_MappingBase):
    """Runtime-validated DTO for STRAT calculation parameters."""

    nH_id: Any | None = None
    nL_id: Any | None = None
    nSub_id: Any | None = None
    l0: float | None = None
    stack_string: str | None = None
    wl_range: list[float] | None = None
    wl_step: float | None = None
    scan_wl_min: float | None = None
    scan_wl_max: float | None = None
    reality_sim_params: dict[str, Any] | None = None
    phase_a_seed: int | None = None
    robustness_seed: int | None = None

    def __post_init__(self) -> None:
        if self.wl_range is not None and len(self.wl_range) >= 2:
            wl_min, wl_max = float(self.wl_range[0]), float(self.wl_range[-1])
            if self.scan_wl_min is None:
                object.__setattr__(self, "scan_wl_min", wl_min)
            if self.scan_wl_max is None:
                object.__setattr__(self, "scan_wl_max", wl_max)

    def __eq__(self, other: Any) -> bool:
        if self._eq_mapping(other):
            return True
        if isinstance(other, StratParamsDTO):
            return self.model_dump(exclude_none=True) == other.model_dump(exclude_none=True)
        return super().__eq__(other)


class StratOptiResultsDTO(_MappingBase):
    """Runtime-validated DTO for STRAT optimization results."""

    p_thick_nominal: Any | None = None
    all_strategies: list[Any] | None = None
    clues_at_wl: dict[float, dict[str, complex]] | None = None
    raw_results_thickness: Any | None = None

    def __eq__(self, other: Any) -> bool:
        if self._eq_mapping(other):
            return True
        if isinstance(other, StratOptiResultsDTO):
            return self.model_dump(exclude_none=True) == other.model_dump(exclude_none=True)
        return super().__eq__(other)


def _copy_legacy_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    return dict(params)


@dataclass(frozen=True)
class WorkerThreadRequest:
    """DTO boundary for STRAT WorkerThread payload."""

    step: int = 0
    params: StratParamsDTO = field(default_factory=lambda: StratParamsDTO())
    opti_results: StratOptiResultsDTO | None = None
    timing_logger: TimingLogger | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.params, StratParamsDTO):
            object.__setattr__(self, "params", StratParamsDTO.model_validate(self.params or {}))
        if self.opti_results is not None and not isinstance(self.opti_results, StratOptiResultsDTO):
            object.__setattr__(self, "opti_results", StratOptiResultsDTO.model_validate(self.opti_results))

    @staticmethod
    def from_legacy(
        *,
        step: int,
        params: dict[str, Any] | None,
        opti_results: dict[str, Any] | None = None,
        timing_logger: TimingLogger | None = None,
    ) -> "WorkerThreadRequest":
        return WorkerThreadRequest(
            step=int(step),
            params=StratParamsDTO.model_validate(_copy_legacy_params(params)),
            opti_results=StratOptiResultsDTO.model_validate(opti_results) if isinstance(opti_results, dict) else opti_results,
            timing_logger=timing_logger,
        )


@dataclass(frozen=True)
class WorkerThreadResult:
    """DTO boundary for STRAT WorkerThread output payload."""

    nominal_results: dict[str, Any] | None = None
    seel_data: dict[str, Any] | None = None
    opti_results: StratOptiResultsDTO | None = None
    final_results: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.opti_results is not None and not isinstance(self.opti_results, StratOptiResultsDTO):
            object.__setattr__(self, "opti_results", StratOptiResultsDTO.model_validate(self.opti_results))

    @staticmethod
    def _build(*, nominal_results=None, seel_data=None, opti_results=None, final_results=None) -> "WorkerThreadResult":
        return WorkerThreadResult(
            nominal_results=dict(nominal_results) if nominal_results is not None else None,
            seel_data=dict(seel_data) if seel_data is not None else None,
            opti_results=opti_results,
            final_results=dict(final_results) if final_results is not None else None,
        )

    @staticmethod
    def for_step_0(nominal_results: dict[str, Any], seel_data: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult._build(nominal_results=nominal_results, seel_data=seel_data)

    @staticmethod
    def for_step_2(opti_results: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult._build(opti_results=opti_results)

    @staticmethod
    def for_step_3(final_results: dict[str, Any]) -> "WorkerThreadResult":
        return WorkerThreadResult._build(final_results=final_results)

    @staticmethod
    def for_step_23(
        *,
        opti_results: dict[str, Any],
        final_results: dict[str, Any],
    ) -> "WorkerThreadResult":
        return WorkerThreadResult._build(opti_results=opti_results, final_results=final_results)

    @staticmethod
    def for_step_33(
        *,
        opti_results: dict[str, Any],
        final_results: dict[str, Any],
    ) -> "WorkerThreadResult":
        return WorkerThreadResult._build(opti_results=opti_results, final_results=final_results)

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.nominal_results is not None:
            out["nominal_results"] = self.nominal_results
        if self.seel_data is not None:
            out["seel_data"] = self.seel_data
        if self.opti_results is not None:
            out["opti_results"] = self.opti_results.model_dump(exclude_none=True)
        if self.final_results is not None:
            out["final_results"] = self.final_results
        return out

