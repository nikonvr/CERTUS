"""Dataset 1 of the method paper (OE_resonances/dataset; 2026-11-02, owner: "complete it"): every design behind Table 1,
the twelve re-optimizations of Sec. 7.2, the designs of the three targets (Figs. 1, 2 and 4) and those of the half circle
with n_H = 2.1 (Secs. 3 and 5), with the thicknesses exactly as computed. Each design is judged again from the written
file by Code 1 (NumPy only, independent of the CERTUS kernel that produced it): against the paper as printed for Table 1,
against its source otherwise; MF on the nominal grid everywhere, resolved for Table 1, the re-optimizations and Fig. 2.
Single designs: the format of Code 1 (layer, material, thickness_nm; layer 1 on the substrate). Collections: one row per
design, seq (materials from the substrate) and d_nm (thicknesses in the same order). Supersedes oe_dataset_classical.py.
usage: python oe_dataset.py OE_CODE_DIR
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import classical_trub104 as ct  # puts OE_CODE_DIR (argv[1]) on the path and imports Code 1
import numpy as np

os.environ.setdefault("SEARCH_TARGET", "threeline")
import oe_spectra_figure as osf  # noqa: E402  (the three targets)

hr = ct.hr
OUT = Path(sys.argv[1]).parent / "dataset"
GRID = np.arange(400.0, 701.0)
TARGETS = (("semi", "half_circle"), ("mshape", "spectral_m"), ("highpass", "long_wave_pass"))
BAD: list[str] = []


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


DEEP = next(r for r in rows("fig4_2020_designs.csv") if r["design"] == "deep")
REFINE = {float(r["grid_nm"]): r for r in rows("threeline_refine_probe_trub101.csv")}
INJECT = {float(r["k"]): r for r in rows("inject_k_trub101_designs.csv")}
#: file of table1/, source row, MF of Table 1 on the 277 points and resolved (as printed), resolved step (nm)
TABLE1 = (("101_polished_0.005nm.csv", REFINE[0.005], "0.0445", "0.0347", 0.001),
          ("101_polished_0.001nm.csv", REFINE[0.001], "0.0445", "0.0272", 0.001),
          ("101_absorption_k1e-3.csv", INJECT[0.001], "0.0412", "0.351", 0.001),
          ("101_absorption_k5e-3.csv", INJECT[0.005], "2.91", "1.97", 0.001),
          ("101_exchange_round12.csv", rows("exchange_trub101_round12.csv")[0], "0.0461", "0.096", 0.001),
          # 2026-11-03: the window and the two charges with the corrected method (fixed detector, top of the peak)
          ("101_window.csv", rows("threeline_track_quad_trub101.csv")[-1], "0.0209", "0.0296", 0.001),
          ("101_charged.csv", rows("threeline_track_height_trub101.csv")[-1], "0.0239", "0.0215", 0.001),
          ("classical_103_recreated.csv", rows("fig4_2020_classical_nolsub.csv")[0], "0.0133", "0.0354", 0.0002),
          ("classical_103_charged.csv", rows("threeline_track_height_classical103.csv")[-1], "0.0294", "0.0286",
           0.0002))


def check(tag, ok, text):
    if not ok:
        BAD.append(tag)
    print(f"{tag}: {text}{'' if ok else '  <- DIFFERENT'}", flush=True)


def as_printed(x, printed):
    return round(x, len(printed.split(".")[1])) == float(printed)


def close(x, ref, rel=1e-4):
    return abs(x - ref) <= rel * abs(ref)


def mf_target(tag, nl, d, step):
    """MF (%) of a design of an arbitrary target with Code 1, on 1 nm (the grid of Fig. 2) or finer steps."""
    w = GRID if step == 1.0 else np.arange(400.0, 700.0 + step / 2, step)
    tg = osf.target(tag, w)
    keep = ~np.isnan(tg)
    w, tg = w[keep], tg[keep]
    s2 = sum(float(np.sum((hr.transmittance(nl, d, w[k:k + 20000]) - tg[k:k + 20000]) ** 2))
             for k in range(0, len(w), 20000))
    return 100.0 * np.sqrt(s2 / len(w))


def table1() -> None:
    (OUT / "table1").mkdir(parents=True, exist_ok=True)
    for name, r, nom_p, res_p, h in TABLE1:
        seq, tokens = r.get("seq") or DEEP["seq"], r["d_nm"].split()
        with open(OUT / "table1" / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["layer", "material", "thickness_nm"])
            w.writerows((k + 1, m, t) for k, (m, t) in enumerate(zip(seq, tokens, strict=True)))
        back = rows(OUT / "table1" / name)
        nl, d = [ct.N_IDX[b["material"]] for b in back], np.array([float(b["thickness_nm"]) for b in back])
        nom, res = ct.judged(nl, d, 1.0)[0], ct.judged(nl, d, h)[0]
        check(f"table1/{name}", as_printed(nom, nom_p) and as_printed(res, res_p),
              f"{len(d)} layers, MF {nom:.4f} %, {res:.4f} % on {h:g} nm; Table 1: {nom_p}, {res_p}")


def reoptimizations() -> None:
    last: dict = {}
    for r in rows("optimizer_test_trub101.csv"):
        key = (int(r["seed"]), r["method"])
        if key not in last or int(r["round"]) > int(last[key]["round"]):
            last[key] = r
    with open(OUT / "reoptimizations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start", "method", "rounds", "mf_nominal_pct", "mf_resolved_pct", "seq", "d_nm"])
        for (seed, method), r in sorted(last.items()):
            w.writerow([seed, {"nominal": "grid", "pole": "poles charged"}[method], r["round"],
                        f"{float(r['mf_nominal']):.6g}", f"{float(r['mf_resolved']):.6g}", DEEP["seq"], r["d_nm"]])
    for r in rows(OUT / "reoptimizations.csv"):
        nl, d = [ct.N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
        nom, res = ct.judged(nl, d, 1.0)[0], ct.judged(nl, d, 0.001)[0]
        check(f"reoptimizations start {r['start']}, {r['method']}",
              close(nom, float(r["mf_nominal_pct"])) and close(res, float(r["mf_resolved_pct"])),
              f"MF {nom:.4f} %, {res:.4f} % on 0.001 nm; source {r['mf_nominal_pct']}, {r['mf_resolved_pct']}")


def collection(path, tag, n_h, designs, stats) -> None:
    """designs: rows with seq, d_nm; stats: dicts (run, search, layers, ot_nm, ot_c_nm, mf_*_pct, resonances,
    highest_peak_pct), in the same order; only the designs with a nominal MF below 5 % (Figs. 1 and 4) are kept."""
    assert len(designs) == len(stats), (path, len(designs), len(stats))
    n = worst = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["run", "search", "layers", "ot_nm", "ot_c_nm", "mf_nominal_pct", "mf_resolved_pct", "resonances",
                "highest_peak_pct"]
        w.writerow([*cols, "seq", "d_nm"])
        for dsg, st in zip(designs, stats, strict=True):
            seq, d = dsg["seq"], np.array([float(v) for v in dsg["d_nm"].split()])
            nl = [n_h if m == "H" else 1.45 for m in seq]
            ot = float(np.dot(nl, d))
            assert len(seq) == int(st["layers"]), (path, st)
            assert abs(ot - float(st["ot_nm"])) < 1.0, (path, st, ot)
            if float(st["mf_nominal_pct"]) >= 5.0:
                continue
            nom = mf_target(tag, nl, d, 1.0)
            worst = max(worst, abs(nom - float(st["mf_nominal_pct"])))
            w.writerow([st[c] for c in cols] + [seq, dsg["d_nm"]])
            n += 1
    check(path.name, worst < 6e-5, f"{n} designs, nominal MF of Code 1 within {worst:.1e} % of the source")


def targets() -> None:
    (OUT / "targets").mkdir(parents=True, exist_ok=True)
    for tag, name in TARGETS:
        designs, stats = [], []
        for run in (5, 6):
            for kind in ("curve", "front"):
                designs += rows(f"{kind}_nolsub_{tag}_free_s{run}.csv")
            stats.extend({"run": run, "search": st["kind"], "layers": st["layers"],
                          "ot_nm": f"{float(st['ot_nm']):.1f}", "ot_c_nm": f"{float(st['ot_c']):.1f}",
                          "mf_nominal_pct": f"{float(st['mf_nominal']):.6g}",
                          "mf_resolved_pct": f"{float(st['mf_resolved']):.6g}", "resonances": st["poles"],
                          "highest_peak_pct": f"{100 * float(st['highest']):.4g}"}
                         for st in rows(f"nolsub_{tag}_threshold_s{run}.csv"))
        collection(OUT / "targets" / f"{name}.csv", tag, 2.35, designs, stats)
    designs, stats = [], []
    for run in (7, 8):  # n_H = 2.1: statistics only printed by semi_threshold.py, in the order of the designs
        for kind in ("curve", "front"):
            designs += rows(f"{kind}_nolsub_semi_free_s{run}.csv")
        for line in open(f"nolsub_nh21_threshold_s{run}.out", encoding="utf-8"):
            t = line.split()
            if t and t[0] in ("curve", "front"):
                stats.append({"run": run, "search": t[0], "layers": t[2], "ot_nm": t[4], "ot_c_nm": t[19],
                              "mf_nominal_pct": t[6], "mf_resolved_pct": t[9], "resonances": t[14],
                              "highest_peak_pct": t[16]})
    collection(OUT / "targets" / "half_circle_nH2.1.csv", "semi", 2.1, designs, stats)
    with open(OUT / "targets" / "figure2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["target", "design", "layers", "ot_nm", "mf_nominal_pct", "mf_resolved_pct", "seq", "d_nm"])
        for tag, name in TARGETS:
            for r in rows(f"nolsub_{tag}_spectra_designs.csv"):
                w.writerow([name, {"grid": "optimized on the grid", "charged": "poles charged"}[r["which"]],
                            r["layers"], f"{float(r['ot_nm']):.1f}", f"{float(r['mf_nominal']):.6g}",
                            f"{float(r['mf_resolved']):.6g}", r["seq"], r["d_nm"]])
    for r in rows(OUT / "targets" / "figure2.csv"):
        tag = next(t for t, n in TARGETS if n == r["target"])
        nl, d = [ct.N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
        nom, res = mf_target(tag, nl, d, 1.0), mf_target(tag, nl, d, 0.001)
        check(f"figure2 {r['target']}, {r['design']}", close(nom, float(r["mf_nominal_pct"])),
              f"MF {nom:.4f} %, {res:.4f} % on 0.001 nm; source {r['mf_nominal_pct']}, {r['mf_resolved_pct']}")


def synthesis() -> None:
    """Sec. 7.3 (sec73.sh, seed 9): for the M target and the long-wave pass, the judged designs of the two searches and
    the cured best design of each N of the search on the grid."""
    (OUT / "synthesis").mkdir(parents=True, exist_ok=True)
    for t, name in (("mshape", "spectral_m"), ("highpass", "long_wave_pass")):
        for tag, kind in ((f"nolsub_{t}", "search_on_the_grid"), (f"poles3_nolsub_{t}", "search_with_poles")):
            designs = rows(f"curve_{tag}_free_s9.csv") + rows(f"front_{tag}_free_s9.csv")
            stats = [{"run": 9, "search": st["kind"], "layers": st["layers"], "ot_nm": f"{float(st['ot_nm']):.1f}",
                      "ot_c_nm": f"{float(st['ot_c']):.1f}", "mf_nominal_pct": f"{float(st['mf_nominal']):.6g}",
                      "mf_resolved_pct": f"{float(st['mf_resolved']):.6g}", "resonances": st["poles"],
                      "highest_peak_pct": f"{100 * float(st['highest']):.4g}"} for st in rows(f"{tag}_threshold_s9.csv")]
            collection(OUT / "synthesis" / f"{name}_{kind}.csv", t, 2.35, designs, stats)
        cured = rows(f"nolsub_{t}_cure_archive_s9.csv")
        path = OUT / "synthesis" / f"{name}_search_on_the_grid_cured.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["layers", "ot_nm", "mf_nominal_before_pct", "mf_resolved_before_pct", "mf_nominal_after_pct",
                        "mf_resolved_after_pct", "highest_peak_after_pct", "seq", "d_nm"])
            for r in cured:
                w.writerow([r["layers"], f"{float(r['ot_nm']):.1f}", f"{float(r['nominal_before']):.6g}",
                            f"{float(r['resolved_before']):.6g}", f"{float(r['nominal_after']):.6g}",
                            f"{float(r['resolved_after']):.6g}", f"{100 * float(r['highest_after']):.4g}", r["seq"],
                            r["d_nm"]])
        worst, b = 0.0, None
        for r in rows(path):
            nl, d = [ct.N_IDX[m] for m in r["seq"]], np.array([float(v) for v in r["d_nm"].split()])
            worst = max(worst, abs(mf_target(t, nl, d, 1.0) - float(r["mf_nominal_after_pct"])))
            if b is None or float(r["mf_resolved_after_pct"]) < float(b["mf_resolved_after_pct"]):
                b = r
        nl, d = [ct.N_IDX[m] for m in b["seq"]], np.array([float(v) for v in b["d_nm"].split()])
        res = mf_target(t, nl, d, 0.001)
        check(path.name, worst < 6e-5 and close(res, float(b["mf_resolved_after_pct"])),
              f"{len(cured)} designs, nominal MF of Code 1 within {worst:.1e} %; the best, {b['layers']} layers, "
              f"resolved {res:.4f} % (source {b['mf_resolved_after_pct']})")


def main() -> None:
    for old in ("three_line_classical_103_recreated.csv", "three_line_classical_103_charged.csv"):
        (OUT / old).unlink(missing_ok=True)  # now in table1/
    table1()
    reoptimizations()
    targets()
    if os.path.exists("nolsub_highpass_cure_archive_s9.csv"):  # Sec. 7.3, once sec73.sh has run on both targets
        synthesis()
    print(f"checks failed: {len(BAD)} {BAD}", flush=True)


if __name__ == "__main__":
    main()
