"""PREFLIGHT -- run this BEFORE touching anything, and paste the whole output.

    .venv\\Scripts\\python.exe scripts\\preflight.py

Answers, in one command, the four questions of CLAUDE.md section 0, plus three
more that have each cost a session on this project. It prints one verdict line:

    PREFLIGHT=GO      -- the repository is in a known good state, work may start
    PREFLIGHT=STOP    -- something is wrong, DO NOT modify anything, report it

The checks are deliberately cheap. The test suite is NOT run here (it takes
~3 min); the caller runs it separately when the roadmap asks for it.

Read-only: this script writes nothing and changes nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT = Path(r"C:\dev\gemini")

# Running `python scripts/preflight.py` puts `scripts/` on sys.path, not the repo
# root, so `import certus` would fail for a reason that has nothing to do with the
# repository being wrong. Put the root first.
sys.path.insert(0, str(ROOT))

#: The one interpreter version this project targets. A different patch level is not
#: fatal, but it invalidates the numba caches and can move the last digits of a
#: RESULT -- which would otherwise be blamed on whatever was edited last.
REFERENCE_PYTHON = "3.14.7"

#: Files whose modification invalidates every subsequent measurement.
#: CLAUDE.md forbid 4: the example file drifted four times, always permissively.
SACRED_FILES = (
    "example/example_strat/JSON-strat-example.json",
    "pyproject.toml",
)

failures: list[str] = []
warnings: list[str] = []


def run(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check(label: str, ok: bool, detail: str, fatal: bool = True) -> None:
    print(f"  [{'OK ' if ok else 'BAD'}] {label}: {detail}")
    if not ok:
        (failures if fatal else warnings).append(f"{label}: {detail}")


print("=" * 72)
print("PREFLIGHT -- CERTUS")
print("=" * 72)

# 1. The right copy of the repository. Several coexist on this machine, and
#    editing one while measuring another produces no error message at all.
print("\n1. WORKING DIRECTORY")
try:
    import certus.physics.certus_opt_tmm as tmm_mod

    tmm_path = Path(tmm_mod.__file__).resolve()
except Exception as exc:  # noqa: BLE001 -- any import failure is a stop
    tmm_path = None
    check("import certus.physics.certus_opt_tmm", False, f"FAILED: {exc}")
if tmm_path is not None:
    check(
        "certus_opt_tmm resolves inside C:\\dev\\gemini",
        EXPECTED_ROOT in tmm_path.parents,
        str(tmm_path),
    )

# 2. Committing here must not publish. Under its short name the hook pushes to
#    the PUBLIC repository, and --no-verify does not stop it.
print("\n2. POST-COMMIT HOOK")
hooks = ROOT / ".git" / "hooks"
live_hook = hooks / "post-commit"
disabled = sorted(p.name for p in hooks.glob("post-commit*")) if hooks.is_dir() else []
check(
    "post-commit is DISABLED",
    not live_hook.exists(),
    f"found: {', '.join(disabled) if disabled else '(none)'}",
)

# 3. Python version. PEP 758 `except A, B:` is used in 14 modules and is a
#    syntax error before 3.14.
print("\n3. INTERPRETER")
version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
check("python >= 3.14 (PEP 758 syntax)", sys.version_info >= (3, 14), version)
check(
    f"python is the reference {REFERENCE_PYTHON}",
    version == REFERENCE_PYTHON,
    version if version == REFERENCE_PYTHON
    else f"{version} -- reference measurements were taken under {REFERENCE_PYTHON}; "
         "numba caches are invalidated and the last digits of a RESULT may move. "
         "Record this version next to any number you report.",
    fatal=False,
)
check(
    "running the venv interpreter",
    "\\.venv\\" in sys.executable or "/.venv/" in sys.executable,
    sys.executable,
    fatal=False,
)

# 4. Lint must already be clean, otherwise a later failure cannot be attributed.
print("\n4. LINT")
code, out = run(sys.executable, "-m", "ruff", "check", ".")
check("ruff check .", out.strip().endswith("All checks passed!"), out.splitlines()[-1] if out else "(no output)")

# 5. Sacred files untouched.
print("\n5. FILES THAT MUST NOT BE MODIFIED")
code, out = run("git", "status", "--porcelain")
dirty = {line[3:].strip().strip('"') for line in out.splitlines() if line.strip()}
for sacred in SACRED_FILES:
    check(f"{sacred} unmodified", sacred not in dirty, "clean" if sacred not in dirty else "MODIFIED")

# 6. The baseline tag must still exist, or nobody can separate one session's
#    work from what existed before it.
print("\n6. BASELINE TAG")
code, out = run("git", "log", "--oneline", "-1", "depart-gemini")
check("tag depart-gemini exists", code == 0, out.splitlines()[0] if out else "unknown revision")

# 7. A dirty tree before starting means an unfinished action is in the way.
print("\n7. WORKING TREE")
code, out = run("git", "status", "--porcelain", "--untracked-files=no")
n_dirty = len([ln for ln in out.splitlines() if ln.strip()])
check(
    "no uncommitted change to tracked files",
    n_dirty == 0,
    "clean" if n_dirty == 0 else f"{n_dirty} modified file(s) -- finish or revert the action in progress",
    fatal=False,
)

code, out = run("git", "rev-parse", "--abbrev-ref", "HEAD")
print(f"  [   ] branch: {out}")
code, out = run("git", "log", "--oneline", "-1")
print(f"  [   ] HEAD: {out}")

print("\n" + "=" * 72)
for w in warnings:
    print(f"WARNING  {w}")
if failures:
    for f in failures:
        print(f"BLOCKING {f}")
    print("\nPREFLIGHT=STOP")
    print("Do NOT modify anything. Paste this output and report it as-is.")
    raise SystemExit(1)
print("\nPREFLIGHT=GO")
raise SystemExit(0)
