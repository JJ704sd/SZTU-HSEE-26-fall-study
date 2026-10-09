# -*- coding: utf-8 -*-
"""
================================================================================
【已废弃 / 无任何引用】本文件的 Doc 类基于 Word COM 逐段写入报告。
本机的 Word COM 是个不稳定的 shim，大量 COM 往返会随机报
RPC_E_CALL_REJECTED 并卡死，因此报告生成已改为：
    DOCX —— ooxml_docx.DocxBuilder（纯 OOXML，零 COM）
    PDF  —— pdf_report.PdfDoc（reportlab 直出）
保留本文件仅为记录被放弃的方案，可安全忽略；
实验主流程与 make_report.py 都不依赖它。
================================================================================
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
SHOT = OUT / "截图"
REPORT_DIR = BASE.parent / "报告"
REPORT_DIR.mkdir(exist_ok=True)

import win32com.client as wc  # noqa: E402

# ---------------------------------------------------------------- 排版常量 ---
FONT_CN = "宋体"
FONT_CN_BOLD = "黑体"
FONT_EN = "Times New Roman"
FONT_MONO = "Consolas"

SZ_TITLE = 22      # 二号
SZ_H1 = 15         # 小三
SZ_H2 = 12         # 小四
SZ_BODY = 10.5     # 五号
SZ_SMALL = 9
SZ_CODE = 8.5

LINE_BODY = 16     # 正文固定行距（磅）
USABLE_CM = 16.0   # A4 去掉左右页边距后的可用宽度


# ------------------------------------------------------------ Word 操作封装 ---
class Doc:
    def __init__(self, app):
        self.app = app
        self.doc = app.Documents.Add()
        self.sel = app.Selection
        self.sel.HomeKey(6)  # wdStory

    # ---------- 基础段落 ----------
    def para(self, text="", size=SZ_BODY, cjk=FONT_CN, latin=FONT_EN, bold=False,
             align=0, space_before=0, space_after=4, line=LINE_BODY,
             color=0, indent_first=0, left_indent=0, shade=False):
        """0=左 1=中 2=右 3=两端对齐"""
        sel = self.sel
        sel.EndKey(6)
        sel.ParagraphFormat.Alignment = align
        sel.ParagraphFormat.SpaceBefore = space_before
        sel.ParagraphFormat.SpaceAfter = space_after
        sel.ParagraphFormat.LineSpacingRule = 4   # wdLineSpaceExactly
        sel.ParagraphFormat.LineSpacing = line
        sel.ParagraphFormat.LeftIndent = left_indent
        sel.ParagraphFormat.FirstLineIndent = indent_first
        # 代码块设置过底纹，这里必须显式复位，否则底纹会"传染"给后续段落
        try:
            sel.Paragraphs(1).Shading.BackgroundPatternColor = (
                0xF5F5F0 if shade else -16777216)   # wdColorAutomatic
        except Exception:
            pass
        f = sel.Font
        f.Name = latin
        f.NameFarEast = cjk
        f.Size = size
        f.Bold = bold
        f.Color = color
        f.Italic = False
        sel.TypeText(text)
        sel.TypeParagraph()
        return self

    def title(self, text, size=SZ_TITLE):
        return self.para(text, size=size, cjk=FONT_CN_BOLD, bold=True,
                         align=1, space_before=6, space_after=10, line=size + 12)

    def h1(self, text):
        return self.para(text, size=SZ_H1, cjk=FONT_CN_BOLD, bold=True,
                         align=0, space_before=10, space_after=6, line=20)

    def h2(self, text):
        return self.para(text, size=SZ_H2, cjk=FONT_CN_BOLD, bold=True,
                         align=0, space_before=6, space_after=3, line=17)

    def body(self, text, indent=True, size=SZ_BODY):
        return self.para(text, size=size, align=3, indent_first=size * 2 if indent else 0)

    def bullet(self, text, size=SZ_BODY):
        return self.para("· " + text, size=size, align=3,
                         left_indent=size * 2, space_after=2)

    def note(self, text, size=SZ_SMALL):
        return self.para(text, size=size, align=3, color=0x595959,
                         left_indent=size * 2, space_after=3)

    def code(self, lines, caption=None):
        """等宽代码块：浅灰底纹 + 无缩进 + 窄行距。"""
        if caption:
            self.para(caption, size=SZ_SMALL, cjk=FONT_CN_BOLD, bold=True,
                      space_before=4, space_after=1, line=12)
        sel = self.sel
        for i, ln in enumerate(lines):
            sel.EndKey(6)
            pf = sel.ParagraphFormat
            pf.Alignment = 0
            pf.LeftIndent = 10
            pf.RightIndent = 4
            pf.FirstLineIndent = 0
            pf.SpaceBefore = 0
            pf.SpaceAfter = 0
            pf.LineSpacingRule = 4
            pf.LineSpacing = 11.5
            f = sel.Font
            f.Name = FONT_MONO
            f.NameFarEast = FONT_CN
            f.Size = SZ_CODE
            f.Bold = False
            f.Color = 0
            sel.Paragraphs(1).Shading.BackgroundPatternColor = 0xF5F5F0
            sel.TypeText(ln if ln else " ")
            if i < len(lines) - 1:
                sel.TypeParagraph()
        sel.EndKey(6)
        sel.TypeParagraph()

    def table(self, header, rows, widths=None, size=SZ_SMALL, caption=None):
        if caption:
            self.para(caption, size=SZ_SMALL, cjk=FONT_CN_BOLD, bold=True,
                      space_before=5, space_after=2, line=12)
        sel = self.sel
        sel.EndKey(6)
        rng = sel.Range
        tbl = self.doc.Tables.Add(rng, len(rows) + 1, len(header))
        tbl.Range.Font.Name = FONT_EN
        tbl.Range.Font.NameFarEast = FONT_CN
        tbl.Range.Font.Size = size
        tbl.Range.ParagraphFormat.LineSpacingRule = 0
        tbl.Range.ParagraphFormat.SpaceBefore = 1
        tbl.Range.ParagraphFormat.SpaceAfter = 1
        tbl.Range.ParagraphFormat.Alignment = 1

        for j, h in enumerate(header):
            c = tbl.Cell(1, j + 1)          # 表头加粗
            c.Range.Text = str(h)
            c.Range.Font.Bold = True
            c.Range.Font.NameFarEast = FONT_CN_BOLD
            c.Shading.BackgroundPatternColor = 0xEDEDED
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                tbl.Cell(i + 2, j + 1).Range.Text = str(v)

        tbl.Borders.Enable = True
        tbl.PreferredWidthType = 2      # wdPreferredWidthPercent
        tbl.PreferredWidth = 100
        if widths:
            total = sum(widths)
            for j, w in enumerate(widths):
                tbl.Columns(j + 1).PreferredWidthType = 2
                tbl.Columns(j + 1).PreferredWidth = 100 * w / total
        # 表头跨页重复
        tbl.Rows(1).HeadingFormat = True

        sel.EndKey(6)
        sel.TypeParagraph()
        return tbl

    def image(self, filename, caption=None, width_cm=None):
        path = SHOT / filename
        if not path.is_file():
            self.para(f"[截图缺失：{filename}]", size=SZ_SMALL, color=0xC00000)
            return
        if width_cm is None:
            from PIL import Image
            w, h = Image.open(path).size
            width_cm = min(USABLE_CM, USABLE_CM)
        sel = self.sel
        sel.EndKey(6)
        sel.ParagraphFormat.Alignment = 1
        sel.ParagraphFormat.SpaceBefore = 4
        sel.ParagraphFormat.SpaceAfter = 2
        sel.ParagraphFormat.LineSpacingRule = 0
        # AddPicture 直接返回 InlineShape，不要再用 InlineShapes(n) 反查
        shp = sel.InlineShapes.AddPicture(str(path), False, True, sel.Range)
        shp.LockAspectRatio = True
        shp.Width = self.app.CentimetersToPoints(width_cm)
        sel.EndKey(6)
        sel.TypeParagraph()
        if caption:
            self.para(caption, size=SZ_SMALL, align=1, color=0x595959,
                      space_after=6, line=12)

    def page_break(self):
        sel = self.sel
        sel.EndKey(6)
        sel.InsertBreak(7)   # wdPageBreak

    def finish(self):
        # 页面设置：A4 + 页边距
        ps = self.doc.PageSetup
        ps.PageWidth = self.app.CentimetersToPoints(21.0)
        ps.PageHeight = self.app.CentimetersToPoints(29.7)
        ps.TopMargin = self.app.CentimetersToPoints(2.2)
        ps.BottomMargin = self.app.CentimetersToPoints(2.0)
        ps.LeftMargin = self.app.CentimetersToPoints(2.5)
        ps.RightMargin = self.app.CentimetersToPoints(2.5)
