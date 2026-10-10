# -*- coding: utf-8 -*-
"""
================================================================================
实验一 · 运行结果截图生成器
--------------------------------------------------------------------------------
报告要求"运行结果截图必须清晰可读"。本脚本把**真实运行输出**渲染成终端风格的
PNG 图片，报告里直接插图——不使用任何示意图或手绘内容。

设计取舍：报告要打印/提交 PDF，所以用**浅色背景**而不是常见的深色终端主题，
避免大面积底色在黑白打印时糊成一片。

运行：python make_shots.py
================================================================================
"""

import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
TOOLS = BASE.parent / "_tools"
SHOT_DIR = BASE / "outputs" / "截图"
SHOT_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = r"C:\Windows\Fonts\simsun.ttc"
FONT_INDEX = 1          # NSimSun 新宋体：ASCII 与 CJK 同宽，适合终端排版
FS = 19                 # 字号（实际按 2 倍分辨率绘制再缩放，保证清晰）
SCALE = 2

BG        = (252, 252, 250)
BAR       = (238, 240, 244)
BAR_TEXT  = (60, 66, 78)
TEXT      = (28, 30, 34)
DIM       = (120, 126, 138)
RULE      = (214, 218, 226)
PASS      = (22, 110, 60)
FAIL      = (176, 32, 32)
TITLE     = (32, 64, 128)


def load_lines(path):
    """
    日志由 PowerShell 重定向产生，编码不固定（PS 5.1 默认写 UTF-16LE），
    这里直接复用本实验自己的多编码读取函数——正好是用本实验的成果解决本实验的问题。
    """
    sys.path.insert(0, str(BASE))
    from exp1_starter import read_text_checked
    text, enc, _, _ = read_text_checked(path)
    return text.replace("\r\n", "\n").splitlines()


def slice_by_markers(lines, start, end, include_end=False):
    """按标记行截取片段；start 为 None 表示到文件首。默认不包含 end 行本身。"""
    si = 0 if start is None else next(
        (i for i, l in enumerate(lines) if start in l), None)
    if si is None:
        raise SystemExit(f"未找到起始标记：{start}")
    ei = len(lines)
    if end is not None:
        for i in range(si, len(lines)):
            if end in lines[i]:
                ei = i + 1 if include_end else i
                break
    # 去掉尾部空行
    while ei > si and not lines[ei - 1].strip():
        ei -= 1
    return lines[si:ei]


def display_width(s):
    """终端显示宽度：CJK 与全角字符占 2 列。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


MAX_COLS = 190          # 单行折行宽度（列）
# 为什么是 190：实测各组最长原行有 402~423 列（切词结果把 60 个 token 逐个列出）。
# 早先按 168 列硬截，等于把这一行悄悄砍掉一半多；改成折行后内容完整。
#
# 这个值是**版面换来的**，不是随手取的：报告总页数 10 页是指导书硬上限，而打印字号
# = 字符宽 / 图宽，图一旦变高，占用的版面就等比变多，页数立刻顶破。实测各档
# （三张组图，落版宽 9.4cm，格式 = 落版高 / 字号）：
#   120 列 → 6.4cm / 2.2pt → 报告 11 页（超限）
#   150 列 → 4.7cm / 1.7pt → 报告 11 页（超限）
#   190 列 → 3.7cm / 1.4pt → 10 页，且与原 10 页版本高度基本持平
# 想让截图真正变清晰，只能整页少放内容（删掉与 5.2/5.3 表格重复的 token 明细），
# 或者把 10 页上限让给截图——两者都要先定夺，不该在排版参数里偷偷做掉。


def wrap_cols(s, cols=MAX_COLS, min_tail=16):
    """把超过 cols 列的一行按显示宽度折行，返回若干行。

    为什么必须折行而不是直接截断：报告要求「截图清晰可读」，而落版宽度固定，
    打印字号 = 字符宽 / 图宽。图一旦被最长的那行撑到 168 列，其余几十行都跟着
    被缩小到 ~1.5pt（实测，见 _tools/probe_shots.py），印出来根本读不出来。
    折行只改变长宽比、不丢任何字符，是唯一不损失信息的做法。

    断点优先落在逗号/空格附近，且保证续行不短于 min_tail 列，避免在行尾
    孤零零地甩一两个字。纯 ASCII 串按显示宽度切即可。
    """
    if display_width(s) <= cols:
        return [s]
    parts, rest = [], s
    while display_width(rest) > cols:
        # 在最后一列附近找一个像断点的位置
        cut, acc, best = 0, 0, 0
        for i, ch in enumerate(rest):
            w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
            if acc + w > cols:
                break
            acc += w
            cut = i + 1
            if ch in "，。；、,; ":
                best = i + 1
        # 断点太靠前（续行会太短）就退回 cols 处的硬边界
        if best and (cols - display_width(rest[:best])) < min_tail:
            best = cut
        parts.append(rest[:best])
        rest = rest[best:]
    if rest:
        parts.append(rest)
    return parts


def colorize(line):
    """按内容给行上色：断言结果、错误、分隔线、标题。"""
    s = line.strip()
    if s.startswith("[PASS]"):
        return PASS
    if s.startswith("[FAIL]") or "✗" in line or "Error" in s or "error" in s:
        return FAIL
    if s.startswith("【") or s.startswith("第 "):
        return TITLE
    if set(s) <= set("=-") and len(s) >= 8:
        return DIM
    if line.startswith("  识别编码") or line.startswith("  BOM"):
        return TEXT
    return TEXT


def render(lines, title, out_name, max_lines=None):
    if max_lines:
        lines = lines[:max_lines]

    # 先折行再量宽度：宽度由折行后的最长行决定，图才不会被一行长文本撑爆
    wrapped = []
    for ln in lines:
        wrapped.extend(wrap_cols(ln))
    lines = wrapped

    font = ImageFont.truetype(FONT_PATH, FS * SCALE, index=FONT_INDEX)
    font_sm = ImageFont.truetype(FONT_PATH, int(FS * 0.86) * SCALE, index=FONT_INDEX)

    probe = Image.new("RGB", (10, 10))
    d0 = ImageDraw.Draw(probe)
    cw = d0.textlength("M", font=font)          # 等宽：全角占两格
    lh = int(FS * SCALE * 1.55)
    pad = 14 * SCALE
    bar_h = int(30 * SCALE)

    # 宽度按实际最长行计算（CJK 按 2 列计），避免右侧被裁掉
    need_cols = max((display_width(l) for l in lines), default=80)
    need_cols = max(need_cols, display_width(title) + 4)
    width = int(cw * min(need_cols, MAX_COLS + 8)) + pad * 2
    height = bar_h + pad * 2 + lh * len(lines)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, width, bar_h], fill=BAR)
    d.line([0, bar_h, width, bar_h], fill=RULE, width=max(1, SCALE // 2))
    d.text((pad, bar_h // 2), title, font=font_sm, fill=BAR_TEXT, anchor="lm")

    y = bar_h + pad
    for ln in lines:
        col = colorize(ln)
        d.text((pad, y), ln, font=font, fill=col, anchor="lt")
        y += lh

    # 缩小回 1x（PIL 按 2x 绘制再 LANCZOS 缩放，边缘更干净）
    img = img.resize((width // SCALE, height // SCALE), Image.LANCZOS)
    out = SHOT_DIR / out_name
    img.save(out, "PNG", optimize=True)
    flag = "  [! 超高" if img.size[1] > MAX_H_PX else ""
    print(f"  写入 {out.name}  {img.size[0]}x{img.size[1]}px  "
          f"({len(lines)} 行, {out.stat().st_size // 1024} KB){flag}")
    return out


JOBS = [
    # (源文件, 起始标记, 结束标记, 图片标题, 输出名)
    ("v_main.txt", "【第 0 部分】", "【第 2 部分】", "python exp1_starter.py  —  环境自检与停用词表",
     "shot1_env.png"),
    ("v_main.txt", "【A 组 · 必做】", "【B 组 · 必做】", None,
     "shot2_A.png"),
    ("v_main.txt", "【B 组 · 必做】", "【C 组 · 必做】", None,
     "shot3_B.png"),
    ("v_main.txt", "【C 组 · 必做】", "【D 组 · 必做】", None,
     "shot4_C.png"),
    ("v_main.txt", "【D 组 · 必做】", "【E 组 · 选做】", None,
     "shot5_D.png"),
    ("v_main.txt", "【断言汇总】", None, "python exp1_starter.py  —  断言汇总（31 条全部通过）",
     "shot6_summary.png"),
    ("v_debug.txt", "调试 1", "调试 2", "python debug_record.py  —  调试 1：BOM 陷阱",
     "shot7_debug1.png"),
    ("v_debug.txt", "调试 3", "调试 4", "python debug_record.py  —  调试 3：尾随空格",
     "shot8_debug3.png"),
    ("v_onsite.txt", "【汇总】", None, "python onsite_check.py  —  60 张现场任务卡汇总",
     "shot9_onsite.png"),
]

MAX_H_PX = 1500        # 单张截图最大高度（超过则告警，避免报告里塞进整页巨图）


def main():
    print(f"截图输出目录：{SHOT_DIR}")
    made = []
    for fname, start, end, title, out in JOBS:
        src = TOOLS / fname
        if not src.is_file():
            print(f"  跳过（源文件不存在）：{src}")
            continue
        lines = slice_by_markers(load_lines(src), start, end)
        if title is None:
            # 自动取该组的标题行作为图标题
            head = next((l.strip() for l in lines if l.strip().startswith("【")), "")
            title = f"python exp1_starter.py  —  {head}"
        made.append(render(lines, title, out))
    print(f"\n共生成 {len(made)} 张截图。")


if __name__ == "__main__":
    main()
