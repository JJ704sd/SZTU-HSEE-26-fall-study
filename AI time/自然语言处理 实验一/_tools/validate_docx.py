# -*- coding: utf-8 -*-
"""DOCX 结构自检：zip 完整性、必需部件、XML 良构、图片嵌入数、正文可提取性。"""
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

DOCX = Path(r"D:\深技大课程学习\AI time\自然语言处理 实验一\报告"
            r"\学号+姓名+实验1-NLP开发环境与基础文本处理.docx")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ok = True
print(f"检查文件：{DOCX.name}  ({DOCX.stat().st_size // 1024} KB)")

z = zipfile.ZipFile(DOCX)
bad = z.testzip()
print(f"[{'OK' if bad is None else 'FAIL'}] zip 完整性" + ("" if bad is None else f" -> 损坏 {bad}"))
ok &= bad is None

names = z.namelist()
for req in ("[Content_Types].xml", "_rels/.rels", "word/document.xml",
            "word/styles.xml", "word/_rels/document.xml.rels"):
    has = req in names
    print(f"[{'OK' if has else 'FAIL'}] 必需部件 {req}")
    ok &= has

for part in ("word/document.xml", "word/styles.xml", "[Content_Types].xml",
             "word/_rels/document.xml.rels", "_rels/.rels"):
    try:
        ET.fromstring(z.read(part))
        print(f"[OK] XML 良构 {part}")
    except ET.ParseError as e:
        print(f"[FAIL] XML 良构 {part} -> {e}")
        ok = False

imgs = [n for n in names if n.startswith("word/media/")]
print(f"[{'OK' if imgs else 'WARN'}] 内嵌图片 {len(imgs)} 张")

root = ET.fromstring(z.read("word/document.xml"))
body = root.find(f"{W}body")
paras = body.findall(f"{W}p")
tables = body.findall(f"{W}tbl")
drawings = body.iter(f"{W}drawing")
ndraw = len(list(drawings))
sect = body.find(f"{W}sectPr")
print(f"[OK] 顶层段落 {len(paras)}，表格 {len(tables)}，图形 {ndraw}")
print(f"[{'OK' if sect is not None else 'FAIL'}] sectPr（页面设置）存在")
ok &= sect is not None


def all_text(el):
    return "".join(t.text or "" for t in el.iter(f"{W}t"))


text = all_text(body)
print(f"[OK] 可提取正文 {len(text)} 字符")

checks = [
    ("一、实验目的", "第一章节标题"),
    ("二、实验原理", "实验原理"),
    ("三、实验仪器与编程环境", "实验环境"),
    ("四、实验内容", "实验内容"),
    ("五、代码（附注解）与结果分析", "代码与结果"),
    ("六、实验总结与感悟（AI 辅助说明）", "总结与 AI 说明"),
    ("七、思考题", "思考题"),
    ("电子签名", "签名栏"),
    ("成绩评定", "成绩评定"),
    ("选做", "选做小节"),
    ("AI 辅助说明", "AI 使用说明"),
]
print("\n章节完整性：")
for kw, label in checks:
    hit = kw in text
    print(f"  [{'OK' if hit else 'FAIL'}] {label}：{kw}")
    ok &= hit

# 图片关系是否都在 rels 里声明
rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
rel_ids = {r.get("Id") for r in rels}
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
embeds = [b.get(f"{R}embed") for b in root.iter(
    "{http://schemas.openxmlformats.org/drawingml/2006/main}blip")]
missing = [e for e in embeds if e not in rel_ids]
print(f"\n[{'OK' if not missing else 'FAIL'}] 图片关系引用完整 "
      f"（引用 {len(embeds)} 个，缺失 {len(missing)} 个）")
ok &= not missing

print("\n结论：" + ("全部通过" if ok else "存在问题，需修复"))
sys.exit(0 if ok else 1)
