"""`requirements.lock` is an export of `uv.lock`: the Windows release workflow installs it and the
security workflow audits it. Exported once and never again, it had fallen 32 packages behind,
a pydantic pre-release included, so the audit was checking versions nobody ran. After every
`uv lock --upgrade`, rerun the export command written in its header.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _exported_pins(text: str) -> dict[str, str]:
    pins = {}
    for line in text.splitlines():
        match = PIN.match(line)
        if match:
            pins[_normalized(match.group(1))] = match.group(2)
    return pins


def test_requirements_lock_pins_the_versions_of_uv_lock() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked = {_normalized(p["name"]): p["version"] for p in lock["package"] if "version" in p}
    exported = _exported_pins((ROOT / "requirements.lock").read_text(encoding="utf-8"))
    assert exported, "requirements.lock pins nothing"
    drift = {name: (version, locked.get(name)) for name, version in exported.items() if locked.get(name) != version}
    assert not drift, (
        "requirements.lock differs from uv.lock, as (exported, locked): "
        f"{drift}; rerun the export command written in its header"
    )
