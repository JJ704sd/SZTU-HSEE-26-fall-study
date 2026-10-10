# -*- coding: utf-8 -*-
"""量各页填充率：把每页渲染成 PNG，测「最后一个有墨迹的像素行」占正文可用高度的比例。

为什么不用 pypdf 的 visitor_text 坐标：reportlab 输出的文本对象里 `cm` 自带位移，
`cm[5] + tm[5]` 会算出负基线（本实测：p2 = -304，填充率算出 150%，明显荒谬）。
坐标法在这套链路上不可靠，改成渲染测像素——没有中间假设。
"""
import pathlib
import shutil
import subprocess
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
BASE = pathlib.Path(__file__).resolve().parent.parent
PDF = BASE / "报告" / "202400502133陈佳豪实验1.pdf"
TMP = BASE / "_fill"
DPI = 100
RENDER_H = int(841.89 / 72 * DPI)          # A4 纵向像素高
MARGIN_PX = int(72.0 / 72 * DPI)          # 上下页边距 2.54cm = 72pt

if shutil.which("pdftoppm") is None:
    for cand in (r"C:\Program Files\MiKTeX\miktex\bin\x64",):
        if (pathlib.Path(cand) / "pdftoppm.exe").is_file():
            shutil.which  # noqa
            import os
            os.environ["PATH"] += ";" + cand
            break

TMP.mkdir(exist_ok=True)
for old in TMP.glob("*.png"):
    old.unlink()
subprocess.run(["pdftoppm", "-r", str(DPI), "-png", str(PDF), str(TMP / "p")],
               check=True, capture_output=True)

files = sorted(TMP.glob("p-*.png"))
avail = RENDER_H - 2 * MARGIN_PX
print(f"{'页':>3} {'正文区墨迹高':>13} {'占正文可用高':>12}  判定")
total = 0.0
for i, f in enumerate(files, 1):
    im = Image.open(f).convert("L")
    w, h = im.size
    px = im.load()
    top, bot = MARGIN_PX, h - MARGIN_PX - 1
    first = last = None
    for y in range(top, bot + 1):
        row_has = False
        for x in range(0, w, 2):          # 每 2 px 采样一次，够用且快 4 倍
            if px[x, y] < 200:
                row_has = True
                break
        if row_has:
            if first is None:
                first = y
            last = y
    if first is None:
        print(f"{i:>3} {'(正文区空白)':>13}")
        continue
    used = last - first + 1
    pct = used / avail
    total += pct
    verdict = "满" if pct > 0.9 else ("空" if pct < 0.6 else "正常")
    print(f"{i:>3} {used:>10}px {pct * 100:>11.1f}%  {verdict}")

print(f"\n总页数 = {len(files)}   等效满页 = {total:.2f}")
shutil.rmtree(TMP, ignore_errors=True)