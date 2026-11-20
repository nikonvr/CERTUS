"""Mechanical audit of the 15 HTML guides of pages/ (review of 2026-11-20).

Per page: duplicate ids, internal anchors without target, images without alt, heading-level jumps, empty links,
`lang` attribute, repeated words ("de de"), leftover markers (TODO, FIXME, XXX, ???), runs of double spaces in text,
and the visible text size. Standard library only.

    python reports/relecture_html_2026-11-20/audit_html.py
"""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = sorted((ROOT / "pages").glob("*.html"))
VOID = {"br", "img", "hr", "meta", "link", "input", "col", "area", "base", "source", "wbr", "embed", "param", "track"}


class Audit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.img_no_alt = 0
        self.headings: list[int] = []
        self.empty_links = 0
        self.lang = None
        self.text: list[str] = []
        self.skip = 0
        self.stack: list[str] = []
        self.mismatch: list[str] = []
        self._in_a = False
        self._a_text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a":
            self._in_a, self._a_text = True, ""
            if a.get("href"):
                self.hrefs.append(a["href"])
        if tag == "img" and not a.get("alt"):
            self.img_no_alt += 1
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag in ("script", "style"):
            self.skip += 1
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            self._in_a = False
            if not self._a_text.strip():
                self.empty_links += 1
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in VOID:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.mismatch.append(self.stack.pop())
            self.stack.pop()
        else:
            self.mismatch.append("/" + tag)

    def handle_data(self, data):
        if self._in_a:
            self._a_text += data
        if not self.skip:
            self.text.append(data)


print("page | Ko texte | ids doublés | ancres sans cible | img sans alt | sauts de titre | liens vides | lang | "
      "balises mal fermées | mots répétés | marqueurs")
for page in PAGES:
    audit = Audit()
    audit.feed(page.read_text(encoding="utf-8"))
    ids = Counter(audit.ids)
    dup = [i for i, n in ids.items() if n > 1]
    anchors = [h[1:] for h in audit.hrefs if h.startswith("#")]
    missing = sorted({x for x in anchors if x and x not in ids})
    jumps = sum(1 for a, b in zip(audit.headings, audit.headings[1:], strict=False) if b > a + 1)
    text = " ".join(audit.text)
    words = re.findall(r"\b(\w+)\s+\1\b", text, flags=re.IGNORECASE)
    repeated = [w for w in words if not w.isdigit() and w.lower() not in {"nous", "vous"}]
    markers = re.findall(r"\b(TODO|FIXME|XXX)\b|\?\?\?", text)
    unclosed = [t for t in audit.mismatch + audit.stack if t not in ("p", "li", "html", "body", "head", "/p")]
    print(f"{page.name} | {len(text) // 1024} | {dup[:4]} | {missing[:6]} | {audit.img_no_alt} | {jumps} | "
          f"{audit.empty_links} | {audit.lang} | {unclosed[:5]} | {repeated[:6]} | {markers[:3]}")
