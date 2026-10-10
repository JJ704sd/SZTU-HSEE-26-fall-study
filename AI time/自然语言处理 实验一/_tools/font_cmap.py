# -*- coding: utf-8 -*-
"""
================================================================================
字体 cmap 解析（零依赖）—— 回答「这个字，字体里到底有没有」
--------------------------------------------------------------------------------
为什么需要它
    报告里出现过两类**渲染期**缺陷，pdftotext / pypdf 都**看不见**：
      1. 字形缺失：写入 `뮻`(谚文)、`ઑ`(古吉拉特文)、`U+E490`(私用区) 这类字符时，
         SimSun / SimHei / NSimSun 根本没有对应字形，PDF 里就渲染成空白或方块，
         但文字抽取照样能抽出这些码位——**文本层是好的，视觉上是坏的**。
      2. 这类字符混进正文时看起来像乱码，很难一眼认出是缺字形而不是"内容就这样"。

    所以直接查字体的 cmap：这个码位在不在字体的覆盖范围里。
    只解析 format 4（BMP）子表——正文用到的字符全在 BMP 内，足够。

不引第三方依赖
    fontTools 本机没装，而这个检查要能随时跑，所以手写解析。
================================================================================
"""

import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def _tables(data: bytes, base: int = 0):
    """返回 {tag: (offset, length)}；支持 ttf 与 ttc（自动取第 0 号字体）。"""
    if data[:4] == b"ttcf":
        n = struct.unpack_from(">I", data, 8)[0]
        base = struct.unpack_from(">I", data, 12)[0]        # 偏移表目录里的第 0 个
        if n < 1:
            return {}
    num = struct.unpack_from(">H", data, base + 4)[0]
    out = {}
    for i in range(num):
        rec = base + 12 + i * 16
        tag, _cs, off, ln = struct.unpack_from(">4sIII", data, rec)
        out[tag.decode("latin-1")] = (off, ln)
    return out


def cmap_ranges(path, subfont=0):
    """返回该字体 cmap 覆盖的码位区间列表 [(start, end), ...]，已合并。"""
    data = Path(path).read_bytes()
    # ttc 里逐个字体找偏移表
    if data[:4] == b"ttcf":
        n = struct.unpack_from(">I", data, 8)[0]
        offsets = [struct.unpack_from(">I", data, 12 + 4 * i)[0] for i in range(n)]
    else:
        offsets = [0]
    if subfont >= len(offsets):
        raise IndexError(f"{path} 只有 {len(offsets)} 个字体，取不到 #{subfont}")
    base = offsets[subfont]

    tabs = _tables(data, base)
    if "cmap" not in tabs:
        return []
    cmoff = tabs["cmap"][0]
    ntab = struct.unpack_from(">H", data, cmoff + 2)[0]

    best = None
    for i in range(ntab):
        pid, eid, off = struct.unpack_from(">HHI", data, cmoff + 4 + i * 8)
        score = {(3, 10): 5, (3, 1): 4, (0, 4): 3, (0, 3): 3, (0, 6): 3, (0, 1): 1}
        s = score.get((pid, eid), 0)
        if s and (best is None or s > best[0]):
            best = (s, cmoff + off)
    if best is None:
        return []

    sub = best[1]
    fmt = struct.unpack_from(">H", data, sub)[0]
    if fmt != 4:
        return []                    # format 12/13/14 是补充平面，中文正文用不到

    seg_x2 = struct.unpack_from(">H", data, sub + 6)[0]
    seg = seg_x2 // 2
    end_base = sub + 14
    start_base = end_base + seg_x2 + 2
    ranges = []
    for i in range(seg):
        end = struct.unpack_from(">H", data, end_base + i * 2)[0]
        start = struct.unpack_from(">H", data, start_base + i * 2)[0]
        if start <= end:
            ranges.append((start, end))
    ranges.sort()
    merged = []
    for s, e in ranges:
        if merged and s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [tuple(x) for x in merged]


def covers(ranges, cp):
    lo, hi = 0, len(ranges) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s, e = ranges[mid]
        if cp < s:
            hi = mid - 1
        elif cp > e:
            lo = mid + 1
        else:
            return True
    return False


if __name__ == "__main__":
    import unicodedata

    fonts = {r"C:\Windows\Fonts\simsun.ttc": (0, "SimSun"),
             r"C:\Windows\Fonts\simsun.ttc": (1, "NSimSun")}
    # ttc 两个字体要分别取
    for idx, name in ((0, "SimSun"), (1, "NSimSun")):
        r = cmap_ranges(r"C:\Windows\Fonts\simsun.ttc", subfont=idx)
        print(f"{name}: {len(r)} 段，示例 {r[:4]}")
    r = cmap_ranges(r"C:\Windows\Fonts\simhei.ttf", subfont=0)
    print(f"SimHei: {len(r)} 段，示例 {r[:4]}")
    for ch in "뮻ઑ胣諥跦藥铧赵…“”":
        print(ch, "U+%04X" % ord(ch),
              {n: covers(cmap_ranges(p, i), ord(ch))
               for (p, i), n in (((r"C:\Windows\Fonts\simsun.ttc", 0), "SimSun"),
                                  ((r"C:\Windows\Fonts\simsun.ttc", 1), "NSimSun"),
                                  ((r"C:\Windows\Fonts\simhei.ttf", 0), "SimHei"))})