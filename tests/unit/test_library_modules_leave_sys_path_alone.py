"""Importing a module of the certus package does not put its folder on sys.path.

Nine library modules call create_module_environment(__file__, ...), and bootstrap_app used to
insert the folder of that file at the front of sys.path: certus/core, certus/ui, certus/utils,
certus/spline. Each neighbour in those folders became importable a second time under its bare
name, as a separate module object: depending on the order of the imports, `import
certus_curve_smoother` loaded certus/utils/certus_curve_smoother.py instead of the entry script
at the root. An application script still puts its own folder, the root, on sys.path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "certus"
LIBRARY_IMPORTS = (
    "import certus.core.certus_index_core, certus.utils.certus_re_helpers, certus.spline.certus_index_spline_core\n"
)


def _run(code: str) -> str:
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout


def _inside_the_package(lines: list[str]) -> list[str]:
    return [p for p in lines if p and Path(p).resolve().is_relative_to(PACKAGE)]


def test_library_modules_put_no_package_folder_on_sys_path() -> None:
    stdout = _run("import sys\n" + LIBRARY_IMPORTS + "print('\\n'.join(sys.path))\n")
    assert _inside_the_package(stdout.splitlines()) == []


def test_no_module_of_the_package_is_importable_by_its_bare_name() -> None:
    """The consequence: `import certus_index_core` found certus/core/certus_index_core.py."""
    stdout = _run(
        "import importlib.util, pathlib\n"
        + LIBRARY_IMPORTS
        + "for sub in ('core', 'ui', 'utils', 'spline'):\n"
        "    for f in sorted(pathlib.Path('certus', sub).glob('*.py')):\n"
        "        spec = importlib.util.find_spec(f.stem)\n"
        "        if spec is not None and spec.origin:\n"
        "            print(spec.origin)\n"
    )
    inside = _inside_the_package(stdout.splitlines())
    assert inside == [], f"{len(inside)} modules of the package importable by their bare name, e.g. {inside[:3]}"
