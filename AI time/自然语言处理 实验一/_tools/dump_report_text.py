# -*- coding: utf-8 -*-
"""把报告 PDF 全文按页导出成纯文本，供逐句核对（不抽关键词，只看内容）。"""
import pathlib
import sys

import pypdf

sys.stdout.reconfigure(encoding="utf-8")
BASE = pathlib.Path(__file__).resolve().parent.parent
PDF = BASE / "报告" / "202400502133陈佳豪实验1.pdf"

out = []
for i, p in enumerate(pypdf.PdfReader(str(PDF)).pages, 1):
    out.append(f"\n{'=' * 30} 第 {i} 页 {'=' * 30}\n" + (p.extract_text() or ""))

dst = BASE / "_rep.txt"
dst.write_text("\n".join(out), encoding="utf-8")
print(f"已导出 {dst.name}，{sum(len(x) for x in out)} 字符")