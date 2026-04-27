"""Headless service scaffolding for CERTUS scientific pipelines.

This module introduces lightweight service abstractions that decouple
GUI orchestration from computation entry points, without changing the
existing scientific kernels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from certus_metrology import RunContext, RunManifest, ValidationStatus


@dataclass(frozen=True)
class BaseHeadlessRequest:
    """Public contract for all headless service requests."""

    config: Any
    source_paths: list[str] = field(default_factory=list)
    seed: int | None = None
    app_id: str = "unknown"
    app_version: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.OK


@dataclass(frozen=True)
class BaseHeadlessResponse:
    """Public contract for all headless service responses."""

    result: Any
    manifest: RunManifest


ReqT = TypeVar("ReqT", bound=BaseHeadlessRequest)
ResT = TypeVar("ResT", bound=BaseHeadlessResponse)


class BaseHeadlessService(Generic[ReqT, ResT]):
    """Shared wrapper for headless services with manifest injection."""

    def __init__(self, runner: Callable[[Any], Any]):
        self._runner = runner

    @staticmethod
    def _normalize_source_paths(source_paths: list[str]) -> list[str]:
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
class IndexFitRequest(BaseHeadlessRequest):
    """Headless request payload for INDEX fit execution."""

    app_id: str = "CERTUS_INDEX"


@dataclass(frozen=True)
class IndexFitResponse(BaseHeadlessResponse):
    """Headless response for INDEX fit execution."""


class IndexFitService(BaseHeadlessService[IndexFitRequest, IndexFitResponse]):
    """Thin headless service wrapper around an injected INDEX runner.

    The service does not implement the optimization itself yet. It wraps the
    existing computation entry-point (runner), enriches execution with a
    reproducibility manifest, and returns a typed response.
    """

    def __init__(self, runner: Callable[[Any], Any]):
        super().__init__(runner)

    def fit(self, request: IndexFitRequest) -> IndexFitResponse:
        result = self._runner(request.config)
        return IndexFitResponse(result=result, manifest=self._build_manifest(request))


@dataclass(frozen=True)
class SubstrateIndexRequest(BaseHeadlessRequest):
    """Headless request payload for Substrate Index fits."""

    app_id: str = "CERTUS_SUBSTRATE_INDEX"


@dataclass(frozen=True)
class SubstrateIndexResponse(BaseHeadlessResponse):
    """Headless response for Substrate Index execution."""


class SubstrateIndexService(BaseHeadlessService[SubstrateIndexRequest, SubstrateIndexResponse]):
    """Headless wrapper for substrate index computation entry points."""

    def __init__(self, runner: Callable[[Any], Any]):
        super().__init__(runner)

    def fit(self, request: SubstrateIndexRequest) -> SubstrateIndexResponse:
        result = self._runner(request.config)
        return SubstrateIndexResponse(result=result, manifest=self._build_manifest(request))


@dataclass(frozen=True)
class REFitRequest(BaseHeadlessRequest):
    """Headless request payload for Reverse Engineering execution."""

    app_id: str = "CERTUS_RE"


@dataclass(frozen=True)
class REFitResponse(BaseHeadlessResponse):
    """Headless response for Reverse Engineering execution."""


class REFitService(BaseHeadlessService[REFitRequest, REFitResponse]):
    """Headless wrapper for RE computation entry points."""

    def __init__(self, runner: Callable[[Any], Any]):
        super().__init__(runner)

    def fit(self, request: REFitRequest) -> REFitResponse:
        result = self._runner(request.config)
        return REFitResponse(result=result, manifest=self._build_manifest(request))

