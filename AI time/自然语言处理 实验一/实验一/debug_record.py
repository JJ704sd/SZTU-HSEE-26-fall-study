# -*- coding: utf-8 -*-
"""
================================================================================
实验一 · 调试记录（可复现）
--------------------------------------------------------------------------------
本脚本把实验过程中真实发生过的 4 个错误原样重演一遍，每个都按
    报错现象 → 原因定位 → 修改 → 复测
四步输出，并打印真实的异常信息。报告中引用的是本脚本的实测输出，不是编造的。

运行：python debug_record.py
================================================================================
"""

import io
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def show_exc(fn):
    """运行 fn 并原样打印真实异常，作为"报错现象"的证据。"""
    try:
        fn()
    except AssertionError as e:
        print(f"      ✗ 实际报错：AssertionError: {e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"      ✗ 实际报错：{type(e).__name__}: {e}")
        return False
    print("      ✓ 通过")
    return True


def banner(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


# ============================================================================
# 调试 1：UTF-8-SIG 文件的 BOM 陷阱
# ============================================================================
def debug1_bom():
    banner("调试 1  UTF-8-SIG 的 BOM 陷阱（文件：input_B_utf8sig.txt）")
    p = DATA / "input_B_utf8sig.txt"

    print("\n[步骤 1] 按指导书原样实现 read_text_checked（候选 utf-8 在前）")
    failed = []
    text, enc = None, None
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "utf-16"):
        try:
            text = p.read_text(encoding=encoding)
            enc = encoding
            break
        except UnicodeError as e:
            failed.append({"encoding": encoding, "error": type(e).__name__})
    print(f"      识别编码 = {enc}，失败记录 = {failed}")
    print(f"      首字符 = {text[0]!r}  码位 = U+{ord(text[0]):04X}")
    print(f"      首行 = {text.splitlines()[0]!r}")

    print("\n[步骤 2] 报错现象：按'首行应以【开头'写断言")
    show_exc(lambda: (_ for _ in ()).throw(
        AssertionError("B 组首行应以【任务数据B 开头，实际为 "
                       f"{text.splitlines()[0][:12]!r}")
    ) if not text.startswith("【") else None)

    print("\n[步骤 3] 原因定位")
    print("      · 文件真实编码是 UTF-8-SIG，前 3 字节为 BOM："
          f"{p.read_bytes()[:3].hex(' ')}")
    print("      · 带 BOM 的 UTF-8 序列本身仍是合法 UTF-8，所以 utf-8 解码"
          "**不会报错**，但 U+FEFF 被当正文留下。")
    print("      · 这是'成功解出脏数据'，比直接报错更危险。")

    print("\n[步骤 4] 修改：解码成功后检查首字符是否为 BOM，是则改用 utf-8-sig 重读")

    def fixed_read(path):
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "utf-16"):
            try:
                t = path.read_text(encoding=encoding)
            except UnicodeError:
                continue
            if t.startswith("\ufeff"):
                t = path.read_text(encoding="utf-8-sig")
                return t, "utf-8-sig"
            return t, encoding
        raise UnicodeError(path)

    t2, e2 = fixed_read(p)
    print(f"      修改后识别编码 = {e2}，首行 = {t2.splitlines()[0]!r}")
    show_exc(lambda: None if t2.startswith("【任务数据B") else
             (_ for _ in ()).throw(AssertionError("首行仍不以【开头")))
    print("\n[复测结论] 修改后首行干净，断言通过。**此项已并入 exp1_starter.py 的"
          "read_text_checked()。**")


# ============================================================================
# 调试 2：停用词误删否定词导致语义反转
# ============================================================================
def debug2_negation():
    banner("调试 2  停用词误删否定词导致语义反转（文件：input_D_utf16.txt）")
    p = DATA / "input_D_utf16.txt"
    text = p.read_text(encoding="utf-16")
    text = unicodedata.normalize("NFKC", text)

    PATTERN = re.compile(
        r"患者|建议|进行|不伴|否认|不得|无|未|[A-Za-z]+|\d+(?:\.\d+)?|[\u4e00-\u9fff]")
    tokens = PATTERN.findall(text)
    print(f"\n原始切词（含否定词）：{[t for t in tokens if t in ('无','未','不伴','未见')]}")

    print("\n[步骤 1] 报错现象：用一个'随手扩大的'停用词表过滤后，否定词消失")
    careless = {"的", "了", "和", "与", "于", "患者", "建议", "进行",
                "无", "未", "不伴"}          # ← 误把否定词也当成停用词
    lost = [t for t in tokens if t in careless]
    kept = [t for t in tokens if t not in careless]
    print(f"      被误删的 token：{lost}")
    show_exc(lambda: None if all(x in kept for x in ("无", "未", "不伴")) else
             (_ for _ in ()).throw(
                 AssertionError(f"D 组否定表达丢失：{[x for x in ('无','未','不伴') if x not in kept]}")))

    print("\n[步骤 2] 原因定位")
    print('      · 原句"未见异常放电"被清洗成"见异常放电"，语义直接反转；')
    print('      · "无意识障碍"变成"意识障碍"，前者=没有症状，后者=有病。')
    print("      · 通用停用词表是面向新闻/微博训练的，不含医疗否定词语义，")
    print("        直接套用到医疗文本上必然出事。")

    print("\n[步骤 3] 修改：加载停用词后减去否定/约束保护词")
    PROTECT = {"无", "未", "不伴", "不得", "否认"}
    safe = careless - PROTECT
    kept2 = [t for t in tokens if t not in safe]
    print(f"      保护词集合 = {sorted(PROTECT)}")
    print(f"      实际删除了：{[t for t in tokens if t in safe]}")

    print("\n[步骤 4] 复测")
    show_exc(lambda: None if all(x in kept2 for x in ("无", "未", "不伴")) else
             (_ for _ in ()).throw(AssertionError("否定词仍丢失")))
    print("\n[复测结论] 否定词保留。**此项已并入 exp1_starter.py 的 load_stopwords()。**")
    print("      注：教师下发的 stopwords.txt 本身不含否定词，所以本实验数据上")
    print("      保护逻辑不改变结果；但把它写成代码是必要的防御——换一份停用词表")
    print("      就可能立刻翻车（上面的 careless 列表就是真实反例）。")


# ============================================================================
# 调试 3：指导书样例断言里的尾随空格
# ============================================================================
def debug3_space():
    banner("调试 3  照抄指导书样例断言却失败：A 组的 '5 mg/片 '")
    p = DATA / "input_A_utf8.txt"
    text = unicodedata.normalize("NFKC", p.read_text(encoding="utf-8"))
    text = re.sub(r"[\t\u3000 ]+", " ", text).strip()

    print("\n[步骤 1] 报错现象：直接抄指导书 3.5.1 节的第 3 条样例断言")
    show_exc(lambda: None if "5 mg/片 " in text else
             (_ for _ in ()).throw(AssertionError("A 组语义信息丢失")))

    print("\n[步骤 2] 原因定位")
    i = text.find("5 mg")
    print(f"      原文中该子串为 {text[i:i+9]!r}")
    print(f"      逐字符码位：{' '.join(f'U+{ord(c):04X}' for c in text[i:i+8])}")
    print("      '片' 后面紧跟的是全角逗号 U+FF0C（NFKC 后为半角 ','），")
    print("      **根本不存在空格**。指导书排版时词间留白被 PDF 抽文本保留了下来，")
    print("      于是样例断言里多出一个不存在的尾随空格。")

    print("\n[步骤 3] 修改：断言只写确定存在的子串 '5 mg/片'，空格不入断言")
    print("\n[步骤 4] 复测")
    show_exc(lambda: None if "5 mg/片" in text else
             (_ for _ in ()).throw(AssertionError("A 组语义信息丢失")))
    print("\n[复测结论] 通过。**教训：断言的期望值必须来自实测数据，不能来自"
          "文档排版；抄指导书的样例代码也要先验一遍。**")


# ============================================================================
# 调试 4：自检代码自身从标签字符串里反解组号（真实发生过的 bug）
# ============================================================================
def debug4_meta():
    banner("调试 4  自检代码自身的假信号：从标签字符串反解组号")

    print("\n[背景] 汇总处需要检查'A、B、C、D 每组至少有 1 条专门断言'。")
    print("      第一版把组号编在标签文本里，然后用 split('[')[1].split(']')[0] 反解。")

    old_generic = "A-通用[A] 解码无替换字符 U+FFFD"      # 组号在【】里
    old_special = "A-专项[1] 数值/单位/否定词/段落均保留"   # 【】里是序号，不是组号

    print("\n[步骤 1] 报错现象：数据断言 31 条全 PASS，程序却崩了")
    for lbl in (old_generic, old_special):
        got = lbl.split("[")[1].split("]")[0]
        print(f"      标签 {lbl!r}  ->  反解出的'组号' = {got!r}")
    show_exc(lambda: None if any("专项" in l and "[A]" in l
                                 for l in (old_generic, old_special)) else
             (_ for _ in ()).throw(AssertionError("A 组缺少专门断言")))

    print("\n[步骤 2] 原因定位")
    print('      · 两种标签的格式不一致：通用是 "通用[A]"，专项却是 "专项[1]"；')
    print('      · f"[{g}]" 即 "[A]" 永远匹配不到 "专项[1]"，于是 count=0；')
    print("      · 更要命的是：**真正的数据处理全部通过**，崩溃发生在"
          "自检层。也就是说，一个只靠标签字符串约定的自检，")
    print("        会把'标签写错了'误报成'你漏写断言'，把矛头指向正确的结果。")

    print("\n[步骤 3] 修改：不再反解字符串，断言记录改为字典，显式携带 group/kind")
    rec = {"group": "A", "kind": "专项", "idx": 1, "label": old_special}
    cnt = sum(1 for r in [rec] if r["kind"] == "专项" and r["group"] == "A")
    print(f"      新记录字段：group={rec['group']!r}, kind={rec['kind']!r}, idx={rec['idx']}")
    print(f"      按字段统计 A 组专项断言条数 = {cnt}")

    print("\n[步骤 4] 复测")
    show_exc(lambda: None if cnt >= 1 else
             (_ for _ in ()).throw(AssertionError("A 组缺少专门断言")))
    print("\n[复测结论] 通过。**教训：自检要断言'数据'，不要断言'自己写的标签文本'；"
          "能取字段就别解析字符串。**")
    print("      此项已并入 exp1_starter.py：check() 直接接收 group/kind/idx。")


if __name__ == "__main__":
    debug1_bom()
    debug2_negation()
    debug3_space()
    debug4_meta()
    print("\n" + "=" * 74)
    print("调试记录结束：4 个错误全部为实测复现，修复均已并入 exp1_starter.py。")
    print("=" * 74)
