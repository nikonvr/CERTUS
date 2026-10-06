# Third-party notices

> **Draft of 2026-10-06, for the owner to review.** Items marked « à confirmer par toi » are those whose source or
> licence the repository does not establish; the marker goes once the item is settled.

CERTUS is licensed under the GPL-3.0-only ([`LICENSE`](LICENSE)). This file lists what the repository and the frozen
executable redistribute that is the work of others. The licence of a third-party item keeps applying to it: the
GPL-3.0 does not replace it.

## 1. Icons: Lucide and Feather

`certus/ui/certus_icons.py` carries the SVG path data of 44 icons, which its comment attributes to the Lucide icon set
(ISC). Lucide declares part of its set derived from Feather (MIT), so both notices apply.

```text
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

```text
The MIT License (MIT)

Copyright (c) 2013-2023 Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 2. Published optical data

Measured values from the literature and from manufacturers, reproduced for computation and cited here.

| data | where | source |
|---|---|---|
| fused silica, Sellmeier | `certus/core/certus_substrate_db.py`, `data/materials_v1.json` | I. H. Malitson, *J. Opt. Soc. Am.* 55, 1205 (1965) |
| N-BK7, Sellmeier | same | SCHOTT Zemax catalogue 2017-01-20b |
| D263T eco, Sellmeier | same | SCHOTT Zemax catalogue 2017-01-20b (D263TECO) |
| sapphire, ordinary ray, Sellmeier | same | I. H. Malitson and M. J. Dodge, *J. Opt. Soc. Am.* 62, 1405 (1972); formula in M. J. Dodge, *Handbook of Laser Science and Technology* IV, CRC Press (1986) |
| B270i, Sellmeier | same | B1 and C1 fitted to the line indices of the SCHOTT B 270 i data sheet; the other four terms: « à confirmer par toi » |
| silicon, n and k, 200–5200 nm | `example/database_index/indices.xlsx`, sheet `Si-substrate` | from 1200 nm on, the Sellmeier formula of C. D. Salzberg and J. J. Villa, *J. Opt. Soc. Am.* 47, 244 (1957), within 5e-5; below 1200 nm: « à confirmer par toi » |
| silicon, 15-point fallback | `certus_physics/materials_data.py` | same Salzberg and Villa formula from 1200 nm on; a rough placeholder below |
| CIE 1931 2° colour-matching functions, illuminant D65 | `certus/physics/certus_colorimetry.py` | CIE (ISO/CIE 11664-1 and 11664-2); licence of the CIE tables: « à confirmer par toi » |
| Cauchy presets | `data/materials_v1.json` | « à confirmer par toi » |
| sapphire index table | `example/database_index/sapphire_index.txt` and its copy in `example/example_index/` | « à confirmer par toi »: it follows neither ray of Malitson and Dodge (up to 1.6e-2 from the ordinary, 1.1e-2 from the extraordinary) |

## 3. In the frozen executable

The executable that the `release-windows` workflow builds from `requirements.lock` bundles, besides CERTUS, the
Python runtime and the runtime dependencies of `pyproject.toml` with theirs. Licences as each distribution declares
them (read from the installed metadata on 2026-10-06); the full texts are in each project's distribution.

| component | declared licence |
|---|---|
| Python runtime and standard library | PSF-2.0; the components it bundles (OpenSSL, libffi, SQLite, …) are listed in its licence file |
| PyInstaller bootloader | GPL-2.0-or-later with the bootloader exception |
| Microsoft Visual C++ runtime (`VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`, `VCOMP140.DLL`) | Microsoft Visual Studio redistribution terms: « à confirmer par toi » |
| PyQt6 | GPL-3.0-only |
| Qt 6 (PyQt6-Qt6) | LGPL v3; the modules Qt itself bundles: <https://doc.qt.io/qt-6/licenses-used-in-qt.html> |
| PyQt6-sip | BSD-2-Clause |
| NumPy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| SciPy, numba, pandas, cycler, kiwisolver, XlsxWriter, cloudpickle, colorama | BSD License |
| llvmlite | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception |
| contourpy, joblib | BSD-3-Clause |
| Matplotlib | Python Software Foundation License |
| pyqtgraph, pydantic, pydantic-core, annotated-types, typing-inspection, fonttools, pyparsing | MIT |
| openpyxl, et-xmlfile, six | MIT License |
| Pillow | MIT-CMU |
| python-dateutil | BSD License; Apache Software License |
| packaging | Apache-2.0 OR BSD-2-Clause |
| tzdata | Apache-2.0 |
| typing-extensions | PSF-2.0 |

## 4. Loaded by the HTML pages, not redistributed

The pages of `pages/` and some reports of `reports/` load, when they are opened, MathJax 3 (Apache-2.0), Mermaid 10
(MIT), Plotly 2.27.0 (MIT), Tailwind CSS (MIT) and the Google fonts STIX Two Text, Source Code Pro, Inter and Outfit
(SIL OFL 1.1). They come from their CDNs; none of them is in the repository.

## 5. To be confirmed

- The logo files `certus.svg`, `certus2.svg`, `certus.png` and `certus.ico`: « à confirmer par toi ».
- Code ported from `certus_re` (Zenodo, concept DOI 10.5281/zenodo.22756244), the owner's own package: licence of the
  Zenodo deposit, « à confirmer par toi ».
- The other files of `example/` and `samples/` (measurements, simulations, configurations) are taken to be the
  owner's: « à confirmer par toi ».
