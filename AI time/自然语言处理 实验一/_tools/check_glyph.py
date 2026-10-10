# -*- coding: utf-8 -*-
"""查某个字符在 SimSun / SimHei / NSimSun 里到底有没有字形。

背景：reportlab 把没有字形的字符写成 .notdef(glyph 0)，PDF 里渲染成空框，
但文本层抽出来是 U+0000——于是「文本层里有这个字」这种检查完全发现不了。
所以字形这件事必须直接问字体，不能问 PDF。

用法：python check_glyph.py "␣" "　"
"""
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from font_cmap import cmap_ranges, covers          # noqa: E402

FONTS = [
    (r"C:\Windows\Fonts\simsun.ttc", 0, "SimSun"),
    (r"C:\Windows\Fonts\simsun.ttc", 1, "NSimSun"),
    (r"C:\Windows\Fonts\simhei.ttf", 0, "SimHei"),
]

tables = []
for path, idx, name in FONTS:
    if Path(path).is_file():
        tables.append((name, cmap_ranges(path, subfont=idx)))
    else:
        print(f"字体缺失：{path}")


def docx_text(path):
    """从 DOCX 取全部文字。

    为什么从 DOCX 而不是 PDF 抽文本：PDF 里没有字形的字符已经被写成 glyph 0，
    抽出来是 U+0000，**原字符已经丢了**，再问字体就问不出来了。
    DOCX 走的是另一套后端、字面原样保留，是唯一可信的"我到底想印什么"的来源。
    """
    import zipfile
    from xml.etree import ElementTree as ET
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return "".join(t.text or "" for t in root.iter(f"{W}t"))


def main():
    args = sys.argv[1:]

    # 模式：扫描整份 DOCX，列出所有三种字体都覆盖不到的字符
    if args and args[0] == "--docx":
        target = Path(args[1]) if len(args) > 1 else Path(
            r"D:\深技大课程学习\AI time\自然语言处理 实验一\报告"
            r"\202400502133陈佳豪实验1.docx")
        text = docx_text(target)
        print(f"扫描 {target.name}  文本 {len(text)} 字符\n")
        miss = {}
        for ch in text:
            cp = ord(ch)
            if cp < 0x20 or cp in (0x7F,) or ch in " \n\r\t":
                continue
            if cp in miss:
                miss[cp][1] += 1
                continue
            if not any(covers(t, cp) for _, t in tables):
                miss[cp] = [ch, 1]
        if not miss:
            print("结论：DOCX 里的字符三种字体全部覆盖。")
            return 0
        print("结论：以下字符三种字体都没有，PDF 上会渲染成空框：")
        for cp, (ch, n) in sorted(miss.items()):
            where = ""
            i = text.find(ch)
            if i >= 0:
                where = f"  上下文 …{text[max(0, i-16):i+12]}…"
            print(f"  U+{cp:04X} {ch!r:<8} ×{n:<3} "
                  f"{unicodedata.name(ch, '?')}{where}")
        return 1

    if not args:
        print(__doc__)
        return 2
    bad = 0
    for ch in args:
        cp = ord(ch)
        line = [f"U+{cp:04X} {ch!r:<10} {unicodedata.name(ch, '?')[:40]:<42}"]
        for name, t in tables:
            has = covers(t, cp)
            line.append(f"{name}:{'有' if has else '缺'}")
            if not has:
                bad += 1
        print("  ".join(line))
    print()
    if bad:
        print(f"结论：有 {bad} 处缺字形——这些字符在 PDF 里会渲染成空白/方块。")
        return 1
    print("结论：全部字符三种字体均有字形。")
    return 0


if __name__ == "__main__":
    sys.exit(main())