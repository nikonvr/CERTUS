"""Headless service scaffolding for CERTUS scientific pipelines.

This module introduces lightweight service abstractions that decouple
GUI orchestration from computation entry points, without changing the
existing scientific kernels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Generic, Protocol, TypeAlias, TypeVar

from certus_dto import (
    BaseHeadlessRequestModel,
    IndexFitRequestModel,
    REFitRequestModel,
    SubstrateIndexRequestModel,
)
from certus_metrology import RunContext, RunManifest, ValidationStatus


class HeadlessRunner(Protocol):
    """Callable contract for injected headless computation runners."""

    def __call__(self, config: Any) -> Any:
        """Execute a computation from a validated service config."""


Runner: TypeAlias = HeadlessRunner


ConfigT = TypeVar("ConfigT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class BaseHeadlessRequest(Generic[ConfigT]):
    """Public contract for all headless service requests."""

    config: ConfigT
    source_paths: list[str] = field(default_factory=list)
    seed: int | None = None
    app_id: str = "unknown"
    app_version: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.OK


@dataclass(frozen=True)
class BaseHeadlessResponse(Generic[ResultT]):
    """Public contract for all headless service responses."""

    result: ResultT
    manifest: RunManifest


HeadlessPayload: TypeAlias = BaseHeadlessRequest[Any] | Mapping[str, Any]
ReqT = TypeVar("ReqT", bound=BaseHeadlessRequest[Any])
ResT = TypeVar("ResT", bound=BaseHeadlessResponse[Any])


class BaseHeadlessService(Generic[ReqT, ResT]):
    """Shared wrapper for headless services with manifest injection."""

    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    @staticmethod
    def _to_dataclass_request(
        request: HeadlessPayload,
        model_cls: type[BaseHeadlessRequestModel],
        dc_cls: type[ReqT],
    ) -> ReqT:
        """Validate payload via Pydantic then materialize legacy dataclass request."""
        if isinstance(request, dc_cls):
            payload = asdict(request)
        elif isinstance(request, Mapping):
            payload = dict(request)
        else:
            raise TypeError(f"Unsupported request type: {type(request).__name__}")

        dto = model_cls.model_validate(payload)
        status_raw = str(dto.status)
        try:
            status = ValidationStatus(status_raw)
        except ValueError:
            status = ValidationStatus.OK

        warnings = list(dto.warnings)
        if status is ValidationStatus.OK and status_raw != ValidationStatus.OK.value:
            warnings.append(f"Unknown validation status normalized to OK: {status_raw}")

        return dc_cls(
            config=dto.config,
            source_paths=list(dto.source_paths),
            seed=dto.seed,
            app_id=dto.app_id,
            app_version=dto.app_version,
            warnings=warnings,
            status=status,
        )

    @staticmethod
    def _normalize_source_paths(source_paths: Sequence[str]) -> list[str]:
        """Canonicalize source paths before manifest fingerprinting."""
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in source_paths:
            path = str(raw or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            normalized.append(path)
        return normalized

    def _build_manifest(self, request: BaseHeadlessRequest) -> RunManifest:
        ctx = RunContext.create(
            app_id=request.app_id,
            app_version=request.app_version,
            seed=request.seed,
            input_paths=self._normalize_source_paths(list(request.source_paths)),
            warnings=list(request.warnings),
            status=request.status,
            params={"config_repr": repr(request.config)},
        )
        return RunManifest(run_context=ctx)


@dataclass(frozen=True)
class IndexFitRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for INDEX fit execution."""

    app_id: str = "CERTUS_INDEX"


@dataclass(frozen=True)
class IndexFitResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for INDEX fit execution."""


class IndexFitService(BaseHeadlessService[IndexFitRequest, IndexFitResponse]):
    """Thin headless service wrapper around an injected INDEX runner.

    The service does not implement the optimization itself yet. It wraps the
    existing computation entry-point (runner), enriches execution with a
    reproducibility manifest, and returns a typed response.
    """

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)

    def fit(self, request: IndexFitRequest | Mapping[str, Any]) -> IndexFitResponse:
        req = self._to_dataclass_request(request, IndexFitRequestModel, IndexFitRequest)
        result = self._runner(req.config)
        return IndexFitResponse(result=result, manifest=self._build_manifest(req))


@dataclass(frozen=True)
class SubstrateIndexRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for Substrate Index fits."""

    app_id: str = "CERTUS_SUBSTRATE_INDEX"


@dataclass(frozen=True)
class SubstrateIndexResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for Substrate Index execution."""


class SubstrateIndexService(BaseHeadlessService[SubstrateIndexRequest, SubstrateIndexResponse]):
    """Headless wrapper for substrate index computation entry points."""

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)

    def fit(self, request: SubstrateIndexRequest | Mapping[str, Any]) -> SubstrateIndexResponse:
        req = self._to_dataclass_request(request, SubstrateIndexRequestModel, SubstrateIndexRequest)
        result = self._runner(req.config)
        return SubstrateIndexResponse(result=result, manifest=self._build_manifest(req))


@dataclass(frozen=True)
class REFitRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for Reverse Engineering execution."""

    app_id: str = "CERTUS_RE"


@dataclass(frozen=True)
class REFitResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for Reverse Engineering execution."""


class REFitService(BaseHeadlessService[REFitRequest, REFitResponse]):
    """Headless wrapper for RE computation entry points."""

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)

    def fit(self, request: REFitRequest | Mapping[str, Any]) -> REFitResponse:
        req = self._to_dataclass_request(request, REFitRequestModel, REFitRequest)
        result = self._runner(req.config)
        return REFitResponse(result=result, manifest=self._build_manifest(req))
