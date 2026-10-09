# -*- coding: utf-8 -*-
"""
================================================================================
实验一 · 现场新句任务卡核验器
--------------------------------------------------------------------------------
对应指导书 上机步骤 6：教师按"班级-名单序号"发放任务卡，学生先写出预期结果，
再运行程序，并解释一条与任务卡要求对应的断言。

用法：
    python onsite_check.py            # 批量核验全部任务卡（教师抽检 / 自查用）
    python onsite_check.py 1班-01     # 只核验指定卡片（课堂现场用）

设计要点：断言的**期望值由该卡片自己的输入句推导**，而不是写死常量。
例如手机号期望命中数 = 输入句里 11 位数字串的个数。这样换一张卡不用改代码，
也不会出现"断言写死了自己读出来的内容"这种自欺。
================================================================================
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
CARD_DIR = BASE / "现场新句任务卡"
DATA_STOP = BASE / "stopwords.txt"

sys.path.insert(0, str(BASE))
from exp1_starter import (  # noqa: E402  复用同一条流水线，避免两套实现不一致
    normalize_text, privacy_mask, tokenize, filter_stopwords, PROTECT_WORDS, KEEP_WORDS,
)

# ---------------------------------------------------------------- 卡片解析 ---
def parse_card(path):
    text = path.read_text(encoding="utf-8")
    g = lambda k: (re.search(rf"{k}：(.+)", text).group(1).strip() if re.search(rf"{k}：(.+)", text) else "")  # noqa: E731
    return {
        "id": g("编号"),
        "type": g("类型"),
        "sentence": g("输入句"),
        "task": g("现场任务"),
        "file": path.name,
    }


# ------------------------------------------------------- 期望值由输入推导 ---
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FULLWIDTH_DIGIT = re.compile(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
UNIT_RE = re.compile(r"mmHg|mg|ml|mol|kg|cm|mm|bpm|mmol/L", re.IGNORECASE)
NEG_RE = re.compile(r"不伴|不得|未见|无|未")
# 否定 token 的口径必须与指导书规定的切词规则一致：
# 指导书 3.5.1 节第 6 条断言要求 tokens_D 中含有 "未"，因此切词规则里
# 未见/无意识 不会被当成整词，而是拆成 未/见、无/意/识/障/碍。
# 若擅自把 未见 加进多字优先规则，token 里就不再有 "未"，指导书自己的断言会先失败。
# 这一点在写期望值时必须想清楚，否则会误判自己的程序有 bug（实测踩过）。
NEG_TOKENS = ("不伴", "不得", "否认", "无", "未")


def build_expectations(card):
    """从卡片输入句本身推导出断言期望值。"""
    s = card["sentence"]
    exp = {
        "numbers": NUM_RE.findall(s),
        "units": UNIT_RE.findall(s),
        # 只取切词规则真正会产出的否定 token，而不是原文里的否定短语
        "negations": [w for w in NEG_TOKENS if w in s],
        "neg_phrases": NEG_RE.findall(s),
        "phone_n": len(PHONE_RE.findall(s)),
        "email_n": len(EMAIL_RE.findall(s)),
        "fullwidth_digits": FULLWIDTH_DIGIT.findall(s),
    }
    return exp


# ------------------------------------------------------------------ 核验 ---
def check_card(card, stopwords):
    s = card["sentence"]
    exp = build_expectations(card)
    ty = card["type"].replace("组", "").strip()

    norm = normalize_text(s)
    masked, hits = privacy_mask(norm)
    tokens = tokenize(masked)
    kept = filter_stopwords(tokens, stopwords, KEEP_WORDS)

    results = []   # (断言名, 是否通过, 说明)

    # ---------- 全类型通用 ----------
    results.append((
        "解密后无替换字符 U+FFFD", "\ufffd" not in s, "文本含替换字符"))
    results.append((
        f"掩码后无 11 位手机号明文（输入含 {exp['phone_n']} 个）",
        not PHONE_RE.search(masked), "仍有未掩码手机号"))

    # ---------- 按卡片类型给出专项断言 ----------
    if ty == "A":
        lost_n = [n for n in exp["numbers"] if n not in masked]
        lost_u = [u for u in exp["units"] if u not in masked]
        lost_c = [c for c in ("不得", "不伴", "无", "未") if c in s and c not in masked]
        results.append((
            f"A 专项：数值 {exp['numbers']} 全部保留", not lost_n, f"丢失 {lost_n}"))
        results.append((
            f"A 专项：单位 {exp['units']} 全部保留", not lost_u, f"丢失 {lost_u}"))
        results.append((
            "A 专项：约束词全部保留", not lost_c, f"丢失约束词 {lost_c}"))

    elif ty == "B":
        results.append((
            f"B 专项：手机号命中 {exp['phone_n']} 处",
            hits["mobile"] == exp["phone_n"],
            f"实际 {hits['mobile']} 处"))
        results.append((
            f"B 专项：邮箱命中 {exp['email_n']} 处",
            hits["email"] == exp["email_n"],
            f"实际 {hits['email']} 处"))
        lost_n = [n for n in exp["numbers"] if n not in masked and n not in
                  [m[-4:] for m in re.findall(r"1[3-9]\d\*{4}(\d{4})", masked)]]
        results.append((
            "B 专项：非隐私类数值（如血糖值）仍保留",
            all(n in masked for n in NUM_RE.findall(s)
                if not (len(n) == 11 and n.isdigit())),
            "掩码误伤了业务数值"))

    elif ty == "C":
        results.append((
            f"C 专项：输入含 {len(exp['fullwidth_digits'])} 个全角数字，"
            f"规范化后 0 个",
            not FULLWIDTH_DIGIT.search(norm),
            f"仍残留 {FULLWIDTH_DIGIT.findall(norm)}"))
        half = [unicodedata.normalize("NFKC", d) for d in exp["fullwidth_digits"]]
        results.append((
            "C 专项：全角数字已转为半角",
            all(h in norm for h in half),
            "半角数字未出现"))
        results.append((
            "C 专项：汉字内容未被破坏",
            all(c in norm for c in "康复训练完成检查"),
            "汉字被误删"))

    elif ty == "D":
        need = sorted(set(exp["negations"]))
        lost = [w for w in need if w not in kept]
        results.append((
            f"D 专项：否定表达 {need} 切词后保留",
            all(w in tokens for w in need),
            f"切词阶段丢失 {[w for w in need if w not in tokens]}"))
        results.append((
            f"D 专项：否定表达 {need} 过滤停用词后仍保留",
            not lost,
            f"被停用词误删 {lost}"))

    return {"card": card, "type": ty, "expect": exp,
            "norm": norm, "masked": masked, "hits": hits,
            "tokens": tokens, "kept": kept, "results": results}


def report_one(res, verbose=True):
    c, ty = res["card"], res["type"]
    print("\n" + "-" * 74)
    print(f"卡片 {c['id']}（{c['file']}）   类型：{ty}组   现场任务：{c['task']}")
    print("-" * 74)
    print(f"  输入句      ：{c['sentence']}")
    print(f"  规范化后    ：{res['norm']}")
    if res["hits"]["mobile"] or res["hits"]["email"]:
        print(f"  掩码后      ：{res['masked']}"
              f"   (手机号×{res['hits']['mobile']}，邮箱×{res['hits']['email']})")
    print(f"  切词        ：{res['tokens']}")
    if ty == "D":
        print(f"  过滤停用词后：{res['kept']}")
    print("  断言核验：")
    for name, ok, msg in res["results"]:
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  → {msg}"))
    return all(ok for _, ok, _ in res["results"])


def main():
    load = [ln.strip() for ln in DATA_STOP.read_text(encoding="utf-8").splitlines() if ln.strip()]
    stopwords = set(load) - PROTECT_WORDS

    targets = sys.argv[1:]
    if targets:
        paths = []
        for t in targets:
            p = CARD_DIR / f"{t}.txt"
            if not p.is_file():
                cand = list(CARD_DIR.glob(f"*{t}*.txt"))
                if not cand:
                    print(f"未找到任务卡：{t}")
                    return 2
                p = cand[0]
            paths.append(p)
    else:
        paths = sorted(CARD_DIR.glob("*.txt"))

    print("=" * 74)
    print(f"现场新句任务卡核验  共 {len(paths)} 张")
    print(f"停用词表 {len(load)} 个，否定保护词 {sorted(PROTECT_WORDS)}")
    print("=" * 74)

    results = []
    for p in paths:
        res = check_card(parse_card(p), stopwords)
        results.append(res)
        report_one(res)

    # -------- 汇总 --------
    total_assert = sum(len(r["results"]) for r in results)
    failed = [(r, n, m) for r in results for n, ok, m in r["results"] if not ok]
    print("\n" + "=" * 74)
    print("【汇总】")
    print("=" * 74)
    print(f"  卡片数 {len(results)}，断言总数 {total_assert}，"
          f"失败 {len(failed)}")
    by_type = {}
    for r in results:
        t = by_type.setdefault(r["type"], [0, 0])
        t[0] += 1
        t[1] += sum(1 for _, ok, _ in r["results"] if not ok)
    print("  按类型：" + "，".join(f"{k}组 {v[0]}张/失败{v[1]}" for k, v in sorted(by_type.items())))
    if failed:
        print("\n  失败明细：")
        for r, n, m in failed:
            print(f"    {r['card']['id']}  {n}  → {m}")
    else:
        print("\n  全部卡片全部断言通过。")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
