# -*- coding: utf-8 -*-
"""
================================================================================
中文排版禁则（避头/避尾）实测检查
--------------------------------------------------------------------------------
用法：python _tools/check_kinsoku.py [报告PDF路径]

为什么要有这个脚本
    正文通篇用全角标点，而 reportlab 自带的 ALL_CANNOT_START 收的是**半角**
    , . : ; ? ! " )，全角 ，：；？！ 根本不在表里，断行时拦不住，
    这些字符就会落到行首。这里不靠肉眼判断，直接从**生成出来的 PDF**
    逐行抽出行首字符来数。

怎么区分「正文」和「代码」
    按**字体**判定，不靠字符串猜测：
        代码块 = NSimSun（本项目 code_block 指定的等宽新宋体）
        正文   = SimSun / SimHei
    代码块里的三引号 docstring、正则尾部的右括号属于代码语法，不是中文避头
    问题，混进来会让判据失真（实测第一版就把 4 个代码行误报成违规）。

怎么区分「项目符号」
    本报告的项目符号一律以 "· " 起头（见 make_report.build_body 的 bullet），
    是刻意的列表标记，不是断行把 · 甩到了行首，直接跳过。

判据边界（别让后人误以为它验过内容）
    只查「行首/行尾是否出现禁则字符」，不查排版是否好看、截图是否清楚、
    内容是否正确。
================================================================================
"""

import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 不得出现在行首（避头）
CANNOT_START = set("，。、；：！？”’）］｝》〉」』】〕％‰°…～·’”")
# 不得出现在行尾（避尾）—— 只提示，不计入失败：reportlab 不做这一侧
CANNOT_END = set("“‘（［｛《〈「『【〔")

BULLET = "·"          # 本报告的项目符号
CODE_FONT = "NSimSun"  # 代码块专用字体

# 不允许被断行拆开的整词：文件名、编码名、带箭头的数值链等。
# reportlab 的 CJK 断行是逐字进行的，列一窄就会从词中间断开，
# 出现过 `optional_G_utf8sig.tx` + `t`、`utf-8-si` + `g` 这类半截词。
NO_BREAK = [
    "input_A_utf8.txt", "input_B_utf8sig.txt", "input_C_gb18030.txt",
    "input_D_utf16.txt", "optional_E_utf8.txt", "optional_F_gb18030.txt",
    "optional_G_utf8sig.txt", "optional_H_utf16.txt", "optional_I_utf8.txt",
    "optional_J_gb18030.txt",
    "utf-8-sig", "utf-16", "gb18030", "NFKC", "PROTECT_WORDS",
    "load_stopwords", "exp1_starter.py", "debug_record.py", "verify_report.py",
]


def _page_lines(page):
    """按实际 y 坐标把 PDF 页面切成行，并标出该行是否属于代码块。

    注意坐标合成：pypdf 的 visitor 回调里 tm 是**相对当前文本对象原点**的，
    reportlab 整段共用一个文本对象，同一个 tm[5] 会被多行共用（实测一页
    605 个文本块只落在 22 个 tm[5] 上，直接按 tm 分行会把整页并成 22 行）。
    真实位置要取 cm 与 tm 的平移分量之和。
    """
    items = []

    def visit(text, cm, tm, fd, fs):
        if not text or not text.strip():
            return
        base = (fd or {}).get("/BaseFont") or ""
        items.append((round(float(cm[5]) + float(tm[5]), 1),
                      float(cm[4]) + float(tm[4]), text, str(base)))

    page.extract_text(visitor_text=visit)
    items.sort(key=lambda it: (-it[0], it[1]))

    lines, cur, cur_y = [], [], None
    for y, x, t, f in items:
        if cur_y is None or abs(y - cur_y) > 2.0:
            if cur:
                lines.append(cur)
            cur, cur_y = [(x, t, f)], y
        else:
            cur.append((x, t, f))
    if cur:
        lines.append(cur)

    out = []
    for ln in lines:
        text = "".join(t for _, t, _ in ln)
        fonts = [f for _, _, f in ln]
        n_code = sum(1 for f in fonts if CODE_FONT in f)
        is_code = n_code * 2 >= len(fonts)
        out.append((text, is_code))
    return out


FONTS = [                       # (路径, subfont 序号, 名称)
    (r"C:\Windows\Fonts\simsun.ttc", 0, "SimSun"),
    (r"C:\Windows\Fonts\simsun.ttc", 1, "NSimSun"),
    (r"C:\Windows\Fonts\simhei.ttf", 0, "SimHei"),
]

_font_cache = None


def _missing_glyphs(text):
    """返回 text 中三种字体都覆盖不到的字符（会渲染成空白/方块）。"""
    global _font_cache
    if _font_cache is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from font_cmap import cmap_ranges, covers
        tables = []
        for path, idx, _name in FONTS:
            if not Path(path).is_file():
                continue
            tables.append(cmap_ranges(path, subfont=idx))
        _font_cache = (tables, covers)
    tables, covers = _font_cache
    if not tables:
        return []
    miss, seen = [], set()
    for ch in text:
        cp = ord(ch)
        if cp < 0x20 or ch in " \n\r\t" or cp in seen:
            continue
        seen.add(cp)
        if not any(covers(t, cp) for t in tables):
            miss.append(ch)
    return miss


def main():
    root = Path(__file__).resolve().parent.parent
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        root / "报告" / "202400502133陈佳豪实验1.pdf"
    if not pdf.is_file():
        print(f"[FAIL] 报告 PDF 不存在：{pdf}")
        return 1

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    head_bad, tail_bad = Counter(), Counter()
    head_ex, tail_ex = [], []
    n_line = n_code = n_bullet = 0
    page_text = []

    for pno, page in enumerate(reader.pages, 1):
        for text, is_code in _page_lines(page):
            page_text.append(text)
            line = text.strip()
            if not line:
                continue
            if is_code:
                n_code += 1
                continue
            if line.startswith(BULLET):
                n_bullet += 1
                continue
            n_line += 1
            h, t = line[0], line[-1]
            if h in CANNOT_START:
                head_bad[h] += 1
                if len(head_ex) < 15:
                    head_ex.append((pno, line[:40], h))
            if t in CANNOT_END:
                tail_bad[t] += 1
                if len(tail_ex) < 8:
                    tail_ex.append((pno, line[-40:], t))

    print("=" * 74)
    print("中文排版禁则（避头/避尾）实测检查")
    print("=" * 74)
    print(f"  报告        ：{pdf.name}")
    print(f"  页数        ：{len(reader.pages)}")
    print(f"  正文行      ：{n_line}   （已排除代码行 {n_code}、项目符号行 {n_bullet}）")
    print(f"  避头禁则集  ：{len(CANNOT_START)} 字符")

    ok = not head_bad
    print()
    if head_bad:
        print("  [行首避头违规] —— 必须为 0：")
        for ch, n in head_bad.most_common():
            print(f"    {ch!r:<8} U+{ord(ch):04X}  x{n:<3} "
                  f"{unicodedata.name(ch, '?')}")
        for pno, line, ch in head_ex:
            print(f"      p{pno:<3} {line!r:<46} <- {ch!r}")
    else:
        print("  [OK] 正文行首无避头违规。")

    if tail_bad:
        print("\n  [行尾避尾提示] —— 不计入失败，仅供人工判断：")
        for ch, n in tail_bad.most_common():
            print(f"    {ch!r:<8} x{n}")
        for pno, line, ch in tail_ex:
            print(f"      p{pno:<3} {line!r:<46} <- {ch!r}")

    # ---- 整词完整性：列宽被改窄时最容易悄悄回归的一项 ----------------------
    flat = "".join(page_text)
    broken = [tok for tok in NO_BREAK if tok not in flat]
    print(f"\n  整词完整性  ：抽查 {len(NO_BREAK)} 个文件名/编码名/函数名")
    if broken:
        print(f"  [断词] 以下整词在 PDF 中找不到完整形态（多半是被列宽拆开了）：")
        for tok in broken:
            print(f"    - {tok}")
        ok = False
    else:
        print("  [OK] 抽查的整词全部完整，未被断行拆开。")

    # ---- 字形覆盖：文本层正常、视觉上是空白方块的一类缺陷 -------------------
    # 先看 PDF 文本层里的「.notdef 指纹」。这一条不能省：
    # reportlab 遇到没有字形的字符会写 glyph 0，PDF 里渲染成空框，但文本层
    # 抽出来是 U+0000（或 U+FFFD），**原字符已经不在文本层里了**。
    # 所以下面 _missing_glyphs(flat) 那种"拿文本层问字体"的做法，
    # 对这类缺陷结构性失明——实测漏掉了 U+2423（␣）渲染成 \x00\x00。
    # 指纹是唯一能在事后看见它的证据，必须单独判。
    notdef = sorted({c for c in flat if c in ("\x00", "�")})
    miss = _missing_glyphs(flat)
    print("\n  字形覆盖    ：对照 SimSun / SimHei / NSimSun 的 cmap")
    if notdef:
        print(f"  [缺字形] PDF 文本层里出现 {len(notdef)} 个 .notdef 指纹字符，"
              f"说明有字符**没有字形**、在页面上渲染成了空框：")
        for c in notdef:
            n = flat.count(c)
            idx = flat.find(c)
            ctx = flat[max(0, idx - 18):idx + 6].replace("\n", " ")
            print(f"    {c!r} U+{ord(c):04X} ×{n}  上下文 …{ctx}…")
        ok = False
    if miss:
        print("  [缺字形] 以下字符三种字体都没有，PDF 里会渲染成空白/方块：")
        for ch in miss[:20]:
            print(f"    {ch!r} U+{ord(ch):04X}  {unicodedata.name(ch, '?')}")
        ok = False
    if not notdef and not miss:
        print("  [OK] 报告用到的字符三种字体均有字形，且没有 .notdef 指纹。")

    print("\n  结论：" + ("全部通过。" if ok else "存在排版问题，见上。"))
    print("=" * 74)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())