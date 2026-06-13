"""Generates pages/complete_certus_report.html - Premium & Interactive Version."""

from __future__ import annotations


import json

import sys

from pathlib import Path

from string import Template


_BENCH_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(_BENCH_DIR))


import benchmark_dTds_extrema as b_ext


_ROOT = _BENCH_DIR


def _extract_extrema_table():

    nums = b_ext.LAMBDA_EXTREMA_REF_NM

    if nums is None or len(nums) == 0:
        return "<tr><td colspan='6'>Extrema not found</td></tr>"

    tbody_lines = []

    n = len(nums)

    rows = (n + 2) // 3

    for row in range(rows):
        tds = []

        for col in range(3):
            i = row + col * rows

            if i < n:
                tds.append(
                    f'<td class="px-2 py-1 text-slate-400 font-mono text-[10px]">{i + 1}</td>'
                    f'<td class="px-2 py-1 text-right font-mono text-xs text-slate-600">{float(nums[i]):.2f}</td>'
                )

            else:
                tds.append("<td></td><td></td>")

        tbody_lines.append('<tr class="border-b border-slate-50">' + "".join(tds) + "</tr>")

    return "\n".join(tbody_lines)


def _html_results_from_latest_jsonl(root: Path) -> tuple[str, dict]:

    candidates = list(root.glob("benchmark_dTds_extrema_results*.jsonl"))

    if not candidates:
        return (
            "<div class='p-8 text-center text-slate-400 italic bg-slate-50 rounded-2xl'>No run data detected.</div>",
            {},
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    records: list[dict] = []

    with latest.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    if not records:
        return "<div class='p-8 text-center text-slate-400 italic bg-slate-50 rounded-2xl'>Empty log file.</div>", {}

    rows_html = []

    for rec in records:
        ip = rec.get("index_probe_6p") or {}

        status_color = (
            "text-green-600 bg-green-50 shadow-[0_0_10px_rgba(16,185,129,0.1)]"
            if rec.get("success_quality")
            else "text-rose-600 bg-rose-50"
        )

        rows_html.append(f"""

            <tr class="border-b border-slate-50 hover:bg-slate-50/50 transition-colors animate-fade-in">

                <td class="py-4 px-4 font-bold text-slate-700">{rec.get("sigma_lambda_nm", "0")}</td>

                <td class="py-4 px-4 text-center">

                    <span class="px-2 py-1 rounded-full text-[10px] font-bold uppercase {status_color}">

                        {rec.get("success_quality", "False")}

                    </span>

                </td>

                <td class="py-4 px-4 font-mono text-xs text-slate-500">{float(rec.get("mse_residual", 0)):.2e}</td>

                <td class="py-4 px-4 font-mono text-xs font-bold text-primary-600">{float(ip.get("rmse_delta_n", 0)):.2e}</td>

                <td class="py-4 px-4 font-mono text-xs text-slate-500">{float(rec.get("d_um", 0)):.4f}</td>

                <td class="py-4 px-4 text-xs font-medium text-slate-300">{rec.get("nfev", "-")}</td>

            </tr>

        """)

    table_html = f"""

    <div class="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">

        <table class="w-full text-left border-collapse">

            <thead>

                <tr class="bg-slate-50 text-slate-500 text-[10px] uppercase tracking-widest font-bold">

                    <th class="px-4 py-3">sigma (nm)</th>

                    <th class="px-4 py-3 text-center">Status</th>

                    <th class="px-4 py-3 font-mono">MSE</th>

                    <th class="px-4 py-3">RMSE(Deltan)</th>

                    <th class="px-4 py-3">d (µm)</th>

                    <th class="px-4 py-3">Evals</th>

                </tr>

            </thead>

            <tbody class="divide-y divide-slate-50">{"".join(rows_html)}</tbody>

        </table>

    </div>

    """

    return table_html + _generate_smart_graphs(records), records[-1]


def _generate_smart_graphs(records: list[dict]) -> str:

    if not records:
        return ""

    traces_n = []

    zone_analysis = []

    for rec in records:
        sig = float(rec.get("sigma_lambda_nm", 0))

        ip = rec.get("index_probe_6p")

        if not ip:
            continue

        lam, dn = ip.get("lambda_nm", []), ip.get("delta_n", [])

        abs_dn = [abs(x) for x in dn]

        traces_n.append(
            f"{{ x: {json.dumps(lam)}, y: {json.dumps(abs_dn)}, mode: 'lines', name: 'sigma = {sig}nm', line: {{ width: 2.5 }} }}"
        )

        v_errs = [abs(dn[i]) for i, l in enumerate(lam) if 400 <= l <= 700]

        n_errs = [abs(dn[i]) for i, l in enumerate(lam) if l > 700]

        max_v, max_n = max(v_errs) if v_errs else 0, max(n_errs) if n_errs else 0

        target = 0.05

        def status_ui(v, target=target):

            return f'<span class="flex items-center gap-1.5 {"text-emerald-600" if v <= target else "text-rose-500"} font-bold">{"●" if v <= target else "×"} <span class="text-[10px] text-slate-400 font-normal">({v:.3f})</span></span>'

        zone_analysis.append(f"""

        <tr class="border-b border-slate-50 text-xs">

            <td class="py-3 px-4 font-mono text-slate-500">{sig}</td>

            <td class="py-3 px-4">{status_ui(max_v)}</td>

            <td class="py-3 px-4">{status_ui(max_n)}</td>

        </tr>""")

    return f"""

    <div class="mt-12 space-y-8 animate-fade-in">

        <div class="glass rounded-[2rem] p-8 shadow-2xl shadow-primary-900/5 overflow-hidden">

            <h3 class="text-xl font-display font-bold text-slate-900 mb-2">Absolute Precision vs Spectrum</h3>

            <div id="smartPlotN" class="w-full h-[450px] bg-white rounded-xl"></div>

        </div>

        <div class="glass rounded-[2rem] p-8 shadow-xl shadow-slate-200/50">

            <h4 class="text-lg font-display font-bold text-slate-800 mb-6">Zonal Diagnostic (Target Deltan <= 0.05)</h4>

            <table class="w-full text-left">

                <thead>

                    <tr class="text-[10px] text-slate-400 uppercase tracking-widest border-b border-slate-100">

                        <th class="pb-3 px-4">sigma (nm)</th><th class="pb-3 px-4">Visible (VIS)</th><th class="pb-3 px-4">Near IR (NIR)</th>

                    </tr>

                </thead>

                <tbody>{"".join(zone_analysis)}</tbody>

            </table>

        </div>

        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>

        <script>

            var tracesN = [{",".join(traces_n)}];

            var layoutN = {{

                xaxis: {{ title: 'Wavelength lambda (nm)', gridcolor: '#f1f5f9' }},

                yaxis: {{ title: '|Deltan|', type: 'log', gridcolor: '#f1f5f9' }},

                margin: {{ l: 60, r: 20, t: 30, b: 50 }},

                shapes: [{{ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: 0.05, y1: 0.05, line: {{ color: '#10b981', dash: 'dash' }} }}]

            }};

            Plotly.newPlot('smartPlotN', tracesN, layoutN);

        </script>

    </div>

    """


tbody = _extract_extrema_table()

run_table_html, last_rec = _html_results_from_latest_jsonl(_ROOT)


# Dynamic determination of constants

n_nodes = len(b_ext.LAMBDA_EXTREMA_REF_NM)

n_sub = b_ext.N_SUB

d_val = last_rec.get("d_um", 3.0)

n_probe = len(last_rec.get("index_probe_6p", {}).get("lambda_nm", []))


HTML_TEMPLATE = Template(r"""<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="utf-8"/><title>CERTUS - Topological Bench Report</title>

<script src="https://cdn.tailwindcss.com?plugins=typography"></script>

<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@700&display=swap" rel="stylesheet">

<style>

  body { background: #fcfdfe; color: #1e293b; font-family: 'Inter', sans-serif; }

  .glass { background: rgba(255, 255, 255, 0.95); border: 1px solid #f1f5f9; }

  .gradient-text { background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

  @keyframes slide { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

  .animate-fade-in { animation: slide 0.8s ease-out forwards; }

  .hidden { display: none !important; }

</style>

<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>

</head>

<body class="antialiased min-h-screen pb-24">

<div id="offline-banner" class="hidden fixed top-0 left-0 w-full bg-amber-100 border-b border-amber-200 text-amber-800 px-4 py-2 text-center text-sm z-50">
  ⚠️ Scientific formulas and diagrams may not render correctly without an internet connection (CDN-based assets).
</div>

<script>
  window.addEventListener('load', function() {
    // Check if CDN assets loaded (MathJax or Plotly as proxies for connectivity)
    if (typeof MathJax === 'undefined' || typeof Plotly === 'undefined') {
      document.getElementById('offline-banner').classList.remove('hidden');
    }
  });
</script>

<div class="max-w-6xl mx-auto px-8 pt-16">

    <header class="mb-20 animate-fade-in">

        <h1 class="text-6xl font-display font-bold text-slate-900 mb-8 tracking-tight">Topological <span class="gradient-text">Diagnostic</span></h1>

        <p class="text-xl text-slate-500 font-light max-w-3xl leading-relaxed">Validation of the spectrophotometric inversion robustness via synthetic modeling of a <strong>$D_LO µm</strong> layer.</p>

    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">

        <div class="lg:col-span-4 space-y-8 animate-fade-in">

            <div class="bg-slate-900 text-white rounded-[2rem] p-10 shadow-2xl relative overflow-hidden">

                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-10">Run Metadata</h3>

                <div class="space-y-6 font-mono text-[11px]">

                    <div class="flex justify-between border-b border-white/5 pb-3"><span>NODES</span><span class="text-sky-400">$N_NODES</span></div>

                    <div class="flex justify-between border-b border-white/5 pb-3"><span>SUBSTRATE</span><span class="text-sky-400">$N_SUB</span></div>

                    <div class="flex justify-between border-b border-white/5 pb-3"><span>NP PROBES</span><span class="text-sky-400">$INDEX_LOG_N</span></div>

                </div>

            </div>

            <div class="glass rounded-[2rem] p-10 shadow-sm">

                <h4 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-50 pb-4">Extrema lambda (nm)</h4>

                <table class="w-full text-[10px] font-mono"><tbody>$TBODY</tbody></table>

            </div>

        </div>

        <div class="lg:col-span-8 space-y-12 animate-fade-in">

            <section class="glass rounded-[2.5rem] p-10 shadow-2xl shadow-slate-200/40">

                <h2 class="text-2xl font-display font-bold text-slate-900 mb-8">Statistical Results</h2>

                $RUN_TABLE

            </section>

        </div>

    </div>

</div>

</body></html>""")


html_content = HTML_TEMPLATE.substitute(
    N_NODES=str(n_nodes),
    N_SUB=str(n_sub),
    D_LO=f"{d_val:.2f}",
    TBODY=tbody,
    RUN_TABLE=run_table_html,
    INDEX_LOG_N=str(n_probe),
)


out = _ROOT / "pages" / "complete_certus_report.html"

out.parent.mkdir(parents=True, exist_ok=True)

out.write_text(html_content, encoding="utf-8")

print(f"PREMIUM report generated: {out}")
