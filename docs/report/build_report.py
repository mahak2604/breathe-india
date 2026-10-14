"""
Builds the submission copy of the written report (Word) from docs/report/report.md.

    python docs/report/build_report.py            -> docs/report/Breathe_India_report.docx

The editable, shareable version of the same text lives in Claude Docs; this script lays it out
compactly (A4, 10 pt) so it fits the 5-7 page limit. Convert to PDF with Word (File > Save as PDF)
or let tools/docx_to_pdf.ps1 do it.
"""

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
SRC = HERE / "report.md"
OUT = HERE / "Breathe_India_report.docx"

NAVY = RGBColor(0x0D, 0x36, 0x6B)
INK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x52, 0x51, 0x4E)
LINK = RGBColor(0x25, 0x6A, 0xBF)
FONT = "Calibri"
IMAGE_WIDTHS_CM = {"13_counterfactual_cities": 17.0, "dashboard_1_overview": 15.5, "04_insight_ranking_error": 11.5}

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def set_cell_fill(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def set_cell_margins(table, top=40, bottom=40, left=70, right=70):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def table_borders(table, color="C3C2B7"):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "bottom", "insideH"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), color)
        borders.append(el)
    for edge in ("left", "right", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def add_hyperlink(paragraph, text, url, size):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "256ABF")
    r_pr.append(color)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    r_pr.append(sz)
    run.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def add_inline(paragraph, text, size=10, color=INK, bold=False, italic=False):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            add_inline(paragraph, part[2:-2], size, color, bold=True, italic=italic)
        elif part.startswith("`"):
            r = paragraph.add_run(part[1:-1])
            r.font.name, r.font.size, r.font.color.rgb = "Consolas", Pt(size - 1), GREY
        elif part.startswith("["):
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part).groups()
            add_hyperlink(paragraph, label, url, size)
        elif part.startswith("*"):
            add_inline(paragraph, part[1:-1], size, color, bold=bold, italic=True)
        else:
            r = paragraph.add_run(part)
            r.font.size, r.font.color.rgb, r.bold, r.italic = Pt(size), color, bold, italic


def para(doc, text="", size=10, color=INK, space_after=4, italic=False, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing = 1.08
    if align:
        p.alignment = align
    add_inline(p, text, size, color, italic=italic)
    return p


def heading(doc, text, level):
    p = doc.add_heading(level=level)
    p.paragraph_format.space_before = Pt(10 if level == 2 else 6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = FONT
    r.font.size = Pt({1: 18, 2: 13, 3: 11}[level])
    r.font.color.rgb = NAVY
    r.bold = True
    return p


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    t = doc.add_table(rows=len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True
    table_borders(t)
    set_cell_margins(t)
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            add_inline(p, text, size=8.5, color=INK, bold=(i == 0))
            if i == 0:
                set_cell_fill(cell, "E8EEF7")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(1.7)
    sec.left_margin = sec.right_margin = Cm(1.9)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    # footer: short title + page x of y
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = fp.add_run("Breathe India · Data Wrangling Group Project · page ")
    run.font.size, run.font.color.rgb = Pt(8), GREY
    for field in ("PAGE", " of ", "NUMPAGES"):
        if field == " of ":
            r = fp.add_run(" of ")
            r.font.size, r.font.color.rgb = Pt(8), GREY
            continue
        r = fp.add_run()
        r.font.size, r.font.color.rgb = Pt(8), GREY
        for tag, text in (("begin", None), ("instr", field), ("end", None)):
            if tag == "instr":
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            else:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            r._r.append(el)

    lines = SRC.read_text(encoding="utf-8").splitlines()
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            heading(doc, line[2:], 1)
        elif line.startswith("## "):
            section = line[3:]
            heading(doc, section, 2)
        elif line.startswith("### "):
            heading(doc, line[4:], 3)
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            add_table(doc, rows)
            continue
        elif line.startswith("!["):
            path = re.match(r"!\[[^\]]*\]\(([^)]+)\)", line).group(1)
            img = (HERE / path).resolve()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(img), width=Cm(IMAGE_WIDTHS_CM.get(img.stem, 15)))
        elif line.startswith("*Figure"):
            para(doc, line.strip("*"), size=8.5, color=GREY, italic=True, space_after=8,
                 align=WD_ALIGN_PARAGRAPH.CENTER)
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
            add_inline(p, line[2:])
        elif re.match(r"\d+\. ", line) and section == "References":
            p = para(doc, line, size=9, space_after=2)              # numbered by hand: one Word list only
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.first_line_indent = Cm(-0.6)
        elif re.match(r"\d+\. ", line):
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
            add_inline(p, re.sub(r"^\d+\. ", "", line))
        elif lines[i - 1].startswith("# "):
            para(doc, line, size=9.5, color=GREY, space_after=8)      # byline under the title
        else:
            para(doc, line)
        i += 1

    doc.core_properties.title = "Breathe India: What Really Drives Air Pollution in Indian Cities?"
    doc.core_properties.author = "Mahak Wadhawan, Yash Shah"
    doc.save(OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    build()
