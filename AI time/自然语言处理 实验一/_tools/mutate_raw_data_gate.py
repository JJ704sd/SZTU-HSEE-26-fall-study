# -*- coding: utf-8 -*-
"""
================================================================================
变异测试：证明第【10】【11】项不是「永远绿」的门禁
--------------------------------------------------------------------------------
用法：python _tools/mutate_raw_data_gate.py [docx]
      （可选传待核验的 DOCX；正式件被 WPS 占用、报告只生成到暂存路径时必需，
        否则沙箱里复制到的是上一版报告，基线会因自指检查而红，变异结果就没意义了）

做法：把整个工作区复制到临时目录，在**副本**上做 8 种破坏，逐个确认
verify_report.py 里对应的检查行真的变成 [FAIL]。

为什么必须在副本上做：这两项核对的正是「原始文件不得被改动」。
拿真身去改再改回来，等于用违反被测规则的动作去测规则；一旦中途异常退出，
留在磁盘上的就是一份被动过的原始数据——这个代价不可接受。
因此 verify_report.py 的根目录做成可传参（见其文件头），变异全在副本内完成。

基线要求：未变异的副本必须全绿（否则"变异被抓"可能只是因为基线本来就红）。
================================================================================
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / "实验一" / "verify_report.py"

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "原始底稿_*.docx", "_auth")
DOCX_NAME = "202400502133陈佳豪实验1.docx"
# 正式件可能被 WPS 锁住而只能生成到暂存路径；沙箱必须用"本轮真正要交付的那份"
SRC_DOCX = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "报告" / DOCX_NAME


def build_sandbox(tmp: Path) -> Path:
    """复制一份可独立运行的工作区。verify_report 依赖 outputs/、报告/、材料/、实验一/*.py。"""
    for sub in ("实验一", "材料", "报告"):
        shutil.copytree(ROOT / sub, tmp / sub, ignore=IGNORE)
    shutil.copyfile(SRC_DOCX, tmp / "报告" / DOCX_NAME)
    return tmp


def run_verify(sandbox: Path):
    docx = sandbox / "报告" / DOCX_NAME
    r = subprocess.run(
        [sys.executable, str(sandbox / "实验一" / "verify_report.py"), str(docx), str(sandbox)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = {}
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"\s*\[(PASS|FAIL)\]\s*(.+?)(?:\s{2,}->.*)?$", ln)
        if m:
            lines[m.group(2).strip()] = m.group(1)
    return r.returncode, lines, r.stdout or ""


# ------------------------------------------------------------------ 变异定义 ---
def mut_flip_byte(s):
    """改 data/input_A_utf8.txt 的一个字节 —— 模拟「顺手改了点原始数据」"""
    p = s / "实验一" / "data" / "input_A_utf8.txt"
    raw = bytearray(p.read_bytes())
    raw[0] ^= 0x20
    p.write_bytes(bytes(raw))


def mut_delete_data(s):
    p = s / "实验一" / "data" / "optional_E_utf8.txt"
    p.unlink()


def mut_extra_file(s):
    (s / "实验一" / "data" / "input_E_utf8_backup.txt").write_text("x", encoding="utf-8")


def mut_flip_card(s):
    p = s / "实验一" / "现场新句任务卡" / "1班-01.txt"
    raw = bytearray(p.read_bytes())
    raw[0] ^= 0x20
    p.write_bytes(bytes(raw))


def mut_flip_stopwords(s):
    p = s / "实验一" / "stopwords.txt"
    p.write_text(p.read_text(encoding="utf-8") + "的\n", encoding="utf-8")


def mut_drop_card(s):
    """删一张任务卡：断言总数不变，但「60 张」这个数字就该对不上了"""
    (s / "实验一" / "现场新句任务卡" / "2班-30.txt").unlink()


def mut_drop_assertion(s):
    """从 onsite_check.py 副本里摘掉一条 C 专项断言：卡片数不变，断言总数应从 286 掉下来"""
    p = s / "实验一" / "onsite_check.py"
    src = p.read_text(encoding="utf-8")
    old = """        results.append((
            "C 专项：汉字内容未被破坏",
            all(c in norm for c in "康复训练完成检查"),
            "汉字被误删"))
"""
    assert old in src, "onsite_check.py 结构变了，变异定义失效"
    p.write_text(src.replace(old, ""), encoding="utf-8")


def mut_remove_baseline(s):
    """把基准副本整个删掉：门禁必须显式报错，而不是「找不到就没查」地静默通过"""
    shutil.rmtree(next(p for p in (s / "材料").iterdir() if p.is_dir()))


# (变异名, 施加函数, 期望变 FAIL 的检查行关键字)
MUTATIONS = [
    ("改动 data/input_A_utf8.txt 一个字节", mut_flip_byte, "SHA256 与原件一致"),
    ("删除 data/optional_E_utf8.txt", mut_delete_data, "在工作副本中齐全"),
    ("data/ 多放一个备份文件", mut_extra_file, "无多余文件"),
    ("改动任务卡 1班-01.txt 一个字节", mut_flip_card, "SHA256 与原件一致"),
    ("往 stopwords.txt 追加一个词", mut_flip_stopwords, "SHA256 与原件一致"),
    ("删除任务卡 2班-30.txt", mut_drop_card, "与现算一致"),
    ("从 onsite_check.py 摘掉一条 C 专项断言", mut_drop_assertion, "与现算一致"),
    ("整个删掉材料/基准副本", mut_remove_baseline, "找到原始数据基准副本"),
]


def main():
    print("=" * 74)
    print("变异测试：第【10】【11】项门禁有效性")
    print("=" * 74)

    # ---- 基线：副本必须全绿 ----
    with tempfile.TemporaryDirectory() as td:
        s0 = build_sandbox(Path(td) / "base")
        code0, lines0, _ = run_verify(s0)
        fails = [k for k, v in lines0.items() if v == "FAIL"]
        print(f"\n[基线] 副本未变异 -> 退出码 {code0}，失败 {len(fails)} 项"
              + (f"：{fails}" if fails else "（全绿，符合预期）"))
        baseline_ok = code0 == 0 and not fails
        if not baseline_ok:
            print("!! 基线就不绿，后面的「变异被抓」没有意义。先修基线。")
            return 1

    bad = 0
    for i, (name, fn, expect_kw) in enumerate(MUTATIONS, 1):
        with tempfile.TemporaryDirectory() as td:
            s = build_sandbox(Path(td) / f"m{i}")
            fn(s)
            code, lines, out = run_verify(s)
            hit = [k for k, v in lines.items() if v == "FAIL" and expect_kw in k]
            caught = code != 0 and bool(hit)
            mark = "抓到了" if caught else "漏了"
            print(f"\n  [{i}/{len(MUTATIONS)}] {name}")
            print(f"        期望含「{expect_kw}」的行变红 → {mark}")
            if not caught:
                bad += 1
                failed_keys = [k for k, v in lines.items() if v == "FAIL"]
                print(f"        实际退出码 {code}，变红的行：{failed_keys or '无'}")
                print("        （若没有变红，说明这道门禁对该破坏是瞎的）")

    print("\n" + "=" * 74)
    if bad:
        print(f"结果：{len(MUTATIONS) - bad}/{len(MUTATIONS)} 个变异被抓，{bad} 个漏网。")
    else:
        print(f"结果：基线全绿，{len(MUTATIONS)}/{len(MUTATIONS)} 个变异全部被抓。")
    print("=" * 74)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
