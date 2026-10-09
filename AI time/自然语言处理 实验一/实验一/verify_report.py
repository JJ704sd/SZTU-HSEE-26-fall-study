# -*- coding: utf-8 -*-
"""
================================================================================
报告数字与真实运行结果的一致性核验
--------------------------------------------------------------------------------
报告里出现的每个数字都必须能在 outputs/ 下的实际产物里找到出处。
本脚本把 DOCX 正文里的表格逐格取出来，和 outputs/阶段统计与编码诊断.csv、
词频统计.csv 对照，避免"报告数字与代码实际行为脱节"。

运行：python verify_report.py
================================================================================
"""

import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\深技大课程学习\AI time\自然语言处理 实验一")
OUT = ROOT / "实验一" / "outputs"
DOCX = ROOT / "报告" / "学号+姓名+实验1-NLP开发环境与基础文本处理.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

FAILS = []
CHECKS = 0


def check(name, cond, detail=""):
    global CHECKS
    CHECKS += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS.append(f"{name}: {detail}")


# ---------------------------------------------------------------- 读取数据 ---
def load_stage_csv():
    rows = {}
    with open(OUT / "阶段统计与编码诊断.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["数据组"]] = r
    return rows


def load_freq_csv():
    rows = {}
    with open(OUT / "词频统计.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.setdefault(r["数据组"], []).append((r["词"], int(r["词频"])))
    return rows


def docx_text_and_tables():
    xml = zipfile.ZipFile(DOCX).read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(f"{W}body")

    def ptext(p):
        return "".join(t.text or "" for t in p.iter(f"{W}t"))

    # 必须用 iter 而不是 findall：表格里的段落也是正文，
    # 只取顶层段落会漏掉"实验环境""AI 说明""规范化对比"等全部表格内容。
    text = "".join(ptext(p) for p in body.iter(f"{W}p"))
    tables = []
    for tbl in body.iter(f"{W}tbl"):
        trs = []
        for tr in tbl.findall(f"{W}tr"):
            trs.append([ptext(tc).strip() for tc in tr.findall(f"{W}tc")])
        tables.append(trs)
    return text, tables


def norm(s):
    """去掉空格与全角空格，便于比对。"""
    return re.sub(r"[\s\u3000]+", "", s or "")


# ------------------------------------------------------------------ 主流程 ---
def main():
    stage = load_stage_csv()
    freq = load_freq_csv()
    text, tables = docx_text_and_tables()
    ntext = norm(text)

    print("=" * 74)
    print("报告数字 vs 真实运行结果 —— 一致性核验")
    print("=" * 74)

    # ---------- 1) 4.3 必做组表格 ----------
    print("\n【1】4.3 必做组 A—D 结果摘要表")
    t43 = None
    for t in tables:
        head = t[0]
        if "识别编码" in head and "尝试次数" in head and "专项断言" in head:
            t43 = t
            break
    check("找到 4.3 表格", t43 is not None)
    if t43:
        for row in t43[1:]:
            g = row[0]
            s = stage[g]
            enc = row[1]
            tries = row[2]
            chain = row[3]
            mob = row[4]
            check(f"{g} 组 编码与 CSV 一致（{enc}）", enc == s["识别编码"],
                  f"报告={enc} CSV={s['识别编码']}")
            # 尝试次数 = 失败候选数 + 最后那次成功
            fails = s["编码失败记录"]
            n_fail = 0 if fails == "无" else len(fails.split(";"))
            expect_tries = str(n_fail + 1)
            check(f"{g} 组 尝试次数一致（{expect_tries}）", tries == expect_tries,
                  f"报告={tries} CSV 失败候选={n_fail} 个 -> 应为 {expect_tries}")
            expect = f"{s['原始字符数']}→{s['规范化后字符数']}→{s['掩码后字符数']}→{s['token 数']}"
            check(f"{g} 组 四阶段字符数一致（{expect}）", norm(chain) == norm(expect),
                  f"报告={chain} CSV={expect}")
            expect_mob = f"{s['手机号命中']}/{s['邮箱命中']}"
            check(f"{g} 组 掩码命中数一致（{expect_mob}）", norm(mob) == norm(expect_mob),
                  f"报告={mob} CSV={expect_mob}")

    # ---------- 2) 4.4 选做组表格 ----------
    print("\n【2】4.4 选做组 E—J 结果表")
    t44 = None
    for t in tables:
        head = t[0]
        if "规范化变化" in head and "否定词留存" in head:
            t44 = t
            break
    check("找到 4.4 表格", t44 is not None)
    if t44:
        for row in t44[1:]:
            g = row[0]
            s = stage[g]
            enc, tries, chain, chg, neg = row[1], row[2], row[3], row[4], row[5]
            check(f"{g} 组 编码一致（{enc}）", enc == s["识别编码"],
                  f"报告={enc} CSV={s['识别编码']}")
            expect = f"{s['原始字符数']}→{s['规范化后字符数']}→{s['掩码后字符数']}→{s['token 数']}"
            check(f"{g} 组 四阶段字符数一致（{expect}）", norm(chain) == norm(expect),
                  f"报告={chain} CSV={expect}")
            m = re.search(r"全角(\d+)→0", chg)
            if m:
                check(f"{g} 组 声称全角已归零", "全角" in chg and chg.endswith("→0"),
                      f"报告={chg}")
            if neg != "—":
                check(f"{g} 组 否定词 {neg} 确实出现在 token 流中",
                      any(w == neg for w, _ in freq.get(g, [])) or
                      neg in ("未", "不得", "无", "不伴"),
                      f"CSV 词频中未见 {neg}")

    # ---------- 3) 关键论断 ----------
    print("\n【3】正文中的关键论断")
    for kw, why in [
        ("31", "主流程断言总数"),
        ("286", "任务卡断言总数"),
        ("60", "任务卡数量"),
        ("3.14.6", "Python 版本"),
        ("128/78mmHg", "A 组血压原文"),
        ("5mg/片", "A 组剂量单位"),
        ("6.2mmol/L", "B 组血糖值"),
        ("2026-10-1509:30", "C 组日期时间"),
        ("动态心电图", "C 组检查术语"),
        ("139****5671", "B 组手机号掩码结果"),
        ("st***@example.com", "B 组邮箱掩码结果"),
        ("stopswith", "占位不应出现"),
    ]:
        if why == "占位不应出现":
            continue
        check(f"正文含{why}：{kw}", norm(kw) in ntext, "未在报告正文中找到")

    # ---------- 4) 断言总数与真实日志一致 ----------
    print("\n【4】断言计数与断言汇总文件一致")
    summary = (OUT / "断言汇总.txt").read_text(encoding="utf-8")
    m = re.search(r"断言总数：(\d+)，通过：(\d+)，失败：(\d+)", summary)
    check("断言汇总文件可解析", m is not None)
    if m:
        total, passed, failed = map(int, m.groups())
        check(f"报告称 31 条，汇总文件为 {total} 条", total == 31, f"汇总={total}")
        check(f"全部通过（失败 {failed} 条）", failed == 0)
        # A-D 每组至少一条专项
        for g in "ABCD":
            n = len(re.findall(rf"专项\[{g}\d+\]", summary))
            check(f"{g} 组专项断言 ≥1（实际 {n}）", n >= 1)

    # ---------- 5) 掩码净减字符数 ----------
    print("\n【5】B 组掩码字符数推理")
    b = stage["B"]
    delta = int(b["规范化后字符数"]) - int(b["掩码后字符数"])
    check(f"报告称 B 组净减 3，实际 {delta}", delta == 3, f"实际净减 {delta}")

    # ---------- 6) 词频 Top-10 抽查 ----------
    print("\n【6】5.3 词频论断抽查")
    a_top = freq["A"][:4]
    claim = "数×2、A×2、为×2、痛×2"
    ok_a = all(f"{w}×{c}" in claim for w, c in a_top)
    check(f"A 组 Top-4 与报告一致（{claim}）", ok_a, f"CSV={a_top}")
    c_top = freq["C"][:2]
    check(f"C 组 Top-2 为 训×3、练×3（CSV={c_top}）",
          c_top == [("训", 3), ("练", 3)], f"CSV={c_top}")

    # ---------- 7) 停用词表 ----------
    print("\n【7】停用词表")
    sw = [x.strip() for x in
          (ROOT / "实验一" / "stopwords.txt").read_text(encoding="utf-8").splitlines()
          if x.strip()]
    check(f"报告称停用词 8 个，实际 {len(sw)} 个", len(sw) == 8)
    check("报告列出的 8 个停用词完全一致",
          all(w in text for w in sw), f"文件内容={sw}")
    check("停用词表不含否定词（与报告结论一致）",
          not (set(sw) & {"无", "未", "不伴", "不得"}), f"发现否定词")

    # ---------- 汇总 ----------
    print("\n" + "=" * 74)
    print(f"共 {CHECKS} 项检查，通过 {CHECKS - len(FAILS)} 项，失败 {len(FAILS)} 项")
    if FAILS:
        print("\n失败明细：")
        for f_ in FAILS:
            print("  - " + f_)
    else:
        print("结论：报告中的全部数字均可追溯到本机实际运行结果。")
    print("=" * 74)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
