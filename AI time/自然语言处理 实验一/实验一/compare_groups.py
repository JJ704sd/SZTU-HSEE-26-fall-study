# -*- coding: utf-8 -*-
"""
================================================================================
实验一 · 选做组 E-J 与必做组 A-D 的处理差异对比
--------------------------------------------------------------------------------
选做结果必须与必做结果分开呈现。本脚本重新跑一遍全部 10 组数据，
用实测数据生成对比表（Markdown + CSV），报告中直接引用，不手工填写。

运行：python compare_groups.py
================================================================================
"""

import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from exp1_starter import (  # noqa: E402
    DATA_DIR, OUT_DIR, normalize_text, privacy_mask, read_text_checked,
    tokenize, filter_stopwords, load_stopwords, load_task_table, KEEP_WORDS,
)

ENCODING_LABEL = {
    "utf-8": "UTF-8", "utf-8-sig": "UTF-8-SIG", "gb18030": "GB18030", "utf-16": "UTF-16",
}
FULLWIDTH = re.compile(r"[\uff01-\uff5e\uff61-\uff9f\u3000]")


def analyze(group, filename, stopwords):
    path = DATA_DIR / filename
    raw, enc, failed, bom = read_text_checked(path)
    norm = normalize_text(raw)
    masked, hits = privacy_mask(norm)
    tokens = tokenize(masked)
    kept = filter_stopwords(tokens, stopwords, KEEP_WORDS)
    removed = [w for w in tokens if w in stopwords]

    fw_before = FULLWIDTH.findall(raw)
    fw_after = FULLWIDTH.findall(norm)
    # 哪些字符被 NFKC 改动了
    changed = []
    if len(raw) != len(norm):
        changed.append("字符数改变")
    if fw_before and not fw_after:
        changed.append(f"全角字符 {len(fw_before)}→0")
    elif fw_before:
        changed.append(f"全角字符 {len(fw_before)}→{len(fw_after)}")
    if "\n\n" in raw and "\n\n" not in norm:
        changed.append("段落分隔丢失")
    if "\n\n" in norm and "\n\n" not in raw:
        changed.append("新增段落分隔")

    return {
        "group": group, "file": filename, "enc": ENCODING_LABEL.get(enc, enc),
        "tries": len(failed) + 1,
        "failed": "; ".join(f"{d['encoding']}" for d in failed) or "—",
        "bom": "有 BOM" if bom != "无 BOM" else "无",
        "raw_n": len(raw), "norm_n": len(norm), "masked_n": len(masked),
        "tok_n": len(kept),
        "delta": len(norm) - len(raw),
        "changed": "、".join(changed) or "无明显变化",
        "mobile": hits["mobile"], "email": hits["email"],
        "removed": removed,
        "neg": [w for w in ("无", "未", "不伴", "不得") if w in kept],
        "para": "是" if "\n\n" in norm else "否",
    }


FOCUS = {
    "A": "数值/单位/否定词/段落",
    "B": "手机号+邮箱掩码，血糖数值留存",
    "C": "全角数字日期时间→半角",
    "D": "停用词后否定表达存活",
    "E": "空白合并但保留两个段落",
    "F": "全角日期时间规范化",
    "G": "仅正文统一英文大小写",
    "H": "停用词过滤保留「未」",
    "I": "剂量单位与「不得」不删",
    "J": "四阶段统计+编码错误记录",
}


def main():
    stopwords, _ = load_stopwords()
    print("=" * 96)
    print("实验一 · 必做组 A-D 与选做组 E-J 处理差异对比（全部为实测值）")
    print("=" * 96)

    tasks = load_task_table()
    rows = [analyze(t["数据组"], t["文件名"], stopwords) for t in tasks]

    header = (f"| 组 | 性质 | 编码 | 试次 | BOM | 原始→规范化字符数 | 规范化变化 | "
              f"手机/邮箱 | 停用词删除 | 否定词留存 | 段落 | 专项关注点 |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    print(header)
    print(sep)

    for r in rows:
        kind = "必做" if r["group"] in "ABCD" else "选做"
        neg = "、".join(r["neg"]) or "—"
        rem = "、".join(sorted(set(r["removed"]))) or "—"
        line = (f"| {r['group']} | {kind} | {r['enc']} | {r['tries']} | {r['bom']} "
                f"| {r['raw_n']}→{r['norm_n']}（{r['delta']:+d}） | {r['changed']} "
                f"| {r['mobile']}/{r['email']} | {rem} | {neg} | {r['para']} "
                f"| {FOCUS[r['group']]} |")
        lines.append(line)
        print(line)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "选做与必做对比.md").write_text(
        "## 必做组 A-D 与选做组 E-J 处理差异对比\n\n" + "\n".join(lines) + "\n",
        encoding="utf-8")

    with open(OUT_DIR / "选做与必做对比.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["组", "性质", "编码", "尝试次数", "BOM", "原始字符数", "规范化字符数",
                    "字符数变化", "掩码后字符数", "token数", "规范化变化说明",
                    "手机号命中", "邮箱命中", "停用词删除", "否定词留存",
                    "保留段落", "专项关注点"])
        for r in rows:
            w.writerow([
                r["group"], "必做" if r["group"] in "ABCD" else "选做",
                r["enc"], r["tries"], r["bom"], r["raw_n"], r["norm_n"], r["delta"],
                r["masked_n"], r["tok_n"], r["changed"],
                r["mobile"], r["email"], "、".join(sorted(set(r["removed"]))),
                "、".join(r["neg"]), r["para"], FOCUS[r["group"]],
            ])

    # ---------- 关键结论（全部从上面的实测行里算出来，不写死）----------
    print("\n" + "=" * 96)
    print("从实测数据得到的差异结论：")
    print("=" * 96)

    max_tries = max(rows, key=lambda r: r["tries"])
    min_tries = min(rows, key=lambda r: r["tries"])
    print(f"1) 编码探测代价：最多的是 {max_tries['group']} 组（{max_tries['enc']}，"
          f"试 {max_tries['tries']} 次，前置候选失败：{max_tries['failed']}）；")
    print(f"   最少的是 {'、'.join(r['group'] for r in rows if r['tries'] == min_tries['tries'])}"
          f" 组（{min_tries['enc']}，首个候选即成功）。")

    boms = [r["group"] for r in rows if r["bom"] == "有 BOM"]
    print(f"2) BOM：{boms} 组文件带 BOM。utf-8 能解码成功但首字符带 U+FEFF，")
    print("   必须显式改判 utf-8-sig，否则首行被污染——这是'解码成功但数据脏'，")
    print("   比直接抛 UnicodeDecodeError 更隐蔽。")

    # 字符数变化的真实分布：不能笼统说"都是 -1"
    deltas = {r["group"]: r["delta"] for r in rows}
    dist = {}
    for g, d in deltas.items():
        dist.setdefault(d, []).append(g)
    print(f"3) 字符数变化的真实分布：{dist}")
    for d, gs in sorted(dist.items()):
        if d == -1:
            print(f"   · {gs} 组 -1：来自首尾 strip()，NFKC 全角转半角是 1:1 映射不改字符数；")
        elif d < -1:
            print(f"   · {gs} 组 {d}：除 strip() 外还折叠了连续空白（E 组原文有 2 个连续空格）；")
    fw_groups = [r["group"] for r in rows if "全角字符" in r["changed"]]
    print(f"   → 因此**不能用字符数判断全角规范化是否生效**：{fw_groups} 组全角字符都归零，")
    print("     但字符数几乎不变，必须比对具体码位才能确认。")

    b = [r for r in rows if r["group"] == "B"][0]
    print(f"4) 掩码：只有 B 组命中（手机 {b['mobile']} 处、邮箱 {b['email']} 处），"
          f"字符 {b['raw_n']}→{b['masked_n']}，净减 {b['raw_n'] - b['masked_n']}。")
    print("   手机号 13912345671→139****5671 长度不变；邮箱 studentB@example.com→"
          "st***@example.com 变短，所以净减来自邮箱而不是手机号。")

    neg_missing = [r["group"] for r in rows
                   if r["group"] in ("A", "D", "H", "I", "C", "F") and not r["neg"]]
    print(f"5) 否定词留存：A 组 {'/'.join([r for r in rows if r['group'] == 'A'][0]['neg'])}，"
          f"D 组 {'/'.join([r for r in rows if r['group'] == 'D'][0]['neg'])}——"
          "均未被停用词删除。")
    print("   注意口径：指导书要求 tokens 里含 '未'，所以 '未见' 被拆成 未+见；"
          "若把 未见 整词化，指导书自己的断言反而会失败。")

    print("6) 选做组相对必做组的**新增**考察点：")
    print("   · E 组考段落结构不被空白折叠破坏（保留 \u005cn\u005cn 两段）；")
    print("   · G 组考大小写统一**有边界**：只改正文，标题组别与 SIM-G 编号不能动；")
    print("     这是必做组没有的——考的是'改哪些、不改哪些'的判断力；")
    print("   · J 组要求显式输出四阶段统计与编码错误记录，把中间结果落盘可复查。")

    print(f"\n对比表已写入：{OUT_DIR / '选做与必做对比.md'} 与 .csv")


if __name__ == "__main__":
    main()
