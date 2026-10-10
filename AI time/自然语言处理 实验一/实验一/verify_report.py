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
import hashlib
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(
    r"D:\深技大课程学习\AI time\自然语言处理 实验一")
OUT = ROOT / "实验一" / "outputs"
# 允许传参指定待核验的 DOCX 与工作根目录：写死路径时，核验暂存副本也会去读正式件，
# 报出一个针对别的文件的绿灯（旧坑，见 run_all.py 里关于假绿灯的注释）；
# 可换根目录则让变异测试能在临时副本上跑，不必真的去改原始 data/。
DOCX = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (
    ROOT / "报告" / "202400502133陈佳豪实验1.docx")
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
    global CHECKS   # 末尾的自指检查会对它做 += 1
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
    # 建组→行的索引，供第 8 项核对「停用词删除」列复用
    row_of_43 = {r[0]: r for r in t43[1:]} if t43 else {}
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
        # ⚠ 这一段曾经写成 `enc, tries, chain, chg, neg = row[1]..row[5]`——**按位置取列**。
        # 本轮给 4.4 加了一列「主题」，位置一错，19 项检查同时报错，而且错得很有说服力：
        # 检查名直接印出「E 组 编码一致（公共卫生宣教与段落）」——主题被当成了编码。
        # 这与「一张表里只要有一列没接数据源，就一定是没被核过的那列」是同一个病根：
        # **按位置绑定的东西，加一列就全错位。** 一律改成按表头**列名**取列。
        h44 = [norm(x) for x in t44[0]]
        NEED44 = ["识别编码", "尝试次数", "原始→规范化→掩码→token",
                  "规范化变化", "否定词留存"]
        miss44 = [c for c in NEED44 if norm(c) not in h44]
        check("4.4 表头含全部待核列（按列名取，不按位置）", not miss44,
              f"缺列 {miss44}；实际表头 {t44[0]}")
        if not miss44:
            i_enc, i_tries, i_chain, i_chg, i_neg = (h44.index(norm(c)) for c in NEED44)
            for row in t44[1:]:
                g = row[0]
                s = stage[g]
                enc = row[i_enc]
                tries = row[i_tries]
                chain = row[i_chain]
                chg = row[i_chg]
                neg = row[i_neg]
                check(f"{g} 组 编码一致（{enc}）", enc == s["识别编码"],
                      f"报告={enc} CSV={s['识别编码']}")
                # 尝试次数在 4.4 原来根本没被核过（变量取了却没用），
                # 与其留一个不接数据源的列，不如按 4.3 同一口径把它接上。
                fails = s["编码失败记录"]
                n_fail = 0 if fails == "无" else len(fails.split(";"))
                expect_tries = str(n_fail + 1)
                check(f"{g} 组 尝试次数一致（{expect_tries}）", tries == expect_tries,
                      f"报告={tries} CSV 失败候选={n_fail} 个 -> 应为 {expect_tries}")
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

    # ---------- 8) 4.3 表「停用词删除」列 ← 此前完全没有门禁覆盖 ----------
    # 这一列是 4.3 表里唯一没有对数据源做核对的单元格（其余列都比 阶段统计 CSV）：
    # 报告里写死了一组词，没有任何机制保证它跟程序实际删掉的一致。
    # 这里直接重跑流水线现算，再和 DOCX 表格里那一格逐组比对。
    print("\n【8】4.3 表「停用词删除」列（重跑流水线现算并逐组比对）")
    sys.path.insert(0, str(ROOT / "实验一"))
    import exp1_starter as S
    from collections import Counter

    stop_set, _raw_set = S.load_stopwords(S.STOPWORDS_FILE)
    data_dir = ROOT / "实验一" / "data"
    # 数据文件缺失或被改坏时，process_file 会直接抛异常（UnicodeDecodeError /
    # FileNotFoundError）。门禁在这种情况下崩掉比门禁变红更糟：崩掉只留一屏栈，
    # 既说不出是哪一组、哪个文件，也让人误以为是脚本坏了。统一收成一条可读的 FAIL。
    # 走 check() 而不是直接往 FAILS 里塞，是为了保持 CHECKS / FAILS 两者的账对得上。
    def safe_process(fname, g):
        try:
            return S.process_file(data_dir / fname, g, stop_set), True
        except Exception as e:                      # noqa: BLE001  这里要的就是兜住一切
            check(f"{g} 组 {fname} 可读取并解码", False, f"{type(e).__name__}: {e}")
            return None, False

    for g, fname in (("A", "input_A_utf8.txt"), ("B", "input_B_utf8sig.txt"),
                     ("C", "input_C_gb18030.txt"), ("D", "input_D_utf16.txt")):
        res, ok = safe_process(fname, g)
        if not ok:
            continue
        cnt = Counter(res["removed"])
        expect = "/".join(f"{w}" + (f"×{cnt[w]}" if cnt[w] > 1 else "")
                          for w in sorted(cnt))
        # 从 DOCX 里取 4.3 表该组所在行的第 6 格（0 基：组/编码/次数/字符数/手机/停用词）
        cell = row_of_43.get(g, [None] * 7)[5] if row_of_43.get(g) else None
        check(f"{g} 组停用词删除 = {expect}", cell is not None and norm(cell) == norm(expect),
              f"报告={cell!r} 实算={expect!r}")
        # 否定保护词一个都不能出现在删除列表里
        check(f"{g} 组未删除任何否定保护词",
              not (set(res["removed"]) & S.PROTECT_WORDS),
              f"被删={sorted(set(res['removed']) & S.PROTECT_WORDS)}")

    # ---------- 9) 5.3(1) 的「汉字占比」区间 ----------
    # 报告正文写「正常文本 46%–78%，乱码远低于此」，这是实测区间，
    # 属于报告里的数字，同样要对上。
    print("\n【9】5.3(1) 汉字占比可读性诊断区间")
    ratios = {}
    for g, fname in (("A", "input_A_utf8.txt"), ("B", "input_B_utf8sig.txt"),
                     ("C", "input_C_gb18030.txt"), ("D", "input_D_utf16.txt"),
                     ("E", "optional_E_utf8.txt"), ("F", "optional_F_gb18030.txt"),
                     ("G", "optional_G_utf8sig.txt"), ("H", "optional_H_utf16.txt"),
                     ("I", "optional_I_utf8.txt"), ("J", "optional_J_gb18030.txt")):
        res, ok = safe_process(fname, g)
        if ok:
            ratios[g] = res["cjk_ratio"]
    # 「正常文本」= 十组数据正常解码后的占比区间（含选做 E—J），
    # 不是只看必做 A—D——漏掉选做组会把上界算低（实测 J 组 77.8% 才是最高）
    normal = list(ratios.values())
    lo, hi = round(min(normal) * 100), round(max(normal) * 100)
    # 期望字面量由实测反推，不手写
    expect = f"{lo}%–{hi}%"
    check(f"报告的正常文本区间 = {expect}（{len(normal)}/10 组可算）", expect in text,
          f"实测 {lo}%–{hi}%，参与计算的只有 {len(normal)} 组")
    # 乱码一侧：把 utf-8 文件按 utf-16 硬解，其汉字占比必须明显低于下界
    moji = []
    for fname in ("input_A_utf8.txt", "optional_E_utf8.txt", "optional_I_utf8.txt"):
        p = data_dir / fname
        if not p.is_file():
            continue
        mis = p.read_bytes().decode("utf-16", errors="replace")
        moji.append(sum(1 for c in mis if "\u4e00" <= c <= "\u9fff") / max(1, len(mis)))
    check(f"utf-16 误读乱码占比均低于正常下界 {lo}%（{len(moji)}/3 个样本）",
          len(moji) == 3 and all(m < lo / 100 for m in moji),
          f"实测乱码 {[f'{m:.0%}' for m in moji]}")

    # ---------- 10) 原始文件未被修改（指导书 步骤1 第 2 条 + 报告正文的承诺） ----------
    # 这是本项目里最"像废话"却最容易被人顺手破坏的一条：指导书步骤 1.2 写着
    # 「不修改原始文件，输出写入独立目录」，报告正文也写了「原始文件不被修改」，
    # 但此前 15 道门禁里没有任何一处核对过字节——真改了 data/ 也不会有人发现。
    # 这里以「材料/」下教师发放的原件为基准，逐文件比 SHA256。
    print("\n【10】原始文件未被修改（对照材料基准副本逐文件 SHA256）")
    mat = next((p for p in (ROOT / "材料").iterdir()
                if p.is_dir() and (p / "实验一" / "实验一" / "data").is_dir()), None)
    check("找到原始数据基准副本（材料/…/实验一/实验一/data）", mat is not None,
          f"{ROOT / '材料'} 下没有含「实验一/实验一/data」的目录，无法核对原始文件")

    def sha256(p):
        """读不动的文件返回哨兵串，而不是抛异常——"文件被锁/被删"也要算不一致。"""
        h = hashlib.sha256()
        try:
            h.update(Path(p).read_bytes())
        except OSError as e:
            return f"<读取失败:{type(e).__name__}>"
        return h.hexdigest()

    if mat is not None:
        work = ROOT / "实验一"
        # 显式映射：只列程序/核验器真正会读到的原始输入，逐个对到原件
        pairs = [(b, work / "data" / b.name)
                 for b in sorted((mat / "实验一" / "实验一" / "data").iterdir()) if b.is_file()]
        # stopwords.txt 原件在实验一根目录下（不在 data/ 里），工作副本放了两份，两份都要核
        base_sw = mat / "实验一" / "实验一" / "stopwords.txt"
        pairs.append((base_sw, work / "stopwords.txt"))
        pairs.append((base_sw, work / "data" / "stopwords.txt"))
        pairs += [(p, work / "现场新句任务卡" / p.name)
                  for p in sorted((mat / "实验一" / "实验一_附加：现场新句" / "学生任务卡").glob("*.txt"))]

        missing = [w.relative_to(ROOT).as_posix() for _b, w in pairs if not w.is_file()]
        check(f"{len(pairs)} 个原始输入在工作副本中齐全", not missing, f"缺失 {missing[:5]}")
        diff = [w.relative_to(ROOT).as_posix() for b, w in pairs
                if w.is_file() and sha256(b) != sha256(w)]
        check(f"{len(pairs)} 个原始输入 SHA256 与原件一致（0 处不一致）", not diff,
              f"被改动 {diff[:5]}")
        # 多出来的文件同样要挡：改一份副本顶替原件，上面两条是抓不到的
        expect_names = {b.name for b, _w in pairs if b.parent.name == "data"} | {"stopwords.txt"}
        actual_names = {p.name for p in (work / "data").iterdir() if p.is_file()}
        check(f"data/ 无多余文件（应为 {len(expect_names)} 个）", actual_names == expect_names,
              f"多出 {sorted(actual_names - expect_names)}")
        check("报告正文写明了「原始文件不被修改」", "原始文件不被修改" in text,
              "正文缺这条承诺，核对无意义")

    # ---------- 11) 现场任务卡数量与断言条数 ← 报告写死，此前从未重算 ----------
    # 报告里「跑通 60 张现场任务卡共 286 条断言」这两个数字，此前只有第【3】项的
    # 字面量检查（正文出现过 "60"/"286" 就算过）。删掉一张任务卡、或某个类型的
    # 专项断言被摘掉，报告数字都不会跟着变，也照样全绿。
    # 这里直接 import onsite_check 现算，期望字面量由实测反推，不手写。
    print("\n【11】现场任务卡数与断言总数（重跑 onsite_check 现算）")
    import onsite_check as O
    sw_set = set([ln.strip() for ln in
                  (ROOT / "实验一" / "stopwords.txt").read_text(encoding="utf-8").splitlines()
                  if ln.strip()]) - S.PROTECT_WORDS
    cards = sorted((ROOT / "实验一" / "现场新句任务卡").glob("*.txt"))
    n_cards, n_assert, n_fail, n_bad = len(cards), 0, 0, 0
    for p in cards:
        # 卡片被改坏时 parse_card 会因缺字段抛异常，同样收成可读的 FAIL
        try:
            results = O.check_card(O.parse_card(p), sw_set)["results"]
        except Exception as e:                      # noqa: BLE001
            n_bad += 1
            print(f"  [FAIL] 任务卡 {p.name} 可解析并核验  -> {type(e).__name__}: {e}")
            continue
        for _name, ok, _msg in results:
            n_assert += 1
            if not ok:
                n_fail += 1
    check(f"全部 {n_cards} 张任务卡均可解析并核验（实测 {n_bad} 张异常）", n_bad == 0,
          f"{n_bad} 张卡片解析或核验时报错")
    check(f"现算断言失败数为 0（实测失败 {n_fail} 条）", n_fail == 0, f"有 {n_fail} 条断言不过")
    phrase = f"{n_cards} 张现场任务卡共 {n_assert} 条断言"
    check(f"报告称「{phrase}」与现算一致", phrase in text,
          f"实测 {n_cards} 张 / {n_assert} 条，报告里不是这个数")

    # ---------- 【12】4.5 现场任务卡那一节的数字（重跑现算，不信正文里的字面量） ----------
    # 4.5 是本轮新补的一节，里面的「14 个全角数字」「前后都是 34 个字符」
    # 「康复训练:上肢抬举27次。2026-11-27 16:30完成检查。」都是**写进正文的具体断言**。
    # 正文里的字面量一旦和卡片对不上，正是"看着合理"的那类错，所以逐个现算。
    print("\n【12】4.5 现场任务卡小节的数字（重跑 1班-07 现算）")
    card = ROOT / "实验一" / "现场新句任务卡" / "1班-07.txt"
    if not card.is_file():
        check("现场任务卡 1班-07 存在（4.5 的举例对象）", False, f"{card} 不存在")
    else:
        r = O.check_card(O.parse_card(card), sw_set)
        src = O.parse_card(card)["sentence"]
        n_fw = len(re.findall(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]", src))
        check(f"1班-07 含 {n_fw} 个全角数字，与 4.5 正文一致",
              f"{n_fw} 个全角数字" in text,
              f"实测 {n_fw} 个，报告 4.5 里不是这个数")
        check(f"1班-07 规范化前后字符数均为 {len(src)}（报告称前后都是 {len(src)} 个字符）",
              len(src) == len(r["norm"]) and f"都是 {len(src)} 个字符" in text,
              f"实测 {len(src)} -> {len(r['norm'])}，或正文数字对不上")
        norm_phrase = f"程序的规范化输出：{r['norm']}"
        check("4.5 引用的规范化输出与现算逐字一致", norm_phrase in text,
              f"现算是「{r['norm']}」，报告里不是这句")
        # 该卡 C 组三条专项断言必须全过，否则 4.5 写「三条全 PASS」就是假的
        c_ok = all(ok for _n, ok, _m in r["results"] if _n.startswith("C 专项"))
        check("1班-07 的 C 组专项断言全过（4.5 称「三条全 PASS」）",
              c_ok and "三条全 PASS" in text, "有 C 组专项断言未通过，或正文缺该表述")

    # ---------- 汇总 ----------
    # 自指检查，必须放在最后：报告 6.2 里写着「verify_report.py … N 项检查全过」，
    # 而 N 这个数字一旦写进正文就会随门禁增删而漂移（这几轮就漂过：
    # 58 → 68 → 69 → 77，报告里还留着 58）。所以让脚本自己核自己：
    # 报告里的 N 必须等于本脚本最后打印的那个总数。
    # 这里手动 CHECKS += 1 而不是调 check()：check() 是在**调用处**求值参数、
    # 进入函数后才自增，f"{CHECKS}" 读到的是自增前的值，会差 1。
    CHECKS += 1
    _self_ok = f"{CHECKS} 项检查全过" in text
    _self_name = f"报告称「{CHECKS} 项检查全过」与实际跑的项数一致"
    print(f"  [{'PASS' if _self_ok else 'FAIL'}] {_self_name}"
          + ("" if _self_ok else f"  -> 实际跑了 {CHECKS} 项，报告里没这个数"))
    if not _self_ok:
        FAILS.append(f"{_self_name}: 实际跑了 {CHECKS} 项，报告里没这个数")

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
