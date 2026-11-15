"""Check the commits about to be pushed before they become public (chantier 37).

    python scripts\\check_publication.py                    # @{upstream}..HEAD, else origin/master..HEAD
    python scripts\\check_publication.py --range A..B

The repository is public: every commit pushed is published, intermediate ones included. This script reads each
commit of the range, not only the final tree, and checks three things:

* SECRET   an added line that looks like a key, a token, a private key or a password literal  -> fails;
* META     an Office file (xlsx, xlsm, docx, pptx) whose author fields name someone outside the allow list
           (CERTUS, openpyxl, `git config user.name`, and the comma-separated CERTUS_PUBLISH_ALLOW) -> fails;
* REVIEW   an added document that may be a third party's work (pdf, epub, djvu, audio, video), or a commit
           whose author is outside the allow list -> listed for a human, does not fail.

Exit code 0 when nothing fails, 1 otherwise; the last line is PUBLICATION=GO or PUBLICATION=STOP.
The patterns are assembled at run time so that this file does not match itself.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import zipfile

_B = "-----BEGIN "
SECRET_PATTERNS = {
    "private key": re.compile(re.escape(_B) + r"(?:[A-Z]+ )?PRIVATE KEY-----"),
    "AWS key": re.compile("AK" + r"IA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Google key": re.compile("AI" + r"za[0-9A-Za-z_\-]{35}"),
    "API key sk-": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"),
    "password literal": re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*"
        r"[\"'][^\"'\s]{8,}[\"']"
    ),
}
OFFICE = re.compile(r"\.(?:xlsx|xlsm|docx|pptx)$", re.IGNORECASE)
THIRD_PARTY = re.compile(r"\.(?:pdf|epub|djvu|mobi|mp3|flac|wav|mp4|mkv|avi)$", re.IGNORECASE)
AUTHOR_TAGS = (("docProps/core.xml", "dc:creator"), ("docProps/core.xml", "cp:lastModifiedBy"),
               ("docProps/app.xml", "Company"), ("docProps/app.xml", "Manager"))


def git(*args: str, binary: bool = False):
    out = subprocess.run(["git", *args], capture_output=True, check=True).stdout
    return out if binary else out.decode("utf-8", "replace")


def default_range() -> str:
    for base in ("@{upstream}", "origin/master"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", base], capture_output=True).returncode == 0:
            return f"{base}..HEAD"
    raise SystemExit("no upstream and no origin/master: pass --range")


def allow_list() -> set[str]:
    names = {"CERTUS", "openpyxl", ""}
    user = subprocess.run(["git", "config", "--get", "user.name"], capture_output=True, text=True).stdout.strip()
    names.add(user)
    names.update(n.strip() for n in os.environ.get("CERTUS_PUBLISH_ALLOW", "").split(",") if n.strip())
    return names


def secrets_in_patch(patch: str) -> list[tuple[str, str, str]]:
    """(file, kind, line) for each added line matching a secret pattern."""
    found, current = [], "?"
    for line in patch.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and not line.startswith("+++"):
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    found.append((current, kind, line[1:].strip()[:80]))
    return found


def office_authors(blob: bytes) -> list[str]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return []
    names = archive.namelist()
    values = []
    for part, tag in AUTHOR_TAGS:
        if part in names:
            text = archive.read(part).decode("utf-8", "replace")
            values += [m.strip() for m in re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)]
    return values


def check(commit_range: str) -> tuple[list[str], list[str]]:
    allowed = allow_list()
    failures, reviews = [], []
    for sha in git("rev-list", "--reverse", commit_range).split():
        short = sha[:8]
        author = git("show", "-s", "--format=%an", sha).strip()
        if author not in allowed:
            reviews.append(f"REVIEW {short} commit author {author!r}")
        patch = git("show", "--format=", "--no-color", "--unified=0", "--no-ext-diff", sha)
        failures += [f"SECRET {short} {f}: {kind}: {text}" for f, kind, text in secrets_in_patch(patch)]
        for path in git("diff-tree", "--no-commit-id", "-r", "--root", "--name-only", "--diff-filter=ACMR",
                        sha).split("\n"):
            if OFFICE.search(path):
                foreign = sorted({v for v in office_authors(git("show", f"{sha}:{path}", binary=True))
                                  if v not in allowed})
                if foreign:
                    failures.append(f"META {short} {path}: authors {foreign}")
            elif THIRD_PARTY.search(path):
                reviews.append(f"REVIEW {short} {path}: may be a third party's work")
    return failures, reviews


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--range", dest="commit_range", help="git revision range, default @{upstream}..HEAD")
    args = parser.parse_args(argv)
    commit_range = args.commit_range or default_range()
    failures, reviews = check(commit_range)
    count = len(git("rev-list", commit_range).split())
    for line in failures + reviews:
        print(line)
    print(f"RANGE={commit_range} COMMITS={count} FAILURES={len(failures)} REVIEWS={len(reviews)}")
    print("PUBLICATION=" + ("STOP" if failures else "GO"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
