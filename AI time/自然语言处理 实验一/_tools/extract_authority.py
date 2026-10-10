# -*- coding: utf-8 -*-
"""抽取三份权威文件（指导书 PDF / 报告模板 DOCX / 评分标准 DOCX）的正文，供逐条核对。

注意：不要用 `python -c "..."` 内联跑中文路径——PowerShell 5.1 会把参数按本地
代码页转码，中文路径在传给 Python 之前就已经损坏（实测报
FileNotFoundError: '����\\ʵ��һָ����_...'）。必须走脚本文件。
"""
import pathlib
import re
import sys
import zipfile

import pypdf

sys.stdout.reconfigure(encoding="utf-8")

BASE = pathlib.Path(__file__).resolve().parent.parent
# 三份权威文件在「材料\实验课讲义+数据\」下，不在「材料\」根下。
MAT = next(p for p in (BASE / "材料").iterdir()
           if p.is_dir() and (p / "实验一指导书_NLP开发环境与基础文本处理.pdf").is_file())
OUT = BASE / "_auth"
OUT.mkdir(exist_ok=True)

# ---- 1) 指导书 PDF ----
r = pypdf.PdfReader(str(MAT / "实验一指导书_NLP开发环境与基础文本处理.pdf"))
parts = []
for i, p in enumerate(r.pages, 1):
    parts.append(f"\n========== [PDF p{i}] ==========\n" + (p.extract_text() or ""))
(OUT / "guide.txt").write_text("\n".join(parts), encoding="utf-8")
print(f"指导书 PDF: {len(r.pages)} 页, {sum(len(x) for x in parts)} 字符")

# ---- 2) 两个 DOCX ----
for name, dst in (
    ("自然语言处理-实验报告要求及评分标准.docx", "score.txt"),
    ("自然语言处理-实验报告模板.docx", "tpl.txt"),
):
    xml = zipfile.ZipFile(MAT / name).read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tc>", " | ", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    xml = xml.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    (OUT / dst).write_text(xml, encoding="utf-8")
    print(f"{dst}: {len(xml)} 字符")