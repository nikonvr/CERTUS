"""Visualization 1 of the OE paper (2026-11-03, owner: "go"): the exchange method against the charge of the poles, round
by round, on the stop band 400-430 nm of the re-created 101-layer design.

Left: exchange (exchange_trub101_trace.csv: the design of every round and the points added so far, found by a scan every
0.0002 nm). Right: charge at the poles (threeline_track_height_trub101.csv: the design of every round); the poles found
on it from the complex plane (Code 1, find_poles) mark the tops charged in the next round, and the inset shows them in
the complex wavelength plane. T is computed every 0.0005 nm by Code 1; faint blue: the design as re-created.
usage: python visualization1.py OUT.gif|OUT.mp4 [FPS]   (an .mp4 needs env FFMPEG_EXE, the path of an ffmpeg binary)
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter  # noqa: E402

CODE = Path(__file__).resolve().parents[6] / "OE_resonances" / "code"
sys.path.insert(0, str(CODE))
import hidden_resonances as hr  # noqa: E402

BANDS = [(445, 455, 1.0), (505, 515, 1.0), (635, 645, 1.0), (400, 440, 0.0), (460, 500, 0.0), (520, 630, 0.0),
         (650, 700, 0.0)]
W = np.arange(400.0, 430.0 + 1e-9, 0.0005)
GRID = np.arange(400.0, 431.0)


def target_fn(lam):
    return next((t for a, b, t in BANDS if a <= lam <= b), 0.0)


def design(row):
    return [{"H": 2.35, "L": 1.45}[m] for m in row["seq"]], np.array([float(v) for v in row["d_nm"].split()])


def spectrum(nl, d, w):
    return np.concatenate([hr.transmittance(nl, d, w[k:k + 20000]) for k in range(0, len(w), 20000)])


ex = list(csv.DictReader(open("exchange_trub101_trace.csv", encoding="utf-8")))
ch = list(csv.DictReader(open("threeline_track_height_trub101.csv", encoding="utf-8")))
n = min(len(ex), len(ch))
nl0, d0 = design(ch[0])
t0 = 100 * spectrum(nl0, d0, W)
frames = []
for k in range(n):
    nle, de = design(ex[k])
    nlc, dc = design(ch[k])
    extra = [float(v) for v in ex[k]["extra_nm"].split()]
    extra = np.array([x for x in extra if 400.0 <= x <= 430.0])
    poles = [p for p in hr.find_poles(nlc, dc, [(400, 440)], target_fn) if p[0] <= 430.0]
    tops = np.array([hr.top_of_peak(nlc, dc, p[0], p[1], target_fn) for p in poles])
    frames.append({
        "te": 100 * spectrum(nle, de, W), "tge": 100 * spectrum(nle, de, GRID),
        "xe": extra, "txe": 100 * spectrum(nle, de, extra) if len(extra) else np.array([]),
        "ne": len(ex[k]["extra_nm"].split()),
        "tc": 100 * spectrum(nlc, dc, W), "tgc": 100 * spectrum(nlc, dc, GRID),
        "xc": tops, "txc": 100 * spectrum(nlc, dc, tops) if len(tops) else np.array([]),
        "poles": [(1 / p[3].real, -p[1] / 2) for p in poles], "mfc": float(ch[k]["mf_resolved"]), "nc": len(poles),
    })
    print(f"round {k}: exchange {frames[-1]['ne']} points, charge {len(poles)} poles", flush=True)

fig, axs = plt.subplots(1, 3, figsize=(12, 4.0), gridspec_kw={"width_ratios": [1.0, 1.0, 0.55]})
fig.subplots_adjust(left=0.06, right=0.99, bottom=0.13, top=0.84, wspace=0.18)
ax, ins = axs[:2], axs[2]  # third panel: the charged poles in the complex wavelength plane


def draw(k):
    f = frames[k]
    for a in ax:
        a.clear()
    ins.clear()
    for a, key, col, title in ((ax[0], "e", "C4", "exchange: points added at the peaks found"),
                               (ax[1], "c", "C2", "charge: one point at the top of each pole's peak")):
        a.semilogy(W, np.maximum(t0, 1e-5), color="C0", lw=0.5, alpha=0.25, label="as re-created")
        a.semilogy(W, np.maximum(f["t" + key], 1e-5), color=col, lw=0.9, label=f"round {k}")
        a.semilogy(GRID, np.maximum(f["tg" + key], 1e-5), "k.", ms=3, label="the 277-point grid")
        a.set_xlim(400, 430)
        a.set_ylim(1e-4, 100)
        a.set_xlabel("wavelength (nm)")
        a.set_title(title, fontsize=9)
    if len(f["xe"]):
        ax[0].semilogy(f["xe"], np.maximum(f["txe"], 1e-5), "v", color="k", ms=4, label="added points")
    if len(f["xc"]):
        ax[1].semilogy(f["xc"], np.maximum(f["txc"], 1e-5), "o", color="C3", ms=4, label="charged tops")
    ax[0].set_ylabel("T (%), target 0")
    ax[0].text(0.02, 0.04, f"277 + {f['ne']} points, resolved MF {float(ex[k]['mf_resolved']):.3f} %",
               transform=ax[0].transAxes, fontsize=8)
    ax[1].text(0.02, 0.04, f"277 + {f['nc']} points, resolved MF {f['mfc']:.4f} %", transform=ax[1].transAxes,
               fontsize=8)
    for a in ax:
        a.legend(fontsize=7, loc="upper left")
    for j in range(k + 1):  # trail of the earlier rounds, the current one in full colour
        for x, y in frames[j]["poles"]:
            ins.plot(x, y, "x", color="C3" if j == k else "0.75", ms=6 if j == k else 3)
    ins.set_xlim(400, 430)
    ins.set_ylim(-0.18, 0.005)
    ins.axhline(0, color="0.5", lw=0.6)
    ins.set_xlabel(r"Re $\lambda$ (nm)")
    ins.set_ylabel(r"Im $\lambda$ (nm)")
    ins.set_title("charged poles (grey: earlier rounds)", fontsize=9)
    fig.suptitle(f"re-created 101-layer three-line filter, stop band 400-430 nm: round {k} of 40", fontsize=10)


anim = FuncAnimation(fig, draw, frames=n)
fps = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
if sys.argv[1].endswith(".mp4"):  # 2026-11-03: H.264 for Optica's Visualization 1, ffmpeg given by FFMPEG_EXE
    import os

    plt.rcParams["animation.ffmpeg_path"] = os.environ["FFMPEG_EXE"]
    writer = FFMpegWriter(fps=fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "18"])
else:
    writer = PillowWriter(fps=fps)
anim.save(sys.argv[1], writer=writer, dpi=150 if sys.argv[1].endswith(".mp4") else 100)
for k in (0, 1, 12, n - 1):
    draw(k)
    fig.savefig(str(Path(sys.argv[1]).with_suffix("")) + f"_round{k}.png", dpi=100)
print("written", sys.argv[1], flush=True)
