"""CERTUS configuration persistence helpers."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any


def get_resource_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base_path = Path(sys.executable).resolve().parent
    else:
        base_path = Path(__file__).resolve().parents[2]
    resource = Path(filename)
    if resource.is_absolute():
        return str(resource)
    return str((base_path / resource).resolve())

CONFIG_SCHEMA_VERSION = 1


class ConfigManager:
    """Small JSON config manager with schema versioning."""

    def __init__(self, filename: str, default_value: Any, key_name: str):
        self.filename = filename
        self.default_value = default_value
        self.key_name = key_name
        self._value = default_value
        self.reload()

    def _path(self) -> Path:
        return Path(get_resource_path(self.filename))

    def _load(self) -> Any:
        try:
            config_path = self._path()
            if not config_path.exists():
                self._value = self.default_value
                return self.default_value
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
            if not isinstance(config, dict):
                self._value = self.default_value
                return self.default_value
            if self.key_name not in config:
                self._value = self.default_value
                return self.default_value
            self._value = config.get(self.key_name, self.default_value)
            return self._value
        except (OSError, IOError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logging.debug("Could not load %s: %s", self.filename, exc)
            self._value = self.default_value
            return self.default_value

    def save(self, value: Any) -> bool:
        try:
            config_path = self._path()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config: dict[str, Any] = {}
            if config_path.exists():
                try:
                    with config_path.open("r", encoding="utf-8") as f:
                        parsed = json.load(f)
                        if isinstance(parsed, dict):
                            config = parsed
                except (OSError, IOError, json.JSONDecodeError, TypeError):
                    config = {}
            config["schema_version"] = CONFIG_SCHEMA_VERSION
            config[self.key_name] = value
            tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, sort_keys=True)
                f.write("\n")
            tmp_path.replace(config_path)
            self._value = value
            return True
        except (OSError, IOError, TypeError, ValueError) as exc:
            logging.warning("Could not save %s: %s", self.filename, exc)
            return False

    def get(self) -> Any:
        return self._value

    def reload(self) -> Any:
        return self._load()

    def set(self, value: Any) -> bool:
        return self.save(value)
