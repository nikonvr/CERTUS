"""Headless service scaffolding for CERTUS scientific pipelines.

This module introduces lightweight service abstractions that decouple
GUI orchestration from computation entry points, without changing the
existing scientific kernels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Generic, Protocol, TypeAlias, TypeVar

from certus.utils.certus_dto import (
    BaseHeadlessRequestModel,
    IndexFitRequestModel,
    REFitRequestModel,
    SubstrateIndexRequestModel,
)
from certus.core.certus_metrology import RunContext, RunManifest, ValidationStatus


class HeadlessRunner(Protocol):
    """Callable contract for injected headless computation runners."""

    def __call__(self, config: Any) -> Any:
        """Execute a computation from a validated service config."""


Runner: TypeAlias = HeadlessRunner


ConfigT = TypeVar("ConfigT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class BaseHeadlessRequest(Generic[ConfigT]):
    """Public contract for all headless service requests.

    The request object intentionally carries traceability fields so callers can
    correlate a run across logs, manifests and test fixtures without relying on
    implicit globals.
    """

    config: ConfigT
    source_paths: list[str] = field(default_factory=list)
    seed: int | None = None
    run_id: str | None = None
    app_id: str = "unknown"
    app_version: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.OK
    created_at: str | None = None
    initiated_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
        status_candidates = [status_raw]
        if "." in status_raw:
            status_candidates.append(status_raw.split(".")[-1])
        status = ValidationStatus.OK
        for candidate in status_candidates:
            try:
                status = ValidationStatus(candidate)
                break
            except ValueError:
                continue

        warnings = list(dto.warnings)
        if status is ValidationStatus.OK and status_raw != ValidationStatus.OK.value:
            warnings.append(f"Unknown validation status normalized to OK: {status_raw}")

        return dc_cls(
            config=dto.config,
            source_paths=list(dto.source_paths),
            seed=dto.seed,
            run_id=getattr(dto, "run_id", None),
            app_id=dto.app_id,
            app_version=dto.app_version,
            warnings=warnings,
            status=status,
            created_at=getattr(dto, "created_at", None),
            initiated_by=getattr(dto, "initiated_by", None),
            metadata=dict(getattr(dto, "metadata", {})),
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

    @staticmethod
    def _build_trace_payload(request: BaseHeadlessRequest[Any]) -> dict[str, Any]:
        """Return the normalized trace payload shared by runners and manifests."""
        return {
            "run_id": request.run_id,
            "initiated_by": request.initiated_by,
            "created_at": request.created_at,
            "metadata": dict(request.metadata),
        }

    @staticmethod
    def _build_params_payload(request: BaseHeadlessRequest[Any]) -> dict[str, Any]:
        """Return the manifest params payload for a headless request."""
        return {
            "config_repr": repr(request.config),
            **BaseHeadlessService._build_trace_payload(request),
        }

    def _build_manifest(self, request: BaseHeadlessRequest) -> RunManifest:
        params = self._build_params_payload(request)
        ctx = RunContext.create(
            app_id=request.app_id,
            app_version=request.app_version,
            seed=request.seed,
            input_paths=self._normalize_source_paths(list(request.source_paths)),
            warnings=list(request.warnings),
            status=request.status,
            params=params,
        )
        return RunManifest(run_context=ctx)

    @staticmethod
    def _build_runner_payload(request: BaseHeadlessRequest[Any]) -> dict[str, Any]:
        """Return a minimal, explicit payload for downstream runners.

        The runner remains backward-compatible and receives the configuration
        object, while trace fields stay available on the request and manifest.
        """
        return {
            "config": request.config,
            "app_id": request.app_id,
            "app_version": request.app_version,
            "seed": request.seed,
            "source_paths": list(request.source_paths),
            **BaseHeadlessService._build_trace_payload(request),
        }


@dataclass(frozen=True)
class IndexFitRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for INDEX fit execution."""

    app_id: str = "CERTUS_INDEX"


@dataclass(frozen=True)
class IndexFitResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for INDEX fit execution."""


class _DelegatedFitServiceBase(BaseHeadlessService[ReqT, ResT]):
    request_model: type[BaseHeadlessRequestModel]
    request_type: type[ReqT]
    response_type: type[ResT]

    def fit(self, request: ReqT | Mapping[str, Any]) -> ResT:
        req = self._to_dataclass_request(request, self.request_model, self.request_type)
        result = self._runner(req.config)
        manifest = self._build_manifest(req)
        return self.response_type(result=result, manifest=manifest)


class IndexFitService(_DelegatedFitServiceBase[IndexFitRequest, IndexFitResponse]):
    """Thin headless service wrapper around an injected INDEX runner.

    The service does not implement the optimization itself yet. It wraps the
    existing computation entry-point (runner), enriches execution with a
    reproducibility manifest, and returns a typed response.
    """

    request_model = IndexFitRequestModel
    request_type = IndexFitRequest
    response_type = IndexFitResponse

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)


@dataclass(frozen=True)
class SubstrateIndexRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for Substrate Index fits."""

    app_id: str = "CERTUS_SUBSTRATE_INDEX"


@dataclass(frozen=True)
class SubstrateIndexResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for Substrate Index execution."""


class SubstrateIndexService(_DelegatedFitServiceBase[SubstrateIndexRequest, SubstrateIndexResponse]):
    """Headless wrapper for substrate index computation entry points."""

    request_model = SubstrateIndexRequestModel
    request_type = SubstrateIndexRequest
    response_type = SubstrateIndexResponse

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)


@dataclass(frozen=True)
class REFitRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for Reverse Engineering execution."""

    app_id: str = "CERTUS_RE"


@dataclass(frozen=True)
class REFitResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response for Reverse Engineering execution."""


class REFitService(_DelegatedFitServiceBase[REFitRequest, REFitResponse]):
    """Headless wrapper for RE computation entry points."""

    request_model = REFitRequestModel
    request_type = REFitRequest
    response_type = REFitResponse

    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)
