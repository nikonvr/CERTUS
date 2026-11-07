"""Seed files for the RICL ultimate runs (2026-11-05), read from archived campaigns; no optimization here.

seeds_tl_published.csv : Trubetskov 2020 Fig. 4 designs re-created from the figure (deep 101, classical 104 layers).
seeds_tl_certus.csv    : CERTUS three-line designs of the archived campaigns, 12 500-15 000 nm, 80-130 layers, the
                         best distinct ones by nominal MF (includes the 109-layer design of the article).
seeds_tl_scratch.csv   : CERTUS designs grown from the bare substrate only (gradual evolution, Trubetskov 2020 step,
                         files gradual_*grow*.csv), 12 500-15 000 nm: no published design in their ancestry.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE.parent / "DESIGN_bs5050_2026-10-22" / "tikhonravov" / "envelope_v2"
PILOT = HERE.parent / "DESIGN_resonances_integration_2026-11-05" / "pour_article"


def write(name: str, rows: list[dict]) -> None:
    with (HERE / name).open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["name", "layers", "tot", "mf", "seq", "d_nm"])
        w.writeheader()
        w.writerows(rows)
    print(name, len(rows))


def main() -> None:
    pub = []
    with (ENV / "fig4_2020_designs.csv").open(encoding="utf-8") as h:
        pub.extend({"name": f"trub2020_{r['design']}", "layers": r["layers"], "tot": r["tot"],
                    "mf": float(r["mf_oracle"]), "seq": r["seq"], "d_nm": r["d_nm"]} for r in csv.DictReader(h))
    write("seeds_tl_published.csv", pub)

    js = json.loads((PILOT / "initial_design.json").read_text(encoding="utf-8"))
    own = [{"name": "certus109", "layers": js["layers"], "tot": js["total_ot_nm"], "mf": js["mf_oracle"],
            "seq": js["seq"], "d_nm": js["d_nm"]}]
    scratch = []
    with (ENV / "grid_threeline_judged.csv").open(encoding="utf-8") as h:
        rows = [r for r in csv.DictReader(h) if 12500 <= float(r["tot"]) <= 15000 and 80 <= int(r["layers"]) <= 130]
    rows.sort(key=lambda r: float(r["mf_nominal"]))
    seen = set()
    for r in rows:
        key = round(float(r["mf_nominal"]), 9)
        if key in seen or "partial" in r["source"]:
            continue
        seen.add(key)
        row = {"name": r["source"].replace(".csv", ""), "layers": r["layers"], "tot": r["tot"],
               "mf": r["mf_nominal"], "seq": r["seq"], "d_nm": r["d_nm"]}
        if len(own) < 24:
            own.append(row)
        src = r["source"]
        if "grow" in src and "cont" not in src and "seed" not in src and len(scratch) < 24:
            scratch.append(row)
    write("seeds_tl_certus.csv", own)
    write("seeds_tl_scratch.csv", scratch)

    # every archived three-line design whose ancestry excludes the published designs (no germ of them)
    banned = ("seed", "deep2020", "up14k", "trub")
    indep = []
    with (ENV / "grid_threeline_judged.csv").open(encoding="utf-8") as h:
        for r in csv.DictReader(h):
            src = r["source"]
            if "partial" in src or any(b in src for b in banned):
                continue
            indep.append({"name": src.replace(".csv", ""), "layers": r["layers"], "tot": r["tot"],
                          "mf": r["mf_nominal"], "seq": r["seq"], "d_nm": r["d_nm"]})
    write("seeds_tl_independent.csv", indep)

    # 2012 constrained problem (51 layers, OT 100-350 nm): the ten published designs (Fig. 3) and CERTUS results
    c51 = []
    with (ENV / "fig3_2012_designs.csv").open(encoding="utf-8") as h:
        c51.extend({"name": f"pub2012_p{r['panel']}s{r['side']}", "layers": len(r["seq"]), "tot": r["tot"],
                    "mf": float(r["mf_oracle"]), "seq": r["seq"], "d_nm": r["d_nm"]} for r in csv.DictReader(h))
    for f in sorted(ENV.glob("constrained_threeline_N51*.csv")):
        with f.open(encoding="utf-8") as h:
            for k, r in enumerate(csv.DictReader(h)):
                c51.append({"name": f"{f.stem}#{k}", "layers": r["layers"], "tot": r["total_ot_nm"],
                            "mf": r["mf_oracle"], "seq": r["seq"], "d_nm": r["d_nm"]})
    write("seeds_c51.csv", c51)

    # 50/50 (1996 problem): archived CERTUS designs with full sequences
    bs = []
    for f in [ENV / "curve_mono_free.csv", ENV / "grid_bs5050_repolish.csv", *sorted(ENV.glob("curve_free_s*.csv")),
              *sorted(ENV.glob("curve_foc27-36_free_s*.csv")), *sorted(ENV.glob("curve_abl_*_free_s*.csv"))]:
        if not f.exists():
            continue
        with f.open(encoding="utf-8") as h:
            for k, r in enumerate(csv.DictReader(h)):
                if r.get("seq") and r.get("d_nm"):
                    bs.append({"name": f"{f.stem}#{k}", "layers": len(r["seq"]), "tot": "", "mf": "",
                               "seq": r["seq"], "d_nm": r["d_nm"]})
    write("seeds_bs.csv", bs)


if __name__ == "__main__":
    main()
