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

# ---------------------------------------------------------------------------
# 中文避头（禁则）补丁
# ---------------------------------------------------------------------------
# reportlab 自带的 ALL_CANNOT_START 只收**半角**标点：
#     u'!\',.:;?!")]\u3001\u3002\u300d\u300f\u3011\u3015\uff3d\u3011\uff09'
# 其中 , . : ; ? ! " ) 都是半角。而本报告正文通篇用的是**全角** 标点，
# ，、：；？！ 全都不在表内，断行时拦不住，于是这些字符会落到行首
# （实测：行首全角逗号 7 处、全角冒号 2 处、全角分号 1 处）。
#
# 这里把全角标点补进该表。注意补的只是「避头」方向（左括号/前引号仍允许断在行尾）。
# 生效位置是 reportlab.platypus.paragraph.breakLinesCJK() 里的 `u not in ALL_CANNOT_START`，
# 那里用的是模块全局名，所以要重绑这个模块属性，而不是改 textsplit 的原表。
EXTRA_CANNOT_START = (
    "，。、；：！？＂＇％‰°…～·’”›"   # 全角避头
    "’”"                                              # 右引号（表里只有 " 半角）
)


def _patch_kinsoku():
    """把全角避头字符并入 reportlab 的 ALL_CANNOT_START。"""
    from reportlab.lib import textsplit
    from reportlab.platypus import paragraph as _para

    base = textsplit.ALL_CANNOT_START
    merged = base + "".join(c for c in EXTRA_CANNOT_START if c not in base)
    textsplit.ALL_CANNOT_START = merged
    # paragraph 模块在 import 时把名字绑到了自己模块里，断行逻辑读的是这一份
    _para.ALL_CANNOT_START = merged
    return merged


_KINSOKU_TABLE = None

_FONTS_READY = False

# 中文字体名 -> reportlab 注册名
FONT_MAP = {"宋体": "SimSun", "黑体": "SimHei", "SimSun": "SimSun",
            "SimHei": "SimHei", "新宋体": "NSimSun", "NSimSun": "NSimSun"}


def _register_fonts():
    global _FONTS_READY, _KINSOKU_TABLE
    if _FONTS_READY:
        return
    _KINSOKU_TABLE = _patch_kinsoku()
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

    # 页面设置与模板 sectPr 保持一致：上下 2.54cm，左右 3.175cm
    def __init__(self, path, margin_top=2.54, margin_bottom=2.54,
                 margin_lr=3.175):
        _register_fonts()
        self.path = Path(path)
        self.story = []
        self.pagesize = A4
        self.mt, self.mb, self.ml, self.mr = margin_top, margin_bottom, margin_lr, margin_lr

    # ------------------------------------------------------------------ 段落 ---
    def para(self, text="", size=10.5, cjk="SimSun", latin="SimSun", bold=False,
             align="left", space_before=0, space_after=4, line=16,
             color=0, indent_first=0, left_indent=0, right_indent=0, shade=None,
             line_rule="exact"):
        col = colors.HexColor(f"#{color:06X}") if isinstance(color, int) \
            else colors.HexColor(f"#{color}")
        font = FONT_MAP.get(cjk, "SimSun")
        if bold and font == "SimSun":
            font = "SimHei"          # 宋体无粗体，粗体一律用黑体
        # line_rule="auto" 时 line 是倍数（模板封面为 2.5 倍行距）
        leading = size * line if line_rule == "auto" else line
        st = ParagraphStyle(
            "p", fontName=font, fontSize=size,
            leading=leading, alignment=ALIGN_MAP[align],
            spaceBefore=space_before, spaceAfter=space_after,
            firstLineIndent=indent_first, leftIndent=left_indent,
            rightIndent=right_indent, textColor=col,
            backColor=colors.HexColor(f"#{shade}") if shade else None,
            wordWrap="CJK", splitLongWords=1,
        )
        self.story.append(Paragraph(_x(text), st))

    def code_block(self, lines, size=7.4):
        for ln in lines:
            st = ParagraphStyle(
                "c", fontName="NSimSun", fontSize=size, leading=size * 1.28,
                alignment=TA_LEFT, spaceBefore=0, spaceAfter=0,
                leftIndent=5, rightIndent=3,
                backColor=colors.HexColor("#F5F5F0"),
                wordWrap="CJK", splitLongWords=1,
            )
            self.story.append(Paragraph(_x(ln if ln else " "), st))
        self.story.append(Spacer(1, 4))

    def table(self, header, rows, widths=None, size=8.5, caption=None,
              min_row_h=0, bold_all=False, tbl_width_pct=None,
              align="center", split_in_row=True):
        """align 决定**数据格**的对齐：
          "center" —— 数值/短标签型数据表（4.3、4.4、封面得分表）
          "left"   —— 成段文字型表（环境表、4.1、5.4 调试记录、6.2 AI 说明）
        两者不能混：同一张表里数据格全居中而正文左对齐，短行会被推到中间、
        末行参差，看着像没对齐；这属于规范性明文考察的「一致性」一项。
        表头一律居中。
        """
        if caption:
            self.para(caption, size=9, cjk="SimHei", bold=True,
                      space_before=5, space_after=2, line=12)
        ncol = len(header)
        ratios = widths or [1] * ncol
        total = sum(ratios)
        avail = (self.pagesize[0] - (self.ml + self.mr) * cm)
        if tbl_width_pct:
            avail = avail * tbl_width_pct / 100.0
        colw = [avail * r / total for r in ratios]
        data_align = ALIGN_MAP[align]

        def cell(v, is_head):
            st = ParagraphStyle(
                "cell", fontName="SimHei" if (is_head or bold_all) else "SimSun",
                fontSize=size, leading=size * 1.35,
                alignment=TA_CENTER if is_head else data_align,
                textColor=colors.black, wordWrap="CJK", splitLongWords=1,
            )
            return Paragraph(_x(str(v)), st)

        data = [[cell(h, True) for h in header]] + [[cell(v, False) for v in r]
                                                     for r in rows]
        # splitInRow=1：允许表格行内部跨页拆分。
        # 默认只在"行与行之间"断开，AI 说明表那种很长的单元格会整块跳到下一页，
        # 在上一页留下大片空白，从而把总页数顶上去。
        # 反过来，单元格不长的表（5.4 调试记录）要显式关掉：开着会在页末吐出一个
        # 没有数据行的孤行表头，下一页再重复一次表头。
        t = Table(data, colWidths=colw, repeatRows=1, splitByRow=1,
                  splitInRow=1 if split_in_row else 0)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9A9A9A")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        if not bold_all:
            style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")))
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
    """转义 reportlab 的 mini-HTML 特殊字符，并把换行转成 <br/>。

    顺序很重要：先转义 & < >，再处理换行，
    否则 <br/> 本身也会被转义掉。
    OOXML 后端在 _run() 里用 <w:br/> 处理换行，两边行为一致。
    """
    t = (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return t.replace("\n", "<br/>")
