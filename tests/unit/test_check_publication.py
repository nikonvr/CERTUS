"""Chantier 37: `scripts/check_publication.py` stops a push that carries a secret or a foreign author.

The seeded secrets are assembled at run time: a literal one in this file would itself be a secret in the index.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_publication.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "CERTUS")
    _git(repo, "config", "user.email", "certus@example.invalid")
    (repo / "a.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "tag", "base")
    return repo


def _commit(repo: Path, name: str, content: bytes) -> None:
    (repo / name).write_bytes(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--range", "base..HEAD"], cwd=repo, capture_output=True,
                          text=True, check=False)


def _xlsx(creator: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("docProps/core.xml", f"<cp:coreProperties><dc:creator>{creator}</dc:creator>"
                                              "</cp:coreProperties>")
    return buffer.getvalue()


def test_a_clean_range_goes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "b.py", b"x = 1\n")
    result = _run(repo)
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip().endswith("PUBLICATION=GO")


def test_a_seeded_token_stops_the_push(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    token = "gh" + "p_" + "A1b2C3d4" * 5
    _commit(repo, "conf.py", f"TOKEN = '{token}'\n".encode())
    result = _run(repo)
    assert result.returncode == 1
    assert "SECRET" in result.stdout
    assert "GitHub token" in result.stdout


def test_a_secret_removed_by_a_later_commit_still_stops_the_push(tmp_path: Path) -> None:
    """Every pushed commit is public, not only the final tree."""
    repo = _repo(tmp_path)
    _commit(repo, "conf.py", ("pass" + "word = '" + "hunter2hunter2" + "'\n").encode())
    _commit(repo, "conf.py", b"password = None\n")
    result = _run(repo)
    assert result.returncode == 1
    assert "password literal" in result.stdout


def test_a_workbook_by_someone_else_stops_the_push(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "data.xlsx", _xlsx("Someone Else"))
    result = _run(repo)
    assert result.returncode == 1
    assert "META" in result.stdout


def test_a_workbook_by_certus_goes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "data.xlsx", _xlsx("CERTUS"))
    assert _run(repo).returncode == 0


def test_a_pdf_is_listed_for_review_without_failing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "paper.pdf", b"%PDF-1.4\n")
    result = _run(repo)
    assert result.returncode == 0
    assert "REVIEW" in result.stdout
