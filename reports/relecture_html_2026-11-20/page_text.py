"""Print the visible text of one guide of pages/, from a marker, for reading (review of 2026-11-20).

    python reports/relecture_html_2026-11-20/page_text.py PAGE.html [start-marker] [max-chars]
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
        elif tag == "div" and (self.skip or ("class", "mermaid") in attrs):
            self.skip += 1  # a Mermaid diagram, and every div nested in it, is code, not prose
        if tag in ("p", "li", "tr", "h1", "h2", "h3", "h4", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "div") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


parser = Text()
parser.feed((ROOT / "pages" / sys.argv[1]).read_text(encoding="utf-8"))
text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
text = re.sub(r"\n\s*\n+", "\n", text)
start = text.find(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else 0
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 12000
sys.stdout.reconfigure(encoding="utf-8")
print(text[max(0, start):max(0, start) + limit])
