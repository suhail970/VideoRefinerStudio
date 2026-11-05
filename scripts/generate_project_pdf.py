"""Build the interactive VideoRefiner Studio project guide PDF."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = ROOT / "test_output" / "ui_workspace.png"
GUIDE_SCREENSHOT = SCREENSHOT
OUTPUT = ROOT / "docs" / "VideoRefiner_Studio_Project_Guide.pdf"

PAGE_W, PAGE_H = A4
MX = 20 * mm
MT = 22 * mm
MB = 18 * mm
CW = PAGE_W - 2 * MX
FRAME_H = PAGE_H - MT - MB

ACCENT = HexColor("#5B4BE6")
ACCENT_DARK = HexColor("#4335C8")
ACCENT_SOFT = HexColor("#EEEBFF")
INK = HexColor("#1D2030")
TEXT = HexColor("#343A4A")
MUTED = HexColor("#6B7280")
BORDER = HexColor("#E1E5EE")
BG = HexColor("#F7F8FC")
GREEN = HexColor("#1F9D6A")
GREEN_SOFT = HexColor("#E8F7F0")
AMBER = HexColor("#B7791F")
AMBER_SOFT = HexColor("#FFF7E6")
RED = HexColor("#D9485F")
RED_SOFT = HexColor("#FDECEF")
BLUE = HexColor("#2F6FED")
WHITE = colors.white

BODY = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=10.2,
    leading=15.2,
    textColor=TEXT,
    spaceAfter=7,
)
LEAD = ParagraphStyle(
    "Lead",
    parent=BODY,
    fontSize=12.2,
    leading=18,
    textColor=INK,
    spaceAfter=11,
)
SMALL = ParagraphStyle(
    "Small",
    parent=BODY,
    fontSize=8.4,
    leading=11.5,
    textColor=MUTED,
    spaceAfter=4,
)
CAPTION = ParagraphStyle(
    "Caption",
    parent=SMALL,
    fontSize=8.2,
    leading=11,
    textColor=MUTED,
)
H1 = ParagraphStyle(
    "H1",
    fontName="Helvetica-Bold",
    fontSize=23,
    leading=27,
    textColor=INK,
    spaceAfter=4,
)
H2 = ParagraphStyle(
    "H2",
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=17,
    textColor=INK,
    spaceBefore=12,
    spaceAfter=5,
)
H3 = ParagraphStyle(
    "H3",
    fontName="Helvetica-Bold",
    fontSize=10.4,
    leading=14,
    textColor=INK,
    spaceBefore=7,
    spaceAfter=2,
)
KICKER = ParagraphStyle(
    "Kicker",
    fontName="Helvetica-Bold",
    fontSize=7.4,
    leading=10,
    textColor=ACCENT,
    spaceAfter=5,
)
BULLET = ParagraphStyle(
    "Bullet",
    parent=BODY,
    leftIndent=13,
    bulletIndent=2,
    bulletFontName="Helvetica-Bold",
    bulletFontSize=9,
    bulletColor=ACCENT,
    spaceAfter=4,
)
TABLE_HEAD = ParagraphStyle(
    "TableHead",
    fontName="Helvetica-Bold",
    fontSize=8.3,
    leading=10.5,
    textColor=WHITE,
)
TABLE_BODY = ParagraphStyle(
    "TableBody",
    fontName="Helvetica",
    fontSize=8.5,
    leading=11.5,
    textColor=TEXT,
)
TABLE_BODY_BOLD = ParagraphStyle(
    "TableBodyBold",
    parent=TABLE_BODY,
    fontName="Helvetica-Bold",
    textColor=INK,
)
CARD_TITLE = ParagraphStyle(
    "CardTitle",
    fontName="Helvetica-Bold",
    fontSize=11.3,
    leading=14,
    textColor=INK,
    spaceAfter=4,
)
CARD_TEXT = ParagraphStyle(
    "CardText",
    fontName="Helvetica",
    fontSize=8.9,
    leading=12.4,
    textColor=TEXT,
)
CARD_NUM = ParagraphStyle(
    "CardNum",
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=11,
    textColor=ACCENT,
    spaceAfter=4,
)
CENTER = ParagraphStyle(
    "Center",
    parent=BODY,
    alignment=TA_CENTER,
)


def hexcolor(color: colors.Color) -> str:
    return "#" + color.hexval().replace("0x", "")


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def link(url: str, label: str | None = None) -> str:
    return f'<link href="{url}" color="#2F6FED">{label or url}</link>'


def section(num: str, title: str, intro: str) -> list:
    return [
        p(f'<font color="{hexcolor(ACCENT)}">{num}</font>  {title}', H1),
        HRFlowable(width="100%", thickness=0.8, color=BORDER, spaceBefore=2, spaceAfter=12),
        p(intro, LEAD),
    ]


def bullets(items: list[str]) -> list:
    return [Paragraph(item, BULLET, bulletText="\x95") for item in items]


def callout(title: str, text: str, kind: str = "info") -> Table:
    palette = {
        "info": (ACCENT, ACCENT_SOFT),
        "success": (GREEN, GREEN_SOFT),
        "warning": (AMBER, AMBER_SOFT),
        "danger": (RED, RED_SOFT),
    }
    line, fill = palette[kind]
    body = f'<b>{title}</b><br/>{text}' if title else text
    table = Table([[p(body, ParagraphStyle("Callout", parent=BODY, fontSize=9.2, leading=13.2))]], colWidths=[CW])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return table


def data_table(headers: list[str], rows: list[list[str]], widths: list[float], *, font: float = 8.5) -> Table:
    head = [p(h, TABLE_HEAD) for h in headers]
    body_style = ParagraphStyle("TableBodyCustom", parent=TABLE_BODY, fontSize=font, leading=font * 1.35)
    data = [head] + [[p(str(cell), body_style) for cell in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), BG))
    table.setStyle(TableStyle(commands))
    return table


def stat_strip(items: list[tuple[str, str]]) -> Table:
    cells = []
    for value, label in items:
        inner = Table(
            [
                [p(value, ParagraphStyle("StatValue", fontName="Helvetica-Bold", fontSize=19, leading=22, textColor=ACCENT))],
                [p(label, ParagraphStyle("StatLabel", fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED))],
            ],
            colWidths=[CW / len(items) - 10],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
                ]
            )
        )
        cells.append(inner)
    strip = Table([cells], colWidths=[CW / len(items)] * len(items), hAlign="LEFT")
    strip.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return strip


def card(number: str, title: str, text: str, width: float) -> Table:
    table = Table(
        [
            [p(number, CARD_NUM)],
            [p(title, CARD_TITLE)],
            [p(text, CARD_TEXT)],
        ],
        colWidths=[width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 1),
            ]
        )
    )
    return table


def feature_grid(items: list[tuple[str, str, str]]) -> Table:
    cell_w = CW / 2 - 5
    rows = []
    for i in range(0, len(items), 2):
        row = [card(*items[i], cell_w)]
        if i + 1 < len(items):
            row.append(card(*items[i + 1], cell_w))
        else:
            row.append(Spacer(1, 1))
        rows.append(row)
    grid = Table(rows, colWidths=[CW / 2, CW / 2], hAlign="LEFT")
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return grid


class ArchitectureDiagram(Flowable):
    def __init__(self, width: float = CW) -> None:
        super().__init__()
        self.width = width
        self.height = 146

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(BG)
        c.roundRect(0, 0, self.width, self.height, 8, stroke=0, fill=1)
        labels = [
            ("GUI", "CustomTkinter"),
            ("Jobs", "Threads + queue"),
            ("Jasna", "Scan / restore"),
            ("GPU", "CUDA / TensorRT"),
            ("Media", "PyAV / FFmpeg"),
        ]
        box_w = (self.width - 48) / 5
        box_h = 53
        y = 58
        for index, (title, sub) in enumerate(labels):
            x = 12 + index * (box_w + 9)
            c.setFillColor(WHITE)
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.7)
            c.roundRect(x, y, box_w, box_h, 5, stroke=1, fill=1)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x + box_w / 2, y + 33, title)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 6.8)
            c.drawCentredString(x + box_w / 2, y + 18, sub)
            if index < len(labels) - 1:
                ax1 = x + box_w + 1
                ax2 = x + box_w + 8
                ay = y + box_h / 2
                c.setStrokeColor(ACCENT)
                c.setLineWidth(1)
                c.line(ax1, ay, ax2, ay)
                c.setFillColor(ACCENT)
                path = c.beginPath()
                path.moveTo(ax2, ay)
                path.lineTo(ax2 - 3, ay + 2.5)
                path.lineTo(ax2 - 3, ay - 2.5)
                path.close()
                c.drawPath(path, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(12, 128, "CONTROL PATH")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.2)
        c.drawRightString(self.width - 12, 128, "The UI stays responsive while jobs run")
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.line(12, 123, self.width - 12, 123)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.4)
        c.drawString(12, 20, "The queue sends progress back to the UI. Heavy work never runs on the window thread.")
        c.restoreState()


class Checklist(Flowable):
    def __init__(self, items: list[str], width: float = CW) -> None:
        super().__init__()
        self.items = items
        self.width = width
        self.height = len(items) * 23 + 8

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        y = self.height - 17
        for index, label in enumerate(self.items, start=1):
            c.setFillColor(WHITE)
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.45)
            c.rect(0, y - 3, self.width, 21, stroke=1, fill=1)
            c.acroForm.checkbox(
                name=f"setup_check_{index}",
                tooltip=label,
                x=7,
                y=y + 1,
                size=11,
                checked=False,
                buttonStyle="check",
                borderColor=BORDER,
                fillColor=WHITE,
                textColor=ACCENT,
                borderWidth=0.8,
                forceBorder=True,
                fieldFlags="",
                relative=True,
            )
            c.setFillColor(TEXT)
            c.setFont("Helvetica", 9.2)
            c.drawString(27, y + 3, label)
            y -= 23
        c.restoreState()


class CoverPage(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = PAGE_W
        self.height = PAGE_H

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return 1, 1

    def draw(self) -> None:
        pass


class GuideDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs) -> None:
        super().__init__(filename, **kwargs)
        cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover_frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        body_frame = Frame(MX, MB, CW, FRAME_H, id="body_frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[cover_frame], onPage=self._draw_cover),
                PageTemplate(id="body", frames=[body_frame], onPage=self._draw_body_page),
            ]
        )
        self._key_counts: dict[str, int] = {}

    def beforeDocument(self) -> None:
        self._key_counts = {}

    def _key_for(self, prefix: str, plain: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:44] or "section"
        base = f"{prefix}-{slug}"
        count = self._key_counts.get(base, 0) + 1
        self._key_counts[base] = count
        return f"{base}-{count}"

    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        plain = flowable.getPlainText().strip()
        if style == "H1":
            if plain.lower() == "contents":
                key = "contents"
            else:
                key = self._key_for("section", plain)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(plain, key, level=0, closed=False)
            if plain.lower() != "contents":
                self.notify("TOCEntry", (0, plain, self.page, key))
        elif style == "H2":
            key = self._key_for("topic", plain)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(plain, key, level=1, closed=False)

    def _draw_cover(self, canvas, doc) -> None:
        c = canvas
        c.saveState()
        c.setFillColor(BG)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        c.setFillColor(colors.Color(0.357, 0.294, 0.902, alpha=0.075))
        c.circle(PAGE_W - 22, PAGE_H - 38, 155, stroke=0, fill=1)
        c.circle(PAGE_W - 70, 170, 112, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, 0, 8, PAGE_H, stroke=0, fill=1)

        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(MX, PAGE_H - 52, "PROJECT GUIDE  /  OCTOBER 2026")
        c.drawRightString(PAGE_W - MX, PAGE_H - 52, "INTERACTIVE PDF")

        c.setFillColor(ACCENT)
        c.roundRect(MX, PAGE_H - 130, 46, 46, 10, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 19)
        c.drawCentredString(MX + 23, PAGE_H - 113, "VR")

        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 35)
        c.drawString(MX, PAGE_H - 190, "VideoRefiner")
        c.drawString(MX, PAGE_H - 229, "Studio")
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(MX, PAGE_H - 258, "A local Windows app for mosaic detection and video restoration.")

        c.setFillColor(TEXT)
        c.setFont("Helvetica", 11.2)
        c.drawString(MX, PAGE_H - 292, "Find mosaic areas, restore them with AI, compare the result, and export safely.")
        c.drawString(MX, PAGE_H - 309, "Everything stays on your computer. No cloud. No account. No telemetry.")

        chips = [("PRODUCT GUIDE", ACCENT_SOFT, ACCENT), ("TECHNICAL HANDOFF", BG, MUTED), ("TEST REPORT", GREEN_SOFT, GREEN)]
        chip_x = MX
        for label, fill, text_color in chips:
            width = stringWidth(label, "Helvetica-Bold", 7) + 22
            c.setFillColor(fill)
            c.setStrokeColor(BORDER)
            c.roundRect(chip_x, PAGE_H - 348, width, 20, 10, stroke=1, fill=1)
            c.setFillColor(text_color)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(chip_x + width / 2, PAGE_H - 341, label)
            chip_x += width + 8

        image_x = MX
        image_y = 135
        image_w = PAGE_W - 2 * MX
        image_h = image_w * 968 / 1800
        if GUIDE_SCREENSHOT.is_file():
            image_w_px, image_h_px = ImageReader(str(GUIDE_SCREENSHOT)).getSize()
            image_h = image_w * image_h_px / image_w_px
        c.setFillColor(colors.Color(0.357, 0.294, 0.902, alpha=0.11))
        c.roundRect(image_x + 5, image_y - 5, image_w, image_h, 9, stroke=0, fill=1)
        if GUIDE_SCREENSHOT.is_file():
            c.setFillAlpha(1)
            c.setStrokeAlpha(1)
            c.drawImage(str(GUIDE_SCREENSHOT), image_x, image_y, width=image_w, height=image_h, mask="auto")
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.8)
            c.rect(image_x, image_y, image_w, image_h, stroke=1, fill=0)
        else:
            c.setFillColor(WHITE)
            c.rect(image_x, image_y, image_w, image_h, stroke=1, fill=1)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 9)
            c.drawCentredString(PAGE_W / 2, image_y + image_h / 2, "Workspace screenshot")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.4)
        c.drawString(MX, 119, "WORKSPACE PREVIEW  /  SOURCE + RESTORED COMPARISON")

        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.4)
        c.drawString(MX, 55, "Version 0.1.0  /  Built and tested locally  /  AGPL-3.0-only")
        c.drawRightString(PAGE_W - MX, 55, "Click the contents or use the bookmarks panel")
        c.restoreState()

    def _draw_body_page(self, canvas, doc) -> None:
        if doc.page == 1:
            return
        c = canvas
        c.saveState()
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.line(MX, PAGE_H - 44, PAGE_W - MX, PAGE_H - 44)
        c.setFillColor(ACCENT)
        c.rect(MX, PAGE_H - 49, 5, 5, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(MX + 10, PAGE_H - 50, "VIDEOREFINER STUDIO")
        c.drawRightString(PAGE_W - MX, PAGE_H - 50, "PROJECT GUIDE  /  OCTOBER 2026")

        c.setStrokeColor(BORDER)
        c.line(MX, 45, PAGE_W - MX, 45)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.2)
        c.drawString(MX, 33, "Version 0.1.0  /  Local build")

        if doc.page > 2:
            label = "Back to Contents"
            label_w = stringWidth(label, "Helvetica", 7.2)
            label_x = (PAGE_W - label_w) / 2
            c.linkRect("", "contents", (label_x - 4, 29, label_x + label_w + 4, 41), relative=0, thickness=0)
            c.setFillColor(ACCENT)
            c.drawString(label_x, 33, label)

        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 8.2)
        c.drawRightString(PAGE_W - MX, 33, f"{doc.page:02d}")
        c.restoreState()


def toc_page() -> list:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOC1",
            fontName="Helvetica",
            fontSize=9.9,
            leading=16.2,
            textColor=TEXT,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=1,
            spaceAfter=0,
        )
    ]
    toc.dotsMinLevel = 0

    how_to = Table(
        [[
            p("<b>How to use this PDF</b>", ParagraphStyle("HowTitle", parent=BODY, fontSize=9.4, leading=12, textColor=INK)),
            p("Click a heading or page number to jump. Use the PDF bookmarks panel for a section list. The setup checklist on page 8 can be filled in.", ParagraphStyle("HowBody", parent=SMALL, fontSize=8.5, leading=11.8)),
        ]],
        colWidths=[120, CW - 120],
    )
    how_to.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return [
        p("START HERE", KICKER),
        p("Contents", H1),
        HRFlowable(width="100%", thickness=0.8, color=BORDER, spaceBefore=2, spaceAfter=10),
        how_to,
        Spacer(1, 10),
        toc,
        Spacer(1, 14),
        callout(
            "What is interactive?",
            "The contents list, footer links, and repository links are clickable. The PDF has bookmarks for every section and topic. The setup checklist contains fillable checkboxes.",
            "info",
        ),
        Spacer(1, 8),
        callout(
            "The short version",
            "VideoRefiner Studio is a working local prototype. It scans a video, restores selected ranges with BasicVSR++, and exports a new file without touching the source. All three workflow tests pass.",
            "success",
        ),
    ]


def page_glance() -> list:
    story = section(
        "01",
        "Project at a Glance",
        "VideoRefiner Studio is a small desktop app for a focused job: find mosaic areas, restore them, and check the result before saving. It hides the heavy AI work behind a clear, light interface.",
    )
    story += [
        stat_strip([("100%", "Local processing"), ("3/3", "Workflow tests pass"), ("AGPL", "Open-source license")]),
        Spacer(1, 14),
        p("The problem", H2),
        p("Mosaic blur hides parts of a video. Repairing it by hand means finding each area, fixing it frame by frame, and checking the result. That takes time and is easy to get wrong."),
        p("The solution", H2),
        p("The app samples the video, marks likely mosaic ranges on a timeline, and restores only the ranges you choose. You compare source and result at the same moment, then export a new file. The source file is never overwritten."),
        p("Who it is for", H2),
        *bullets(
            [
                "People who edit their own local video and want a simple desktop tool.",
                "Reviewers who need a fast before/after check without a cloud upload.",
                "Developers who want a readable example of a Jasna desktop front end.",
            ]
        ),
        p("Design principles", H2),
        *bullets(
            [
                "<b>Private by default.</b> Video, frames, and settings stay on this computer.",
                "<b>Safe by default.</b> Every export gets a new path and the source is read-only.",
                "<b>Clear by default.</b> One main workflow, visible progress, and plain-language errors.",
                "<b>Fast where it matters.</b> GPU detection, TensorRT, and smart range rendering.",
            ]
        ),
    ]
    return story


def page_features() -> list:
    story = section(
        "02",
        "Feature Map",
        "Six features define the current build. Each one supports the same simple loop: import, scan, select, restore, compare, export.",
    )
    story += [
        feature_grid(
            [
                ("01", "Local scan", "Samples one frame per second. The detector scores each sample and turns the scores into one-second ranges."),
                ("02", "Range or whole video", "Restore only the selected ranges, or process the full video with a codec of your choice."),
                ("03", "BasicVSR++ restore", "Uses the Lada BasicVSR++ model on the NVIDIA GPU to rebuild detail inside the selected areas."),
                ("04", "Before / after compare", "Switch between Original, Compare, Side by side, and Wipe. Compare the same timestamp."),
                ("05", "Safe export", "Writes a new file with a unique name. Preserves audio when the source has it. Never overwrites the source."),
                ("06", "System check", "Shows GPU, VRAM, CUDA, TensorRT, FFmpeg, model, and VLC status in one place."),
            ]
        ),
        Spacer(1, 4),
        p("What is not in this build", H2),
        callout(
            "Kept out on purpose",
            "No cloud processing, no account, no telemetry, and no paid API. LTX, UNet 4x, and SD 1.5 models are not included. This build uses BasicVSR++ only. Audio is muxed into exports but is not previewed.",
            "warning",
        ),
    ]
    return story


def page_architecture() -> list:
    story = section(
        "03",
        "Architecture at a Glance",
        "The app separates the window from the work. The window stays responsive while background threads scan and restore video.",
    )
    story += [
        ArchitectureDiagram(),
        Spacer(1, 12),
        p("The parts", H2),
        data_table(
            ["Part", "What it does", "Why it matters"],
            [
                ["Desktop UI", "CustomTkinter views, settings, timeline, player, and status footer.", "One clear place to control the job."],
                ["Job layer", "Scan and restore threads send events through a queue.", "The window does not freeze during long work."],
                ["Jasna engine", "Pinned upstream engine for detection and restoration.", "The AI logic stays upstream and unmodified."],
                ["GPU runtime", "CUDA, PyTorch, TensorRT, and the compiled detector.", "Fast local inference on an NVIDIA card."],
                ["Media layer", "PyAV and FFmpeg for frames, muxing, and preview.", "Readable video and preserved audio."],
            ],
            [72, 260, 150],
            font=8.2,
        ),
        Spacer(1, 8),
        p("Why this design works", H2),
        *bullets(
            [
                "The UI thread only draws and reacts. It does not decode or run AI.",
                "Workers own the long tasks and report progress as messages.",
                "Settings are small and local, so a restart is cheap and predictable.",
                "The source file is treated as read-only input, not as a working file.",
            ]
        ),
    ]
    return story


def page_pipeline() -> list:
    story = section(
        "04",
        "Processing Pipeline",
        "The workflow is a straight line. Each step gives you something visible before the next step starts.",
    )
    steps = [
        ("1", "Import", "FFprobe reads the file. The header shows name, size, frame rate, duration, codec, and audio status. The source is only read."),
        ("2", "Scan", "The detector looks at one frame per second. Each sample gets a score. Scores become short ranges on the timeline."),
        ("3", "Select", "Choose ranges on the timeline or press Select all. You can change confidence and clip settings before restoring."),
        ("4", "Restore", "BasicVSR++ processes the selected clips on the GPU. Overlap and crossfade help hide the joins between clips."),
        ("5", "Compare and export", "Watch the result at the same timestamp. Save a new file with a unique name, then open it in your player."),
    ]
    rows = []
    for num, title, text in steps:
        rows.append([p(num, ParagraphStyle("StepNum", fontName="Helvetica-Bold", fontSize=15, textColor=ACCENT, alignment=TA_CENTER)), p(title, H3), p(text, TABLE_BODY)])
    pipeline = Table(rows, colWidths=[30, 82, CW - 112], hAlign="LEFT")
    pipeline.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story += [
        pipeline,
        Spacer(1, 10),
        p("Smart range rendering", H2),
        p("For selected ranges, the app restores the marked parts and streams the rest of the video from the source. This keeps untouched scenes from being re-encoded. It also keeps the source codec, which is why selected-range mode supports only H.264, HEVC, and AV1 sources."),
        callout(
            "The important rule",
            "Selected ranges keep the source codec. Whole video uses the codec you pick. If the source codec cannot be smart-rendered, the app disables selected-range restore and asks you to use whole video.",
            "info",
        ),
    ]
    return story


def page_ui() -> list:
    story = section(
        "05",
        "UI Tour",
        "The main workspace is built around one screen. The source and result are always visible together, and the start button stays in the footer.",
    )
    if GUIDE_SCREENSHOT.is_file():
        image_w = CW
        image_w_px, image_h_px = ImageReader(str(GUIDE_SCREENSHOT)).getSize()
        image_h = image_w * image_h_px / image_w_px
        image = Image(str(GUIDE_SCREENSHOT), width=image_w, height=image_h)
        image_table = Table([[image]], colWidths=[CW], hAlign="LEFT")
        image_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("BACKGROUND", (0, 0), (-1, -1), INK),
                ]
            )
        )
        story += [image_table, p("Workspace after a completed selected-range restore. Screenshot generated by scripts/ui_screenshot.py.", CAPTION)]
    else:
        story += [callout("Screenshot missing", "Run scripts/ui_screenshot.py to regenerate test_output/ui_workspace.png.", "warning")]

    story += [
        Spacer(1, 5),
        p("What to notice", H2),
        data_table(
            ["Area", "What it shows", "What you can do"],
            [
                ["Left sidebar", "Import, Workspace, Compare, System, About, and the local GPU card.", "Move between views and check free VRAM."],
                ["Header", "File name, resolution, frame rate, duration, codec, and audio.", "Confirm you loaded the right file."],
                ["Preview", "Source and restored frames, player, and compare modes.", "Switch views, play, scrub, or wipe."],
                ["Timeline", "Detected ranges and selected ranges.", "Select all, clear, rescan, or pick a subset."],
                ["Settings", "Detector, confidence, clip size, overlap, denoise, and scene detection.", "Tune quality and GPU load."],
                ["Footer", "Status, progress, stats, and Start restoration.", "Start, cancel, or open the log."],
            ],
            [78, 252, 152],
            font=8.0,
        ),
    ]
    return story


def page_setup() -> list:
    story = section(
        "06",
        "Setup and Launch",
        "The current workspace is already set up. This page is also useful for a clean machine or a new clone.",
    )
    story += [
        p("Already set up?", H2),
        p('Double-click <b>run.bat</b>, or run this command from the project folder:'),
        callout("Run the app", '<font name="Courier">.venv\\Scripts\\python.exe main.py</font>', "success"),
        p("Fresh setup", H2),
        p('Install <b>uv</b>, <b>Git for Windows</b>, and <b>FFmpeg</b>, then run:'),
        callout(
            "Bootstrap command",
            '<font name="Courier">powershell -ExecutionPolicy Bypass -File scripts\\bootstrap.ps1</font>',
            "info",
        ),
        Spacer(1, 8),
        data_table(
            ["Need", "Version or note"],
            [
                ["Windows", "Windows 10 or 11, 64-bit."],
                ["GPU", "NVIDIA GPU with a current driver. This build was tested on an RTX 3050 6 GB Laptop GPU."],
                ["Python", "3.13, created by uv inside the project .venv."],
                ["Media tools", "FFmpeg and ffprobe on PATH. Version 9.0 was used for this build."],
                ["Disk", "Room for the virtual environment and model files. Models are several hundred MB."],
            ],
            [92, 390],
            font=8.3,
        ),
        p("Setup checklist", H2),
        p("These checkboxes are fillable in a PDF reader that supports forms, such as Adobe Acrobat or Microsoft Edge.", SMALL),
        Checklist(
            [
                "Windows PC with an NVIDIA GPU",
                "Current NVIDIA driver installed",
                "uv installed and available on PATH",
                "Git for Windows installed",
                "FFmpeg and ffprobe on PATH",
                "scripts\\bootstrap.ps1 finished successfully",
                "run.bat opens the app and the GPU card turns green",
            ]
        ),
        Spacer(1, 8),
        p(
            "Settings live in <b>%LOCALAPPDATA%\\VideoRefinerStudio</b>. Set <b>VIDEOREFINER_CONFIG_DIR</b> to use a different folder. "
            f"Useful links: {link('https://docs.astral.sh/uv/', 'uv')}, {link('https://git-scm.com/', 'Git')}, {link('https://ffmpeg.org/', 'FFmpeg')}, {link('https://github.com/Kruk2/jasna', 'Jasna')}.",
            SMALL,
        ),
    ]
    return story


def page_quick_start() -> list:
    story = section(
        "07",
        "Quick-Start Workflow",
        "This is the normal path for a new video. The first scan can be slower because the detector may compile a TensorRT engine.",
    )
    steps = [
        ("1", "Import", "Use Import video or drop a file on the import screen."),
        ("2", "Choose scope", "Keep Selected ranges for a fast repair, or choose Whole video."),
        ("3", "Scan", "Press Scan. Watch the timeline fill with ranges."),
        ("4", "Select", "Press Select all or tick the ranges you want. Check the count and duration."),
        ("5", "Tune", "Lower confidence if mosaics are missed. Raise it if normal areas are flagged."),
        ("6", "Start", "Press Start restoration in the footer. Keep the window open while it works."),
        ("7", "Check and save", "Compare at the same timestamp. Use Output folder if needed, then open the new file."),
    ]
    rows = [[p(num, ParagraphStyle("QNum", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT)), p(title, TABLE_BODY_BOLD), p(text, TABLE_BODY)] for num, title, text in steps]
    table = Table(rows, colWidths=[24, 84, CW - 108], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.45, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 10),
        p("Quick tuning guide", H2),
        data_table(
            ["Symptom", "Try this"],
            [
                ["Mosaic areas are missed", "Lower Confidence in small steps, then rescan."],
                ["Normal areas are flagged", "Raise Confidence, then rescan."],
                ["GPU runs out of memory", "Lower Max clip size, close other GPU apps, or use H.264 whole video."],
                ["Selected ranges are disabled", "Use an H.264, HEVC, or AV1 source, select a range, or switch to Whole video."],
            ],
            [180, 302],
            font=8.4,
        ),
        Spacer(1, 8),
        callout("Good first test", "Use a short 10-second clip. Confirm the preview, compare modes, audio, and output file before starting a long video.", "success"),
    ]
    return story


def page_models() -> list:
    story = section(
        "08",
        "Models, Codecs, and Export Rules",
        "Three local model files do the AI work. The app chooses safe defaults for a 6 GB GPU.",
    )
    story += [
        data_table(
            ["Model", "Role", "License", "Default?"],
            [
                ["lada_mosaic_restoration_model_generic_v1.2.pth", "BasicVSR++ restoration", "AGPL-3.0", "Yes"],
                ["lada_mosaic_detection_model_v4_fast.pt", "Lada YOLO v4 fast detector", "AGPL-3.0", "Yes"],
                ["rfdetr-v6-large.onnx", "Optional RF-DETR large detector", "Apache-2.0", "No"],
            ],
            [196, 140, 80, 66],
            font=8.1,
        ),
        Spacer(1, 8),
        p("What the models do", H2),
        p("The <b>detector</b> finds likely mosaic areas. The <b>restoration model</b> rebuilds detail inside those areas. The detector is the fast part. The restoration model does the heavy visual work."),
        p("Codec rules", H2),
        data_table(
            ["Mode", "Codec behavior", "When to use it"],
            [
                ["Selected ranges", "Always keeps the source codec. Supports H.264, HEVC, and AV1 sources.", "Fast repair of specific ranges."],
                ["Whole video", "Uses the codec you choose: H.264, HEVC, or AV1.", "Unsupported source codec or a full re-encode."],
            ],
            [100, 250, 132],
            font=8.2,
        ),
        p("Export rules", H2),
        *bullets(
            [
                "The app writes a new file with a unique name. An existing file or the source is never overwritten.",
                "The default suffix is <b>_restored</b>. Change it in settings if you want a different tag.",
                "Source audio is muxed into the export when present.",
                "The comparison player does not play audio. This is expected.",
            ]
        ),
        callout("Quality setting", "CQ controls quality. A lower CQ means higher quality and a larger file. The allowed range depends on the codec.", "info"),
    ]
    return story


def page_tests() -> list:
    story = section(
        "09",
        "Test Results and Evidence",
        "The test opens the real desktop window, uses an isolated settings folder, and runs the same code paths as a person using the app.",
    )
    story += [
        data_table(
            ["Case", "Output", "Audio", "Check", "Evidence"],
            [
                ["Selected ranges + compare", "10.0 s HEVC", "No source audio", "PASS", "Preview difference 2.32"],
                ["Whole video", "4.9 s H.264", "Preserved", "PASS", "Audio present in output"],
                ["Selected ranges + audio", "10.0 s HEVC", "Preserved", "PASS", "Audio + difference 2.32"],
            ],
            [126, 88, 82, 46, 140],
            font=8.0,
        ),
        Spacer(1, 8),
        p("What the test proves", H2),
        *bullets(
            [
                "The app loads a video and shows the correct file facts in the header.",
                "Scanning finds ranges and enabling the Start button works.",
                "Selected-range restore writes a complete output file.",
                "Whole-video restore preserves audio.",
                "The restored preview is visibly different from the source (mean difference 2.32).",
                "Compare mode and playback update the live UI.",
            ]
        ),
        p("Reproduce it", H2),
        callout(
            "Test command",
            '<font name="Courier">.venv\\Scripts\\python.exe scripts\\ui_workflow_test.py</font><br/>'
            "The test prints PASS at the end. Output files are written under <b>test_output\\ui_test</b> with unique names.",
            "success",
        ),
        Spacer(1, 8),
        callout(
            "Small note",
            "The test terminal may show one harmless Tkinter finalizer warning when the test window is torn down. The workflow still finishes with PASS, and the warning does not appear during normal app use.",
            "warning",
        ),
    ]
    return story


def page_performance() -> list:
    story = section(
        "10",
        "Performance and VRAM Guidance",
        "The GPU does the heavy work. The biggest limits are video size, clip size, and how much VRAM is free.",
    )
    story += [
        data_table(
            ["Factor", "Effect", "What to do"],
            [
                ["Resolution", "4K needs much more VRAM than 1080p.", "Start at 1080p. Use shorter test clips."],
                ["Video length", "Long videos take longer to scan and restore.", "Test the workflow on 10 seconds first."],
                ["Detector", "RF-DETR is more accurate but slower and larger.", "Keep Lada YOLO for speed on 6 GB."],
                ["Max clip size", "Large clips need more VRAM at once.", "Lower it if the GPU runs out of memory."],
                ["First run", "TensorRT may compile the detector once.", "Wait for the first scan to finish."],
            ],
            [112, 225, 145],
            font=8.2,
        ),
        p("6 GB VRAM starting point", H2),
        *bullets(
            [
                "Use 1080p video and the default Lada YOLO detector.",
                "Keep Max clip size at 60 frames. Try 30 or 24 if memory is tight.",
                "Close games, browsers with many tabs, and other GPU apps before a long job.",
                "If selected-range mode is not needed, try whole-video H.264 for a smaller memory footprint.",
                "Scene-cut detection is on by default. It can add work on videos with many cuts.",
            ]
        ),
        callout("Speed is local", "There is no upload or queue wait. Speed depends on this computer's GPU, driver, video, and settings.", "info"),
        p("What good looks like", H2),
        p("The 10-second HEVC test clip restored in about 20-30 seconds on the test machine after warm-up. Treat this as a rough guide, not a promise. Longer and larger videos take longer."),
    ]
    return story


def page_troubleshooting() -> list:
    story = section(
        "11",
        "Troubleshooting",
        "Start with the System view and the log. Most problems have a clear cause and a simple fix.",
    )
    story += [
        data_table(
            ["Problem", "What to try"],
            [
                ["App does not start", "Open %LOCALAPPDATA%\\VideoRefinerStudio\\app.log and read the last error."],
                ["App says CUDA is not available", "Update the NVIDIA driver and confirm the .venv has the CUDA build of PyTorch."],
                ["Start restoration is disabled", "Select a range, use H.264/HEVC/AV1 for selected mode, or switch to Whole video."],
                ["GPU runs out of memory", "Lower Max clip size, close other GPU apps, or use H.264 whole-video export."],
                ["Scan is very slow", "The first run may compile TensorRT. Later runs reuse the engine."],
                ["Preview is black or frozen", "Move the playhead, switch Original/Compare, or reload the video."],
                ["No preview audio", "Expected. Audio is preserved in the export but not played in the compare view."],
                ["Wrong or stale settings", "Delete settings.json or set VIDEOREFINER_CONFIG_DIR to a fresh folder."],
            ],
            [168, 314],
            font=8.3,
        ),
        Spacer(1, 10),
        p("Where things are", H2),
        data_table(
            ["Item", "Path"],
            [
                ["Log", "%LOCALAPPDATA%\\VideoRefinerStudio\\app.log"],
                ["Settings", "%LOCALAPPDATA%\\VideoRefinerStudio\\settings.json"],
                ["Models", "model_weights\\ inside the project"],
                ["Test outputs", "test_output\\ui_test\\ inside the project"],
            ],
            [100, 382],
            font=8.4,
        ),
        Spacer(1, 8),
        callout("System view", "The System view checks the GPU, VRAM, CUDA, TensorRT, FFmpeg, model files, and optional VLC. Open it before changing code or reinstalling packages.", "info"),
    ]
    return story


def page_limitations() -> list:
    story = section(
        "12",
        "Limitations and Next Steps",
        "This is a working local build, not a finished commercial product. The limits are known and the next steps are clear.",
    )
    story += [
        p("Current limits", H2),
        *bullets(
            [
                "<b>Windows and NVIDIA only.</b> There is no CPU-only or AMD path in this build.",
                "<b>6 GB VRAM is a real limit.</b> 4K and high-frame-rate video can run out of memory.",
                "<b>The first run can be slow.</b> TensorRT may compile a detector engine once.",
                "<b>No installer.</b> The app runs from this folder with the project virtual environment.",
                "<b>No audio preview.</b> Audio is preserved in exports only.",
                "<b>BasicVSR++ only.</b> LTX, UNet 4x, and SD 1.5 are not part of this build.",
            ]
        ),
        p("Possible next steps", H2),
        data_table(
            ["Next step", "Why it helps"],
            [
                ["Signed Windows installer", "Makes setup and first launch much easier for non-developers."],
                ["Batch queue", "Lets a user prepare several videos and walk away."],
                ["Presets", "Saves good settings for 1080p, 4K, animation, or low-VRAM runs."],
                ["Better progress estimates", "Shows time remaining from real job history."],
                ["More compare tools", "Add zoom, frame step, and saved snapshots."],
                ["More detectors", "Offer a quality/speed choice without editing files."],
            ],
            [150, 332],
            font=8.3,
        ),
        Spacer(1, 8),
        callout("Project status", "Version 0.1.0 is a working local prototype with a complete import-to-export loop and passing workflow tests.", "success"),
    ]
    return story


def page_licensing() -> list:
    story = section(
        "13",
        "Licensing and Attribution",
        "VideoRefiner Studio is free and open source under AGPL-3.0-only because it uses Jasna. Keep the notices with the app.",
    )
    story += [
        p("The main license", H2),
        p("The project is distributed under the <b>GNU Affero General Public License version 3.0 only</b>. The full text is in <b>LICENSE</b>. If you share the app, provide the corresponding source and keep the attribution."),
        data_table(
            ["Component", "License", "Note"],
            [
                ["VideoRefiner Studio", "AGPL-3.0-only", "Desktop front end and UI."],
                ["Jasna 0.12.0", "AGPL-3.0-only", "Pinned upstream engine in vendor/jasna."],
                ["Lada models", "AGPL-3.0", "BasicVSR++ restoration and YOLO detector."],
                ["RF-DETR large", "Apache-2.0", "Optional detector model."],
                ["PyTorch / TensorRT", "BSD / NVIDIA", "Runtime and inference tools."],
                ["FFmpeg / PyAV", "LGPL/GPL / BSD", "Media read, write, and mux."],
            ],
            [132, 100, 250],
            font=8.2,
        ),
        Spacer(1, 8),
        p("What to keep", H2),
        *bullets(
            [
                "<b>LICENSE</b>, <b>NOTICE</b>, and <b>THIRD_PARTY_NOTICES.md</b>.",
                "Jasna's notices under <b>vendor/jasna</b>.",
                "Model provenance and license notes for any model you redistribute.",
                "A clear note that the app is local and has no telemetry.",
            ]
        ),
        callout(
            "Simple rule",
            "Edit only media you have permission to edit. If you share the app or a modified version, share the source and keep the license notices.",
            "warning",
        ),
        Spacer(1, 8),
        p(f"Project links: {link('https://github.com/Kruk2/jasna', 'Jasna')}  /  {link('https://www.gnu.org/licenses/agpl-3.0.html', 'AGPL-3.0')}", SMALL),
    ]
    return story


def page_appendix() -> list:
    story = section(
        "14",
        "Appendix",
        "A quick map of the files, commands, and words used in this guide.",
    )
    story += [
        p("File map", H2),
        data_table(
            ["Path", "Role"],
            [
                ["main.py", "DPI setup, logging, environment defaults, app entry point."],
                ["videorefiner/app.py", "Main window, views, timeline, compare player, status footer."],
                ["videorefiner/engine.py", "Scan and restore workers, GPU checks, codec rules."],
                ["videorefiner/media.py", "Video probe, frame preview, compare composition, playback."],
                ["videorefiner/settings.py", "JSON settings and config-directory override."],
                ["videorefiner/widgets.py", "Scroll area, cards, timeline, pills, and UI parts."],
                ["scripts/bootstrap.ps1", "Clean-clone setup for Windows."],
                ["scripts/download_models.py", "SHA-256 checked model downloads."],
                ["scripts/ui_workflow_test.py", "Three-case end-to-end UI test."],
                ["vendor/jasna", "Pinned upstream Jasna source, not modified."],
            ],
            [180, 302],
            font=8.0,
        ),
        p("Commands", H2),
        data_table(
            ["Task", "Command"],
            [
                ["Run", ".venv\\Scripts\\python.exe main.py"],
                ["Run tests", ".venv\\Scripts\\python.exe scripts\\ui_workflow_test.py"],
                ["Screenshot", ".venv\\Scripts\\python.exe scripts\\ui_screenshot.py"],
                ["Models", ".venv\\Scripts\\python.exe scripts\\download_models.py"],
            ],
            [80, 402],
            font=8.2,
        ),
        p("Words used in this guide", H2),
        data_table(
            ["Word", "Simple meaning"],
            [
                ["Mosaic", "A blocky blur that hides part of a video."],
                ["Codec", "The format used to compress video, such as H.264 or HEVC."],
                ["CQ", "A quality setting. Lower means better quality and a bigger file."],
                ["TensorRT", "An NVIDIA tool that makes AI models run faster."],
                ["VRAM", "Memory on the graphics card."],
                ["Smart render", "Re-encode only the changed ranges and copy the rest."],
            ],
            [78, 404],
            font=8.2,
        ),
    ]
    return story




def prepare_screenshot(output_dir: Path) -> None:
    global GUIDE_SCREENSHOT
    if not SCREENSHOT.is_file():
        return
    from PIL import Image as PILImage

    image = PILImage.open(SCREENSHOT).convert("RGB")
    image = image.crop((0, 0, image.width, min(image.height, 968)))
    target = output_dir / "assets" / "ui_workspace_clean.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    GUIDE_SCREENSHOT = target

def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    prepare_screenshot(output.parent)
    doc = GuideDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=MX,
        rightMargin=MX,
        topMargin=MT,
        bottomMargin=MB,
        title="VideoRefiner Studio - Project Guide",
        author="VideoRefiner Studio",
        subject="Interactive project guide, architecture, setup, tests, and licensing",
        creator="VideoRefiner Studio",
    )

    story = [Spacer(1, 1), NextPageTemplate("body"), PageBreak()]
    story += toc_page()
    story.append(PageBreak())
    for builder in (
        page_glance,
        page_features,
        page_architecture,
        page_pipeline,
        page_ui,
        page_setup,
        page_quick_start,
        page_models,
        page_tests,
        page_performance,
        page_troubleshooting,
        page_limitations,
        page_licensing,
        page_appendix,
    ):
        story += builder()
        story.append(PageBreak())
    story.pop()

    doc.multiBuild(story)
    print(f"saved {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
