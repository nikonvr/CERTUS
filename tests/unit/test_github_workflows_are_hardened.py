"""The workflows run with the least rights, on every branch, on actions that cannot move.

Measured on 2026-09-29, before this guard:
- `security.yml` ran on `["main", "master"]` only, and its cron runs on the default branch only:
  on the working branch, `refactor-corridors-mixins`, no dependency audit and no secret scan ever ran,
  while `lint` and `tests` (no branch filter, on purpose) ran on each push;
- no workflow but `security.yml` said what rights its token has, and `security-events: write` was
  given to the whole workflow, to the job that scans a lockfile as much as to the one that uploads
  CodeQL results;
- every action was named by a tag (`actions/checkout@v4`), which its maintainer can move: a third
  party's tag (`gitleaks/gitleaks-action@v2`, `astral-sh/setup-uv@v5`) changes what a job runs
  without any change of ours;
- `actions/checkout` left the token in `.git/config` of jobs that never push.

The files are read as text: PyYAML is not a dependency of the project, and what is checked (a line
of `uses:`, a top-level key) needs no parser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

#: The workflows that check every push: a branch list goes stale, "code was pushed" does not.
EVERY_BRANCH = ("lint.yml", "tests.yml", "security.yml")

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<action>[^\s@]+)@(?P<ref>\S+)(?P<comment>\s+#.*)?$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _uses(path: Path) -> list[re.Match]:
    return [m for line in _text(path).splitlines() if (m := USES.match(line))]


def test_the_workflows_are_found() -> None:
    """Negative control: with none found, every test below would pass for nothing."""
    assert {p.name for p in WORKFLOWS} >= {"lint.yml", "tests.yml", "security.yml", "release-windows.yml"}
    assert sum(len(_uses(p)) for p in WORKFLOWS) >= 10


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit(path) -> None:
    for match in _uses(path):
        assert SHA.match(match["ref"]), f"{path.name}: {match['action']}@{match['ref']} is a tag, not a commit"
        assert match["comment"], (f"{path.name}: {match['action']} is pinned but does not say which release: "
            "Dependabot and the reader need `# vX.Y.Z`")
        assert re.search(r"#\s*v\d", match["comment"]), (f"{path.name}: {match['action']} is pinned but does not say which release: "
            "Dependabot and the reader need `# vX.Y.Z`")


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_says_what_rights_its_token_has(path) -> None:
    text = _text(path)

    assert re.search(r"^permissions:\n  contents: read$", text, flags=re.MULTILINE), (
        f"{path.name} has no top-level `permissions: contents: read`"
    )
    # No write right for the whole workflow: it goes to the job that needs it.
    top_level = text.split("\njobs:\n", 1)[0]
    assert "write" not in top_level.split("permissions:", 1)[1], f"{path.name} gives a write right to every job"


def test_the_codeql_upload_is_the_only_job_that_writes() -> None:
    text = _text(ROOT / ".github" / "workflows" / "security.yml")
    jobs = text.split("\njobs:\n", 1)[1]
    scan, codeql = jobs.split("\n  codeql:\n", 1)

    assert "write" not in scan
    assert "security-events: write" in codeql


@pytest.mark.parametrize("name", EVERY_BRANCH)
def test_the_checks_run_on_every_branch(name) -> None:
    triggers = _text(ROOT / ".github" / "workflows" / name).split("\njobs:\n", 1)[0].split("\non:\n", 1)[1]
    triggers = triggers.split("\npermissions:", 1)[0]

    assert re.search(r"^  push:\s*$", triggers, flags=re.MULTILINE), f"{name} does not run on push"
    assert re.search(r"^  pull_request:\s*$", triggers, flags=re.MULTILINE), f"{name} does not run on pull requests"
    assert "branches:" not in triggers, f"{name} lists branches: a list goes stale"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_checkout_does_not_keep_the_token(path) -> None:
    text = _text(path)
    checkouts = [m for m in _uses(path) if m["action"] == "actions/checkout"]

    assert checkouts, f"{path.name} has no checkout: the count below would prove nothing"
    assert text.count("persist-credentials: false") == len(checkouts)


def test_the_secret_scan_can_see_the_commits_it_scans() -> None:
    """gitleaks reads `first^..last` of a push; a depth-1 checkout has no such range.

    Measured 2026-09-30, on the first push of this branch (53 commits): the step failed with
    `unknown revision 2727bc0^..78fda46` after scanning ~0 bytes ("no leaks found in partial scan"). A check
    that fails before it reads anything proves nothing, and a red workflow nobody believes ends up unread.
    """
    text = _text(ROOT / ".github" / "workflows" / "security.yml")
    scan = text.split("\njobs:\n", 1)[1].split("\n  codeql:\n", 1)[0]
    checkout = scan.split("- name: Checkout", 1)[1].split("- name:", 1)[0]

    assert "gitleaks/gitleaks-action" in scan
    assert re.search(r"^\s+fetch-depth: 0\s*$", checkout, flags=re.MULTILINE)


def test_dependabot_keeps_the_pinned_actions_up_to_date() -> None:
    config = _text(ROOT / ".github" / "dependabot.yml")

    assert 'package-ecosystem: "github-actions"' in config
    assert 'directory: "/"' in config
