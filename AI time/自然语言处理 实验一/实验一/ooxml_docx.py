# -*- coding: utf-8 -*-
"""
================================================================================
最小 OOXML (.docx) 生成器
--------------------------------------------------------------------------------
为什么不用 Word COM 逐段写入：本机的 Word COM 是一个不太可靠的 shim，
大量 COM 往返调用会出现 RPC_E_CALL_REJECTED（被呼叫方拒绝接收呼叫）并卡死。
改为直接生成 OOXML —— 完全可控、可复现、零 COM 依赖；
最后只用 Word 做一次"打开并导出 PDF"。

支持：段落（字体/字号/加粗/颜色/对齐/行距/缩进/底纹）、代码块、
      表格（边框/列宽/表头底纹/跨页重复）、内嵌图片（按厘米定宽）、分页符、A4 页面设置。

EMU：1 cm = 360000 EMU      缇(twip)：1 cm = 567 twip，1 pt = 20 twip
字号 w:sz 单位为半磅（half-point），10.5 pt -> 21
================================================================================
"""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

CM_EMU = 360000
CM_TWIP = 567

FONT_CN = "宋体"
FONT_CN_BOLD = "黑体"
FONT_EN = "Times New Roman"
FONT_MONO = "Consolas"

PAGE_W_CM, PAGE_H_CM = 21.0, 29.7
# 页面设置照抄模板 sectPr：pgSz 11906x16838（A4），
# pgMar top/bottom=1440 twips(2.54cm)，left/right=1800 twips(3.175cm)
MARGIN_T, MARGIN_B, MARGIN_L, MARGIN_R = 2.54, 2.54, 3.175, 3.175
USABLE_CM = PAGE_W_CM - MARGIN_L - MARGIN_R      # 14.65cm


def esc(t):
    return escape(str(t))


class DocxBuilder:
    def __init__(self):
        self.body = []
        self.images = []          # [(rel_id, filename, bytes)]
        self._rel_no = 10
        self._img_no = 0

    # ------------------------------------------------------------ 内部工具 ---
    def _next_img(self, path):
        self._img_no += 1
        rid = f"rId{self._rel_no}"
        self._rel_no += 1
        self.images.append((rid, f"image{self._img_no}{path.suffix}", path.read_bytes()))
        return rid, self._img_no

    @staticmethod
    def _run(text, size=10.5, cjk=FONT_CN, latin=FONT_EN, bold=False,
             color="000000", italic=False):
        rpr = [f'<w:rFonts w:ascii="{latin}" w:hAnsi="{latin}" w:eastAsia="{cjk}" w:cs="{latin}"/>']
        if bold:
            rpr.append("<w:b/>")
        if italic:
            rpr.append("<w:i/>")
        rpr.append(f'<w:color w:val="{color}"/>')
        rpr.append(f'<w:sz w:val="{int(round(size * 2))}"/>')
        rpr.append(f'<w:szCs w:val="{int(round(size * 2))}"/>')
        body = esc(text).replace("\n", "</w:t><w:br/><w:t xml:space=\"preserve\">")
        return (f"<w:r><w:rPr>{''.join(rpr)}</w:rPr>"
                f'<w:t xml:space="preserve">{body}</w:t></w:r>')

    # ------------------------------------------------------------ 段落 API ---
    def para(self, text="", size=10.5, cjk=FONT_CN, latin=FONT_EN, bold=False,
             align="left", space_before=0, space_after=4, line=16,
             color="000000", indent_first=0, left_indent=0, right_indent=0,
             shade=None, line_rule="exact"):
        """
        line_rule="exact"：line 是磅值（固定行距），单位 20 twip/pt
        line_rule="auto" ：line 是"240 分之一行"（倍数行距），480=2 倍、600=2.5 倍
        模板封面的字段行就是 spacing(line=600, lineRule=auto)，即 2.5 倍行距。
        """
        if line_rule == "auto":
            sp = (f'<w:spacing w:before="{int(space_before * 20)}" '
                  f'w:after="{int(space_after * 20)}" '
                  f'w:line="{int(round(line * 240))}" w:lineRule="auto"/>')
        else:
            sp = (f'<w:spacing w:before="{int(space_before * 20)}" '
                  f'w:after="{int(space_after * 20)}" '
                  f'w:line="{int(line * 20)}" w:lineRule="exact"/>')
        ppr = [sp]
        ind = []
        if left_indent:
            ind.append(f'w:left="{int(left_indent * 20)}"')
        if right_indent:
            ind.append(f'w:right="{int(right_indent * 20)}"')
        if indent_first:
            ind.append(f'w:firstLine="{int(indent_first * 20)}"')
        if ind:
            ppr.append(f'<w:ind {" ".join(ind)}/>')
        ppr.append(f'<w:jc w:val="{align}"/>')
        if shade:
            ppr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
        self.body.append(
            f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>"
            f'{self._run(text, size, cjk, latin, bold, color)}</w:p>')

    def code_block(self, lines, size=8.0):
        """等宽代码块：整块同底纹、窄行距、无首行缩进。"""
        for ln in lines:
            self.para(ln if ln else " ", size=size, cjk=FONT_CN, latin=FONT_MONO,
                      align="left", space_before=0, space_after=0, line=10.5,
                      left_indent=0.6, right_indent=0.2, shade="F5F5F0")
        self.para("", size=4, space_after=0, line=5)

    def table(self, header, rows, widths=None, size=8.5, caption=None,
              min_row_h=0, bold_all=False, tbl_width_pct=None,
              align="center", split_in_row=True):
        # min_row_h / bold_all / tbl_width_pct 主要供 PDF 后端使用，
        # OOXML 侧能表达的部分照单实现
        if caption:
            self.para(caption, size=9, cjk=FONT_CN_BOLD, bold=True,
                      space_before=5, space_after=2, line=12)
        ncol = len(header)
        ratios = widths or [1] * ncol
        total = sum(ratios)
        cols = [int(USABLE_CM * CM_TWIP * r / total) for r in ratios]
        cols[-1] = int(USABLE_CM * CM_TWIP) - sum(cols[:-1])

        border = "".join(
            f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="9A9A9A"/>'
            for s in ("top", "left", "bottom", "right", "insideH", "insideV"))

        grid = "".join(f'<w:gridCol w:w="{c}"/>' for c in cols)
        # tbl_width_pct：不给就是 100% 满宽；给百分比则按比例收窄
        # （模板的「得分」表是 tblW=0 auto，不是满宽）
        if tbl_width_pct:
            tw = f'<w:tblW w:w="{int(tbl_width_pct * 50)}" w:type="pct"/>'
            cols = [int(c * tbl_width_pct / 100) for c in cols]
            grid = "".join(f'<w:gridCol w:w="{c}"/>' for c in cols)
        else:
            tw = '<w:tblW w:w="5000" w:type="pct"/>'

        out = [f'<w:tbl><w:tblPr>{tw}'
               f'<w:tblBorders>{border}</w:tblBorders>'
               f'<w:tblLayout w:type="fixed"/>'
               f'<w:tblCellMar>'
               f'<w:top w:w="20" w:type="dxa"/><w:left w:w="60" w:type="dxa"/>'
               f'<w:bottom w:w="20" w:type="dxa"/><w:right w:w="60" w:type="dxa"/>'
               f'</w:tblCellMar></w:tblPr>'
               f'<w:tblGrid>{grid}</w:tblGrid>']

        def row(cells, header_row=False, min_h=0):
            trpr = "<w:trPr><w:tblHeader/></w:trPr>" if header_row else ""
            if min_h:
                trpr = (f"<w:trPr>{'<w:tblHeader/>' if header_row else ''}"
                        f'<w:trHeight w:val="{int(min_h * 20)}" w:hRule="atLeast"/>'
                        f"</w:trPr>")
            tcs = []
            for j, v in enumerate(cells):
                shd = ('<w:shd w:val="clear" w:color="auto" w:fill="EDEDED"/>'
                       if header_row and not bold_all else "")
                bold = header_row or bold_all
                # 表头居中；数据格按调用方指定。文字型表（align="left"）若也居中，
                # 短行会被推到中间、末行参差，与正文的左对齐不一致。
                jc = "center" if header_row else align
                tcs.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{cols[j]}" w:type="dxa"/>{shd}'
                    f'<w:vAlign w:val="center"/></w:tcPr>'
                    f'<w:p><w:pPr><w:spacing w:before="10" w:after="10" '
                    f'w:line="240" w:lineRule="auto"/><w:jc w:val="{jc}"/></w:pPr>'
                    f'{self._run(v, size, FONT_CN if bold else FONT_CN, FONT_EN, bold)}'
                    f'</w:p></w:tc>')
            return f"<w:tr>{trpr}{''.join(tcs)}</w:tr>"

        out.append(row(header, True, 0))
        for r in rows:
            out.append(row(r, False, min_row_h))
        out.append("</w:tbl>")
        self.body.append("".join(out))
        self.para("", size=5, space_after=0, line=6)   # 表后必须有段落

    def image(self, path, width_cm=USABLE_CM):
        p = Path(path)
        if not p.is_file():
            self.para(f"[截图缺失：{p.name}]", size=9, color="C00000")
            return
        from PIL import Image
        with Image.open(p) as im:
            iw, ih = im.size
        cx = int(width_cm * CM_EMU)
        cy = int(cx * ih / iw)
        rid, idx = self._next_img(p)
        self.body.append(
            f'<w:p><w:pPr><w:spacing w:before="60" w:after="40"/>'
            f'<w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{idx}" name="Picture {idx}"/>'
            f'<wp:cNvGraphicFramePr>'
            f'<a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData '
            f'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{idx}" name="{esc(p.name)}"/>'
            f'<pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/>'
            f'<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            f'</pic:pic></a:graphicData></a:graphic>'
            f'</wp:inline></w:drawing></w:r></w:p>')

    def page_break(self):
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    # ---------------------------------------------------------------- 打包 ---
    def save(self, path):
        sectpr = (
            f'<w:sectPr><w:pgSz w:w="{int(PAGE_W_CM * CM_TWIP)}" '
            f'w:h="{int(PAGE_H_CM * CM_TWIP)}"/>'
            f'<w:pgMar w:top="{int(MARGIN_T * CM_TWIP)}" '
            f'w:right="{int(MARGIN_R * CM_TWIP)}" '
            f'w:bottom="{int(MARGIN_B * CM_TWIP)}" '
            f'w:left="{int(MARGIN_L * CM_TWIP)}" '
            f'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>')

        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<w:body>{"".join(self.body)}{sectpr}</w:body></w:document>')

        rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/styles" Target="styles.xml"/>']
        for rid, name, _ in self.images:
            rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                        f'officeDocument/2006/relationships/image" Target="media/{name}"/>')
        rels.append("</Relationships>")

        styles = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:docDefaults><w:rPrDefault><w:rPr>'
            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
            'w:eastAsia="宋体" w:cs="Times New Roman"/>'
            '<w:sz w:val="21"/><w:szCs w:val="21"/>'
            '</w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="320" w:lineRule="exact"/>'
            '</w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>')

        ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Default Extension="png" ContentType="image/png"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.'
              'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/styles.xml" ContentType="application/vnd.'
              'openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')

        root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                     'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                     '</Relationships>')

        path = Path(path)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("_rels/.rels", root_rels)
            z.writestr("word/document.xml", document)
            z.writestr("word/styles.xml", styles)
            z.writestr("word/_rels/document.xml.rels", "".join(rels))
            for _, name, data in self.images:
                z.writestr(f"word/media/{name}", data)
        return path
