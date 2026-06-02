"""Headless design service for CERTUS_DESIGN.

This wraps the existing design optimization workflow so it can be invoked
without instantiating the PyQt worker directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from certus.utils.certus_services import BaseHeadlessRequest, BaseHeadlessResponse, BaseHeadlessService
from certus.core.certus_metrology import ValidationStatus
from certus.workers.certus_design_workers_dto import DesignParamsDTO, OptimWorkerRequest, OptimWorkerResult


_DESIGN_CFG_KEYS = {
    "mats",
    "stack",
    "ep0",
    "ep",
    "wls",
    "tgts",
    "l0",
    "mode",
    "ep_back",
    "oblique_mode",
    "oblique_tgts",
    "local_delta_nm",
    "pre_polish",
    "cycle_rel_gain_min",
    "cycle_no_gain_patience",
    "run_seed",
    "n",
    "sigma",
    "has_back",
    "n_back_T",
    "d_back",
}


@dataclass(frozen=True)
class DesignStrategyRequest(BaseHeadlessRequest[dict[str, Any]]):
    """Headless request payload for design optimization."""

    app_id: str = "CERTUS_DESIGN"
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DesignStrategyResponse(BaseHeadlessResponse[dict[str, Any]]):
    """Headless response payload for design optimization."""


class DesignStrategyService(BaseHeadlessService[DesignStrategyRequest, DesignStrategyResponse]):
    """Lightweight headless wrapper for the design optimization pipeline."""

    def __init__(self, runner) -> None:
        super().__init__(runner)

    @staticmethod
    def _normalize_request(request: DesignStrategyRequest | Mapping[str, Any]) -> DesignStrategyRequest:
        """Normalize legacy and typed payloads into a single request contract."""
        if isinstance(request, DesignStrategyRequest):
            return request
        if isinstance(request, Mapping):
            payload = dict(request)
            source_paths = [str(path) for path in payload.get("source_paths", []) if str(path).strip()]
            status_raw = payload.get("status", ValidationStatus.OK)
            if isinstance(status_raw, ValidationStatus):
                status = status_raw
            else:
                try:
                    status = ValidationStatus(status_raw)
                except Exception:
                    try:
                        status = ValidationStatus[str(status_raw)]
                    except Exception:
                        status = ValidationStatus.OK
            config_obj = payload.get("config", payload.get("cfg", payload))
            if isinstance(config_obj, Mapping):
                cfg = {k: v for k, v in config_obj.items() if k in _DESIGN_CFG_KEYS}
            else:
                cfg = dict(payload)
            return DesignStrategyRequest(
                config=cfg,
                source_paths=source_paths,
                seed=payload.get("seed"),
                app_id=str(payload.get("app_id", "CERTUS_DESIGN")),
                app_version=str(payload.get("app_version", "unknown")),
                warnings=[str(w) for w in payload.get("warnings", [])],
                status=status,
            )
        raise TypeError(f"Unsupported request type: {type(request).__name__}")

    @staticmethod
    def _extract_design_config(payload: dict[str, Any]) -> dict[str, Any]:
        """Extract and filter design configuration from payload."""
        config_obj = payload.get("config", payload.get("cfg", payload))
        if isinstance(config_obj, Mapping):
            return {k: v for k, v in config_obj.items() if k in _DESIGN_CFG_KEYS}
        return {}

    @staticmethod
    def _build_runner_payload(cfg: dict[str, Any]) -> dict[str, Any]:
        """Convert a validated config into the exact payload expected by the worker runner."""
        params = DesignParamsDTO.model_validate(cfg)
        legacy_cfg = OptimWorkerRequest.from_legacy(cfg).cfg
        return {"cfg": legacy_cfg, "params": params.model_dump()}

    def optimize(self, request: DesignStrategyRequest | Mapping[str, Any]) -> DesignStrategyResponse:
        req = self._normalize_request(request)
        cfg = dict(req.config or {})
        runner_payload = self._build_runner_payload(cfg)
        result = self._runner(runner_payload)
        if isinstance(result, dict) and "ok" in result:
            return DesignStrategyResponse(result=result, manifest=self._build_manifest(req))
        return DesignStrategyResponse(
            result=OptimWorkerResult.success(ep=[], rmse=0.0).to_legacy_dict(),
            manifest=self._build_manifest(req),
        )
