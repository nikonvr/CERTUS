r"""Submission version of the method paper for Optics Express (2026-11-03, owner: chain everything). Optica asks for one
.tex file in standard LaTeX without custom macros, with the files at the root of the archive; its template is optional.
From OE_resonances/main.tex, in OE_resonances/submission/: the header of internal notes dropped (it names the other
paper and the likely referees), the draft date removed, \todo replaced by red text, the appendix table inlined, the
figures copied to the root with flat \includegraphics paths; compiled twice; main.tex and the figures zipped. The
working main.tex is left as it is.
usage: python make_submission.py OE_DIR
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PDFLATEX = r"C:\Users\Fabien\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
BS = chr(92)


def main() -> None:
    oe = Path(sys.argv[1])
    out = oe / "submission"
    out.mkdir(exist_ok=True)
    for old in out.iterdir():  # emptied, not removed: the folder may be open in Explorer or held by the Drive sync
        try:
            old.unlink()
        except PermissionError:
            print(f"locked, left in place: {old.name}")
    tex = (oe / "main.tex").read_text(encoding="utf-8")
    tex = tex[tex.index(BS + "documentclass"):]
    tex = re.sub(r"^\\newcommand\{\\todo\}.*\n", "", tex, flags=re.MULTILINE)
    tex = re.sub(r"\\todo\{([^{}]*)\}", lambda m: BS + "textcolor{red}{[" + m.group(1) + "]}", tex)
    tex = re.sub(r"^\\date\{.*\}\n", lambda _m: BS + "date{}\n", tex, flags=re.MULTILINE)
    app = (oe / "appendix_design.tex").read_text(encoding="utf-8")
    app = "".join(line for line in app.splitlines(keepends=True) if not line.lstrip().startswith("%"))
    tex = tex.replace(BS + "input{appendix_design.tex}", app.rstrip("\n"))
    figs = sorted(set(re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", tex)))
    for f in figs:
        shutil.copy(oe / f, out / Path(f).name)
        tex = tex.replace("{" + f + "}", "{" + Path(f).name + "}")
    left = [w for w in (BS + "todo", BS + "input", BS + "include{", "CERTUS", "RICL", "optimality paper") if w in tex]
    (out / "main.tex").write_text(tex, encoding="utf-8")
    for _ in range(2):
        subprocess.run([PDFLATEX, "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=out,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    log = (out / "main.log").read_text(encoding="latin-1")
    pages = re.search(r"Output written on main\.pdf \((\d+) pages", log)
    bad = re.findall(r"^(?:! .*|LaTeX Warning: (?:Reference|Citation).*|Overfull .*)$", log, flags=re.MULTILINE)
    name = "oe_submission_source.zip"
    with zipfile.ZipFile(out / name, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ["main.tex", *(Path(f).name for f in figs)]:
            z.write(out / f, f)
    print(f"{len(figs)} figures; {pages.group(1) if pages else '?'} pages; problems in the log: {bad or 'none'}; "
          f"internal words left: {left or 'none'}; archive {name}")


if __name__ == "__main__":
    main()
