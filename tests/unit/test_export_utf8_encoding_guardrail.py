"""Test de garde-fou d'encodage UTF-8 sous Windows pour éviter les plantages CP1252."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

# Caractères optiques et scientifiques fréquents dans la suite CERTUS
OPTICAL_SYMBOLS = {
    "lambda": "λ = 550.0 nm",
    "micron": "1.2 µm",
    "sigma": "σ = 1.66",
    "delta": "Δd = ±0.5 nm",
    "angle": "θ = 45.0°",
    "checks": "✓ Admissible",
    "trophy": "🏆 Best Strategy",
    "cross": "100 × 50",
    "ineq": "T ≤ 10%",
}


@pytest.mark.unit
def test_optical_symbols_json_roundtrip_utf8() -> None:
    """Vérifie que tous les symboles optiques CERTUS se sérialisent et se relisent en UTF-8 sans altération."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        json.dumps(OPTICAL_SYMBOLS, ensure_ascii=False, indent=2)
        tmp.write(json.dumps(OPTICAL_SYMBOLS, ensure_ascii=False, indent=2))

    try:
        loaded = json.loads(tmp_path.read_text(encoding="utf-8"))
        assert loaded == OPTICAL_SYMBOLS
        assert loaded["lambda"] == "λ = 550.0 nm"
        assert loaded["checks"] == "✓ Admissible"
        assert loaded["trophy"] == "🏆 Best Strategy"
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.unit
def test_certus_reports_write_uses_utf8() -> None:
    """Vérifie que les utilitaires d'écriture asynchrone imposent bien encoding='utf-8'."""
    from certus.utils.certus_reset_framework import AsyncWriteWorker

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_report.json"
        worker = AsyncWriteWorker(lambda: OPTICAL_SYMBOLS, out_file)
        worker.run()

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "λ = 550.0 nm" in content
        assert "✓ Admissible" in content
