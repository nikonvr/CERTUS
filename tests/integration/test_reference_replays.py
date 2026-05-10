from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from _certus_physics_impl import calculate_transmission_single

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_replay_single_layer_index_scenario_v1() -> None:
    base = Path("samples/reference/v1/index_single_layer_basic")
    input_path = base / "input.json"
    expected_path = base / "expected.json"
    manifest_path = base / "manifest.json"

    assert input_path.exists()
    assert expected_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"]["input.json"] == _sha256(input_path)
    assert manifest["files"]["expected.json"] == _sha256(expected_path)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    inp = payload["inputs"]
    tol = payload.get("tolerance", {})
    rtol = float(tol.get("rtol", 1e-9))
    atol = float(tol.get("atol", 1e-12))

    r, t = calculate_transmission_single(
        wavelength=float(inp["wavelength_nm"]),
        n_film_real=float(inp["n_film_real"]),
        n_film_imag=float(inp["n_film_imag"]),
        thickness_nm=float(inp["thickness_nm"]),
        n_sub=complex(float(inp["n_sub_real"]), float(inp["n_sub_imag"])),
    )

    assert np.isclose(float(r), float(expected["outputs"]["reflectance"]), rtol=rtol, atol=atol)
    assert np.isclose(float(t), float(expected["outputs"]["transmittance"]), rtol=rtol, atol=atol)
