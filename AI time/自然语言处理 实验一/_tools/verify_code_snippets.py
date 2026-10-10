# -*- coding: utf-8 -*-
"""核对报告里的代码片段确实来自 exp1_starter.py，而不是我另写一份好看的。

为什么必须查：报告 5.1 标的是「关键代码片段」，读者（老师）会默认它就是程序里
跑的那段。我这轮为了排版把片段"压缩"过——把 `for encoding in CANDIDATE_ENCODINGS`
写成字面量元组、把 `assert ok` 改成 `assert condition`、把真实 docstring 换成一句
摘要。单看报告完全正常，但它已经**不是同一个程序**了。这类漂移没有任何其他
检查能发现：结构自检只看 XML，数字核验只看表格，排版检查只看字形。

判据：代码块里每一行（去掉缩进后）都必须能在 exp1_starter.py 里原样找到。
本脚本自己也被变异测试过——把片段改一个字就会报红。

用法：python verify_code_snippets.py [docx路径] [源码路径]
"""
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(r"D:\深技大课程学习\AI time\自然语言处理 实验一")
DEFAULT_DOCX = ROOT / "报告" / "202400502133陈佳豪实验1.docx"
DEFAULT_SRC = ROOT / "实验一" / "exp1_starter.py"

CODE_FONTS = ("NSimSun", "Consolas")


def code_lines(path):
    """取出 DOCX 里用等宽字体排版的段落（即代码块）。"""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{W}p"):
        fonts = {rf.get(f"{W}ascii") for rf in p.iter(f"{W}rFonts")}
        if not fonts & set(CODE_FONTS):
            continue
        txt = "".join(t.text or "" for t in p.iter(f"{W}t"))
        if txt.strip():
            out.append(txt)
    return out


def main():
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOCX
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SRC
    for p in (docx, src):
        if not p.is_file():
            print(f"文件不存在：{p}")
            return 2

    srclines = src.read_text(encoding="utf-8").splitlines()
    srcset = {ln.strip() for ln in srclines if ln.strip()}
    blocks = code_lines(docx)

    missing = []
    for ln in blocks:
        s = ln.strip()
        if s in srcset:
            continue
        missing.append(ln)

    print("=" * 74)
    print("代码片段 ↔ 源程序 逐行核对")
    print("=" * 74)
    print(f"DOCX : {docx.name}")
    print(f"源码  : {src.name}  ({len(srclines)} 行)")
    print(f"代码块行：{len(blocks)} 行")

    if missing:
        print(f"\n  [FAIL] 有 {len(missing)} 行在源码里找不到原样形态——"
              f"报告里的代码和实际跑的程序对不上：")
        for ln in missing:
            print(f"    {ln.strip()!r}")
        print("\n  结论：代码片段与源程序不一致。摘录只能删，不能改写。")
        print("=" * 74)
        return 1

    print("\n  [OK] 代码块每一行都能在 exp1_starter.py 里原样找到。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())