"""PREFLIGHT -- run this BEFORE touching anything, and paste the whole output.

    python scripts\\preflight.py

Answers, in one command, the four questions of CLAUDE.md section 0, plus three
more that have each cost a session on this project. It prints one verdict line:

    PREFLIGHT=GO      -- the repository is in a known good state, work may start
    PREFLIGHT=STOP    -- something is wrong, DO NOT modify anything, report it

The checks are deliberately cheap. The test suite is NOT run here (it takes
~3 min); the caller runs it separately when the roadmap asks for it.

Read-only: this script writes nothing and changes nothing.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
# 🔴 There is NO hard-coded expected root, deliberately. A constant `C:\dev\gemini`
# lived here, was never read by any check, and pointed at a directory that no longer
# exists -- an inert filter, the failure mode this project fears most. Check 1 below
# asks the only question that matters and that survives a snapshot copy: does
# `import certus` resolve INSIDE the tree this script was launched from?

# Running `python scripts/preflight.py` puts `scripts/` on sys.path, not the repo
# root, so `import certus` would fail for a reason that has nothing to do with the
# repository being wrong. Put the root first.
sys.path.insert(0, str(ROOT))

#: The one interpreter version this project targets. A different patch level is not
#: fatal, but it invalidates the numba caches and can move the last digits of a
#: RESULT -- which would otherwise be blamed on whatever was edited last.
REFERENCE_PYTHON = "3.14.8"

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
    # In the check, not at the head: a diagnostic must survive a broken import and say so. Keyed by the sources (ETAT D49).
    from certus.core.certus_core import ensure_numba_cache_dir

    ensure_numba_cache_dir()
    import certus.physics.certus_opt_tmm as tmm_mod

    tmm_path = Path(tmm_mod.__file__).resolve()
except Exception as exc:  # any import failure is a stop
    tmm_path = None
    check("import certus.physics.certus_opt_tmm", False, f"FAILED: {exc}")
if tmm_path is not None:
    check(
        f"certus_opt_tmm resolves inside {ROOT}",
        ROOT in tmm_path.parents,
        str(tmm_path),
    )

# 2. Does committing PUBLISH? Under its short name the hook pushes to the PUBLIC
#    repository, and --no-verify does not stop it (it skips pre-commit and
#    commit-msg, never post-commit).
#
#    👤 asked for the push to be ARMED on 2026-08-14. So an armed hook is no longer a
#    failure -- it is the requested state, and this check REPORTS it instead of
#    refusing to work. What it must never do is stay silent: a commit that publishes
#    and a commit that does not look identical in the terminal.
print("\n2. POST-COMMIT HOOK -- does committing PUBLISH?")
# 🔴 CE CONTROLE A ETE FAUX ENTRE LE 2026-08-22 ET SA REPARATION LE MEME JOUR, ET IL ETAIT
# FAUX DANS LE SENS DANGEREUX. Il lisait `.git/hooks/post-commit` EN DUR. Or le hook a
# demenage dans `.githooks/` (versionne) le 2026-08-22, ou il s'arme par
# `git config core.hooksPath .githooks`. Sous cette configuration -- celle qui est VOULUE --
# il n'y a plus rien dans `.git/hooks/`, et le controle imprimait :
#
#     [OK ] post-commit is disabled: committing stays local (found: (none))
#
# alors que le commit suivant POUSSAIT vers le depot PUBLIC. Un [OK] qui affirme l'etat sur
# lequel repose « rien de personnel ne doit entrer dans l'index » (CLAUDE.md §2), pendant que
# l'etat inverse tient.
#
# 🔑 C'est la troisieme occurrence de la MEME faute dans ce fichier -- `EXPECTED_ROOT` au §2,
# le `.venv` code en dur au §3, et celle-ci : coder en dur un CHEMIN au lieu de demander sa
# valeur EFFECTIVE. La reparation ne recalcule donc pas la resolution de git, elle la lui
# DEMANDE : `git rev-parse --git-path hooks` rend `.githooks` quand `core.hooksPath` est pose
# et `.git/hooks` sinon.
_, hooks_dir_raw = run("git", "rev-parse", "--git-path", "hooks")
hooks = (ROOT / hooks_dir_raw) if hooks_dir_raw else (ROOT / ".git" / "hooks")
live_hook = hooks / "post-commit"
found = sorted(p.name for p in hooks.glob("post-commit*")) if hooks.is_dir() else []
_, remote = run("git", "remote", "get-url", "origin")
print(f"  [ i ] hooks effectifs: {hooks_dir_raw or '(inconnu)'} (found: {', '.join(found) or '(none)'})")
if live_hook.is_file():
    print(f"  [ ! ] post-commit is ARMED: every commit PUSHES to {remote or '(unknown remote)'}")
    warnings.append(
        f"post-commit ARMED -- committing publishes to {remote or 'origin'}. "
        "Nothing carrying a personal datum, a credential or a third party's work may be committed."
    )
else:
    print("  [OK ] post-commit is disabled: committing stays local")

# 2bis. The hook's STATE is not the danger -- UNPUSHED COMMITS are.
#
#    🔴 `.git/hooks/` is not versioned, so a hook armed on one machine does not travel to
#    another. Measured on 2026-08-22, when 👤 moved to a second machine mid-campaign: the
#    old machine pushed on every commit, the new one would not have, and NOTHING would have
#    said so. Commits pile up locally and the terminal looks identical.
#
#    🔑 So this check does not ask "is the hook there". It asks the question that actually
#    matters -- IS ANYTHING SITTING HERE THAT THE REMOTE HAS NOT GOT? That answer is true
#    whatever the hook does, and it is the one that loses work.
#
#    The versioned hook now lives in `.githooks/post-commit`; arming it takes one command,
#    `git config core.hooksPath .githooks`. Arming stays DELIBERATE because committing
#    publishes to a public repository (CLAUDE.md §2).
print("\n2bis. IS ANYTHING UNPUSHED?")
_, hooks_path = run("git", "config", "core.hooksPath")
print(f"  [ i ] core.hooksPath = {hooks_path or '(unset -> .git/hooks, NOT versioned)'}")
_, branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
code_ahead, ahead = run("git", "rev-list", "--count", f"origin/{branch}..HEAD")
if code_ahead != 0 or not ahead.isdigit():
    print(f"  [ ! ] cannot compare with origin/{branch} -- no upstream, or fetch never ran")
    warnings.append(
        f"origin/{branch} unreachable: preflight cannot tell whether work is unpushed. "
        "Run `git fetch origin` and look again."
    )
elif int(ahead) > 0:
    print(f"  [ ! ] {ahead} commit(s) HERE that origin/{branch} does NOT have")
    warnings.append(
        f"{ahead} unpushed commit(s) on {branch}. If this machine has no post-commit hook, "
        "they will stay local: `git push origin " + branch + "`."
    )
else:
    print(f"  [OK ] nothing unpushed -- local and origin/{branch} agree")

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
# 🔴 CE CONTROLE S'EST TROMPE TROIS FOIS, ET TOUJOURS DE LA MEME FACON.
#   1. il a exige `.venv` DANS le chemin -- ce qui supposait un venv dans le depot ;
#   2. puis un `pyvenv.cfg` a cote -- ce qui supposait qu'il y ait un venv DU TOUT ;
#   3. or la machine du 2026-09-08 n'en a aucun. Le projet tourne sur le Python
#      systeme, et ce controle avertissait donc EN PERMANENCE sur la seule
#      configuration qui existe.
#
# 🔑 Un avertissement permanent apprend a ignorer les avertissements -- c'est la regle
# que CLAUDE.md applique deja au mode FAST. Et la propriete cherchee n'a JAMAIS ete
# « est-ce un venv » : un venv n'etait qu'un PROXY de « cet interpreteur est equipe
# pour le projet ». On verifie donc l'equipement, qui est la vraie question, et qui
# reste vrai quel que soit l'endroit d'ou l'interpreteur est lance.
_REQUIRED = ("PyQt6", "numpy", "scipy", "numba")
_missing = [m for m in _REQUIRED if importlib.util.find_spec(m) is None]
check(
    "interpreter equipped for the project (" + ", ".join(_REQUIRED) + ")",
    not _missing,
    sys.executable if not _missing else f"{sys.executable}  ->  missing: {', '.join(_missing)}",
    fatal=False,
)
# 🔴 `find_spec` ne dit pas qu'un import REUSSIT. Le 2026-10-02 (ETAT D78), pydantic 2.14.0a1 exigeait
# pydantic-core 2.47.0 avec 2.49.0 installe : le module existait, sa garde de version levait `SystemError`
# a l'import, sept fenetres sur sept mouraient avant de s'afficher -- et ce script disait GO, car il
# n'importait que le calcul optique. On IMPORTE donc ce que l'interface importe, et l'exception dit pourquoi.
# `tests/unit/test_preflight_imports_the_runtime_dependencies.py` y met une dependance qui leve.
_RUNTIME_IMPORTS = (
    "pydantic",
    "PyQt6.QtWidgets",
    "pyqtgraph",
    "matplotlib",
    "pandas",
    "openpyxl",
    "xlsxwriter",
    "joblib",
)
_broken: list[str] = []
for _name in _RUNTIME_IMPORTS:
    try:
        importlib.import_module(_name)
    except Exception as exc:  # a version guard raises SystemError, which is not an ImportError
        _first_line = (str(exc).splitlines() or [""])[0][:300]
        _broken.append(f"{_name} -> {type(exc).__name__}: {_first_line}")
check(
    "runtime dependencies import (" + ", ".join(_RUNTIME_IMPORTS) + ")",
    not _broken,
    "all import"
    if not _broken
    else "; ".join(_broken) + "  [`python -m pip check`; pinned versions: requirements.lock]",
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
