"""
marketmate.mate.tools.pdf_creator
──────────────────────────────────
High-grade PDF document creation tool for MATE's tool-calling agent.

Generates professional-quality PDF documents with:
  - Cover page with title, subtitle, and date
  - Table of contents (for multi-section documents)
  - Rich text formatting: headers, paragraphs, bullet lists, numbered lists
  - Bold, italic, and underline text via inline markup
  - Page numbers and professional typography
  - Automatic page breaks between sections
  - MarketMate branding on cover page

Uses ReportLab — the industry-standard Python PDF library.

Content format:
  The `sections` parameter accepts a JSON array of section objects:
  [
    {
      "heading": "Section Title",
      "body": "Paragraph text with **bold** and __italic__ markup..."
    },
    {
      "heading": "Another Section",
      "body": "- Bullet point one\\n- Bullet point two\\n- Bullet point three"
    }
  ]

  Inline markup:
    **text**   → bold
    __text__   → italic
    ~~text~~   → underline

  List detection:
    Lines starting with "- " or "* " are rendered as bullet lists
    Lines starting with "1. ", "2. ", etc. are rendered as numbered lists

Architecture:
  User asks "Create a PDF about X"
       ↓
  MATE gathers info (web_search, read_url, knowledge)
       ↓
  MATE calls create_pdf(title="...", subtitle="...", sections=[...])
       ↓
  PDF generated and saved to /tmp/mate_pdfs/
       ↓
  Handler sends PDF as Telegram document
       ↓
  User receives a professional PDF file
"""

from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("mate.tools.pdf_creator")

# PDF output directory
_PDF_DIR = os.path.join(os.environ.get("RENDER_TMP", "/tmp"), "mate_pdfs")

# Ensure directory exists
os.makedirs(_PDF_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Repair — handles truncated sections JSON from LLM
# ═══════════════════════════════════════════════════════════════════════════════

def _repair_truncated_json(raw: str) -> list:
    """
    Try to recover a usable list of section objects from truncated JSON.

    When the LLM's max_tokens cuts off the JSON mid-section, this function
    finds the last complete {"heading": "...", "body": "..."} object and
    returns all complete objects found.

    Returns:
        List of valid section dicts, or None if no valid objects found.
    """
    if not raw:
        return None

    # Strategy 1: Find all complete JSON objects with "heading" and "body"
    # Match {"heading": "...", "body": "..."} objects
    pattern = r'\{\s*"heading"\s*:\s*"[^"]*"\s*,\s*"body"\s*:\s*"[^"]*"\s*\}'
    matches = re.findall(pattern, raw, re.DOTALL)

    if matches:
        sections = []
        for match in matches:
            try:
                obj = json.loads(match)
                if "heading" in obj and "body" in obj:
                    sections.append(obj)
            except json.JSONDecodeError:
                continue
        if sections:
            return sections

    # Strategy 2: Try to close the truncated JSON
    # Count open braces/brackets and add closers
    open_braces = raw.count("{") - raw.count("}")
    open_brackets = raw.count("[") - raw.count("]")

    # Remove any incomplete string at the end
    repaired = raw.rstrip()
    if repaired.endswith('"'):
        # Check if this quote is opening or closing
        quote_count = repaired.count('"') - repaired.count('\\"')
        if quote_count % 2 == 1:
            repaired += '"'  # Close the open string

    # Close open braces
    for _ in range(max(0, open_braces)):
        repaired += "}"
    # Close open brackets
    for _ in range(max(0, open_brackets)):
        repaired += "]"

    try:
        result = json.loads(repaired)
        if isinstance(result, list) and result:
            # Validate each item has heading and body
            valid = [s for s in result if isinstance(s, dict) and "heading" in s and "body" in s]
            return valid if valid else None
        return None
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Main PDF Creation Function
# ═══════════════════════════════════════════════════════════════════════════════

async def create_pdf(
    title: str,
    sections: str,
    subtitle: str = "",
    author: str = "MarketMate Intelligence",
) -> Dict[str, Any]:
    """
    Create a professional PDF document.

    Args:
        title:    Document title (displayed on cover page and header)
        sections: JSON string array of section objects with "heading" and "body" keys.
                  Body text supports **bold**, __italic__, ~~underline~~ markup.
                  Lines starting with "- " become bullet lists.
                  Lines starting with "1. " become numbered lists.
        subtitle: Optional subtitle (displayed on cover page)
        author:   Document author (default: "MarketMate Intelligence")

    Returns:
        Dict with:
          - file_path: absolute path to the generated PDF
          - file_name: just the filename
          - title: document title
          - pages: estimated page count
          - sections_count: number of sections
        Or on failure:
          - error: description of the failure
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak,
            HRFlowable,
        )

    except ImportError as imp_err:
        log.error("pdf_creator_reportlab_missing", missing_module=str(imp_err))
        return {
            "error": (
                f"PDF creation is not available — missing dependency: {imp_err}. "
                "Contact support to resolve this."
            ),
        }

    # ── Parse sections JSON ─────────────────────────────────────────────────
    try:
        if isinstance(sections, str):
            # Try direct parse first
            try:
                sections_data = json.loads(sections)
            except json.JSONDecodeError:
                # LLM may have truncated the JSON — try to recover
                # Strategy: find the last complete object and close the array
                repaired = _repair_truncated_json(sections)
                if repaired:
                    sections_data = repaired
                    log.info("pdf_json_repaired", original_len=len(sections), repaired_sections=len(repaired))
                else:
                    return {"error": f"Invalid JSON in sections (truncated?). Try fewer sections with shorter content."}
        elif isinstance(sections, list):
            sections_data = sections
        else:
            return {"error": "sections must be a JSON array or string"}
    except Exception as e:
        return {"error": f"Failed to parse sections: {str(e)}"}

    if not sections_data or not isinstance(sections_data, list):
        return {"error": "sections must be a non-empty JSON array"}

    # ── Generate filename ───────────────────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^a-zA-Z0-9]", "_", title)[:40]
    file_name = f"MATE_{safe_title}_{timestamp}.pdf"
    file_path = os.path.join(_PDF_DIR, file_name)

    # ── Color Palette ───────────────────────────────────────────────────────
    COLOR_PRIMARY = HexColor("#1a1a2e")       # Deep navy
    COLOR_ACCENT = HexColor("#16213e")        # Dark blue
    COLOR_HIGHLIGHT = HexColor("#0f3460")     # Medium blue
    COLOR_GOLD = HexColor("#e2b714")          # MarketMate gold
    COLOR_TEXT = HexColor("#2c2c2c")          # Near-black
    COLOR_LIGHT_TEXT = HexColor("#666666")    # Gray
    COLOR_LINE = HexColor("#cccccc")          # Light gray

    # ── Build Document ──────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title=title,
        author=author,
    )

    # ── Custom Styles ───────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    # Cover title
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=28,
        leading=34,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=12,
        fontName="Helvetica-Bold",
    )

    # Cover subtitle
    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=14,
        leading=20,
        textColor=COLOR_HIGHLIGHT,
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName="Helvetica",
    )

    # Cover metadata
    cover_meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=COLOR_LIGHT_TEXT,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )

    # Section heading (H1)
    h1_style = ParagraphStyle(
        "MateH1",
        parent=styles["Heading1"],
        fontSize=18,
        leading=24,
        textColor=COLOR_PRIMARY,
        spaceBefore=20,
        spaceAfter=10,
        fontName="Helvetica-Bold",
        borderWidth=0,
        borderPadding=0,
    )

    # Sub-heading (H2)
    h2_style = ParagraphStyle(
        "MateH2",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=COLOR_HIGHLIGHT,
        spaceBefore=14,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )

    # Body text
    body_style = ParagraphStyle(
        "MateBody",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=16,
        textColor=COLOR_TEXT,
        alignment=TA_JUSTIFY,
        spaceBefore=4,
        spaceAfter=8,
        fontName="Helvetica",
    )

    # Bullet list item
    bullet_style = ParagraphStyle(
        "MateBullet",
        parent=body_style,
        leftIndent=24,
        bulletIndent=12,
        spaceBefore=2,
        spaceAfter=4,
    )

    # Numbered list item
    number_style = ParagraphStyle(
        "MateNumber",
        parent=body_style,
        leftIndent=24,
        bulletIndent=12,
        spaceBefore=2,
        spaceAfter=4,
    )

    # Footer note style
    note_style = ParagraphStyle(
        "MateNote",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=COLOR_LIGHT_TEXT,
        alignment=TA_LEFT,
        fontName="Helvetica-Oblique",
    )

    # ── Helper: Convert inline markup to ReportLab XML ──────────────────────
    def _format_rich_text(text: str) -> str:
        """Convert **bold**, __italic__, ~~underline~~ to ReportLab markup."""
        # Escape XML special characters first
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        # Bold: **text** → <b>text</b>
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Italic: __text__ → <i>text</i>
        text = re.sub(r"__(.+?)__", r"<i>\1</i>", text)
        # Underline: ~~text~~ → <u>text</u>
        text = re.sub(r"~~(.+?)~~", r"<u>\1</u>", text)

        return text

    # ── Helper: Parse body text into flowables ─────────────────────────────
    def _parse_body(body_text: str) -> list:
        """Parse body text into a list of ReportLab flowables."""
        flowables = []
        lines = body_text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Bullet list item
            if line.startswith("- ") or line.startswith("* "):
                text = _format_rich_text(line[2:])
                flowables.append(Paragraph(
                    f"<bullet>&bull;</bullet> {text}",
                    bullet_style,
                ))
                i += 1
                continue

            # Numbered list item (1. 2. 3. etc.)
            num_match = re.match(r"^(\d+)\.\s+(.+)$", line)
            if num_match:
                num = num_match.group(1)
                text = _format_rich_text(num_match.group(2))
                flowables.append(Paragraph(
                    f"<bullet>{num}.</bullet> {text}",
                    number_style,
                ))
                i += 1
                continue

            # Sub-heading (## at start of line)
            if line.startswith("## "):
                text = _format_rich_text(line[3:])
                flowables.append(Paragraph(text, h2_style))
                i += 1
                continue

            # Regular paragraph — collect consecutive non-empty, non-list lines
            para_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or next_line.startswith("- ") or next_line.startswith("* ") or next_line.startswith("## "):
                    break
                if re.match(r"^\d+\.\s+", next_line):
                    break
                para_lines.append(next_line)
                i += 1

            combined = " ".join(para_lines)
            text = _format_rich_text(combined)
            flowables.append(Paragraph(text, body_style))

        return flowables

    # ── Build Story ─────────────────────────────────────────────────────────
    story = []

    # ── Cover Page ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 2.5 * inch))

    # Decorative line above title
    story.append(HRFlowable(
        width="60%", thickness=2, color=COLOR_GOLD,
        spaceBefore=0, spaceAfter=20,
    ))

    story.append(Paragraph(_format_rich_text(title), cover_title_style))

    if subtitle:
        story.append(Paragraph(_format_rich_text(subtitle), cover_subtitle_style))

    # Decorative line below subtitle
    story.append(HRFlowable(
        width="60%", thickness=2, color=COLOR_GOLD,
        spaceBefore=20, spaceAfter=30,
    ))

    # Metadata
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")
    story.append(Paragraph(f"Generated: {date_str}", cover_meta_style))
    story.append(Paragraph(f"Author: {author}", cover_meta_style))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Powered by MarketMate Intelligence", cover_meta_style))

    # Page break after cover
    story.append(PageBreak())

    # ── Table of Contents (for documents with 3+ sections) ─────────────────
    if len(sections_data) >= 3:
        toc_heading = ParagraphStyle(
            "TOCHeading",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=COLOR_PRIMARY,
            spaceBefore=10,
            spaceAfter=16,
            fontName="Helvetica-Bold",
        )
        story.append(Paragraph("Table of Contents", toc_heading))
        story.append(Spacer(1, 8))

        for idx, section in enumerate(sections_data, 1):
            heading = section.get("heading", f"Section {idx}")
            toc_style = ParagraphStyle(
                f"TOC_{idx}",
                parent=styles["Normal"],
                fontSize=11,
                leading=18,
                textColor=COLOR_HIGHLIGHT,
                leftIndent=12,
                fontName="Helvetica",
            )
            story.append(Paragraph(f"{idx}. {_format_rich_text(heading)}", toc_style))

        story.append(PageBreak())

    # ── Content Sections ────────────────────────────────────────────────────
    for idx, section in enumerate(sections_data, 1):
        heading = section.get("heading", "")
        body = section.get("body", "")

        # Section heading with decorative line
        if heading:
            story.append(Paragraph(_format_rich_text(heading), h1_style))
            story.append(HRFlowable(
                width="100%", thickness=1, color=COLOR_LINE,
                spaceBefore=2, spaceAfter=10,
            ))

        # Body content
        if body:
            body_flowables = _parse_body(body)
            story.extend(body_flowables)

        # Spacer between sections (no page break — continuous flow)
        if idx < len(sections_data):
            story.append(Spacer(1, 16))

    # ── Footer note ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * inch))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=COLOR_LINE,
        spaceBefore=10, spaceAfter=8,
    ))
    story.append(Paragraph(
        f"This document was generated by MarketMate Intelligence on {date_str}. "
        "Content is based on AI-synthesized information and should be verified independently.",
        note_style,
    ))

    # ── Page number callback ────────────────────────────────────────────────
    def _add_page_number(canvas, doc):
        """Add page numbers and header/footer to each page."""
        page_num = canvas.getPageNumber()

        # Skip page number on cover page (page 1)
        if page_num <= 1:
            return

        # Footer: page number
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(COLOR_LIGHT_TEXT)
        canvas.drawCentredString(
            A4[0] / 2,
            0.5 * inch,
            f"Page {page_num - 1}",
        )

        # Header: document title (small, right-aligned)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(
            A4[0] - 1 * inch,
            A4[1] - 0.5 * inch,
            title[:60],
        )

        # Thin line below header
        canvas.setStrokeColor(COLOR_LINE)
        canvas.setLineWidth(0.5)
        canvas.line(
            1 * inch,
            A4[1] - 0.55 * inch,
            A4[0] - 1 * inch,
            A4[1] - 0.55 * inch,
        )

        canvas.restoreState()

    # ── Build PDF ───────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=_add_page_number)

    # ── Estimate page count ─────────────────────────────────────────────────
    file_size = os.path.getsize(file_path)
    estimated_pages = max(1, len(sections_data) // 2 + 2)  # rough estimate

    log.info(
        "pdf_created",
        title=title[:60],
        sections=len(sections_data),
        file_size=file_size,
        file_name=file_name,
    )

    return {
        "file_path": file_path,
        "file_name": file_name,
        "title": title,
        "pages": estimated_pages,
        "sections_count": len(sections_data),
        "file_size_bytes": file_size,
        "message": f"PDF created successfully: {title} ({len(sections_data)} sections)",
    }
