# -*- coding: utf-8 -*-
"""交叉核对：DOCX 与 PDF 是不是同一份内容。

为什么必须单独验：报告有两套**互相独立**的排版后端——
DOCX 走纯 OOXML（ooxml_docx.py），PDF 走 reportlab（pdf_report.py），
只共用一个 Doc 门面。门面参数一旦被某一侧忽略（比如 shade / caption /
align 只在 PDF 生效），PDF 目视完全正常，Word 版却缺东西，
而 DOCX 恰恰是用户手填签名、改思考题后会真正交出去的那份。

判据：DOCX 里每个非空段落的正文（去掉所有空白后）必须能在 PDF 全文里找到。
这是 DOCX ⊆ PDF 的子集检查——PDF 还多出页眉页脚，属正常，不算差异。

用法：python compare_docx_pdf.py [docx路径] [pdf路径]
"""
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

REPORT_DIR = Path(r"D:\深技大课程学习\AI time\自然语言处理 实验一\报告")
DEFAULT_DOCX = REPORT_DIR / "202400502133陈佳豪实验1.docx"
DEFAULT_PDF = REPORT_DIR / "202400502133陈佳豪实验1.pdf"

# 「可见空格」符号：正文里写成 ␣␣ 是为了让"两个连续空格"肉眼可见。
# 两套后端对它的处理可能不一致，所以比对时要把这类符号视为等价——
# 否则会把"同一句话、标记不同"误报成"内容缺失"。
VISIBLE_SPACES = "␣␠▁□■"
_VS_RE = re.compile(f"[{VISIBLE_SPACES}]")

# PDF 抽取时会出现、但正文里不该有的排版噪声
NOISE = re.compile(r"[\s\u00a0\u3000]+")


def norm(s):
    """去掉所有空白后比较：PDF 抽取会在换行处插入空白，DOCX 不会。"""
    return NOISE.sub("", s or "")


def norm_loose(s):
    """先把可见空格符号折成普通空格，再去空白——用于识别"标记不同但内容相同"。"""
    return norm(_VS_RE.sub(" ", s or ""))


def docx_paragraphs(path):
    """按文档顺序取出所有段落文字（含表格单元格内的段落）。"""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{W}p"):
        txt = "".join(t.text or "" for t in p.iter(f"{W}t"))
        if norm(txt):
            out.append(txt)
    return out


def docx_tables_text(path):
    """表格逐格文字，用来核对表格内容。"""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    cells = []
    for tc in root.iter(f"{W}tc"):
        txt = "".join(t.text or "" for t in tc.iter(f"{W}t"))
        if norm(txt):
            cells.append(txt)
    return cells


def pdf_text(path):
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def main():
    # 调试用：python compare_docx_pdf.py --grep 关键词
    if "--grep" in sys.argv:
        kw = sys.argv[sys.argv.index("--grep") + 1]
        pdf = Path(sys.argv[sys.argv.index("--grep") + 2]) if len(sys.argv) > (
            sys.argv.index("--grep") + 2) else DEFAULT_PDF
        txt = pdf_text(pdf)
        for line in txt.splitlines():
            if kw in line:
                print(repr(line))
        return 0

    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOCX
    pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PDF
    for p in (docx, pdf):
        if not p.is_file():
            print(f"文件不存在：{p}")
            return 2
    print(f"DOCX : {docx.name}  ({docx.stat().st_size // 1024} KB)")
    print(f"PDF  : {pdf.name}  ({pdf.stat().st_size // 1024} KB)\n")

    ptxt = norm(pdf_text(pdf))
    paras = docx_paragraphs(docx)
    cells = docx_tables_text(docx)
    raw_pdf_text = pdf_text(pdf)
    loose_pdf = norm_loose(raw_pdf_text)

    missing = []
    marker_only = []
    for t in paras:
        n = norm(t)
        if n in ptxt:
            continue
        if norm_loose(t) in loose_pdf:
            marker_only.append(t)
        else:
            missing.append(("段落", t))
    cells_missing = [t for t in cells if norm(t) not in ptxt]

    print(f"DOCX 非空段落 {len(paras)} 条，表格单元 {len(cells)} 格")
    print(f"PDF  抽取 {len(raw_pdf_text)} 字符（归一化 {len(ptxt)}）")

    if marker_only:
        print(f"\n  [WARN] {len(marker_only)} 处内容两边都在，但可见空格标记渲染不一致：")
        for t in marker_only:
            sym = [c for c in VISIBLE_SPACES if c in t]
            print(f"    DOCX 侧标记 {''.join(sorted(set(sym)))}  {t[:64]!r}")
        print("    → 两套后端对「可见空格」的处理不同，同一句话看起来不一样。")

    if missing or cells_missing:
        print()
        for kind, t in missing:
            print(f"  [FAIL] {kind} 未出现在 PDF：{t[:80]!r}")
        for t in cells_missing:
            print(f"  [FAIL] 表格单元未出现在 PDF：{t[:80]!r}")
        print(f"\n结论：DOCX 有 {len(missing) + len(cells_missing)} 处内容在 PDF 中找不到，"
              f"两侧内容不一致。")
        return 1

    print("\n结论：DOCX 的每一个段落与每一个表格单元都能在 PDF 里逐字找到，"
          "两套后端内容一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())