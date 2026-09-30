"""CERTUS metrology primitives (run context, manifest, fingerprints).

This module is UI-agnostic and can be used by workers/tests.
"""

from __future__ import annotations

import hashlib
import json
import locale
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


try:
    from certus.core.certus_core import __version__ as CERTUS_VERSION
    from certus.core.certus_core import get_materials_db_hash, numba_cache_key
except ImportError:
    CERTUS_VERSION = "unknown"
    def get_materials_db_hash():
        return ""
    def numba_cache_key():
        return ""


@lru_cache(maxsize=1)
def git_state() -> tuple[str, bool | None]:
    """The commit of the checkout that runs, and whether its tracked files differ from it.

    Returns `(sha, dirty)`; `("", None)` when it cannot be known: a frozen build (no repository), no `git`,
    or a repository that does not answer in time (a synchronized folder can be slow). Asked once per process.
    """
    if getattr(sys, "frozen", False):
        return "", None
    root = str(Path(__file__).resolve().parents[2])
    base = ["git", "-C", root, "--no-optional-locks"]
    try:
        head = subprocess.run([*base, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        if head.returncode != 0 or len(head.stdout.strip()) != 40:
            return "", None
        changed = subprocess.run([*base, "diff", "--quiet", "HEAD", "--"], capture_output=True, timeout=10, check=False)
        return head.stdout.strip(), (changed.returncode == 1) if changed.returncode in (0, 1) else None
    except (OSError, subprocess.SubprocessError):
        return "", None


def _distribution_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _numba_cache_in_use() -> str:
    """The directory Numba reads its cache from: what it fixed when it was imported, else what it will read."""
    config = getattr(sys.modules.get("numba"), "config", None)
    if config is not None:
        return str(getattr(config, "CACHE_DIR", "") or "")
    return os.environ.get("NUMBA_CACHE_DIR", "")


def provenance() -> dict[str, Any]:
    """What produced a result, in a flat dictionary a report can carry: enough to run it again.

    Measured on 2026-09-30, none of the 1 451 JSON files of `reports/` carried the commit, the platform or the
    versions of Python, NumPy or Numba (3 named a version): a result nobody could tie to the code that gave it.
    Versions come from the installed distributions, without importing them.

    `numba_cache_keyed` says whether the machine code that computed the result was compiled from these sources:
    True when Numba read the directory that carries their key (`numba_cache_key`), False when it read its own
    default next to the sources (where a caller keeps an OLD callee after an update) or a directory of the
    caller's choosing, whose content nobody named.
    """
    commit, dirty = git_state()
    key = numba_cache_key()
    return {
        "certus_version": CERTUS_VERSION,
        "git_commit": commit or None,
        "git_dirty": dirty,
        "python": platform.python_version(),
        "numpy": _distribution_version("numpy"),
        "scipy": _distribution_version("scipy"),
        "numba": _distribution_version("numba"),
        "numba_cache_key": key or None,
        "numba_cache_keyed": bool(key) and Path(_numba_cache_in_use()).name == key,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


class ValidationStatus(str, Enum):
    """Normalized status for exported scientific runs."""

    OK = "OK"
    WARNING_DATA_NORMALIZED = "WARNING_DATA_NORMALIZED"
    WARNING_EXTRAPOLATION = "WARNING_EXTRAPOLATION"
    WARNING_UNSEEDED_STOCHASTIC = "WARNING_UNSEEDED_STOCHASTIC"
    WARNING_UNCERTAINTY_NOT_COMPUTED = "WARNING_UNCERTAINTY_NOT_COMPUTED"
    ERROR_INVALID_INPUT = "ERROR_INVALID_INPUT"


class InputFingerprint(BaseModel):
    """Stable fingerprint for one input file."""

    model_config = ConfigDict(frozen=True)

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


class SoftwareEnv(BaseModel):
    """Software/runtime environment captured for reproducibility."""

    model_config = ConfigDict(frozen=True)

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


class RunContext(BaseModel):
    """Common context for one scientific run."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: str
    started_at_utc: str
    app_id: str
    app_version: str
    seed: int | None
    software_env: SoftwareEnv
    numba_version: str = "unknown"
    numpy_version: str = "unknown"
    threading_layer: str = "unknown"
    env_locale: str = ""
    cpu_brand: str = ""
    os_release: str = ""
    input_fingerprints: list[InputFingerprint] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    params_hash: str = ""
    materials_db_hash: str = ""
    db_version: str = ""
    git_commit: str = ""
    git_dirty: bool | None = None
    warnings: list[str] = Field(default_factory=list)
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
            numba_version=_get_version("numba"),
            numpy_version=_get_version("numpy"),
            threading_layer=_detect_threading_layer(),
            env_locale=_detect_locale(),
            cpu_brand=_detect_cpu_brand(),
            os_release=platform.release(),
            input_fingerprints=fps,
            params=dict(params or {}) if isinstance(params, dict) else ({"value": params} if params is not None else {}),
            params_hash=compute_params_hash(params) if params is not None else "",
            materials_db_hash=(_db_hash := str(get_materials_db_hash() or "")),
            db_version=_db_hash[:12],
            git_commit=git_state()[0],
            git_dirty=git_state()[1],
            warnings=list(warnings or []),
            status=status,
        )


class RunManifest(BaseModel):
    """Serializable export manifest for one run."""

    model_config = ConfigDict(frozen=True)

    run_context: RunContext

    def to_dict(self) -> dict[str, Any]:
        data = self.run_context.model_dump(mode="json")
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
        return version("PyQt6")
    except PackageNotFoundError:
        return "unknown"


def _detect_threading_layer() -> str:
    try:
        import numba

        return str(numba.threading_layer())
    except (RuntimeError, ValueError, AttributeError):
        return "unknown"


def _detect_locale() -> str:
    try:
        loc = locale.getlocale()
        lang = str((loc[0] if loc else "") or "")
        enc = str(locale.getencoding() or "")
        return f"{lang}.{enc}" if enc else lang
    except (ValueError, OSError):
        return ""


def _detect_cpu_brand() -> str:
    try:
        brand = platform.processor()
        if brand:
            return str(brand)
        return str(platform.machine())
    except (OSError, ValueError):
        return ""
