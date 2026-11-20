"""Print the visible-text context of a regex in the pages of pages/ (review of 2026-11-20).

    python reports/relecture_html_2026-11-20/contexts.py "REGEX" [page-glob] [width]
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def visible(path: Path) -> str:
    parser = Text()
    parser.feed(path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", " ".join(parser.parts))


pattern = re.compile(sys.argv[1], flags=re.IGNORECASE)
glob = sys.argv[2] if len(sys.argv) > 2 else "*.html"
width = int(sys.argv[3]) if len(sys.argv) > 3 else 70
for page in sorted((ROOT / "pages").glob(glob)):
    text = visible(page)
    for m in pattern.finditer(text):
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        print(f"{page.name}: …{text[a:b]}…")
