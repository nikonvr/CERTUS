r"""Order the \bibitem entries of a LaTeX file by first citation (Optica numbers references in citation order).

usage: python reorder_bib.py MAIN.tex   (rewrites the file in place; prints the new order and any uncited entry)
"""

import re
import sys

path = sys.argv[1]
s = open(path, encoding="utf8").read()
start = s.index(r"\begin{thebibliography}")
head_end = s.index("\n", start) + 1
end = s.index(r"\end{thebibliography}")
body, bib = s[:start], s[head_end:end]

order = []
for m in re.finditer(r"\\cite\{([^}]*)\}", body):
    for k in (x.strip() for x in m.group(1).split(",")):
        if k not in order:
            order.append(k)

items = {}
for m in re.finditer(r"\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem\{|\Z)", bib, re.S):
    items[m.group(1)] = m.group(0).rstrip("\n") + "\n"
missing = [k for k in order if k not in items]
uncited = [k for k in items if k not in order]
if missing:
    sys.exit(f"cited but not in the bibliography: {missing}")
new = "".join(items[k] for k in order + uncited)
open(path, "w", encoding="utf8").write(s[:head_end] + new + s[end:])
print("order:", ", ".join(order))
print("uncited (kept at the end):", uncited or "none")
