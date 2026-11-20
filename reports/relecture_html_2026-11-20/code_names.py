"""Which code identifiers quoted in <code> by the guides of pages/ no longer exist in the sources? (review 2026-11-20)

An identifier is a snake_case name with at least one underscore, or a CamelCase name, or a file name (*.py, *.json);
it is looked up as a whole word in the tracked Python, JSON and spec files (git grep -w). Prints the missing ones per page.

    python reports/relecture_html_2026-11-20/code_names.py
"""
from __future__ import annotations

import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Codes(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "code":
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "code":
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.depth:
            self.found.append(data)


NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+|[\w./-]+\.(?:py|json)")
cache: dict[str, bool] = {}


def exists(name: str) -> bool:
    if name not in cache:
        base = Path(name).name if name.endswith((".py", ".json")) else name
        if name.endswith((".py", ".json")):
            out = subprocess.run(["git", "ls-files", f"*{base}"], cwd=ROOT, capture_output=True, text=True).stdout
            cache[name] = bool(out.strip())
        else:
            proc = subprocess.run(["git", "grep", "-q", "-w", "-F", name, "--", "*.py", "*.json", "*.spec"],
                                  cwd=ROOT, capture_output=True)
            cache[name] = proc.returncode == 0
    return cache[name]


for page in sorted((ROOT / "pages").glob("*.html")):
    parser = Codes()
    parser.feed(page.read_text(encoding="utf-8"))
    names = sorted({m.group(0).strip("./") for chunk in parser.found for m in NAME.finditer(chunk)})
    missing = [n for n in names if len(n) > 3 and not exists(n)]
    print(f"{page.name}: {len(names)} names, {len(missing)} missing: {missing}")
