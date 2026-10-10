# -*- coding: utf-8 -*-
"""
深入分析模板/要求 DOCX 的**格式**：段落属性、字体字号、表格结构、页面设置。
目的：让生成的报告在格式上尽量贴合教师下发的模板。
"""
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TPL = Path(sys.argv[1])

z = zipfile.ZipFile(TPL)
print("=" * 74)
print(f"模板：{TPL.name}")
print(f"部件：{[n for n in z.namelist()]}")
print("=" * 74)

doc = ET.fromstring(z.read("word/document.xml"))
body = doc.find(f"{W}body")


def ptext(p):
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def pinfo(p, label=""):
    ppr = p.find(f"{W}pPr")
    txt = ptext(p)[:40]
    bits = []
    if ppr is not None:
        jc = ppr.find(f"{W}jc")
        if jc is not None:
            bits.append(f"jc={jc.get(f'{W}val')}")
        sp = ppr.find(f"{W}spacing")
        if sp is not None:
            bits.append("spacing(" + ",".join(
                f"{k.split('}')[-1]}={v}" for k, v in sp.attrib.items()) + ")")
        ind = ppr.find(f"{W}ind")
        if ind is not None:
            bits.append("ind(" + ",".join(
                f"{k.split('}')[-1]}={v}" for k, v in ind.attrib.items()) + ")")
        rpr = ppr.find(f"{W}rPr")
    # 首个 run 的字体
    for r in p.findall(f"{W}r"):
        rpr = r.find(f"{W}rPr")
        if rpr is not None:
            f = rpr.find(f"{W}rFonts")
            if f is not None:
                bits.append("font(" + ",".join(
                    f"{k.split('}')[-1]}={v}" for k, v in f.attrib.items()) + ")")
            sz = rpr.find(f"{W}sz")
            if sz is not None:
                bits.append(f"sz={sz.get(f'{W}val')}")
            if rpr.find(f"{W}b") is not None:
                bits.append("b")
            if rpr.find(f"{W}i") is not None:
                bits.append("i")
        break
    print(f"  [{label}] {txt!r}")
    if bits:
        print(f"          {'  '.join(bits)}")


print("\n--- body 顶层结构 ---")
for i, ch in enumerate(body):
    tag = ch.tag.split("}")[-1]
    if tag == "p":
        print(f"[{i}] P")
        pinfo(ch)
    elif tag == "tbl":
        rows = ch.findall(f"{W}tr")
        print(f"[{i}] TBL  rows={len(rows)}")
        tblpr = ch.find(f"{W}tblPr")
        if tblpr is not None:
            st = tblpr.find(f"{W}tblStyle")
            w = tblpr.find(f"{W}tblW")
            bd = tblpr.find(f"{W}tblBorders")
            print(f"      style={st.get(f'{W}val') if st is not None else None} "
                  f"width={w.get(f'{W}w') if w is not None else None}"
                  f"{w.get(f'{W}type') if w is not None else ''}")
            print(f"      borders={'yes' if bd is not None else 'no'}")
        grid = ch.find(f"{W}tblGrid")
        if grid is not None:
            print(f"      gridCols={[c.get(f'{W}w') for c in grid.findall(f'{W}gridCol')]}")
        for ri, tr in enumerate(rows[:3]):
            tcs = tr.findall(f"{W}tc")
            print(f"      row{ri}: {len(tcs)} cells -> "
                  + " | ".join("".join(ptext(p) for p in tc.findall(f'{W}p'))[:22]
                              for tc in tcs))
            for tc in tcs[:1]:
                for p in tc.findall(f"{W}p"):
                    pinfo(p, f"r{ri}c0")
        trpr = rows[0].find(f"{W}trPr") if rows else None
        if trpr is not None:
            print(f"      row0 trPr={[c.tag.split('}')[-1] for c in trpr]}")
    elif tag == "sectPr":
        pg = ch.find(f"{W}pgSz")
        mg = ch.find(f"{W}pgMar")
        print(f"[{i}] SECTPR  pgSz={pg.attrib if pg is not None else None}")
        print(f"          pgMar={mg.attrib if mg is not None else None}")

print("\n--- styles.xml 中的命名样式 ---")
try:
    st = ET.fromstring(z.read("word/styles.xml"))
    for s in st.findall(f"{W}style"):
        sid = s.get(f"{W}styleId")
        nm = s.find(f"{W}name")
        print(f"  style id={sid!r} name={nm.get(f'{W}val') if nm is not None else None!r} "
              f"type={s.get(f'{W}type')}")
    dd = st.find(f"{W}docDefaults")
    if dd is not None:
        print("  docDefaults:", ET.tostring(dd, encoding="unicode")[:600])
except KeyError:
    print("  （无 styles.xml）")