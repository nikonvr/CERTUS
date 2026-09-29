"""A report table given as headers and rows is rendered.

generate_html_report read a table from the section's `content` only. The three tables of
DESIGN's HTML reports — the Pareto front and the run manifest of the Pareto summary, the run
manifest of the full results — are given as `headers` and `rows`: each one came out as
« Table content could not be rendered. », in every Pareto summary kept since 2026-05-29.
"""

from __future__ import annotations


def test_a_headers_and_rows_table_is_rendered(tmp_path) -> None:
    from certus.utils.certus_data import generate_html_report

    target = tmp_path / "report.html"
    sections = [
        {"title": "Summary table", "type": "table", "headers": ["N", "Best RMSE"], "rows": [[20, "0.00270"], [22, "0.00269"]]},
    ]

    assert generate_html_report(str(target), "Report", sections)

    html = target.read_text(encoding="utf-8")
    assert "could not be rendered" not in html
    assert "<th>Best RMSE</th>" in html
    assert "<td>0.00269</td>" in html


def test_a_table_given_as_content_renders_as_before(tmp_path) -> None:
    from certus.utils.certus_data import generate_html_report

    target = tmp_path / "report.html"
    sections = [{"title": "Targets", "type": "table", "content": [{"lambda": 400, "T": 0.9}]}]

    assert generate_html_report(str(target), "Report", sections)

    assert "<td>0.9</td>" in target.read_text(encoding="utf-8")
