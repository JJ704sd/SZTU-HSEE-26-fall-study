# -*- coding: utf-8 -*-
"""DOCX 版式一致性实测：直接量 OOXML，核「规范性 10 分」明文考察的那几条。

为什么单独写这个：报告 PDF 好不好看是 reportlab 说了算，Word 版好不好看是
ooxml_docx.py 说了算，两者是**两套独立排版**。PDF 目视正常完全不能推出 DOCX 正常。

而规范性 10 分明文考察「字体/颜色/加粗/行间距是否一致」。本机上交上来的那份
DOCX 实测行距有 7 种、字号 3 档（三分之二文字挤在 8pt 上下），就是栽在这几条上。
所以这几个指标要能**数出来**，不能靠看。

检查项：
  1. 页面可用正文宽度 vs 每张表格 gridCol 之和 —— 溢出右页边距的列出来
  2. 每张表格 gridCol 之和 vs 表格声明的 tblW —— 自相矛盾的列出来
  3. 每张内嵌图 wp:extent 宽 vs 可用正文宽度 —— 超宽的列出来
  4. 字号 w:sz 分布、字体 rFonts 分布、行距 w:spacing/@w:line 分布
  5. 加粗 w:b 与文字颜色 w:color 的使用分布

用法：python audit_docx_layout.py [docx路径]   （缺省验正式交付件）
"""
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

EMU_PER_CM = 360000
TWIP_PER_CM = 567.0          # 1cm = 567 twip（1440 twip/in ÷ 2.54）
HALF_PT = 2                  # w:sz 以半磅为单位


class Audit:
    def __init__(self):
        self.problems = []
        self.notes = []

    def bad(self, msg):
        self.problems.append(msg)

    def ok(self, msg):
        self.notes.append(msg)


def load(path):
    with zipfile.ZipFile(path) as z:
        return ET.fromstring(z.read("word/document.xml"))


def usable_width_cm(root):
    """页面宽度 - 左右页边距。"""
    mar = root.find(f".//{W}sectPr/{W}pgMar")
    sz = root.find(f".//{W}sectPr/{W}pgSz")
    left = int(mar.get(f"{W}left", "0"))
    right = int(mar.get(f"{W}right", "0"))
    width = int(sz.get(f"{W}w", "0"))
    return (width - left - right) / TWIP_PER_CM, mar, sz


def audit_tables(root, usable, a):
    """表格总宽是否超出正文宽度。"""
    idx = 0
    worst = None
    for tbl in root.iter(f"{W}tbl"):
        idx += 1
        cols = [int(g.get(f"{W}w", "0")) for g in tbl.iter(f"{W}gridCol")]
        total = sum(cols) / TWIP_PER_CM
        tblw = tbl.find(f"{W}tblPr/{W}tblW")
        declared = None
        if tblw is not None:
            wt = tblw.get(f"{W}type", "dxa")
            val = int(tblw.get(f"{W}w", "0") or 0)
            declared = (val / TWIP_PER_CM) if wt == "dxa" else None
        if total > usable + 0.05:
            a.bad(f"表 {idx}：gridCol 合计 {total:.2f}cm 超出正文宽度 {usable:.2f}cm"
                  f"（超出 {total - usable:.2f}cm）")
        if declared is not None and abs(declared - total) > 0.15:
            a.bad(f"表 {idx}：tblW 声明 {declared:.2f}cm 与 gridCol 合计 "
                  f"{total:.2f}cm 不一致")
        worst = total if worst is None else max(worst, total)
    a.ok(f"表格 {idx} 张，最宽 {worst:.2f}cm / 可用 {usable:.2f}cm")


def audit_images(root, usable, a):
    extents = []
    for ext in root.iter(f"{WP}extent"):
        cx = int(ext.get("cx", "0"))
        cy = int(ext.get("cy", "0"))
        extents.append((cx / EMU_PER_CM, cy / EMU_PER_CM))
    if not extents:
        a.notes.append("文档内没有图片")
        return
    for i, (w, h) in enumerate(extents, 1):
        if w > usable + 0.05:
            a.bad(f"图 {i}：宽 {w:.2f}cm 超出正文宽度 {usable:.2f}cm")
    widest = max(w for w, _ in extents)
    a.ok(f"内嵌图 {len(extents)} 张，最宽 {widest:.2f}cm / 可用 {usable:.2f}cm")


def classify(p, in_table):
    """段落角色。行距/字号的一致性要**按角色**判，不是全文一个值。

    角色要够细：每张表各自成一个角色（字号按列数定，5 列表比 2 列表小是合理的），
    注记（灰色小字）与正文也分开——它们本就该不同。
    粒度太粗会把这些合理差异误报成不一致，那就不是门禁而是噪声。
    """
    if in_table:
        return in_table
    txt = "".join(t.text or "" for t in p.iter(f"{W}t"))
    if not txt.strip():
        return "空行"
    for rf in p.iter(f"{W}rFonts"):
        a_ = rf.get(f"{W}ascii") or ""
        if "NSimSun" in a_ or "Consolas" in a_:
            return "代码块"
    szs = {int(s.get(f"{W}val", "0")) / HALF_PT for s in p.iter(f"{W}sz")}
    # 图注要**先于**注记判断：两者都是灰色（595959），只能靠前缀区分。
    # 图注 9pt/行距240，note() 注记 9.5pt/行距340，是不同的东西。
    if txt.lstrip().startswith("图 ") or txt.lstrip().startswith("代码 "):
        return "图注"
    cols = {c.get(f"{W}val") for c in p.iter(f"{W}color")}
    if "595959" in cols:
        return "注记"
    if szs and max(szs) >= 14:
        return "标题"
    if szs == {12.0}:
        return "二级标题"
    ppr = p.find(f"{W}pPr")
    if ppr is not None and ppr.find(f"{W}ind") is not None \
            and ppr.find(f"{W}ind").get(f"{W}firstLine"):
        return "正文"
    return "其他段落"


def audit_style_counts(root, a):
    """按角色统计字号 / 行距；同一角色内取值必须唯一。"""
    body = root.find(f"{W}body")

    def walk(el, in_table):
        tbl_no = 0
        for child in el:
            if child.tag == f"{W}p":
                yield child, classify(child, in_table)
            elif child.tag == f"{W}tbl":
                tbl_no += 1
                for p in child.iter(f"{W}p"):
                    yield p, f"表{tbl_no}"
            elif child.tag.endswith("}sdtContent"):
                yield from walk(child, in_table)

    roles = defaultdict(lambda: {"sz": Counter(), "ln": Counter(), "n": 0})
    fonts, colors = Counter(), Counter()
    bold = total = 0

    for p, role in walk(body, False):
        rec = roles[role]
        rec["n"] += 1
        ppr = p.find(f"{W}pPr")
        if ppr is not None:
            sp = ppr.find(f"{W}spacing")
            if sp is not None and sp.get(f"{W}line"):
                rec["ln"][sp.get(f"{W}line")] += 1
        for sz in p.iter(f"{W}sz"):
            rec["sz"][sz.get(f"{W}val")] += 1
        for r in p.findall(f"{W}r"):
            total += 1
            rpr = r.find(f"{W}rPr")
            if rpr is None:
                continue
            if rpr.find(f"{W}b") is not None:
                bold += 1
            c = rpr.find(f"{W}color")
            if c is not None:
                colors[c.get(f"{W}val", "?")] += 1
            rf = rpr.find(f"{W}rFonts")
            if rf is not None:
                fonts[rf.get(f"{W}eastAsia") or rf.get(f"{W}ascii") or "?"] += 1

    print("  --- 按角色的字号 / 行距（同一角色内取值必须唯一）---")
    for role, rec in sorted(roles.items(), key=lambda kv: -kv[1]["n"]):
        szs = sorted({int(k) / HALF_PT for k in rec["sz"]})
        lns = sorted(rec["ln"], key=int) if rec["ln"] else []
        mark = "  " if len(szs) <= 1 and len(lns) <= 1 else "!!"
        print(f"  {mark} {role:<10} {rec['n']:>4} 段  字号{szs}  行距{lns}")
        # 标题的三个层级本来就该不同，按层级放行
        if role in ("标题", "空行"):
            continue
        if len(szs) > 1:
            a.bad(f"角色「{role}」字号有 {len(szs)} 种取值 {szs}，内部不一致")
        if len(lns) > 1:
            a.bad(f"角色「{role}」行距有 {len(lns)} 种取值 {lns}，内部不一致")

    if fonts:
        a.ok(f"中文字体（{len(fonts)} 种）："
             + ", ".join(f"{k}×{v}" for k, v in fonts.most_common()))
    if colors:
        a.ok(f"文字颜色（{len(colors)} 种）："
             + ", ".join(f"{k}×{v}" for k, v in colors.most_common()))
    a.ok(f"run 总数 {total}，其中加粗 {bold} 个")


def main():
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"D:\深技大课程学习\AI time\自然语言处理 实验一\报告"
        r"\202400502133陈佳豪实验1.docx")
    print(f"检查文件：{docx.name}  ({docx.stat().st_size // 1024} KB)")
    root = load(docx)
    usable, mar, sz = usable_width_cm(root)
    print(f"页面 {int(sz.get(W+'w')) / TWIP_PER_CM:.2f}cm 宽，"
          f"正文可用 {usable:.2f}cm"
          f"（左{int(mar.get(W+'left'))/TWIP_PER_CM:.2f} / "
          f"右{int(mar.get(W+'right'))/TWIP_PER_CM:.2f} cm）\n")

    a = Audit()
    audit_tables(root, usable, a)
    audit_images(root, usable, a)
    audit_style_counts(root, a)

    for m in a.notes:
        print(f"  [INFO] {m}")
    print()
    if a.problems:
        for m in a.problems:
            print(f"  [FAIL] {m}")
        print(f"\n结论：发现 {len(a.problems)} 处版式问题。")
        return 1
    print("结论：表格与图片均未溢出正文宽度，行距取值唯一，版式一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())