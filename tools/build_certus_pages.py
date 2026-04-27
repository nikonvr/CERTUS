#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Régénère pages/CERTUS_*.html : <head> unifié (MathJax + Mermaid + assets partagés)
et corps <body> extrait de l'existant.

Usage (depuis la racine du projet) :
    python tools/build_certus_pages.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "pages"
ASSETS = PAGES / "assets"


def _ensure_shared_assets() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    design = PAGES / "CERTUS_DESIGN.html"
    if not design.is_file():
        raise SystemExit(f"Missing {design}")
    text = design.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", text, re.DOTALL)
    if not m:
        raise SystemExit("CERTUS_DESIGN.html: bloc <style> introuvable")
    css_path = ASSETS / "certus_report.css"
    css_path.write_text(m.group(1).strip() + "\n", encoding="utf-8")
    print(f"Wrote {css_path.relative_to(ROOT)}")


def _head_html(title: str) -> str:
    # MathJax avant le script async (recommandé)
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script>
        window.MathJax = {{
            tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']] }}
        }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script src="assets/certus_report_init.js"></script>
    <link rel="stylesheet" href="assets/certus_report.css">
    <style>
        .hidden { display: none !important; }
        #offline-banner { position: fixed; top: 0; left: 0; width: 100%; background: #fef3c7; border-bottom: 1px solid #fde68a; color: #92400e; padding: 8px; text-align: center; font-size: 14px; z-index: 9999; }
    </style>
</head>

<body>
<div id="offline-banner" class="hidden">
  ⚠️ Scientific formulas and diagrams may not render correctly without an internet connection (CDN-based assets).
</div>
<script>
  window.addEventListener('load', function() {
    if (typeof MathJax === 'undefined' || typeof mermaid === 'undefined') {
      document.getElementById('offline-banner').classList.remove('hidden');
    }
  });
</script>


def rebuild_page(html_path: Path) -> None:
    raw = html_path.read_text(encoding="utf-8")
    tm = re.search(r"<title>(.*?)</title>", raw, re.DOTALL | re.IGNORECASE)
    if not tm:
        raise SystemExit(f"{html_path.name}: <title> manquant")
    title = re.sub(r"\s+", " ", tm.group(1).strip())
    bm = re.search(r"<body[^>]*>(.*)</body>", raw, re.DOTALL | re.IGNORECASE)
    if not bm:
        raise SystemExit(f"{html_path.name}: <body> manquant")
    body_inner = bm.group(1).strip()
    out = _head_html(title) + body_inner + "\n\n</body>\n</html>\n"
    html_path.write_text(out, encoding="utf-8")
    print(f"Rebuilt {html_path.relative_to(ROOT)}")


def main() -> int:
    if not PAGES.is_dir():
        print("No pages/ directory", file=sys.stderr)
        return 1
    _ensure_shared_assets()
    init_js = ASSETS / "certus_report_init.js"
    if not init_js.is_file():
        print(f"Missing {init_js}", file=sys.stderr)
        return 1
    for html_path in sorted(PAGES.glob("CERTUS_*.html")):
        rebuild_page(html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
