# -*- coding: utf-8 -*-
"""定位 DOCX 里那些「说不清来路」的 run：过小字号、孤立行距、加粗分布。

audit_docx_layout.py 报的是全局分布，但全局分布天然是混的——标题、代码块、
表格单元格、图注的行距本来就不该和正文一样。所以这里改成**按段落归类**，
把「正文段落」单独拎出来看它自己的取值是不是唯一。

用法：python probe_docx_runs.py [docx路径]
"""
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HALF_PT = 2
TWIP_PER_CM = 567.0


def para_text(p):
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def para_style(p):
    """尽量判断这个段落的角色：标题 / 代码 / 表格内 / 图注 / 正文。"""
    ppr = p.find(f"{W}pPr")
    if ppr is None:
        return "正文"
    st = ppr.find(f"{W}pStyle")
    if st is not None:
        return f"样式:{st.get(f'{W}val')}"
    rpr = ppr.find(f"{W}rPr")
    ind = ppr.find(f"{W}ind")
    if ind is not None and ind.get(f"{W}firstLine"):
        return "正文(首行缩进)"
    return "段落"


def classify(p, in_table):
    if in_table:
        return "表格内"
    txt = para_text(p)
    if not txt.strip():
        return "空行"
    # 代码块：新宋体(NSimSun) 作为 ascii 字体，或有等宽底纹
    for rf in p.iter(f"{W}rFonts"):
        if "NSimSun" in (rf.get(f"{W}ascii") or "") or "Consolas" in (rf.get(f"{W}ascii") or ""):
            return "代码块"
    # 标题：字号明显大于 12pt
    for sz in p.iter(f"{W}sz"):
        if int(sz.get(f"{W}val", "0")) / HALF_PT >= 14:
            return "标题"
    if txt.lstrip().startswith("图 ") or txt.lstrip().startswith("代码 "):
        return "图注/代码题注"
    return para_style(p)


def main():
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"D:\深技大课程学习\AI time\自然语言处理 实验一\报告"
        r"\202400502133陈佳豪实验1.docx")
    print(f"检查文件：{docx.name}\n")
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    body = root.find(f"{W}body")

    def walk(el, in_table):
        for child in el:
            tag = child.tag
            if tag == f"{W}p":
                yield child, classify(child, in_table)
            elif tag == f"{W}tbl":
                for p in child.iter(f"{W}p"):
                    yield p, "表格内"
            elif tag.endswith("}sdtContent") or tag == f"{W}sdt":
                yield from walk(child, in_table)

    paras = list(walk(body, False))

    by_role = defaultdict(list)
    for p, role in paras:
        by_role[role].append(p)
    print("=== 段落角色分布 ===")
    for role, ps in sorted(by_role.items(), key=lambda kv: -len(kv[1])):
        print(f"  {role:<16} {len(ps):>4} 段")

    print("\n=== 各角色的字号 / 行距取值 ===")
    for role, ps in sorted(by_role.items(), key=lambda kv: -len(kv[1])):
        szs, lns = Counter(), Counter()
        for p in ps:
            ppr = p.find(f"{W}pPr")
            if ppr is not None:
                sp = ppr.find(f"{W}spacing")
                if sp is not None and sp.get(f"{W}line"):
                    lns[sp.get(f"{W}line")] += 1
            for sz in p.iter(f"{W}sz"):
                szs[sz.get(f"{W}val")] += 1
        szs_real = sorted({int(k) / HALF_PT for k in szs})
        print(f"  {role:<16} 字号{szs_real}  行距{sorted(lns, key=int)}")

    print("\n=== 过小字号（< 8pt）的 run 逐个列出 ===")
    n = 0
    for p, role in paras:
        for r in p.findall(f"{W}r"):
            sz = r.find(f"{W}rPr/{W}sz")
            if sz is None:
                continue
            v = int(sz.get(f"{W}val", "0")) / HALF_PT
            if v < 8:
                txt = "".join(t.text or "" for t in r.iter(f"{W}t"))
                n += 1
                print(f"  [{role}] {v}pt  {txt[:70]!r}")
    if not n:
        print("  （无）")

    # 「段落」角色里行距不唯一的那些，逐条列出来看是不是真·不一致
    print("\n=== 角色=段落 里行距非 340 的条目（正文行距基准是 340）===")
    for p, role in paras:
        if role != "段落":
            continue
        ppr = p.find(f"{W}pPr")
        ln = None
        if ppr is not None:
            sp = ppr.find(f"{W}spacing")
            if sp is not None:
                ln = sp.get(f"{W}line")
        if ln and ln != "340":
            txt = para_text(p).strip()
            szs = {int(s.get(f"{W}val")) / HALF_PT for s in p.iter(f"{W}sz")}
            print(f"  行距 {ln}  字号{sorted(szs)}  {txt[:66]!r}")

    print("\n=== 逐张表格的字号 / 行距 ===")
    for i, tbl in enumerate(root.iter(f"{W}tbl"), 1):
        szs, lns = Counter(), Counter()
        first = ""
        for p in tbl.iter(f"{W}p"):
            if not first:
                first = para_text(p).strip()[:34]
            for sz in p.iter(f"{W}sz"):
                szs[int(sz.get(f"{W}val")) / HALF_PT] += 1
            ppr = p.find(f"{W}pPr")
            if ppr is not None:
                sp = ppr.find(f"{W}spacing")
                if sp is not None and sp.get(f"{W}line"):
                    lns[sp.get(f"{W}line")] += 1
        cols = [int(g.get(f"{W}w", "0")) for g in tbl.iter(f"{W}gridCol")]
        flag = "!!" if len(szs) > 1 else "  "
        print(f"  {flag} 表{i}  {len(cols)}列 {sum(cols)/TWIP_PER_CM:5.2f}cm  "
              f"字号{sorted(szs)} 行距{sorted(lns, key=int)}  首格 {first!r}")

    print("\n=== 角色=其他段落 逐条 ===")
    for p, role in paras:
        if role != "其他段落":
            continue
        szs = sorted({int(s.get(f"{W}val")) / HALF_PT for s in p.iter(f"{W}sz")})
        txt = para_text(p).strip()
        print(f"  字号{szs}  {txt[:64]!r}")


if __name__ == "__main__":
    main()