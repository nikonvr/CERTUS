from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_pyproject_dependencies(pyproject_path: Path) -> set[str]:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(
        r"^\[project\]\s.*?^dependencies\s*=\s*\[(.*?)^\]\s*$",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("Impossible de lire [project].dependencies dans pyproject.toml")
    block = match.group(1)
    names: set[str] = set()
    for raw_line in block.splitlines():
        line = raw_line.strip().strip(",").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith('"') and line.endswith('"'):
            spec = line[1:-1]
        else:
            spec = line
        pkg = re.split(r"[<>=!~;\[\s]", spec, maxsplit=1)[0].strip()
        if pkg:
            names.add(pkg.lower())
    return names


def _parse_lock_requirements(lock_path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==", 1)[0].strip()
        if pkg:
            names.add(pkg.lower())
    return names


def check_lock_is_strictly_pinned() -> list[str]:
    lockfile = REPO_ROOT / "requirements.lock"
    if not lockfile.exists():
        return [f"Fichier manquant: {lockfile.name}"]
    errors: list[str] = []
    for idx, raw_line in enumerate(lockfile.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            errors.append(
                f"requirements.lock:{idx} non figé strictement (attendu 'package==version'): {line}"
            )
            continue
        pkg, ver = line.split("==", 1)
        if not pkg.strip() or not ver.strip():
            errors.append(f"requirements.lock:{idx} entrée lock invalide: {line}")
    return errors


def check_lock_consistency() -> list[str]:
    pyproject = REPO_ROOT / "pyproject.toml"
    lockfile = REPO_ROOT / "requirements.lock"
    if not pyproject.exists():
        return [f"Fichier manquant: {pyproject.name}"]
    if not lockfile.exists():
        return [f"Fichier manquant: {lockfile.name}"]

    pyproject_deps = _parse_pyproject_dependencies(pyproject)
    lock_deps = _parse_lock_requirements(lockfile)
    missing = sorted(dep for dep in pyproject_deps if dep not in lock_deps)
    errors: list[str] = []
    if missing:
        errors.append(
            "Dépendances pyproject absentes du lockfile: " + ", ".join(missing)
        )
    return errors


def check_frozen_artifact() -> list[str]:
    exe = REPO_ROOT / "dist" / "CERTUS_HUB.exe"
    errors: list[str] = []
    if not exe.exists():
        errors.append("Artefact frozen manquant: dist/CERTUS_HUB.exe")
        return errors
    size = exe.stat().st_size
    if size < 5_000_000:
        errors.append(
            f"Artefact frozen trop petit ({size} octets) - build potentiellement incomplet"
        )
    if size > 500_000_000:
        errors.append(
            f"Artefact frozen anormalement volumineux ({size} octets)"
        )
    try:
        data = exe.read_bytes()
        if len(data) < 64 or data[:2] != b"MZ":
            errors.append("Artefact frozen invalide: signature DOS/PE absente (MZ)")
        else:
            pe_off = int.from_bytes(data[0x3C:0x40], "little")
            if pe_off + 4 > len(data) or data[pe_off:pe_off + 4] != b"PE\x00\x00":
                errors.append("Artefact frozen invalide: en-tête PE non trouvé")
    except OSError as exc:
        errors.append(f"Impossible de lire l'artefact frozen: {exc}")
    return errors


def check_frozen_functional_startup(timeout_sec: int = 12) -> list[str]:
    exe = REPO_ROOT / "dist" / "CERTUS_HUB.exe"
    if not exe.exists():
        return ["Artefact frozen manquant: dist/CERTUS_HUB.exe"]

    errors: list[str] = []
    full_env = os.environ.copy()
    full_env["QT_QPA_PLATFORM"] = "offscreen"

    proc = subprocess.Popen([str(exe)], env=full_env)
    start = time.time()
    try:
        while (time.time() - start) < float(timeout_sec):
            code = proc.poll()
            if code is None:
                time.sleep(0.5)
                continue
            if code != 0:
                errors.append(
                    f"Executable frozen s'arrête trop tôt avec code non nul: {code}"
                )
            # If code == 0 quickly, still suspicious for GUI app startup.
            if code == 0 and (time.time() - start) < 2.0:
                errors.append(
                    "Executable frozen termine immédiatement (<2s), démarrage suspect"
                )
            return errors
        # Process stayed up long enough: startup considered healthy.
        return errors
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def check_release_structure() -> list[str]:
    errors: list[str] = []

    workflow = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"
    if not workflow.exists():
        return ["Workflow manquant: .github/workflows/release-windows.yml"]
    wf_text = workflow.read_text(encoding="utf-8")
    required_tokens = [
        "python-version: [ \"3.10\", \"3.11\", \"3.12\" ]",
        "python tools/release_checks.py",
        "python tools/release_checks.py --check-frozen",
        "python tools/release_checks.py --check-frozen-run",
        "./tools/smoke_release.ps1",
        "./tools/build_frozen.ps1",
        "actions/upload-artifact@v4",
        "tests/unit/test_release_guardrails.py",
    ]
    for token in required_tokens:
        if token not in wf_text:
            errors.append(f"Workflow release incomplet (token absent): {token}")

    smoke_script = REPO_ROOT / "tools" / "smoke_release.ps1"
    if not smoke_script.exists():
        errors.append("Script manquant: tools/smoke_release.ps1")
    else:
        smoke_text = smoke_script.read_text(encoding="utf-8")
        if "QT_QPA_PLATFORM" not in smoke_text or "offscreen" not in smoke_text:
            errors.append(
                "Smoke script non conforme: QT_QPA_PLATFORM=offscreen requis"
            )

    spec_file = REPO_ROOT / "certus_hub.spec"
    if not spec_file.exists():
        errors.append("Spec manquant: certus_hub.spec")
    else:
        spec_text = spec_file.read_text(encoding="utf-8")
        for token in ("CERTUS_HUB.py", 'name="CERTUS_HUB"', 'icon="certus.ico"'):
            if token not in spec_text:
                errors.append(f"Spec frozen incomplet (token absent): {token}")

    for asset in ("certus.ico", "certus.svg"):
        if not (REPO_ROOT / asset).exists():
            errors.append(f"Asset release manquant: {asset}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Release checks for CERTUS CI")
    parser.add_argument(
        "--check-frozen",
        action="store_true",
        help="Vérifie la présence/qualité de l'artefact frozen.",
    )
    parser.add_argument(
        "--check-frozen-run",
        action="store_true",
        help="Vérifie un démarrage fonctionnel minimal de l'exécutable frozen.",
    )
    parser.add_argument(
        "--startup-timeout-sec",
        type=int,
        default=12,
        help="Timeout (secondes) pour le check de démarrage frozen.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    failures.extend(check_lock_consistency())
    failures.extend(check_lock_is_strictly_pinned())
    failures.extend(check_release_structure())
    if args.check_frozen:
        failures.extend(check_frozen_artifact())
    if args.check_frozen_run:
        failures.extend(
            check_frozen_functional_startup(timeout_sec=int(args.startup_timeout_sec))
        )

    if failures:
        print("[CERTUS] release checks FAILED")
        for item in failures:
            print(f"- {item}")
        return 1

    print("[CERTUS] release checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
