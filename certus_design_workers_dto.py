"""DTO boundaries for CERTUS_DESIGN workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _copy_legacy_cfg(cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    return dict(cfg)


@dataclass(frozen=True)
class OptimWorkerRequest:
    """DTO boundary for DESIGN OptimWorker payload."""

    cfg: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_legacy(cfg: dict[str, Any] | None) -> "OptimWorkerRequest":
        return OptimWorkerRequest(cfg=_copy_legacy_cfg(cfg))


@dataclass(frozen=True)
class ColorWorkerRequest:
    """DTO boundary for DESIGN ColorWorker payload."""

    cfg: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_legacy(cfg: dict[str, Any] | None) -> "ColorWorkerRequest":
        return ColorWorkerRequest(cfg=_copy_legacy_cfg(cfg))


@dataclass(frozen=True)
class NeedleWorkerRequest:
    """DTO boundary for DESIGN NeedleWorker payload."""

    cfg: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_legacy(cfg: dict[str, Any] | None) -> "NeedleWorkerRequest":
        return NeedleWorkerRequest(cfg=_copy_legacy_cfg(cfg))


@dataclass(frozen=True)
class ColorWorkerResult:
    """DTO boundary for DESIGN ColorWorker output payload."""

    ok: bool
    lab_nom: Any | None = None
    labs: Any | None = None

    @staticmethod
    def success(lab_nom: Any, labs: Any) -> "ColorWorkerResult":
        return ColorWorkerResult(ok=True, lab_nom=lab_nom, labs=labs)

    @staticmethod
    def failure() -> "ColorWorkerResult":
        return ColorWorkerResult(ok=False)

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": bool(self.ok)}
        if self.ok:
            out["lab_nom"] = self.lab_nom
            out["labs"] = self.labs
        return out


@dataclass(frozen=True)
class OptimWorkerResult:
    """DTO boundary for DESIGN OptimWorker output payload."""

    ok: bool
    ep: Any | None = None
    rmse: float | None = None

    @staticmethod
    def success(ep: Any, rmse: float) -> "OptimWorkerResult":
        return OptimWorkerResult(ok=True, ep=ep, rmse=float(rmse))

    @staticmethod
    def failure() -> "OptimWorkerResult":
        return OptimWorkerResult(ok=False)

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": bool(self.ok)}
        if self.ok:
            out["ep"] = self.ep
            out["rmse"] = self.rmse
        return out


@dataclass(frozen=True)
class NeedleWorkerResult:
    """DTO boundary for DESIGN NeedleWorker output payload."""

    action: str
    layer_idx: int | None = None
    depth: float | None = None
    needle_mat: str | None = None
    cost: float | None = None

    @staticmethod
    def action_only(action: str) -> "NeedleWorkerResult":
        return NeedleWorkerResult(action=str(action))

    @staticmethod
    def from_legacy(payload: dict[str, Any] | None) -> "NeedleWorkerResult":
        data = payload if isinstance(payload, dict) else {}
        return NeedleWorkerResult(
            action=str(data.get("action", "none")),
            layer_idx=int(data["layer_idx"]) if data.get("layer_idx") is not None else None,
            depth=float(data["depth"]) if data.get("depth") is not None else None,
            needle_mat=str(data["needle_mat"]) if data.get("needle_mat") is not None else None,
            cost=float(data["cost"]) if data.get("cost") is not None else None,
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"action": self.action}
        if self.layer_idx is not None:
            out["layer_idx"] = int(self.layer_idx)
        if self.depth is not None:
            out["depth"] = float(self.depth)
        if self.needle_mat is not None:
            out["needle_mat"] = self.needle_mat
        if self.cost is not None:
            out["cost"] = float(self.cost)
        return out
