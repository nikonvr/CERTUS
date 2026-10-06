from __future__ import annotations

import hashlib
import json
from pathlib import Path

from certus.core.certus_core import get_materials_db_hash

EXPECTED_MATERIALS_V1_SHA256 = "d2ce255df1af017d3f132f399b3db906ee45e2ee816ffae9e1a2fef3ab6b71aa"


def test_materials_v1_hash_is_locked() -> None:
    db_path = Path("data/materials_v1.json")
    assert db_path.exists()
    content = db_path.read_bytes().replace(b"\r\n", b"\n")
    file_hash = hashlib.sha256(content).hexdigest()
    assert file_hash == EXPECTED_MATERIALS_V1_SHA256
    assert get_materials_db_hash() == EXPECTED_MATERIALS_V1_SHA256


def test_materials_hash_changes_when_coeff_changes() -> None:
    db_path = Path("data/materials_v1.json")
    payload = json.loads(db_path.read_text(encoding="utf-8"))
    payload2 = json.loads(db_path.read_text(encoding="utf-8"))
    payload2["sellmeier_coeffs_by_id"]["0"][0] = float(payload2["sellmeier_coeffs_by_id"]["0"][0]) + 1e-12

    h1 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(json.dumps(payload2, sort_keys=True).encode("utf-8")).hexdigest()
    assert h1 != h2
