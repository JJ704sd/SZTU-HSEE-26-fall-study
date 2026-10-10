# -*- coding: utf-8 -*-
"""
================================================================================
思考题「实测断言」核验器
--------------------------------------------------------------------------------
用法：python verify_thinking.py

为什么要有这个脚本
    第七章思考题里的每个数字都写成了「我实测」，那就必须真的是实测。
    写第一版时我凭常识推，其中两条与事实相反：
      · 以为 C 组用 utf-8 硬解「不报错只变乱码」——实测是直接抛 UnicodeDecodeError；
      · 举 orderId 当误报例子——实测该字段在十组数据里根本不存在。
    评分标准又要求思考题「用自己的语言总结」，写错事实比写得浅更致命。
    所以本脚本把答案里的每个实测断言都从 data/ 现场重算一遍，改数据就会报错。

核验对象
    默认核验 make_report.BUILTIN_THINKING；若存在 思考题_我的答案.md 则核验该文件，
    也就是说你重写之后，本脚本会拿重写版去对——照样能查出数字对不上。

边界
    只核「数字与事实」，不核文采、不核是否像本人写的。措辞是否达标只有老师能判。
================================================================================
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
PHONE_RE = re.compile(r"(?<!1\d)(1[3-9]\d\d|4[5-9]\d|5[0-35-9]\d)\d{4}")


def read(name, enc):
    return (DATA / name).read_bytes().decode(enc)


# ---------------------------------------------------------------- 证据采集 ---
def collect():
    """从 data/ 实测出所有会被写进思考题的事实。"""
    ev = {}

    A = read("input_A_utf8.txt", "utf-8")
    B = read("input_B_utf8sig.txt", "utf-8-sig")
    C_raw = (DATA / "input_C_gb18030.txt").read_bytes()

    # --- Q1：删掉数字与英文字母后各句剩下什么 ---
    ev["Q1_A_bp"] = "家庭血压 128/78 mmHg"
    ev["Q1_A_bp_after"] = re.sub(r"[0-9A-Za-z]+", "", ev["Q1_A_bp"])
    ev["Q1_A_dose"] = "科普标签为5 mg/片"
    ev["Q1_A_dose_after"] = re.sub(r"[0-9A-Za-z]+", "", ev["Q1_A_dose"])
    ev["Q1_B_glu"] = "空腹血糖为6.2 mmol/L"
    ev["Q1_B_glu_after"] = re.sub(r"[0-9A-Za-z]+", "", ev["Q1_B_glu"])
    ev["Q1_A_has_bp"] = ev["Q1_A_bp"] in A
    ev["Q1_A_has_dose"] = ev["Q1_A_dose"] in A
    ev["Q1_B_has_glu"] = ev["Q1_B_glu"] in B

    # --- Q1：删掉标点后 ---
    # 例句必须**从 data/ 里取**，不能手写。第一版这里写死了
    # 「未见异常放电；否认胸痛」，实测十组数据里根本没有这句话：
    # D 组是「未见异常放电，」没有分号，「否认胸痛」全组无（A 组写的是「不伴胸痛」）。
    # 而 chk("Q1.7", ..., True, ...) 的 cond 写死 True，等于只验证
    # 「答案里含有一个由虚构输入算出的字符串」——门禁自己也在验虚构的东西，
    # 于是虚构例句一路绿灯。题目明文要求「结合个人数据举例」，这属于硬伤。
    D = read("input_D_utf16.txt", "utf-16")
    # findall 后要**挑**出要举例的那句，不能取第一个也不能取最长：
    #   · re.search 命中第一个逗号句，那是「编号SIM-D，以下内容为合成教学文本…」这行抬头；
    #   · 取最长也未必对——抬头那句只比临床句多一个字符（实测 27 vs 26）。
    # 判据用语义：这条例子要说明"标点一删、否定范围就读不出来"，
    # 所以必须挑**含否定表达**的那句。
    cands = re.findall(r"[^。\n]{6,}，[^。\n]{6,}", D)
    with_neg = [c for c in cands if any(k in c for k in ("未", "无", "不伴", "否认"))]
    pick = with_neg or cands
    ev["Q1_D_sentence"] = max(pick, key=len) if pick else ""
    ev["Q1_D_sentence_after"] = re.sub(r"[^\w\s]", "", ev["Q1_D_sentence"])

    # C 组同样要解出正文。刻意用「逐个候选尝试」而不是写死 gb18030：
    # 数据万一换了编码，写死会在这一行直接抛异常，门禁崩掉而不是报红。
    C = ""
    for _enc in ("gb18030", "utf-8-sig", "utf-8", "utf-16"):
        try:
            C = C_raw.decode(_enc)
            break
        except Exception:
            continue

    # C 组的日期原文是**全角**，归一后才是半角；第一版直接写半角，
    # 等于把"原文"和"归一结果"混为一谈，而 Q3 讲的正是这件事。
    C_date = re.search(r"[0-9０-９]{4}[-－][0-9０-９]{2}[-－][0-9０-９]{2}"
                       r"[ 　][0-9０-９]{2}[:：][0-9０-９]{2}", C)
    ev["Q1_C_date_raw"] = C_date.group(0) if C_date else ""      # 全角原文
    ev["Q1_C_date"] = unicodedata.normalize("NFKC", ev["Q1_C_date_raw"])
    ev["Q1_C_date_after"] = re.sub(r"[^\w\s]", "", ev["Q1_C_date"])

    # --- Q2：C 组 utf-8 解码的真实行为 ---
    ev["Q2_bytes"] = len(C_raw)
    try:
        C_raw.decode("utf-8")
        ev["Q2_raises"] = False
    except UnicodeDecodeError:
        ev["Q2_raises"] = True
    ig = C_raw.decode("utf-8", errors="ignore")
    rp = C_raw.decode("utf-8", errors="replace")
    ev["Q2_ignore_chars"] = len(ig)
    ev["Q2_lost_pct"] = round(100 * (1 - len(ig) / len(C_raw)), 1)
    ev["Q2_replace_fffd"] = rp.count("\ufffd")
    ev["Q2_ignore_has_fffd"] = "\ufffd" in ig          # 关键：ignore 骗得过通用断言
    ev["Q2_ignore_has_date"] = ev["Q1_C_date"] in ig
    ev["Q2_replace_has_date"] = ev["Q1_C_date"] in rp

    # --- Q3：NFKC 到底改了哪些标点 ---
    # 键名用 ASCII 简写，别拿 unicodedata.name() 当字典键——
    # FULLWIDTH COMMA / IDEOGRAPHIC FULL STOP 这些名字里带空格，写错就是一个 KeyError。
    import unicodedata as ud
    ev["Q3_comma"] = ud.normalize("NFKC", "，")
    ev["Q3_colon"] = ud.normalize("NFKC", "：")
    ev["Q3_semi"] = ud.normalize("NFKC", "；")
    ev["Q3_period"] = ud.normalize("NFKC", "。")
    ev["Q3_circle1"] = ud.normalize("NFKC", "①")
    ev["Q3_paren_ideo"] = ud.normalize("NFKC", "㈠")
    ev["Q3_m2"] = ud.normalize("NFKC", "㎡")
    # 每种全角标点**出现在哪几组**：答案说"实测 C 组的…"，就必须真的在 C 组里。
    # 第一版答案写"C 组的，：；全转成半角"，实测 C 组 ；有 0 处（全角分号在 B 组），
    # 而这层覆盖根本没有，于是错话一路绿灯。
    for tag, fn in (("Q3_C", "input_C_gb18030.txt"), ("Q3_B", "input_B_utf8sig.txt")):
        raw = (DATA / fn).read_bytes()
        for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
            try:
                txt = raw.decode(enc)
                break
            except Exception:
                continue
        ev[f"{tag}_semi"] = txt.count("；")
        ev[f"{tag}_comma"] = txt.count("，")
        ev[f"{tag}_colon"] = txt.count("：")

    # --- Q4：正则的真实漏报 / 误报 ---
    for tag, s in (("hyphen", "138-1234-5678"),
                   ("spaced", "139 1234 5671"),
                   ("atdot", "studentB[at]example[dot]com")):
        ev[f"Q4_fn_{tag}"] = bool(PHONE_RE.search(s) or re.search(r"@", s))
    long_id = "20261015000012345678"
    masked = PHONE_RE.sub(lambda m: "*" * (len(m.group(0)) - 3) + m.group(0)[-3:], long_id)
    ev["Q4_fp_masked"] = masked
    for tag, s in (("datetime", ev["Q1_C_date"]),
                   ("dose", "5 mg/片"),
                   ("glu", "6.2 mmol/L")):
        ev[f"Q4_np_{tag}"] = bool(PHONE_RE.search(s))
    return ev


# ---------------------------------------------------------------- 核验逻辑 ---
def build_checks(ev, text):
    """返回 [(编号, 说明, 条件, 必须出现的字面量), ...]

    设计要点（第一版栽过）：字面量不能手写，必须**由实测值生成**。
    第一版我写死 chk(..., ev['Q3_circle1'], "(1)")，结果实测值是 '1'，
    而答案里的 "(1)" 确实存在，检查照样 PASS——一条永远绿的断言。
    所以凡是「答案里应该出现实测值」的检查，一律用 _lit() 从实测值反推字面量；
    只有「答案里应该出现某个输入样例」的检查才手写字面量（那些输入本身就是固定的）。
    """
    C = []

    def chk(cid, desc, cond, literal=None):
        """literal 为 None 表示「事实基线」：只核事实本身，不要求答案出现某个字面量。

        为什么要有这一档：用户会把思考题改写成自己的话，任何绑定措辞的字面量
        都会在合法改写后误报。事实基线用来守住"数据变了就报错"，与措辞解耦。
        """
        C.append((cid, desc, cond, literal))

    # ---- Q1：输入样例（固定字面量）+ 由实测值反推的残留 -------------------
    chk("Q1.1", "A 组含「家庭血压 128/78 mmHg」", ev["Q1_A_has_bp"], "家庭血压 128/78 mmHg")
    chk("Q1.2", "A 组含「科普标签为5 mg/片」", ev["Q1_A_has_dose"], "科普标签为5 mg/片")
    chk("Q1.3", "B 组含「空腹血糖为6.2 mmol/L」", ev["Q1_B_has_glu"], "空腹血糖为6.2 mmol/L")
    chk("Q1.4", "删数字字母后 A 组血压句残留", True, _lit(ev["Q1_A_bp_after"]))
    chk("Q1.5", "删数字字母后 A 组剂量句残留", True, _lit(ev["Q1_A_dose_after"]))
    chk("Q1.6", "删数字字母后 B 组血糖句残留", True, _lit(ev["Q1_B_glu_after"]))
    # 例句本身取自 D 组，所以要同时核「它真是 D 组的原文」与「删标点后的粘连形态」
    chk("Q1.7", "D 组逗号例句取自 data/ 原文",
        bool(ev["Q1_D_sentence"]) and ev["Q1_D_sentence"] in text, _lit(ev["Q1_D_sentence"]))
    chk("Q1.8", "删掉 D 组逗号后的粘连形态", True, _lit(ev["Q1_D_sentence_after"]))
    chk("Q1.9", "事实基线：C 组日期原文确实是全角（第一版误当成半角）",
        bool(ev["Q1_C_date_raw"]) and any("０" <= c <= "９" for c in ev["Q1_C_date_raw"]))
    chk("Q1.10", "C 组日期 NFKC 归一后的半角形态", True, _lit(ev["Q1_C_date"]))
    chk("Q1.11", "删掉连字符冒号后不可解析", True, _lit(ev["Q1_C_date_after"]))

    # ---- Q2：全部由实测值反推 ---------------------------------------------
    chk("Q2.1", "C 组 utf-8 硬解确实抛异常", ev["Q2_raises"], "UnicodeDecodeError")
    chk("Q2.2", "C 组原始字节数", True, _lit(ev["Q2_bytes"]))
    chk("Q2.3", "ignore 后剩余字符数", True, _lit(ev["Q2_ignore_chars"]))
    chk("Q2.4", "ignore 造成的丢失比例", True, _lit(ev["Q2_lost_pct"]))
    chk("Q2.5", "replace 留下的替换字符数", True, _lit(ev["Q2_replace_fffd"]))
    # 这一条专门盯「ignore 为什么危险」：结果里没有替换字符，通用断言抓不到
    chk("Q2.6", "ignore 结果不含 U+FFFD（所以通用断言拦不住）",
        ev["Q2_ignore_has_fffd"] is False, "U+FFFD")

    # ---- Q3：NFKC 的实际输出，字面量全部由实测反推 --------------------------
    # ---- Q3：NFKC 的实际输出 ----------------------------------------------
    # Q3.1—Q3.3 改为事实基线：它们核的是"NFKC 确实这么转"，
    # 而答案写的是「实测 C 组的「，」「：」全转成半角」，只点名源字符、不写目标形态。
    # 绑定答案措辞（要求出现 `“，”` 这种带引号的形态）会在合法改写后误报，
    # 也会逼着答案写成某个特定标点风格——措辞不是这个门禁要管的事。
    chk("Q3.1", "事实基线：NFKC 把全角逗号转半角", ev["Q3_comma"] == ",")
    chk("Q3.2", "事实基线：NFKC 把全角冒号转半角", ev["Q3_colon"] == ":")
    chk("Q3.3", "事实基线：NFKC 把全角分号转半角", ev["Q3_semi"] == ";")
    chk("Q3.4", "NFKC 保留中文句号 U+3002（不变）", ev["Q3_period"] == "。", "U+3002")
    # 这三条第一版写成了「① 变成 (1)」，实测 ① 的兼容分解是 <circle>0031，NFKC 给的是 '1'
    # 注意：不能只查 '1' —— "(1)" 里也含 '1'，变异测试实测过，弱匹配会漏放。
    # 所以必须把**实测值嵌进完整短语**里查。
    chk("Q3.5", "NFKC 把 ① 变成实测值（实测是 1，不是 (1)）",
        ev["Q3_circle1"] != "(1)", f"① 会变成 {ev['Q3_circle1']}")
    chk("Q3.6", "NFKC 把 ㈠ 变成带括号形式", ev["Q3_paren_ideo"] == "(一)",
        f"㈠ 会变成 {ev['Q3_paren_ideo']}")
    chk("Q3.7", "NFKC 把 ㎡ 变成实测值", ev["Q3_m2"] == "m2", f"㎡ 会变成 {ev['Q3_m2']}")
    # 下面两条是**事实基线**：答案说「实测 C 组的…」，就必须真的在 C 组里。
    # 第一版答案写「C 组的，：；全转成半角」，实测 C 组 ；有 0 处——
    # 而此前没有任何检查碰过「答案说的这组里到底有没有这个字」。
    chk("Q3.8", "事实基线：C 组确有全角逗号与冒号",
        ev["Q3_C_comma"] > 0 and ev["Q3_C_colon"] > 0)
    chk("Q3.9", "事实基线：C 组并无全角分号（全角分号在 B 组）",
        ev["Q3_C_semi"] == 0 and ev["Q3_B_semi"] > 0)

    # ---- Q4：输入样例固定，输出由实测反推 ---------------------------------
    chk("Q4.1", "带连字符手机号被漏掉", ev["Q4_fn_hyphen"] is False, "138-1234-5678")
    chk("Q4.2", "空格分隔手机号被漏掉", ev["Q4_fn_spaced"] is False, "139 1234 5671")
    chk("Q4.3", "反垃圾邮箱被漏掉", ev["Q4_fn_atdot"] is False, "studentB[at]example[dot]com")
    chk("Q4.4", "18 位数字串被误掩成的样子", True, _lit(ev["Q4_fp_masked"]))
    chk("Q4.5", "日期未被误伤", ev["Q4_np_datetime"] is False, "2026-10-15 09:30")
    chk("Q4.6", "剂量未被误伤", ev["Q4_np_dose"] is False, "5 mg/片")
    chk("Q4.7", "血糖值未被误伤", ev["Q4_np_glu"] is False, "6.2 mmol/L")

    return C


# 「xxxId」这类字段名是我编造错误的重灾区：第一版举了 orderId 当误报例子，
# 而该字段在本实验十组数据里根本不存在（实测 grep 零命中）。
# 上面那些检查都是「说了什么就核对什么」，抓不到**多说的**内容——变异测试实测：
# 把 orderId 加回答案，28 项检查照样全绿。所以必须单独立一条守卫：
# 凡是答案里出现的、看起来像字段名的标识符，都必须真的出现在 data/ 里。
FIELD_LIKE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{1,24}(?:Id|ID|_id|_no|No)\b")


def fabricated_fields(text):
    """返回答案里出现、但 data/ 中根本不存在的疑似字段名。"""
    corpus = data_corpus()
    bad = []
    for tok in FIELD_LIKE.findall(text):
        if tok.lower() not in corpus.lower() and tok not in bad:
            bad.append(tok)
    return bad


# ---------------------------------------------------------------- 例句守卫 ---
# 为什么需要它：题目明文要求「结合个人数据举例」，而上面所有检查都只管数字，
# 不管答案里引的那句话到底是不是数据里的。于是虚构的「未见异常放电；否认胸痛」
# 一路绿灯——那句十组数据里根本没有（D 组是「未见异常放电，」，没有分号；
# 「否认胸痛」全组无，A 组写的是「不伴胸痛」）。
#
# 通用守卫而不是逐句写死：把答案里所有「…」引号内的片段挑出来，
# 凡是"纯中文 + 中文标点"（即看起来像记录里的一句话）的，都必须能在 data/ 里找到。
# 靠"纯中文"过滤是为了放过答案里故意引的**输出**形态——
# 「家庭血压 /」「空腹血糖为. /」「20261015 0930」「2026101****012345678」
# 这些都不是原文，里面必有 ASCII 数字/字母/符号，正好被滤掉。
QUOTE_RE = re.compile(r"「([^「」]{5,})」")
ASCII_IN_QUOTE = re.compile(r"[0-9A-Za-z/.:*_\-]")
CJK_PUNCT = "，。、；：？！…（）《》“”‘’【】"


def fabricated_quotes(text):
    """返回答案里引用、但在 data/ 中找不到的"像原句"的片段。"""
    corpus = data_corpus()
    bad = []
    for q in QUOTE_RE.findall(text):
        if ASCII_IN_QUOTE.search(q):        # 含 ASCII → 多半是输出形态，不是原句
            continue
        if not any(c in CJK_PUNCT for c in q):
            continue                        # 没有中文标点 → 不是一句话
        if q in corpus or q + "。" in corpus:
            continue
        if q not in bad:
            bad.append(q)
    return bad


def data_corpus():
    """data/ 十组数据按各自编码解出来的全文拼接。"""
    return "".join(group_text(g) for g in "ABCDEFGHIJ")


# 文件名形如 input_A_utf8.txt / optional_E_utf8.txt，组号在**第二个**下划线段。
# 第一版写 f.name.split("_")[0] != g，而那恒等于 "input"/"optional"，
# 于是 group_text 对每一组都返回空串、data_corpus 返回空串——
# 两道新守卫于是把每一句都判成"数据里没有"，自己把自己变成假红灯。
GROUP_RE = re.compile(r"_([A-J])_")


def decode_bytes(raw: bytes) -> str:
    """按真实编码解出文本。

    不能简单地"按 utf-8-sig → utf-8 → gb18030 顺序试到不报错为止"：
    gb18030 几乎接受任意字节序列，**utf-16 文件会被它硬解成乱码而不抛异常**，
    于是语料里混进的是垃圾，原句永远查不到。先看 BOM 是必须的。
    """
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        for enc in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def group_text(g):
    """某一组数据的全文，按其真实编码解出来。"""
    for f in sorted(DATA.glob("*.txt")):
        m = GROUP_RE.search(f.stem)
        if m and m.group(1) == g:
            return decode_bytes(f.read_bytes())
    return ""


# 组归属守卫：答案写「实测 C 组的「，」」，那个字符就必须真的在 C 组里。
# 第一版答案写「实测 C 组的，：；全转成半角」，而 C 组 ；有 0 处——
# 这类"某组含某字符"的断言此前完全没有覆盖。
#
# 只认紧跟在组名后的那一串「引号+标点」（可连续若干个），
# 窗口刻意开得小：窗口一大就会把后半句里别的组、别的标点也吃进来，误报成一片。
#
# 必须匹配**整串**而不是第一个：第一版只取组名后的第一个标点，
# 于是「实测 C 组的「，」「：」「；」」里的 ；完全没被看见，变异测试当场放行。
# 第二次修错在把右引号当成了可继续的引号——引号必须**成对**匹配，
# 否则 `「，` 就短路了，后面的 「；」 根本不在捕获范围内。
# 覆盖不到的情况由 Q3.9 这类事实基线兜底，不假装这里是完备的。
CLAIM_RE = re.compile(
    r"实测\s*([A-J])\s*组[的]?\s*"
    r"((?:[「“][，。；：、！？][」”]|[\"'][，。；：、！？][\"']){1,6})")


def wrong_group_attribution(text):
    """返回 [(组, 字符)]：答案声称某组含某全角标点，但该组其实没有。"""
    bad = []
    for g, run in CLAIM_RE.findall(text):
        for ch in dict.fromkeys(re.findall(r"[，。；：、！？]", run)):
            if group_text(g).count(ch) == 0 and (g, ch) not in bad:
                bad.append((g, ch))
    return bad


def _lit(v):
    """把实测值转成答案里应当出现的字面量。

    两处刻意的处理：
      · strip()：删词实验的残留常带尾随空格（如 '家庭血压 / '），
        而报告引号里的尾随空格既渲染不出来也不构成断言，比对前统一剥掉。
      · str()：数值直接取字符串。答案里写的是「只剩 35 个字符」「80.8%」
        这类形态，数字本身是子串，能命中即可，不必把整句写死。
    """
    return str(v).strip()


def load_text():
    """返回 (来源说明, 答案全文)。优先用本人重写版。

    同样用 utf-8-sig 读：用户很可能用 PowerShell / 记事本写出带 BOM 的文件，
    漏掉 BOM 就会与 make_report 解析出不同的题数。
    """
    override = BASE / "思考题_我的答案.md"
    if override.is_file():
        return override.name, "\n".join(
            ln.strip() for ln in override.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip())
    sys.path.insert(0, str(BASE))
    from make_report import BUILTIN_THINKING
    return "make_report.BUILTIN_THINKING（内置草稿）", "\n".join(
        t + "\n" + "\n".join(ps) for t, ps in BUILTIN_THINKING)


def main():
    ev = collect()
    src, text = load_text()

    print("=" * 74)
    print("思考题「实测断言」核验")
    print("=" * 74)
    print(f"  答案来源：{src}")
    print(f"  答案字数：{len(text)}")

    checks = build_checks(ev, text)
    ok = 0
    fails = []
    for cid, desc, cond, literal in checks:
        # literal 为 None = 事实基线，只看 cond；否则还要答案里出现该字面量
        hit = bool(cond) and (literal is None or literal in text)
        print(f"  [{'OK' if hit else '!! '}] {cid:<6} {desc}")
        print(f"          实测值：{(literal if literal is not None else '（事实基线，不查字面量）')!r}")
        if hit:
            ok += 1
        else:
            print(f"          !! 条件不成立 或 答案里找不到：{literal!r}")
            fails.append((cid, desc, literal, cond))

    fab = fabricated_fields(text)
    if fab:
        print(f"  [!! ] FAB   答案里出现但 data/ 中不存在的疑似字段名：{fab}")
        fails.append(("FAB", "疑似编造的字段名", str(fab), False))
    else:
        ok += 1
        print("  [OK] FAB   答案里的疑似字段名在 data/ 中均真实存在")

    quotes = fabricated_quotes(text)
    if quotes:
        print(f"  [!! ] QUO   答案引用、但 data/ 里查无此句的例句：{quotes}")
        fails.append(("QUO", "例句并非来自 data/", str(quotes), False))
    else:
        ok += 1
        quoted = [q for q in QUOTE_RE.findall(text)
                  if not ASCII_IN_QUOTE.search(q) and any(c in CJK_PUNCT for c in q)]
        print(f"  [OK] QUO   答案引用的 {len(quoted)} 句原句均能在 data/ 中找到")

    wrong = wrong_group_attribution(text)
    if wrong:
        print(f"  [!! ] GRP   答案声称某组含某全角标点、但该组其实没有：{wrong}")
        fails.append(("GRP", "标点归属写错", str(wrong), False))
    else:
        n_claim = len(CLAIM_RE.findall(text))
        ok += 1
        print(f"  [OK] GRP   {n_claim} 处「实测 X 组的某标点」归属均正确")

    print("\n" + "-" * 74)
    print(f"  共 {len(checks) + 3} 项，通过 {ok} 项，失败 {len(fails)} 项")
    if fails:
        print("\n  失败明细（答案与实测对不上，别交）：")
        for cid, desc, literal, _c in fails:
            print(f"    {cid}  {desc}")
            print(f"          实际应为 {literal!r}")
        print("\n  结论：思考题里的实测断言与 data/ 不符，必须先改对再交。")
        print("=" * 74)
        return 1

    print("\n  结论：思考题里的每个实测数字都能从 data/ 现场重算得到，")
    print("        且答案里没有编造的字段名。")
    print("  注意边界：本脚本只能证明「数字对、字段真」，**证明不了「是你自己写的」**——")
    print("        评分标准要求用自己的语言重写一遍，见 交付说明.md。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())