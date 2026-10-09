# -*- coding: utf-8 -*-
"""
================================================================================
《自然语言处理》实验一  NLP 开发环境与基础文本处理
--------------------------------------------------------------------------------
课程编号：HE00239          实验类型：验证性、必做          学时：2 学时
指导教师：缪尧、张媛       组织形式：个人独立完成
必做数据组：A、B、C、D     选做数据组：E-J（本程序已全部实现）

运行方式（在本文件所在目录执行）：
    python exp1_starter.py

程序用一条命令完成：环境自检 → 编码识别 → 规范化 → 隐私掩码 → 切词 →
停用词过滤 → 词频统计 → 断言核验 → 结果落盘（outputs/）。

设计原则：
  1. 不修改 data/ 下的任何原始文件，处理结果一律写入独立目录 outputs/；
  2. 禁止 errors="ignore"——它会静默丢字，掩盖真实错误；
  3. 断言先行：每组结果先用断言核验语义是否丢失，再写入磁盘；
  4. 所有数字（词频、命中数、字符数）均由本程序实测产生，不手工填写。
================================================================================
"""

import csv
import io
import platform
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# ============================================================================
# 第 0 部分：环境自检（对应指导书 3.1 节）
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent          # 本脚本所在目录，避免写死别人电脑的绝对路径
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "outputs"
STOPWORDS_FILE = BASE_DIR / "stopwords.txt"


def env_check():
    """确认 Python 版本、解释器路径和当前目录。版本必须 >= 3.10。"""
    print("=" * 74)
    print("【第 0 部分】Python 环境自检")
    print("=" * 74)
    print(f"  Python 版本 : {platform.python_version()}")
    print(f"  解释器路径  : {sys.executable}")
    print(f"  操作系统    : {platform.system()} {platform.release()}")
    print(f"  当前目录    : {Path.cwd()}")
    print(f"  脚本目录    : {BASE_DIR}")

    major, minor = sys.version_info[:2]
    assert (major, minor) >= (3, 10), f"Python 版本过低（当前 {major}.{minor}），要求 3.10 及以上"
    assert DATA_DIR.is_dir(), f"数据目录不存在：{DATA_DIR}（请先 cd 进入实验一目录）"
    assert STOPWORDS_FILE.is_file(), f"停用词表不存在：{STOPWORDS_FILE}"
    print("  [OK] 版本、data/ 与 stopwords.txt 均就绪\n")


# ============================================================================
# 第 1 部分：编码识别（对应指导书 3.2 节 / 上机步骤 2）
# ============================================================================

CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "utf-16")


def read_text_checked(path):
    """
    依次尝试四种中文常见编码，成功即返回，并把每次失败的编码与异常类型
    记入 failed 列表作为诊断证据。

    关键细节（指导书步骤 2 特别要求）：
      UTF-8-SIG 文件带 BOM，用普通 utf-8 解码"不会报错"，但首字符会残留
      U+FEFF。这属于"成功解出乱码"的陷阱，必须显式检查并改用 utf-8-sig 重读。

    返回：(文本, 实际编码, 失败记录列表, BOM说明)
    """
    failed = []
    for encoding in CANDIDATE_ENCODINGS:
        try:
            text = Path(path).read_text(encoding=encoding)
        except UnicodeError as error:
            failed.append({"encoding": encoding, "error": type(error).__name__})
            continue

        # utf-8 能解码但残留 BOM —— 说明文件其实是 UTF-8-SIG，改用 utf-8-sig 重读
        if text.startswith("\ufeff"):
            try:
                text = Path(path).read_text(encoding="utf-8-sig")
                return text, "utf-8-sig", failed, "utf-8 可解码但首字符含 BOM，已改用 utf-8-sig 重读"
            except UnicodeError:
                pass
        return text, encoding, failed, "无 BOM"

    raise UnicodeError(f"无法识别文件编码：{path}（已尝试 {CANDIDATE_ENCODINGS}）")


def mojibake_note(text):
    """
    可选诊断：utf-16 几乎不会抛 UnicodeDecodeError——它会把任意偶数长度字节
    强行两两配对解出"看似成功"的内容。因此"没报错"不等于"解码对了"。
    这里用 CJK 字符占比做一个粗略的可读性提示（不参与断言，仅供分析）。
    """
    if not text:
        return 0.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk / len(text)


# ============================================================================
# 第 2 部分：Unicode 规范化与空白处理（对应指导书 3.3 节 / 上机步骤 3）
# ============================================================================

def normalize_text(text):
    """
    规范化流程：NFKC → 统一换行符 → 空白折叠 → 压缩多余空行 → 去首尾空白。

    NFKC 的实际效果（已在 C 组数据上实测，报告中如实列出）：
      · 全角数字 ３０ → 30
      · 全角连字符 － → 半角 -
      · 全角冒号 ： → 半角 :
      · 全角逗号 ， → 半角 ,
      · 但 U+3002「。」没有兼容分解，NFKC 后保持原样
    注意：不能用"只保留汉字"的正则清洗，否则会删掉 128/78 mmHg、5 mg/片
    这类医学关键信息。
    """
    text = unicodedata.normalize("NFKC", text)          # 全角→半角、兼容字符折叠
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # 统一换行符
    text = re.sub(r"[\t\u3000 ]+", " ", text)          # 制表符/全角空格/连续半角空格 → 单空格
    text = re.sub(r"\n{3,}", "\n\n", text)              # 三个以上空行压缩为两个（保留段落）
    return text.strip()


# ============================================================================
# 第 3 部分：隐私字段掩码（对应指导书 3.4 节）
# ============================================================================

PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")


def privacy_mask(text):
    """
    掩码手机号与邮箱，并返回各自的替换次数（用于断言核验）。

      手机号 13912345671 → 139****5671  （前后加 (?<!\\d)/(?!\\d)，避免从长数字中截取片段）
      邮箱 studentB@example.com → st***@example.com （保留前 2 个字符，便于人工核对归属）

    说明：本实验掩码只作用于合成教学数据，不是经过临床验证的完整脱敏系统。
    """
    text, mobile_n = PHONE_RE.subn(r"\1****\2", text)
    text, email_n = EMAIL_RE.subn(r"\1***\2", text)
    return text, {"mobile": mobile_n, "email": email_n}


# ============================================================================
# 第 4 部分：停用词表（否定保护）
# ============================================================================

# 医疗文本的否定/约束词一旦被停用词删掉，语义会完全反转
# （"未见异常" 被清洗成 "见异常"），因此必须从停用词表中剔除。
#
# 注意口径：指导书 3.5.1 节第 6 条断言要求 tokens_D 中含有 "未"，
# 说明规定的切词规则把 "未见" 拆成 未 + 见（见 TOKEN_PATTERN）。
# 所以 PROTECT_WORDS 里的 "未见"/"无异常" 在当前规则下不会被产出，
# 属于防御性冗余：一旦有人把 多字短语 优先规则扩展，它们就已经在保护名单里。
PROTECT_WORDS = {"无", "未", "不伴", "不得", "否认", "未见", "无异常"}


def load_stopwords(filepath=STOPWORDS_FILE):
    """读取停用词表，并剔除否定/约束保护词。"""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = [line.strip() for line in f if line.strip()]
    raw_set = set(raw)
    stop_set = raw_set - PROTECT_WORDS
    dropped = sorted(raw_set & PROTECT_WORDS)
    print(f"  停用词表：共 {len(raw)} 个 -> 过滤后 {len(stop_set)} 个")
    print(f"  保护词命中：{dropped if dropped else '无（本数据组的停用词表不含否定词，保护逻辑不改变结果）'}")
    return stop_set, raw_set


# ============================================================================
# 第 5 部分：切词（对应指导书 3.6 节 / 上机步骤 5）
# ============================================================================

# 多字否定短语必须排在单字规则之前，否则"不伴"会被拆成"不"+"伴"，
# 停用词过滤后否定语义就丢了。
TOKEN_PATTERN = re.compile(
    r"患者|建议|进行|不伴|否认|不得|无|未|[A-Za-z]+|\d+(?:\.\d+)?|[\u4e00-\u9fff]"
)


def tokenize(text):
    """按正则切词，保留汉字单字、英文串、数字（含小数）。"""
    return TOKEN_PATTERN.findall(text)


def filter_stopwords(tokens, stopwords, keep_words):
    """过滤停用词，但 keep_words 中的单位/约束词永远保留。"""
    return [w for w in tokens if (w not in stopwords) or (w in keep_words)]


# 现场保留词：剂量/时间单位与数值关系词，防止它们被误删
KEEP_WORDS = {
    "mg", "ml", "kg", "cm", "mm", "g", "l", "bpm",
    "小时", "分钟", "天", "周", "月", "年",
    "大于", "小于", "等于", "不超过", "至少", "最多",
    "≥", "≤",
}


# ============================================================================
# 第 6 部分：单文件处理流水线
# ============================================================================

REQUIRED = "必做"
OPTIONAL = "选做"

# A-D 必做组的专项任务开关
TASK_SWITCH = {
    "A": "保留血压、剂量单位、否定/约束词和段落",
    "B": "掩码手机号和邮箱，保留血糖数值与单位",
    "C": "把全角数字/标点规范化，并保留日期、时间与检查术语",
    "D": "停用词处理后仍保留 无 / 未 / 不伴 等否定表达",
    # ---- 选做组 ----
    "E": "合并多余空白但保留两个语义段落",
    "F": "规范全角日期时间，保留「动态心电图」检查术语",
    "G": "只统一正文英文大小写，保留组别与 SIM-G 编号",
    "H": "过滤停用词时保留否定词「未」",
    "I": "规范标点但不得删除剂量单位「5 mg/片」与约束词「不得」",
    "J": "输出 原始/规范化/掩码/token 各阶段统计和编码错误记录",
}


def load_task_table():
    """读取教师下发的 任务表.csv，作为任务要求的唯一事实来源。"""
    rows = []
    with open(DATA_DIR / "任务表.csv", "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row["数据组"] = row["数据组"].strip()
            rows.append(row)
    return rows


def process_file(path, group, stopwords):
    """对单个文件跑完整条流水线，返回结构化结果字典。"""
    assert path.is_file(), f"输入文件不存在：{path}"          # 断言 1：文件必须存在

    raw, enc, failed, bom_note = read_text_checked(path)

    assert "\ufffd" not in raw, f"文本中出现替换字符，可能使用了错误编码：{path}"  # 断言 2
    assert bom_note != "", "BOM 说明缺失"

    normalized = normalize_text(raw)
    masked, hits = privacy_mask(normalized)

    # ---- 选做 G：只统一正文英文大小写，标题行与编号行必须原样保留 ----
    lowered = masked
    if group == "G":
        lines = masked.split("\n")
        # 第 1 行是标题【任务数据G：…】，第 2 行含 SIM-G 编号，均不得改动；
        # 只有第 3 行起的正文做小写统一。
        lines = lines[:2] + [ln.lower() for ln in lines[2:]]
        lowered = "\n".join(lines)

    tokens_raw = tokenize(lowered)
    tokens_kept = filter_stopwords(tokens_raw, stopwords, KEEP_WORDS)
    removed = [w for w in tokens_raw if w in stopwords]
    top10 = Counter(tokens_kept).most_common(10)

    return {
        "group": group,
        "file": path.name,
        "encoding": enc,
        "failed": failed,
        "bom_note": bom_note,
        "cjk_ratio": mojibake_note(raw),
        "raw": raw,
        "normalized": normalized,
        "masked": lowered,
        "hits": hits,
        "tokens_raw": tokens_raw,
        "tokens": tokens_kept,
        "removed": removed,
        "top10": top10,
        "n_chars": {
            "raw": len(raw),
            "normalized": len(normalized),
            "masked": len(lowered),
            "tokens": len(tokens_kept),
        },
        "n_lines": {
            "raw": len(raw.splitlines()),
            "normalized": len(normalized.splitlines()),
        },
        "has_paragraph_break": "\n\n" in normalized,
        "neg_words": [w for w in ("无", "未", "不伴", "不得") if w in lowered],
    }


# ============================================================================
# 第 7 部分：断言核验（对应指导书 3.5.1 节，要求共 6 条以上且 A-D 各一条专项）
# ============================================================================

# 每条断言记录为字典，显式携带 group / kind / idx，
# 汇总时直接取字段，不再从标签字符串里反解组号（早期版本正是栽在这里）。
ASSERT_LOG = []


def check(group, kind, idx, text, condition, message):
    """统一的断言记录器：一条 check 计一条断言，失败立即抛出并打印定位信息。"""
    ok = bool(condition)
    label = f"{kind}[{group}{idx}] {text}"
    ASSERT_LOG.append({
        "group": group, "kind": kind, "idx": idx,
        "label": label, "ok": ok, "message": message,
    })
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + ("" if ok else "  → " + message))
    assert ok, f"{label} 失败：{message}"


def run_assertions(res, expect_group):
    """对某一组结果执行通用断言 + 该组专项断言。"""
    print(f"\n--- 断言核验：{expect_group} 组（{res['file']}）---")
    g = expect_group

    # 通用断言 1：解码后无替换字符
    check(g, "通用", 1, "解码无替换字符 U+FFFD",
          "\ufffd" not in res["raw"],
          "出现替换字符，说明误用了错误编码")

    # 通用断言 2：掩码后不得残留 11 位手机号明文
    check(g, "通用", 2, "掩码后无 11 位手机号明文",
          not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", res["masked"]),
          "仍存在未掩码的手机号")

    # ---------- A 组专项：数值、单位、否定/约束词、段落都要保留 ----------
    if g == "A":
        need = ("128/78 mmHg", "5 mg/片", "无", "不伴", "不得")
        missing = [x for x in need if x not in res["normalized"]]
        check(g, "专项", 1, "数值/单位/否定词/段落均保留",
              (not missing) and res["has_paragraph_break"],
              f"A 组语义信息丢失，缺少：{missing}，段落分隔是否存在={res['has_paragraph_break']}")

    # ---------- B 组专项：手机号、邮箱各命中 1 处 ----------
    elif g == "B":
        check(g, "专项", 1, "手机号与邮箱各命中 1 处",
              res["hits"]["mobile"] == 1 and res["hits"]["email"] == 1,
              f"B 组隐私字段命中数不正确：{res['hits']}")
        check(g, "专项", 2, "掩码后保留血糖数值与单位 6.2 mmol/L",
              "6.2 mmol/L" in res["masked"],
              "B 组掩码时把血糖数值/单位一起弄丢了")

    # ---------- C 组专项：全角数字已转换，日期时间与检查术语仍保留 ----------
    elif g == "C":
        ok = ("３０" not in res["normalized"]
              and "2026-10-15 09:30" in res["normalized"]
              and "动态心电图" in res["normalized"])
        check(g, "专项", 1, "全角已转半角且日期时间/检查术语保留",
              ok,
              f"C 组规范化失败：含全角={'３０' in res['normalized']}，"
              f"含日期={'2026-10-15 09:30' in res['normalized']}，"
              f"含术语={'动态心电图' in res['normalized']}")

    # ---------- D 组专项：停用词过滤后否定表达仍保留 ----------
    elif g == "D":
        need = ("无", "未", "不伴")
        missing = [x for x in need if x not in res["tokens"]]
        check(g, "专项", 1, "过滤停用词后 否定词 无/未/不伴 仍保留",
              not missing,
              f"D 组否定表达丢失：{missing}")

    # ---------- E 组专项：多余空白合并但保留两个段落 ----------
    elif g == "E":
        check(g, "专项", 1, "合并多余空白且保留两个段落",
              ("  " not in res["normalized"]) and res["normalized"].count("\n\n") == 1,
              f"E 组段落/空白处理异常：连续空格={'  ' in res['normalized']}，"
              f"空行数={res['normalized'].count(chr(10) * 2)}")

    # ---------- F 组专项：全角日期时间规范化为半角并保留术语 ----------
    elif g == "F":
        check(g, "专项", 1, "全角日期时间已规范化且保留动态心电图",
              ("２０２６" not in res["normalized"]
               and "2026-10-15 09:30" in res["normalized"]
               and "动态心电图" in res["normalized"]),
              "F 组全角日期时间规范化失败或检查术语丢失")

    # ---------- G 组专项：只统一正文大小写，SIM-G 编号与组别保留 ----------
    elif g == "G":
        head = "\n".join(res["masked"].split("\n")[:2])
        check(g, "专项", 1, "仅正文小写化，标题组别与 SIM-G 编号保留",
              ("SIM-G" in head and "【任务数据G" in head
               and "sim-g" not in res["masked"]
               and "caffeine" in res["masked"]
               and "CAFFEINE" not in res["masked"]),
              "G 组大小写统一越界，改动了标题/编号或未统一正文英文")

    # ---------- H 组专项：停用词过滤保留「未」 ----------
    elif g == "H":
        check(g, "专项", 1, "过滤停用词后仍保留否定词「未」",
              "未" in res["tokens"],
              "H 组否定词「未」在停用词过滤后丢失")

    # ---------- I 组专项：剂量单位与约束词不得删除 ----------
    elif g == "I":
        check(g, "专项", 1, "保留 5 mg/片 与约束词「不得」",
              ("5 mg/片" in res["masked"] and "不得" in res["masked"]),
              "I 组剂量单位或约束词「不得」被删除")

    # ---------- J 组专项：四阶段统计与编码错误记录齐全 ----------
    elif g == "J":
        keys = ("raw", "normalized", "masked", "tokens")
        check(g, "专项", 1, "四阶段统计齐全且编码错误记录非空",
              all(k in res["n_chars"] for k in keys) and len(res["failed"]) >= 2,
              f"J 组阶段统计或编码错误记录缺失：{res['n_chars']} / failed={res['failed']}")


# ============================================================================
# 第 8 部分：输出落盘
# ============================================================================

def save_outputs(results, stopwords_raw):
    """把处理结果写入 outputs/，绝不回写 data/ 下的原始文件。"""
    OUT_DIR.mkdir(exist_ok=True)

    # 1) 每组规范化+掩码后的纯文本
    for r in results:
        (OUT_DIR / f"{r['group']}_{Path(r['file']).stem}_processed.txt").write_text(
            r["masked"], encoding="utf-8"
        )

    # 2) 每组的词频表
    with open(OUT_DIR / "词频统计.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["数据组", "文件名", "识别编码", "词", "词频"])
        for r in results:
            for word, cnt in r["top10"]:
                w.writerow([r["group"], r["file"], r["encoding"], word, cnt])

    # 3) 阶段统计 + 编码诊断记录（含 J 组要求的逐阶段字符数）
    with open(OUT_DIR / "阶段统计与编码诊断.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["数据组", "文件名", "识别编码", "原始字符数", "规范化后字符数",
                    "掩码后字符数", "token 数", "原始行数", "规范化后行数",
                    "保留段落", "手机号命中", "邮箱命中",
                    "编码失败记录", "BOM说明", "停用词删除数"])
        for r in results:
            w.writerow([
                r["group"], r["file"], r["encoding"],
                r["n_chars"]["raw"], r["n_chars"]["normalized"], r["n_chars"]["masked"],
                r["n_chars"]["tokens"], r["n_lines"]["raw"], r["n_lines"]["normalized"],
                "是" if r["has_paragraph_break"] else "否",
                r["hits"]["mobile"], r["hits"]["email"],
                "; ".join(f"{d['encoding']}->{d['error']}" for d in r["failed"]) or "无",
                r["bom_note"], len(r["removed"]),
            ])

    # 4) 断言汇总
    passed = sum(1 for r in ASSERT_LOG if r["ok"])
    with open(OUT_DIR / "断言汇总.txt", "w", encoding="utf-8") as f:
        f.write(f"断言总数：{len(ASSERT_LOG)}，通过：{passed}，失败：{len(ASSERT_LOG) - passed}\n\n")
        for r in ASSERT_LOG:
            f.write(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['label']}\n")
            if not r["ok"]:
                f.write(f"       原因：{r['message']}\n")

    print(f"\n  结果已写入：{OUT_DIR}")
    return OUT_DIR


# ============================================================================
# 主流程
# ============================================================================

def main():
    env_check()

    print("=" * 74)
    print("【第 1 部分】加载停用词表")
    print("=" * 74)
    stopwords, stopwords_raw = load_stopwords()

    print("\n" + "=" * 74)
    print("【第 2 部分】读取教师下发的任务表（任务要求的唯一事实来源）")
    print("=" * 74)
    tasks = load_task_table()
    for t in tasks:
        print(f"  {t['数据组']}  {t['性质']}  {t['文件名']:<22} {t['主题']}")
    print()

    results = []
    for t in tasks:
        g, kind = t["数据组"], t["性质"]
        path = DATA_DIR / t["文件名"]

        print("=" * 74)
        print(f"【{g} 组 · {kind}】{t['主题']}   文件：{t['文件名']}")
        print(f"  个人任务：{t['个人任务']}")
        print("=" * 74)

        r = process_file(path, g, stopwords)
        r["kind"] = kind
        results.append(r)

        # ---- 中间输出：让处理过程可观察，而不是只看最终结果 ----
        print(f"  识别编码      : {r['encoding']}")
        print(f"  编码失败记录  : {r['failed'] if r['failed'] else '无（首个候选即成功）'}")
        print(f"  BOM 说明      : {r['bom_note']}")
        print(f"  汉字占比(诊断): {r['cjk_ratio']:.2%}")
        print(f"  规范化前片段  : {r['raw'].splitlines()[2][:60]!r}")
        print(f"  规范化后片段  : {r['normalized'].splitlines()[2][:60]!r}")
        if r["hits"]["mobile"] or r["hits"]["email"]:
            print(f"  隐私掩码      : 手机号×{r['hits']['mobile']}，邮箱×{r['hits']['email']}"
                  f" -> {r['masked'].splitlines()[2][:60]!r}")
        print(f"  切词结果      : {r['tokens_raw']}")
        print(f"  停用词删除    : {r['removed'] if r['removed'] else '无'}")
        print(f"  过滤后 Top-10 : {r['top10']}")
        print(f"  阶段字符数    : 原始{r['n_chars']['raw']} -> 规范化{r['n_chars']['normalized']}"
              f" -> 掩码{r['n_chars']['masked']} -> token{r['n_chars']['tokens']}")

        run_assertions(r, g)

    # ---------- 汇总断言 ----------
    print("\n" + "=" * 74)
    print("【断言汇总】")
    print("=" * 74)
    passed = sum(1 for r in ASSERT_LOG if r["ok"])
    groups_with_specific = sorted({r["group"] for r in ASSERT_LOG if r["kind"] == "专项"})
    print(f"  断言总数 {len(ASSERT_LOG)} 条，通过 {passed} 条，失败 {len(ASSERT_LOG) - passed} 条")
    print(f"  含专项断言的数据组：{groups_with_specific}")
    print(f"  A-D 每组专项断言条数："
          + "，".join(f"{g}={sum(1 for r in ASSERT_LOG if r['kind'] == '专项' and r['group'] == g)}"
                      for g in ("A", "B", "C", "D")))

    assert len(ASSERT_LOG) >= 6, "断言总数不足 6 条"
    assert passed == len(ASSERT_LOG), "存在未通过的断言"
    for g in ("A", "B", "C", "D"):
        n = sum(1 for r in ASSERT_LOG if r["kind"] == "专项" and r["group"] == g)
        assert n >= 1, f"{g} 组缺少专门断言（实际 {n} 条）"

    save_outputs(results, stopwords_raw)

    print("\n" + "=" * 74)
    print(f"实验一主流程完成：{len(results)} 组数据，{len(ASSERT_LOG)} 条断言全部通过。")
    print("=" * 74)


if __name__ == "__main__":
    main()
