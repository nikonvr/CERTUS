"""Pydantic DTO layer for headless requests and user JSON configs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseHeadlessRequestModel(BaseModel):
    """Runtime-validated DTO for headless requests."""

    model_config = ConfigDict(extra="forbid")

    config: Any
    source_paths: list[str] = Field(default_factory=list)
    seed: int | None = None
    run_id: str | None = None
    app_id: str = "unknown"
    app_version: str = "unknown"
    warnings: list[str] = Field(default_factory=list)
    status: str = "OK"
    created_at: str | None = None
    initiated_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexFitRequestModel(BaseHeadlessRequestModel):
    app_id: str = "CERTUS_INDEX"


class SubstrateIndexRequestModel(BaseHeadlessRequestModel):
    app_id: str = "CERTUS_SUBSTRATE_INDEX"


class REFitRequestModel(BaseHeadlessRequestModel):
    app_id: str = "CERTUS_RE"


class StratConfigDTO(BaseModel):
    """Validation DTO for STRAT user JSON configuration."""

    model_config = ConfigDict(extra="allow")

    stack_multipliers: list[float] | None = None
    blocks: list[dict[str, Any]] | None = None
    strategy_id: str | int | None = None
    n_blocks: int | None = None
    h_material_file: str | None = None
    l_material_file: str | None = None
    substrate_choice: str | None = None


class IndexSplineConfigDTO(BaseModel):
    """Validation DTO for INDEX_SPLINE user JSON configuration."""

    model_config = ConfigDict(extra="allow")

    version: str | int | None = None
    model_type: str | None = None
    optimize_n: bool | None = None
    optimize_k: bool | None = None
    use_spline_interp: bool | None = None
    knot_mode: str | None = None
    knot_count: int | None = None
    lambda_min_nm: float | None = None
    lambda_max_nm: float | None = None
