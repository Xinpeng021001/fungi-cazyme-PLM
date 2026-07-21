#!/usr/bin/env python3
"""Render the tracked Chinese ESMC integration report to a portable PDF."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DEFAULT_INPUT = Path("docs/esmc_2026_integration_report_zh.md")
DEFAULT_OUTPUT = Path("output/pdf/esmc_2026_integration_report_zh.pdf")
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)
NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#117C7A")
PALE_TEAL = colors.HexColor("#E9F5F3")
PALE_BLUE = colors.HexColor("#EEF3F8")
INK = colors.HexColor("#24313D")
MUTED = colors.HexColor("#617180")
LINE = colors.HexColor("#CAD5DF")


def _register_font(explicit: Path | None) -> str:
    candidates = (explicit,) if explicit else FONT_CANDIDATES
    for candidate in candidates:
        if candidate and candidate.is_file():
            try:
                pdfmetrics.registerFont(TTFont("FCPLMUnicode", str(candidate)))
                return "FCPLMUnicode"
            except Exception:
                continue
    raise FileNotFoundError(
        "No usable Unicode font found. Pass --font /path/to/a/Chinese-capable.ttf"
    )


def _inline_markup(value: str) -> str:
    """Convert the small inline Markdown subset used by the report."""

    placeholders: dict[str, str] = {}

    def stash(fragment: str) -> str:
        key = f"@@FCPLM{len(placeholders)}@@"
        placeholders[key] = fragment
        return key

    def link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        return stash(f'<a href="{href}" color="#117C7A">{label}</a>')

    def code(match: re.Match[str]) -> str:
        content = html.escape(match.group(1))
        return stash(f'<font name="FCPLMUnicode" color="#7A3E00">{content}</font>')

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = re.sub(r"`([^`]+)`", code, value)
    value = html.escape(value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    for key, fragment in placeholders.items():
        value = value.replace(html.escape(key), fragment)
    return value


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=27,
            leading=37,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=10 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=12.5,
            leading=21,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=font_name,
            fontSize=20,
            leading=27,
            textColor=NAVY,
            spaceBefore=8 * mm,
            spaceAfter=4 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=15.5,
            leading=22,
            textColor=NAVY,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName=font_name,
            fontSize=12.5,
            leading=18,
            textColor=TEAL,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=16,
            textColor=INK,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            spaceAfter=2.2 * mm,
        ),
        "list": ParagraphStyle(
            "List",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.2,
            leading=15,
            textColor=INK,
            leftIndent=7 * mm,
            firstLineIndent=-4 * mm,
            wordWrap="CJK",
            spaceAfter=1.2 * mm,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.4,
            leading=16,
            textColor=NAVY,
            leftIndent=6 * mm,
            rightIndent=4 * mm,
            borderColor=TEAL,
            borderWidth=0,
            borderPadding=4 * mm,
            backColor=PALE_TEAL,
            wordWrap="CJK",
            spaceBefore=2 * mm,
            spaceAfter=4 * mm,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName=font_name,
            fontSize=7.8,
            leading=12,
            textColor=INK,
            leftIndent=4 * mm,
            rightIndent=4 * mm,
            borderPadding=3 * mm,
            backColor=PALE_BLUE,
            wordWrap="CJK",
            spaceBefore=1.5 * mm,
            spaceAfter=3 * mm,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7.5,
            leading=10.5,
            textColor=colors.white,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7.2,
            leading=10.5,
            textColor=INK,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=16,
            textColor=MUTED,
            wordWrap="CJK",
            spaceAfter=1 * mm,
        ),
    }


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _table_flowable(
    lines: list[str], styles: dict[str, ParagraphStyle], available_width: float
) -> Table:
    parsed = [_split_table_row(line) for line in lines]
    if len(parsed) > 1 and _is_table_separator(lines[1]):
        parsed.pop(1)
    width = max(len(row) for row in parsed)
    normalized = [row + [""] * (width - len(row)) for row in parsed]
    data = []
    for row_index, row in enumerate(normalized):
        style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        data.append([Paragraph(_inline_markup(cell), style) for cell in row])
    column_widths = [available_width / width] * width
    table = Table(data, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
            ]
        )
    )
    return table


def _paragraph(lines: Iterable[str], style: ParagraphStyle) -> Paragraph:
    text = " ".join(part.strip() for part in lines if part.strip())
    return Paragraph(_inline_markup(text), style)


def _parse_markdown(
    text: str, styles: dict[str, ParagraphStyle], available_width: float
) -> tuple[str, list[object]]:
    lines = text.splitlines()
    title = "ESM Cambrian × fungi-cazyme-PLM 项目集成报告"
    story: list[object] = []
    paragraph_lines: list[str] = []
    index = 0
    skipped_title = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            story.append(_paragraph(paragraph_lines, styles["body"]))
            paragraph_lines = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            code_html = "<br/>".join(html.escape(part) or "&nbsp;" for part in code_lines)
            story.append(Paragraph(code_html, styles["code"]))
            index += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            flush_paragraph()
            table_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and "|" in candidate[1:]):
                    break
                table_lines.append(candidate)
                index += 1
            story.append(_table_flowable(table_lines, styles, available_width))
            story.append(Spacer(1, 3 * mm))
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            value = heading.group(2)
            if level == 1 and not skipped_title:
                title = value
                skipped_title = True
            else:
                story.append(Paragraph(_inline_markup(value), styles[f"h{level}"]))
            index += 1
            continue

        if stripped == "---":
            flush_paragraph()
            story.append(Spacer(1, 2 * mm))
            story.append(HRFlowable(width="100%", thickness=0.7, color=LINE))
            story.append(Spacer(1, 2 * mm))
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip()[1:].strip())
                index += 1
            story.append(_paragraph(quote_lines, styles["quote"]))
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            marker = "•" if bullet else f"{numbered.group(1)}."
            content = bullet.group(1) if bullet else numbered.group(2)
            story.append(Paragraph(f"{marker}&nbsp;&nbsp;{_inline_markup(content)}", styles["list"]))
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped.startswith("**") and stripped.endswith("  "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped), styles["meta"]))
            index += 1
            continue

        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    return title, story


def _draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
        canvas.setFont("FCPLMUnicode", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, height - 10.5 * mm, "dbCAN-SF | ESMC 2026 integration report")
    canvas.setFont("FCPLMUnicode", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"{doc.page}")
    canvas.drawString(18 * mm, 10 * mm, "2026-07-21 | design and evidence review")
    canvas.restoreState()


def render(input_path: Path, output_path: Path, font_path: Path | None) -> None:
    font_name = _register_font(font_path)
    styles = _styles(font_name)
    source = input_path.read_text(encoding="utf-8")
    available_width = A4[0] - 36 * mm
    title, content = _parse_markdown(source, styles, available_width)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=17 * mm,
        title=title,
        author="dbCAN-SF project",
        subject="Evidence review and implementation plan for ESM Cambrian in fungal CAZyme annotation",
        creator="scripts/report/render_esmc_report.py",
        pageCompression=1,
    )

    cover = [
        Spacer(1, 32 * mm),
        HRFlowable(width=42 * mm, thickness=4, color=TEAL, hAlign="LEFT"),
        Spacer(1, 9 * mm),
        Paragraph(_inline_markup(title), styles["cover_title"]),
        Paragraph(
            "Evidence review, task mapping, architecture, evaluation, risk, compute budget, "
            "and reproducible execution on met.unl.edu",
            styles["cover_subtitle"],
        ),
        Spacer(1, 26 * mm),
        Table(
            [
                [Paragraph("PROJECT", styles["table_header"]), Paragraph("dbCAN-SF / fungi-cazyme-PLM", styles["table_cell"])],
                [Paragraph("VERSION", styles["table_header"]), Paragraph("1.0 - 2026-07-21", styles["table_cell"])],
                [Paragraph("STATUS", styles["table_header"]), Paragraph("Design complete; model training not authorized", styles["table_cell"])],
                [Paragraph("PRIMARY DECISION", styles["table_header"]), Paragraph("ESMC 600M sequence-first; 6B SAE as B8; structure selective", styles["table_cell"])],
            ],
            colWidths=[38 * mm, 116 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), NAVY),
                    ("BACKGROUND", (1, 0), (1, -1), PALE_BLUE),
                    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 35 * mm),
        Paragraph(
            "Primary evidence: Candido et al. 2026 preprint; Biohub official tutorials and current release; "
            "promoted fungi-cazyme-PLM Phase 0 artifacts.",
            styles["meta"],
        ),
        PageBreak(),
    ]

    doc.build(cover + content, onFirstPage=_draw_page, onLaterPages=_draw_page)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    render(args.input.resolve(), args.output.resolve(), args.font)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

