"""DTO boundaries for CERTUS_FIELD workers."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel, ConfigDict, field_validator
from collections.abc import Mapping

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

class FieldParamsDTO(_MappingBase):
    """Runtime-validated DTO for FIELD calculation parameters."""
    n1_rs: list[float] | None = None
    n2_rs: list[float] | None = None
    nSub_rs: list[float] | None = None
    n_supers: list[float] | None = None
    l0: float | None = None
    lambda_calcs: list[float] | None = None
    emp_factors: list[float] | None = None
    layer_types: list[int] | None = None
    seuil_int_1: float | None = 0.5
    seuil_int_2: float | None = 0.5
    alpha: float | None = 0.5
    integral_points: int | None = 50
    maxiter: int | None = 1000
    theta_inc: float | None = 0.0
    pol_flag: int | None = 0
    tolerate_error: float | None = 0.02
    mc_iterations: int | None = 50
    rmin: float | None = 1.0
    rmax: float | None = 1.0
    min_field_active: bool | None = False
    global_opt: bool | None = False
    dmin: float | None = 5.0

    @field_validator('n1_rs', 'n2_rs', 'nSub_rs', 'n_supers', 'lambda_calcs', 'emp_factors', 'layer_types', mode='before')
    @classmethod
    def _ensure_list(cls, v):
        if v is None:
            return v
        if not isinstance(v, (list, tuple, set)):
            try:
                return list(v)
            except TypeError:
                return [v]
        return list(v)

    @field_validator('integral_points', mode='before')
    @classmethod
    def _validate_integral_points(cls, v):
        if v is None or int(v) < 2:
            return 2
        return int(v)

    @field_validator('maxiter', mode='before')
    @classmethod
    def _validate_maxiter(cls, v):
        if v is None or int(v) < 1:
            return 1
        return int(v)

    @field_validator('alpha', 'tolerate_error', mode='before')
    @classmethod
    def _validate_positive_floats(cls, v):
        if v is None:
            return v
        val = float(v)
        return 0.0 if val < 0 else val

@dataclass(frozen=True)
class FieldWorkerRequest:
    """DTO boundary for FIELD WorkerThread payload."""
    action: str = "calculate" # 'calculate' or 'optimize' or 'tolerate'
    params: FieldParamsDTO = field(default_factory=lambda: FieldParamsDTO())

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", (self.action or "calculate").strip().lower())
        if not isinstance(self.params, FieldParamsDTO):
            object.__setattr__(self, "params", FieldParamsDTO.model_validate(self.params or {}))

@dataclass(frozen=True)
class FieldWorkerResult:
    """DTO boundary for FIELD WorkerThread output payload."""
    z_coords: list[float] | None = None
    E2_values: list[float] | None = None
    E2_values_list: list[list[float]] | None = None
    E2_mc_runs: list[list[list[float]]] | None = None
    z_coords_mc: list[list[float]] | None = None
    lambda_calcs: list[float] | None = None
    ep_c1_cn: list[float] | None = None
    integrals: list[float] | None = None
    averages: list[float] | None = None
    
    # Optimization results
    opt_emp_factors: list[float] | None = None
    opt_layer_types: list[int] | None = None
    opt_metrics: dict | None = None
    pareto_solutions: list | None = None
    success: bool = False
    message: str = ""
