# -*- coding: utf-8 -*-
"""量一量终端截图里的死白有多少、落版后字符到底几 pt。

为什么要单独量：`make_shots.py` 按最长行算宽度并封顶 168 列，而多数行的长度
远小于 168，于是右侧留下大片空白；报告再把整幅缩到 9.4cm，字符就被压到 1~2pt，
打印后完全读不出来——而指导书规范分明写「截图清晰美观」。

本脚本只测量不修改，输出交给 make_shots.py 决定裁多少。
注意：标题栏是一条通栏深色矩形，会让 getbbox 恒等于满宽，所以必须把它和正文
分带处理，否则测出来永远是「没有死白」。
"""
import sys
import pathlib

sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageChops

BASE = pathlib.Path(__file__).resolve().parent.parent
SHOT = BASE / "实验一" / "outputs" / "截图"

# 报告里实际落版宽度（cm），见 make_report.py 的 d.image(..., width_cm)
PLACED_CM = {
    "shot3_B.png": 9.4,
    "shot4_C.png": 9.4,
    "shot5_D.png": 9.4,
    "shot6_summary.png": 7.6,
    "shot7_debug1.png": 6.8,
}

BG_MIN = 243          # 三通道最小值 >= 此值视为背景（近白）
PT_PER_CM = 28.3465
CHAR_CELL_PX = 9.0    # NSimSun 14pt @1x 的等宽字符格宽，由 make_shots.py 的 FS 推出


def _content_bbox(im, top, bottom, bg_ref=None):
    """返回 [top,bottom) 这段里非背景像素的横向范围 (l, r)，空则 None。

    bg_ref=None 时按「近白即背景」判定（适用于正文区）。
    标题栏是通栏纯色深底，若也按亮度判定，整条栏会被当成内容，右边界永远是满宽——
    所以标题栏要把「栏底色」当作背景，才能量出栏内文字真正的右边界。
    """
    band = im.crop((0, top, im.width, bottom))
    if bg_ref is None:
        mask = band.convert("L").point(lambda v: 0 if v >= BG_MIN else 255)
    else:
        solid = Image.new("RGB", band.size, bg_ref)
        diff = ImageChops.difference(band, solid).convert("L")
        mask = diff.point(lambda v: 0 if v <= 24 else 255)
    bb = mask.getbbox()
    if not bb:
        return None
    return bb[0], bb[2]


def find_bar_bottom(im):
    """标题栏是通栏纯色矩形；第一行「非纯色」即为正文起点。"""
    px = im.load()
    for y in range(min(im.height, 200)):
        first = px[0, y]
        uniform = True
        for x in range(0, im.width, 17):      # 抽样即可，通栏纯色不会漏
            p = px[x, y]
            if abs(p[0] - first[0]) + abs(p[1] - first[1]) + abs(p[2] - first[2]) > 24:
                uniform = False
                break
        if not uniform:
            return y
    return 0


def main():
    print(f"{'文件':<20}{'原始':>12}{'内容框':>12}{'右死白':>9}{'底死白':>9}"
          f"{'现字号':>9}{'裁后字号':>10}")
    for name, cm in PLACED_CM.items():
        p = SHOT / name
        if not p.is_file():
            print(f"{name:<20}  缺失")
            continue
        im = Image.open(p).convert("RGB")

        bar = find_bar_bottom(im)
        # 标题栏：把「栏底色」当背景，量的是栏内文字而不是整条栏
        bar_fill = im.getpixel((im.width - 4, bar // 2)) if bar else None
        top_r = _content_bbox(im, 0, bar, bar_fill) if bar else None
        # 正文（含结尾那条 ==== 分隔线）的右边界
        body_r = _content_bbox(im, bar, im.height)
        spans = [b for b in (top_r, body_r) if b]     # 每个是 (left, right)
        right = max(b[1] for b in spans)
        left = min(b[0] for b in spans)
        # 纵向：内容最后一行
        mask = im.convert("L").point(lambda v: 0 if v >= BG_MIN else 255)
        bb = mask.getbbox()
        bottom = bb[3]

        content_w = right - left
        old_pt = CHAR_CELL_PX / im.width * cm * PT_PER_CM
        new_pt = CHAR_CELL_PX / content_w * cm * PT_PER_CM
        print(f"{name:<20}{f'{im.width}x{im.height}':>12}"
              f"{f'{content_w}x{bottom}':>12}"
              f"{f'{im.width - right}px':>9}{f'{im.height - bottom}px':>9}"
              f"{f'{old_pt:.1f}pt':>9}{f'{new_pt:.1f}pt':>10}")


if __name__ == "__main__":
    main()
