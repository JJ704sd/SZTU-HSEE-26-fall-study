# -*- coding: utf-8 -*-
"""
================================================================================
实验报告 PDF 生成器（reportlab 直出，不依赖 Word）
--------------------------------------------------------------------------------
本机的 Word COM 是个不稳定的 shim，逐段写入与导出都会随机 RPC_E_CALL_REJECTED。
既然 DOCX 已经用纯 OOXML 生成，PDF 也就不必再经过 Word：
本模块与 ooxml_docx.DocxBuilder 暴露**完全相同的接口**，
因此 make_report.py 里同一份正文可以分别喂给两个后端，两边内容天然一致。

中文字体：正文 宋体(SimSun)，加粗 黑体(SimHei)，代码 新宋体(NSimSun，等宽)。
================================================================================
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

FONT_DIR = Path(r"C:\Windows\Fonts")
ALIGN_MAP = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT, "both": TA_JUSTIFY}

_FONTS_READY = False

# 中文字体名 -> reportlab 注册名
FONT_MAP = {"宋体": "SimSun", "黑体": "SimHei", "SimSun": "SimSun",
            "SimHei": "SimHei", "新宋体": "NSimSun", "NSimSun": "NSimSun"}


def _register_fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    pdfmetrics.registerFont(TTFont("SimSun", str(FONT_DIR / "simsun.ttc"), subfontIndex=0))
    pdfmetrics.registerFont(TTFont("NSimSun", str(FONT_DIR / "simsun.ttc"), subfontIndex=1))
    pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
    # ps2tt() 需要能查到 family/bold/italic，三个字体都要登记 family
    pdfmetrics.registerFontFamily("SimSun", normal="SimSun", bold="SimHei",
                                  italic="SimSun", boldItalic="SimHei")
    pdfmetrics.registerFontFamily("SimHei", normal="SimHei", bold="SimHei",
                                  italic="SimHei", boldItalic="SimHei")
    pdfmetrics.registerFontFamily("NSimSun", normal="NSimSun", bold="NSimSun",
                                  italic="NSimSun", boldItalic="NSimSun")
    _FONTS_READY = True


class PdfDoc:
    """与 ooxml_docx.DocxBuilder 同接口的 PDF 后端。"""

    def __init__(self, path, margin_top=2.2, margin_bottom=2.0,
                 margin_lr=2.5):
        _register_fonts()
        self.path = Path(path)
        self.story = []
        self.pagesize = A4
        self.mt, self.mb, self.ml, self.mr = margin_top, margin_bottom, margin_lr, margin_lr

    # ------------------------------------------------------------------ 段落 ---
    def para(self, text="", size=10.5, cjk="SimSun", latin="SimSun", bold=False,
             align="left", space_before=0, space_after=4, line=16,
             color=0, indent_first=0, left_indent=0, right_indent=0, shade=None):
        col = colors.HexColor(f"#{color:06X}") if isinstance(color, int) \
            else colors.HexColor(f"#{color}")
        font = FONT_MAP.get(cjk, "SimSun")
        if bold and font == "SimSun":
            font = "SimHei"          # 宋体无粗体，粗体一律用黑体
        st = ParagraphStyle(
            "p", fontName=font, fontSize=size,
            leading=line, alignment=ALIGN_MAP[align],
            spaceBefore=space_before, spaceAfter=space_after,
            firstLineIndent=indent_first, leftIndent=left_indent,
            rightIndent=right_indent, textColor=col,
            backColor=colors.HexColor(f"#{shade}") if shade else None,
            wordWrap="CJK", splitLongWords=1,
        )
        self.story.append(Paragraph(_x(text), st))

    def code_block(self, lines, size=7.6):
        for ln in lines:
            st = ParagraphStyle(
                "c", fontName="NSimSun", fontSize=size, leading=size * 1.35,
                alignment=TA_LEFT, spaceBefore=0, spaceAfter=0,
                leftIndent=5, rightIndent=3,
                backColor=colors.HexColor("#F5F5F0"),
                wordWrap="CJK", splitLongWords=1,
            )
            self.story.append(Paragraph(_x(ln if ln else " "), st))
        self.story.append(Spacer(1, 4))

    def table(self, header, rows, widths=None, size=8.5, caption=None,
              min_row_h=0):
        if caption:
            self.para(caption, size=9, cjk="SimHei", bold=True,
                      space_before=5, space_after=2, line=12)
        ncol = len(header)
        ratios = widths or [1] * ncol
        total = sum(ratios)
        avail = self.pagesize[0] - (self.ml + self.mr) * cm
        colw = [avail * r / total for r in ratios]

        def cell(v, is_head):
            st = ParagraphStyle(
                "cell", fontName="SimHei" if is_head else "SimSun",
                fontSize=size, leading=size * 1.35, alignment=TA_CENTER,
                textColor=colors.black, wordWrap="CJK", splitLongWords=1,
            )
            return Paragraph(_x(str(v)), st)

        data = [[cell(h, True) for h in header]] + [[cell(v, False) for v in r]
                                                     for r in rows]
        t = Table(data, colWidths=colw, repeatRows=1)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9A9A9A")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        if min_row_h:
            style.append(("MINROWHEIGHTS", (0, 1), (-1, -1), [min_row_h]))
        t.setStyle(TableStyle(style))
        self.story.append(t)
        self.story.append(Spacer(1, 4))

    def image(self, path, width_cm=16.0):
        p = Path(path)
        if not p.is_file():
            self.para(f"[截图缺失：{p.name}]", size=9, color="C00000")
            return
        from PIL import Image as PILImage
        with PILImage.open(p) as im:
            iw, ih = im.size
        w = width_cm * cm
        h = w * ih / iw
        self.story.append(Image(str(p), width=w, height=h))
        self.story.append(Spacer(1, 2))

    def page_break(self):
        self.story.append(PageBreak())

    # ------------------------------------------------------------------ 输出 ---
    def save(self):
        doc = SimpleDocTemplate(
            str(self.path), pagesize=self.pagesize,
            topMargin=self.mt * cm, bottomMargin=self.mb * cm,
            leftMargin=self.ml * cm, rightMargin=self.mr * cm,
            title="实验1-NLP开发环境与基础文本处理",
            author="深圳技术大学 自然语言处理实验报告",
        )
        doc.build(self.story)
        return self.path


def _x(t):
    """转义 reportlab 的 mini-HTML 特殊字符（& < >）。"""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
