"""UNE SONDE NE DOIT JAMAIS DETRUIRE UN ARTEFACT — le garde, et sa preuve.

🔴 CES TESTS ECHOUENT SUR LE CODE D'AVANT : `scripts/_artefact.py` n'existait pas, et les
quinze sondes ecrivaient par `Path.write_text` direct, donc en ecrasant en silence.

📏 Le defaut a failli coûter deux artefacts le 2026-08-20 : la reference de 8,26 Mo du controle
C1, et 215 Ko de mesures du 19 aout. `CLAUDE.md` interdit 3 rappelle que 193 fichiers de
`reports/` sur 226 ne sont suivis par rien.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _artefact import chemin_libre, ecrire_json  # noqa: E402


class TestCheminLibre:
    def test_pas_de_collision_rend_la_cible(self, tmp_path: Path) -> None:
        c = tmp_path / "mesure.json"
        libre, ancien = chemin_libre(c)
        assert libre == c
        assert ancien is None

    def test_collision_renomme_et_signale_l_ancien(self, tmp_path: Path) -> None:
        c = tmp_path / "mesure.json"
        c.write_text("precieux", encoding="utf-8")
        libre, ancien = chemin_libre(c, horodatage="20260820_100000")
        assert libre.name == "mesure_20260820_100000.json"
        assert ancien == c
        # 🔒 l'essentiel : l'ancien est INTACT
        assert c.read_text(encoding="utf-8") == "precieux"

    def test_deux_collisions_dans_la_meme_seconde(self, tmp_path: Path) -> None:
        """Deux sondes lancees ensemble par un pilote partagent l'horodatage a la seconde."""
        c = tmp_path / "mesure.json"
        c.write_text("a", encoding="utf-8")
        (tmp_path / "mesure_20260820_100000.json").write_text("b", encoding="utf-8")
        libre, _ = chemin_libre(c, horodatage="20260820_100000")
        assert libre.name == "mesure_20260820_100000_1.json"

    def test_le_suffixe_est_conserve(self, tmp_path: Path) -> None:
        c = tmp_path / "courbe.log"
        c.write_text("x", encoding="utf-8")
        libre, _ = chemin_libre(c, horodatage="S")
        assert libre.name == "courbe_S.log"


class TestEcrireJson:
    def test_ecrit_et_rend_le_chemin(self, tmp_path: Path) -> None:
        c = tmp_path / "r.json"
        ecrit = ecrire_json(c, {"a": 1})
        assert ecrit == c
        assert json.loads(c.read_text(encoding="utf-8")) == {"a": 1}

    def test_n_ecrase_jamais(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        c = tmp_path / "r.json"
        c.write_text(json.dumps({"reference": "8,26 Mo"}), encoding="utf-8")
        ecrit = ecrire_json(c, {"neuf": True})
        assert ecrit != c
        # 🔒 LE POINT ENTIER : la reference est intacte
        assert json.loads(c.read_text(encoding="utf-8")) == {"reference": "8,26 Mo"}
        assert json.loads(ecrit.read_text(encoding="utf-8")) == {"neuf": True}
        # 🔒 et la collision est DITE, pas tue
        sortie = capsys.readouterr().out
        assert "EXISTE DEJA" in sortie
        assert "CONSERVE" in sortie

    def test_accents_preserves(self, tmp_path: Path) -> None:
        ecrit = ecrire_json(tmp_path / "r.json", {"verdict": "déposable"})
        assert "déposable" in ecrit.read_text(encoding="utf-8")
