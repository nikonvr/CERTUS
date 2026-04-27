"""CERTUS metrology primitives (run context, manifest, fingerprints).

This module is UI-agnostic and can be used by workers/tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


try:
    from certus_core import __version__ as CERTUS_VERSION
except ImportError:
    CERTUS_VERSION = "unknown"


class ValidationStatus(str, Enum):
    """Normalized status for exported scientific runs."""

    OK = "OK"
    WARNING_DATA_NORMALIZED = "WARNING_DATA_NORMALIZED"
    WARNING_EXTRAPOLATION = "WARNING_EXTRAPOLATION"
    WARNING_UNSEEDED_STOCHASTIC = "WARNING_UNSEEDED_STOCHASTIC"
    WARNING_UNCERTAINTY_NOT_COMPUTED = "WARNING_UNCERTAINTY_NOT_COMPUTED"
    ERROR_INVALID_INPUT = "ERROR_INVALID_INPUT"


@dataclass(frozen=True)
class InputFingerprint:
    """Stable fingerprint for one input file."""

    path: str
    sha256: str
    size: int
    mtime_utc: str

    @staticmethod
    def from_path(path: str) -> "InputFingerprint":
        abs_path = str(Path(path).resolve(strict=False))
        st = Path(abs_path).stat()
        mtime = datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat()
        return InputFingerprint(
            path=abs_path,
            sha256=_sha256_file(abs_path),
            size=int(st.st_size),
            mtime_utc=mtime,
        )


@dataclass(frozen=True)
class SoftwareEnv:
    """Software/runtime environment captured for reproducibility."""

    python: str
    numpy: str = "unknown"
    scipy: str = "unknown"
    numba: str = "unknown"
    pyqt: str = "unknown"
    openpyxl: str = "unknown"
    matplotlib: str = "unknown"
    os: str = ""
    certus_version: str = CERTUS_VERSION

    @staticmethod
    def detect() -> "SoftwareEnv":
        return SoftwareEnv(
            python=platform.python_version(),
            numpy=_get_version("numpy"),
            scipy=_get_version("scipy"),
            numba=_get_version("numba"),
            pyqt=_detect_pyqt_version(),
            openpyxl=_get_version("openpyxl"),
            matplotlib=_get_version("matplotlib"),
            os=f"{platform.system()} {platform.release()}",
            certus_version=CERTUS_VERSION,
        )


@dataclass(frozen=True)
class RunContext:
    """Common context for one scientific run."""

    run_id: str
    started_at_utc: str
    app_id: str
    app_version: str
    seed: int | None
    software_env: SoftwareEnv
    input_fingerprints: list[InputFingerprint] = field(default_factory=list)
    params_hash: str = ""
    warnings: list[str] = field(default_factory=list)
    status: ValidationStatus = ValidationStatus.OK

    @staticmethod
    def create(
        *,
        app_id: str,
        app_version: str,
        seed: int | None = None,
        run_id: str | None = None,
        started_at_utc: str | None = None,
        input_paths: list[str] | None = None,
        params: Any | None = None,
        warnings: list[str] | None = None,
        status: ValidationStatus = ValidationStatus.OK,
    ) -> "RunContext":
        now_utc = started_at_utc or datetime.now(UTC).isoformat()
        rid = run_id or _default_run_id()
        fps: list[InputFingerprint] = []
        for p in input_paths or []:
            try:
                fps.append(InputFingerprint.from_path(p))
            except OSError:
                continue
        return RunContext(
            run_id=rid,
            started_at_utc=now_utc,
            app_id=app_id,
            app_version=app_version,
            seed=seed,
            software_env=SoftwareEnv.detect(),
            input_fingerprints=fps,
            params_hash=compute_params_hash(params) if params is not None else "",
            warnings=list(warnings or []),
            status=status,
        )


@dataclass(frozen=True)
class RunManifest:
    """Serializable export manifest for one run."""

    run_context: RunContext

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self.run_context)
        data["status"] = self.run_context.status.value
        return data

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def as_flat_dict(self) -> dict[str, Any]:
        """Flattened form intended for key/value report sections."""
        data = self.to_dict()
        flat: dict[str, Any] = {}
        for key, val in data.items():
            if isinstance(val, list):
                flat[key] = json.dumps(val, ensure_ascii=False)
            elif isinstance(val, dict):
                flat[key] = json.dumps(val, ensure_ascii=False)
            else:
                flat[key] = val
        return flat


def compute_params_hash(params: Any) -> str:
    """Hash params payload in a deterministic way."""
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("run_%Y%m%dT%H%M%SZ")


def _get_version(module_name: str) -> str:
    try:
        mod = __import__(module_name)
        return str(getattr(mod, "__version__", "unknown"))
    except ImportError:
        return "unknown"


def _detect_pyqt_version() -> str:
    try:
        from PyQt6.QtCore import QT_VERSION_STR

        return str(QT_VERSION_STR)
    except ImportError:
        return "unknown"
