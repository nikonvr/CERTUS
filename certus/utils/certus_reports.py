"""CERTUS premium export templates - Excel + PDF (U10).

A unified, brand-consistent reporting layer so all suite apps (INDEX,
DESIGN, STRAT, METAL, RE) produce **polished** ``.xlsx`` and ``.pdf``
deliverables with a shared header, typography, color palette, and
table styling.

Dependencies
------------

- **Excel**: ``openpyxl`` (already a project dependency).
- **PDF**: ``matplotlib`` (already a project dependency) via its
  ``backend_pdf.PdfPages`` multi-page backend. No extra package needed.

Core abstractions
-----------------

- :class:`ReportContext` - header metadata (title, subtitle, author,
  generated_at, app_name, logo_path).
- :class:`Section` - one logical block of content, one of three kinds:
    * ``"table"``: rows + header + optional column widths.
    * ``"text"``: a paragraph (or list of paragraphs).
    * ``"chart"``: a matplotlib ``Figure`` to embed as an image.
- :func:`build_excel_report(ctx, sections, output_path)` - renders a
  styled multi-sheet ``.xlsx``.
- :func:`build_pdf_report(ctx, sections, output_path)` - renders a
  multi-page ``.pdf`` with a cover page, header strip, and sections.

All rendering functions are idempotent and return the absolute output
path on success. They never raise on empty sections — an empty report
produces a single cover/page-1 with "(no content)" placeholder.

Design rules
------------

- **No GUI**: this module is importable from workers and tests. It
  produces a file on disk, nothing else.
- **Best-effort styling**: when ``openpyxl`` or ``matplotlib`` lacks a
  feature (older version), we degrade gracefully rather than raising.
- **Consistent brand colors**: see :data:`BRAND_COLORS`.

Public API
----------

- :data:`BRAND_COLORS`
- :class:`ReportContext`, :class:`Section`
- :func:`build_excel_report`, :func:`build_pdf_report`
- :func:`report_summary_header(ctx)` - text representation for re-use
"""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Iterable

import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# Brand palette (hex strings)
# =============================================================================


BRAND_COLORS: Final[dict[str, str]] = {
    "primary": "#1F3A8A",
    "primary_soft": "#E0E7FF",
    "accent": "#2563EB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "muted": "#6B7280",
    "surface": "#FFFFFF",
    "alt_row": "#F9FAFB",
    "text": "#111827",
}


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class ReportContext:
    """Metadata used to render the header of each report."""

    title: str
    subtitle: str = ""
    app_name: str = "CERTUS"
    author: str = ""
    generated_at: datetime | None = None
    logo_path: str | None = None
    run_manifest: dict[str, Any] | Any | None = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()

    def header_lines(self) -> list[str]:
        """Return a list of header strings."""
        ts = self.generated_at.strftime("%Y-%m-%d %H:%M:%S") if self.generated_at else ""
        lines = [self.title]
        if self.subtitle:
            lines.append(self.subtitle)
        meta = []
        if self.app_name:
            meta.append(self.app_name)
        if self.author:
            meta.append(f"by {self.author}")
        if ts:
            meta.append(ts)
        if meta:
            lines.append(" • ".join(meta))
        return lines


@dataclass
class Section:
    """A single block of content inside a report.

    Parameters
    ----------
    title:
        Section heading (rendered as a styled row / page heading).
    kind:
        ``"table"`` / ``"text"`` / ``"chart"``.
    rows:
        Used when ``kind=='table'``. A 2D list ``[[row0_cells], ...]``.
    header:
        Used when ``kind=='table'``. Column names. Optional.
    text:
        Used when ``kind=='text'``. Either a single string or a list of
        paragraphs.
    figure:
        Used when ``kind=='chart'``. A matplotlib ``Figure`` or any
        object exposing a ``savefig(path)`` method.
    notes:
        Optional free-form note displayed under the content.
    column_widths:
        Optional list of widths (in Excel characters) for table columns.
    """

    title: str
    kind: str = "text"
    rows: list[list[Any]] = field(default_factory=list)
    header: list[str] = field(default_factory=list)
    text: Any = ""
    figure: Any = None
    notes: str = ""
    column_widths: list[int] | None = None

    def is_table(self) -> bool:
        return self.kind == "table"

    def is_text(self) -> bool:
        return self.kind == "text"

    def is_chart(self) -> bool:
        return self.kind == "chart"


# =============================================================================
# Helpers
# =============================================================================


def report_summary_header(ctx: ReportContext) -> str:
    """Plain-text rendering of the header (useful for logs / PDF page 1)."""
    return "\n".join(ctx.header_lines())


def _safe_cell_value(v: Any) -> Any:
    """Coerce a value so openpyxl accepts it."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    return str(v)


def validate_manifest_for_export(
    manifest: dict[str, Any] | None,
    *,
    auto: bool = False,
    logger_obj: logging.Logger | None = None,
    module_name: str = "",
) -> tuple[bool, list[str]]:
    from certus.utils.certus_data import get_missing_manifest_fields

    missing = get_missing_manifest_fields(manifest)
    if missing and logger_obj:
        missing_txt = ", ".join(missing)
        prefix = f"[{module_name}.export] " if module_name else ""
        logger_obj.error(
            "%sblocked export | reason=incomplete manifest | missing=%s | auto=%s",
            prefix,
            missing_txt,
            auto,
        )
    return (len(missing) == 0), missing


def build_report_context(
    *,
    module_name: str,
    title: str,
    rmse: float | None = None,
    subtitle: str = "",
    app_name: str = "CERTUS",
    author: str = "",
    source_paths: list[str] | None = None,
    run_manifest: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    status: str | None = None,
) -> ReportContext:
    manifest = dict(run_manifest or {})
    if source_paths is not None:
        manifest.setdefault("source_paths", source_paths)
    if warnings:
        manifest.setdefault("warnings", warnings)
    if status:
        manifest.setdefault("status", status)
    if rmse is not None:
        manifest.setdefault("rmse", rmse)
    manifest.setdefault("module_name", module_name)
    return ReportContext(
        title=title,
        subtitle=subtitle,
        app_name=app_name,
        author=author,
        run_manifest=manifest or None,
    )


def build_report_sections(
    *,
    summary: dict[str, Any],
    solution_rows: list[dict[str, Any]] | None = None,
    spectra_df: pd.DataFrame | None = None,
    manifest: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> list[Section]:
    sections: list[Section] = []
    summary_rows = [[k, _safe_cell_value(v)] for k, v in summary.items()]
    sections.append(Section(title="Summary", kind="table", header=["Parameter", "Value"], rows=summary_rows))
    if solution_rows:
        sol_rows = [[_safe_cell_value(r.get("Parameter")), _safe_cell_value(r.get("Value"))] for r in solution_rows]
        sections.append(Section(title="Solution", kind="table", header=["Parameter", "Value"], rows=sol_rows))
    if spectra_df is not None and isinstance(spectra_df, pd.DataFrame) and not spectra_df.empty:
        rows = spectra_df.head(500).astype(object).where(pd.notna(spectra_df.head(500)), None).values.tolist()
        sections.append(Section(title="Spectra", kind="table", header=list(spectra_df.columns), rows=rows))
    if manifest:
        manifest_rows = [[k, _safe_cell_value(v)] for k, v in manifest.items()]
        sections.append(Section(title="Manifest", kind="table", header=["Key", "Value"], rows=manifest_rows))
    if notes:
        sections.append(Section(title="Notes", kind="text", text="\n".join(str(n) for n in notes)))
    return sections


def export_report_bundle(
    *,
    ctx: ReportContext,
    sections: list[Section],
    output_dir: str,
    base_name: str,
    logger_obj: logging.Logger | None = None,
    export_excel: bool = True,
    export_pdf: bool = False,
) -> dict[str, str | None]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, str | None] = {"excel": None, "pdf": None}
    if export_excel:
        result["excel"] = build_excel_report(ctx, sections, str(out_dir / f"{base_name}.xlsx"))
        if logger_obj:
            logger_obj.info("Excel report saved: %s", Path(result["excel"]).name)
    if export_pdf:
        result["pdf"] = build_pdf_report(ctx, sections, str(out_dir / f"{base_name}.pdf"))
        if logger_obj:
            logger_obj.info("PDF report saved: %s", Path(result["pdf"]).name)
    return result


# =============================================================================
# Excel backend (openpyxl)
# =============================================================================


def build_excel_report(
    ctx: ReportContext,
    sections: Iterable[Section],
    output_path: str,
) -> str:
    """Render ``sections`` to a styled ``.xlsx`` file.

    Returns the absolute output path. Raises :class:`ImportError` if
    ``openpyxl`` is not available.
    """
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise ImportError("openpyxl is required for Excel export") from e

    wb = openpyxl.Workbook()
    # Remove the default empty sheet; we'll add one per section + cover.
    default = wb.active
    wb.remove(default)

    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_fill = PatternFill("solid", fgColor=BRAND_COLORS["primary"].lstrip("#"))
    hdr_font = Font(bold=True, color="FFFFFF", size=11)
    title_font = Font(bold=True, size=14, color=BRAND_COLORS["primary"].lstrip("#"))
    sub_font = Font(italic=True, size=10, color=BRAND_COLORS["muted"].lstrip("#"))
    alt_fill = PatternFill("solid", fgColor=BRAND_COLORS["alt_row"].lstrip("#"))

    # -- Cover sheet ------------------------------------------------------
    cover = wb.create_sheet("Summary")
    cover["A1"] = ctx.title
    cover["A1"].font = title_font
    cover.merge_cells("A1:F1")
    if ctx.subtitle:
        cover["A2"] = ctx.subtitle
        cover["A2"].font = sub_font
        cover.merge_cells("A2:F2")
    row = 4
    for line in ctx.header_lines()[1:]:
        cover.cell(row=row, column=1, value=line).font = sub_font
        cover.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1
    cover.column_dimensions["A"].width = 28

    # -- Optional manifest sheet -----------------------------------------
    if ctx.run_manifest is not None:
        manifest_sheet = wb.create_sheet("Manifest")
        manifest_sheet["A1"] = "Manifest"
        manifest_sheet["A1"].font = title_font
        manifest_sheet["A3"] = "Key"
        manifest_sheet["B3"] = "Value"
        manifest_sheet["A3"].font = hdr_font
        manifest_sheet["B3"].font = hdr_font
        manifest_sheet["A3"].fill = hdr_fill
        manifest_sheet["B3"].fill = hdr_fill
        manifest_sheet["A3"].border = border
        manifest_sheet["B3"].border = border

        raw_manifest = ctx.run_manifest
        if hasattr(raw_manifest, "as_flat_dict"):
            items = list(raw_manifest.as_flat_dict().items())
        elif isinstance(raw_manifest, dict):
            items = list(raw_manifest.items())
        else:
            items = [("manifest", str(raw_manifest))]
        row_idx = 4
        for i, (k, v) in enumerate(items):
            c1 = manifest_sheet.cell(row=row_idx, column=1, value=str(k))
            c2 = manifest_sheet.cell(row=row_idx, column=2, value=_safe_cell_value(v))
            c1.border = border
            c2.border = border
            if i % 2 == 1:
                c1.fill = alt_fill
                c2.fill = alt_fill
            row_idx += 1
        manifest_sheet.column_dimensions["A"].width = 28
        manifest_sheet.column_dimensions["B"].width = 90

    # -- Sections ---------------------------------------------------------
    sections = list(sections)
    if not sections:
        cover.cell(row=row + 1, column=1, value="(no content)").font = sub_font

    for sec in sections:
        sheet_name = (sec.title or "Section")[:28] or "Section"
        # Ensure unique name
        existing = set(wb.sheetnames)
        name = sheet_name
        idx = 2
        while name in existing:
            name = f"{sheet_name[:25]} ({idx})"
            idx += 1
        ws = wb.create_sheet(name)

        ws["A1"] = sec.title
        ws["A1"].font = title_font
        ws.merge_cells("A1:F1")

        if sec.is_table():
            r = 3
            # Header
            if sec.header:
                for c, name in enumerate(sec.header, start=1):
                    cell = ws.cell(row=r, column=c, value=str(name))
                    cell.font = hdr_font
                    cell.fill = hdr_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = border
                r += 1
            # Rows
            for i, row_data in enumerate(sec.rows):
                for c, v in enumerate(row_data, start=1):
                    cell = ws.cell(row=r, column=c, value=_safe_cell_value(v))
                    cell.border = border
                    if i % 2 == 1:
                        cell.fill = alt_fill
                r += 1
            # Column widths
            n_cols = max(len(sec.header), max((len(r) for r in sec.rows), default=0))
            for c in range(1, max(n_cols, 1) + 1):
                letter = get_column_letter(c)
                if sec.column_widths and c - 1 < len(sec.column_widths):
                    ws.column_dimensions[letter].width = int(sec.column_widths[c - 1])
                else:
                    ws.column_dimensions[letter].width = 18

        elif sec.is_chart():
            # Try to embed figure as image on the sheet.
            img_path = None
            try:
                import tempfile

                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                if sec.figure is not None and hasattr(sec.figure, "savefig"):
                    sec.figure.savefig(tmp.name, dpi=120, bbox_inches="tight")
                    img_path = tmp.name
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                logger.debug("Excel chart rendering skipped (savefig failed): %s", exc)
                img_path = None
            if img_path and Path(img_path).exists():
                try:
                    from openpyxl.drawing.image import Image as XLImage

                    img = XLImage(img_path)
                    ws.add_image(img, "A3")
                except (ImportError, OSError, RuntimeError, ValueError, TypeError) as exc:
                    logger.debug("Excel chart embedding failed, using placeholder: %s", exc)
                    ws.cell(row=3, column=1, value="(chart unavailable)").font = sub_font
            else:
                ws.cell(row=3, column=1, value="(chart unavailable)").font = sub_font

        else:  # text
            content = sec.text
            if isinstance(content, str):
                paragraphs = [content]
            else:
                try:
                    paragraphs = list(content)
                except TypeError:
                    paragraphs = [str(content)]
            r = 3
            for p in paragraphs:
                ws.cell(row=r, column=1, value=str(p)).alignment = Alignment(wrap_text=True)
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
                r += 1
            ws.column_dimensions["A"].width = 80

        if sec.notes:
            nr = ws.max_row + 2
            cell = ws.cell(row=nr, column=1, value=f"Notes: {sec.notes}")
            cell.font = sub_font

    output_path = str(Path(output_path).resolve(strict=False))
    wb.save(output_path)
    return output_path


# =============================================================================
# PDF backend (matplotlib PdfPages)
# =============================================================================


def build_pdf_report(
    ctx: ReportContext,
    sections: Iterable[Section],
    output_path: str,
) -> str:
    """Render ``sections`` to a styled multi-page ``.pdf`` file.

    Uses matplotlib's ``PdfPages`` so no extra dependency is required.
    """
    try:
        from certus.core.certus_lazy_imports import lazy_matplotlib, lazy_matplotlib_pyplot

        matplotlib = lazy_matplotlib()
        matplotlib.use("Agg", force=False)
        plt = lazy_matplotlib_pyplot()
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError as e:
        raise ImportError("matplotlib is required for PDF export") from e

    output_path = str(Path(output_path).resolve(strict=False))
    sections = list(sections)

    with PdfPages(output_path) as pdf:
        # -- Cover page ---------------------------------------------------
        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait
        ax.axis("off")
        # Brand band
        band = plt.Rectangle((0, 0.90), 1, 0.10, transform=ax.transAxes, color=BRAND_COLORS["primary"], zorder=1)
        ax.add_patch(band)
        # Title
        ax.text(
            0.05, 0.78, ctx.title, fontsize=22, fontweight="bold", color=BRAND_COLORS["primary"], transform=ax.transAxes
        )
        if ctx.subtitle:
            ax.text(
                0.05,
                0.74,
                ctx.subtitle,
                fontsize=13,
                color=BRAND_COLORS["muted"],
                style="italic",
                transform=ax.transAxes,
            )
        # Meta
        y = 0.60
        for line in ctx.header_lines()[1:]:
            ax.text(0.05, y, line, fontsize=10, color=BRAND_COLORS["text"], transform=ax.transAxes)
            y -= 0.025
        if ctx.run_manifest is not None:
            raw_manifest = ctx.run_manifest
            if hasattr(raw_manifest, "as_flat_dict"):
                manifest_dict = dict(raw_manifest.as_flat_dict())
            elif isinstance(raw_manifest, dict):
                manifest_dict = dict(raw_manifest)
            else:
                manifest_dict = {"manifest": str(raw_manifest)}
            manifest_lines = []
            for key in ("run_id", "seed", "status", "started_at_utc", "params_hash"):
                if key in manifest_dict and manifest_dict[key] not in (None, ""):
                    manifest_lines.append(f"{key}: {manifest_dict[key]}")
            if manifest_lines:
                ax.text(
                    0.05,
                    y - 0.01,
                    "Manifest\n" + "\n".join(manifest_lines[:6]),
                    fontsize=9,
                    color=BRAND_COLORS["text"],
                    transform=ax.transAxes,
                )
        # Summary counts
        n_tables = sum(1 for s in sections if s.is_table())
        n_charts = sum(1 for s in sections if s.is_chart())
        n_text = sum(1 for s in sections if s.is_text())
        ax.text(
            0.05,
            0.40,
            "Contents",
            fontsize=14,
            fontweight="bold",
            color=BRAND_COLORS["primary"],
            transform=ax.transAxes,
        )
        ax.text(
            0.05,
            0.36,
            f"- {n_tables} table(s)\n- {n_charts} chart(s)\n- {n_text} text block(s)",
            fontsize=10,
            color=BRAND_COLORS["text"],
            transform=ax.transAxes,
        )
        # Footer
        ax.text(
            0.5,
            0.05,
            f"CERTUS {ctx.app_name} - Premium Report",
            fontsize=9,
            ha="center",
            color="white",
            transform=ax.transAxes,
            bbox=dict(facecolor=BRAND_COLORS["primary"], edgecolor="none", boxstyle="round,pad=0.4"),
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        if not sections:
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis("off")
            ax.text(
                0.5, 0.5, "(no content)", fontsize=14, ha="center", color=BRAND_COLORS["muted"], transform=ax.transAxes
            )
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        # -- Section pages -----------------------------------------------
        for sec in sections:
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis("off")
            # Page header strip
            strip = plt.Rectangle(
                (0, 0.94), 1, 0.06, transform=ax.transAxes, color=BRAND_COLORS["primary_soft"], zorder=1
            )
            ax.add_patch(strip)
            ax.text(
                0.02,
                0.965,
                sec.title,
                fontsize=12,
                fontweight="bold",
                color=BRAND_COLORS["primary"],
                transform=ax.transAxes,
            )
            ax.text(
                0.98, 0.965, ctx.app_name, fontsize=9, ha="right", color=BRAND_COLORS["muted"], transform=ax.transAxes
            )

            if sec.is_table():
                _render_pdf_table(ax, sec)
            elif sec.is_chart():
                _render_pdf_chart(ax, sec)
            else:
                _render_pdf_text(ax, sec)

            if sec.notes:
                ax.text(
                    0.5,
                    0.03,
                    f"Notes: {sec.notes}",
                    fontsize=8,
                    ha="center",
                    color=BRAND_COLORS["muted"],
                    style="italic",
                    transform=ax.transAxes,
                )
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        pdf.infodict()["Title"] = ctx.title
        pdf.infodict()["Author"] = ctx.author or "CERTUS"
        pdf.infodict()["Subject"] = ctx.subtitle or ""

    return output_path


def _render_pdf_table(ax, sec: Section) -> None:
    rows = sec.rows or []
    header = sec.header or []
    if not rows and not header:
        ax.text(0.5, 0.5, "(no rows)", fontsize=11, ha="center", color=BRAND_COLORS["muted"])
        return
    # Build the table-like cells for matplotlib
    cell_text = [[str(c) for c in r] for r in rows]
    col_labels = [str(c) for c in header] if header else None
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    table = ax.table(
        cellText=cell_text if cell_text else [[" "]],
        colLabels=col_labels,
        loc="upper center",
        cellLoc="center",
        colLoc="center",
        bbox=[0.02, 0.05, 0.96, 0.85],
    )
    # Style header
    if col_labels:
        for j in range(len(col_labels)):
            cell = table[(0, j)]
            cell.set_facecolor(BRAND_COLORS["primary"])
            cell.set_text_props(color="white", weight="bold")
    # Alternate row colors
    for i, _ in enumerate(cell_text):
        for j in range(len(cell_text[0]) if cell_text else 0):
            c = table[(i + (1 if col_labels else 0), j)]
            if i % 2 == 1:
                c.set_facecolor(BRAND_COLORS["alt_row"])
    table.auto_set_font_size(False)
    table.set_fontsize(8)


def _render_pdf_text(ax, sec: Section) -> None:
    txt = sec.text
    if isinstance(txt, str):
        paragraphs = [txt]
    else:
        try:
            paragraphs = list(txt)
        except TypeError:
            paragraphs = [str(txt)]
    y = 0.88
    for p in paragraphs:
        ax.text(0.05, y, str(p), fontsize=10, va="top", wrap=True, color=BRAND_COLORS["text"])
        y -= 0.06


def _render_pdf_chart(ax, sec: Section) -> None:
    fig_obj = sec.figure
    if fig_obj is None or not hasattr(fig_obj, "savefig"):
        ax.text(0.5, 0.5, "(chart unavailable)", fontsize=11, ha="center", color=BRAND_COLORS["muted"])
        return
    try:
        import io
        from certus.core.certus_lazy_imports import lazy_matplotlib

        matplotlib = lazy_matplotlib()
        mpimg = matplotlib.image

        buf = io.BytesIO()
        fig_obj.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        img = mpimg.imread(buf, format="png")
        ax.imshow(img, extent=[0.05, 0.95, 0.05, 0.92], aspect="auto", transform=ax.transAxes)
    except (ImportError, OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.debug("PDF chart rendering failed, using placeholder: %s", exc)
        ax.text(0.5, 0.5, "(chart unavailable)", fontsize=11, ha="center", color=BRAND_COLORS["muted"])


__all__ = [
    "BRAND_COLORS",
    "ReportContext",
    "Section",
    "report_summary_header",
    "build_excel_report",
    "build_pdf_report",
]
