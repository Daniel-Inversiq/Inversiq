"""Render Founder_Operating_System_2026-2027.md into a premium, editorial PDF."""
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle

SRC = r"C:\Users\dvanl\Inversiq\Founder_Operating_System_2026-2027.md"
OUT = r"C:\Users\dvanl\Inversiq\Founder_Operating_System_2026-2027.pdf"
FONTS = r"C:\Windows\Fonts"

# ---- Fonts -----------------------------------------------------------------
pdfmetrics.registerFont(TTFont("Body", FONTS + r"\georgia.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", FONTS + r"\georgiab.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", FONTS + r"\georgiai.ttf"))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", FONTS + r"\georgiaz.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                              italic="Body-Italic", boldItalic="Body-BoldItalic")
pdfmetrics.registerFont(TTFont("Sans", FONTS + r"\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("Sans-SB", FONTS + r"\seguisb.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Light", FONTS + r"\segoeuil.ttf"))
pdfmetrics.registerFont(TTFont("Mono", FONTS + r"\consola.ttf"))

# ---- Palette ---------------------------------------------------------------
INK    = HexColor(0x1A1A1A)
ACCENT = HexColor(0x1B2A4A)   # deep navy
MUTED  = HexColor(0x6B7280)   # gray
RULE   = HexColor(0xC9CCD1)
HAIR   = HexColor(0xDADCE0)
BOXBG  = HexColor(0xF4F5F7)

# ---- Styles ----------------------------------------------------------------
body = ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=16.5,
                      textColor=INK, alignment=TA_JUSTIFY, spaceAfter=10)
first = ParagraphStyle("first", parent=body, spaceBefore=2)
quote = ParagraphStyle("quote", fontName="Body-Italic", fontSize=12, leading=18,
                       textColor=ACCENT, leftIndent=18, rightIndent=18,
                       spaceBefore=4, spaceAfter=12)
caption = ParagraphStyle("caption", fontName="Body-Italic", fontSize=10,
                         leading=14, textColor=MUTED, spaceAfter=12)
kicker = ParagraphStyle("kicker", fontName="Sans", fontSize=8.5, leading=12,
                        textColor=MUTED, spaceAfter=3)
h2num = ParagraphStyle("h2num", fontName="Sans", fontSize=9, leading=12,
                       textColor=ACCENT, spaceAfter=2, spaceBefore=6)
h2 = ParagraphStyle("h2", fontName="Sans-SB", fontSize=18, leading=22,
                    textColor=ACCENT, spaceAfter=4)
h3 = ParagraphStyle("h3", fontName="Sans-SB", fontSize=12.5, leading=16,
                    textColor=INK, spaceBefore=10, spaceAfter=5)
li = ParagraphStyle("li", parent=body, leftIndent=20, spaceAfter=7,
                    alignment=TA_LEFT)
mono = ParagraphStyle("mono", fontName="Mono", fontSize=9, leading=13,
                      textColor=INK)
oath = ParagraphStyle("oath", parent=body, fontSize=10.5, leading=17)
sig_label = ParagraphStyle("sig", fontName="Sans", fontSize=9, textColor=MUTED,
                           alignment=TA_LEFT)

# ---- Inline formatting -----------------------------------------------------
def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", t)
    # Georgia (esp. italic) lacks arrow glyphs — render them in a font that has them.
    for ch in ("→", "↓", "↺", "⇒", "←", "↑"):
        t = t.replace(ch, f'<font name="Sans">{ch}</font>')
    return t

def rule(color=RULE, w=0.6, sb=2, sa=10):
    return HRFlowable(width="100%", thickness=w, color=color,
                      spaceBefore=sb, spaceAfter=sa, lineCap="round")

# ---- Title page ------------------------------------------------------------
def title_page():
    s = []
    s.append(Spacer(1, 4.2 * cm))
    s.append(rule(ACCENT, 1.4, 0, 18))
    s.append(Paragraph("I N T E R N &nbsp;&nbsp; D O C U M E N T &nbsp;&nbsp;·&nbsp;&nbsp; V E R T R O U W E L I J K",
                       ParagraphStyle("tk", fontName="Sans", fontSize=9,
                                      textColor=MUTED, alignment=TA_CENTER, spaceAfter=20)))
    s.append(Paragraph("Founder Operating System",
                       ParagraphStyle("tt", fontName="Body-Bold", fontSize=34,
                                      leading=40, textColor=ACCENT, alignment=TA_CENTER)))
    s.append(Spacer(1, 6))
    s.append(Paragraph("2026 &nbsp;–&nbsp; 2027",
                       ParagraphStyle("ty", fontName="Sans-Light", fontSize=22,
                                      textColor=INK, alignment=TA_CENTER, spaceAfter=22)))
    s.append(Paragraph("Een intern document voor twee founders.<br/>Geschreven om over tien jaar nog te bewaren.",
                       ParagraphStyle("ts", fontName="Body-Italic", fontSize=12.5,
                                      leading=20, textColor=MUTED, alignment=TA_CENTER)))
    s.append(Spacer(1, 1.4 * cm))
    s.append(rule(HAIR, 0.6, 0, 12))
    s.append(Paragraph("I N V E R S I Q &nbsp;&nbsp;·&nbsp;&nbsp; S C R Y",
                       ParagraphStyle("tb", fontName="Sans", fontSize=10,
                                      textColor=ACCENT, alignment=TA_CENTER, spaceAfter=4)))
    s.append(Paragraph("Kantelpunt — 20 juli 2026",
                       ParagraphStyle("td", fontName="Body-Italic", fontSize=10,
                                      textColor=MUTED, alignment=TA_CENTER)))
    s.append(PageBreak())
    return s

# ---- Signature block -------------------------------------------------------
def signature_block():
    line_cell = ParagraphStyle("lc", fontName="Body", fontSize=10, textColor=INK)
    cell = [[Paragraph("&nbsp;", line_cell)], [Paragraph("Founder", sig_label)]]
    def col():
        t = Table([[Paragraph("&nbsp;", line_cell)]], colWidths=[6.4 * cm], rowHeights=[12])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, INK)]))
        return t
    inner = Table([[col(), "", col()],
                   [Paragraph("Founder", sig_label), "", Paragraph("Founder", sig_label)]],
                  colWidths=[6.4 * cm, 1.6 * cm, 6.4 * cm])
    inner.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    return inner

# ---- Parse markdown body ---------------------------------------------------
def build_body():
    with open(SRC, encoding="utf-8") as f:
        lines = f.read().split("\n")

    # skip everything up to the first "## " (handled by custom title page)
    start = next(i for i, l in enumerate(lines) if l.startswith("## "))
    lines = lines[start:]

    flow = []
    i = 0
    first_para_in_section = False
    section_count = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Section heading: "## I. Opening Letter"
        m = re.match(r"^##\s+([IVX]+)\.\s+(.*)$", line)
        if m:
            section_count += 1
            blk = []
            if section_count > 1:
                flow.append(PageBreak())
            blk.append(Paragraph(m.group(1), h2num))
            blk.append(Paragraph(inline(m.group(2)), h2))
            blk.append(rule(ACCENT, 1.0, 2, 12))
            flow.append(KeepTogether(blk))
            first_para_in_section = True
            i += 1
            continue

        # Subheading "### ..."
        if line.startswith("### "):
            flow.append(Paragraph(inline(line[4:]), h3))
            i += 1
            continue

        # Horizontal rule
        if stripped == "---":
            flow.append(rule(HAIR, 0.6, 6, 14))
            i += 1
            continue

        # <br>
        if stripped == "<br>" or stripped == "<br/>":
            flow.append(Spacer(1, 8))
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            txt = stripped.lstrip(">").strip()
            flow.append(Paragraph(inline(txt), quote))
            i += 1
            continue

        # Signature underscores
        if stripped.startswith("____"):
            flow.append(Spacer(1, 6))
            flow.append(signature_block())
            flow.append(Spacer(1, 12))
            i += 1
            # skip the following "Founder ... Founder" label line
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and "Founder" in lines[i]:
                i += 1
            continue

        # Numbered list item
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            txt = f'<b>{m.group(1)}.</b>&nbsp;&nbsp;{inline(m.group(2))}'
            flow.append(Paragraph(txt, li))
            i += 1
            continue

        # Bullet list item
        if stripped.startswith("- "):
            txt = f'<font color="#1B2A4A">•</font>&nbsp;&nbsp;{inline(stripped[2:])}'
            flow.append(Paragraph(txt, li))
            i += 1
            continue

        # Standalone italic caption line  *...*
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            flow.append(Paragraph(inline(stripped), caption))
            i += 1
            continue

        # Em-dash signoff line "— *De founders*"
        if stripped.startswith("—"):
            flow.append(Paragraph(inline(stripped), ParagraphStyle(
                "signoff", parent=body, fontName="Body-Italic",
                alignment=TA_LEFT, textColor=ACCENT, spaceBefore=4)))
            i += 1
            continue

        # "Datum:" / "Getekend," lines in the oath
        if stripped in ("Getekend,",) or stripped.startswith("Datum:"):
            flow.append(Paragraph(inline(stripped), ParagraphStyle(
                "plain", parent=body, alignment=TA_LEFT, spaceAfter=6)))
            i += 1
            continue

        # Normal paragraph
        style = first if first_para_in_section else body
        flow.append(Paragraph(inline(stripped), style))
        first_para_in_section = False
        i += 1

    return flow

# ---- Page furniture --------------------------------------------------------
DOC_LABEL = "Founder Operating System  ·  2026–2027"

def footer(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setStrokeColor(HAIR)
    canvas.setLineWidth(0.6)
    y = 1.45 * cm
    canvas.line(2.2 * cm, y + 8, A4[0] - 2.2 * cm, y + 8)
    canvas.setFont("Sans", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2.2 * cm, y - 2, DOC_LABEL)
    canvas.drawRightString(A4[0] - 2.2 * cm, y - 2, str(doc.page - 1))
    canvas.restoreState()

# ---- Build -----------------------------------------------------------------
doc = BaseDocTemplate(
    OUT, pagesize=A4,
    leftMargin=2.4 * cm, rightMargin=2.4 * cm,
    topMargin=2.2 * cm, bottomMargin=2.3 * cm,
    title="Founder Operating System 2026-2027",
    author="The Founders", subject="Inversiq · SCRY",
)
frame = Frame(doc.leftMargin, doc.bottomMargin,
              doc.width, doc.height, id="main")
doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=footer)])

story = title_page() + build_body()
doc.build(story)
print("WROTE", OUT)
