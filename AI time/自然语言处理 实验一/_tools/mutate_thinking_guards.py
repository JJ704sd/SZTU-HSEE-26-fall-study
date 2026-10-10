# -*- coding: utf-8 -*-
"""
================================================================================
变异测试：证明思考题的新守卫（QUO / GRP / Q1.7 / Q1.8）不是「永远绿」
--------------------------------------------------------------------------------
用法：python _tools/mutate_thinking_guards.py

背景：本轮查出三处**答案里的事实错误**，而当时 29 项检查全绿——
    · Q1 举的例句「未见异常放电；否认胸痛」十组数据里根本没有
      （D 组是「未见异常放电，」，没有分号；「否认胸痛」全组无，A 组写的是「不伴胸痛」）；
    · Q3 声称「实测 C 组的，：；全转成半角」，实测 C 组 ；有 0 处（全角分号在 B 组）；
    · Q1 把 C 组全角日期「２０２６－１０－１５ ０９：３０」当成了半角原文。
根因是门禁只核数字、不核"答案引的那句话"和"某个字符属于哪一组"。
修完加了 QUO / GRP 两道守卫 + Q1.7/Q1.8 数据驱动的例句检查，
这里把缺陷重新注入，确认它们会红。

沙箱只复制 verify_thinking.py 需要的东西（*.py + data/），不含 outputs/ 与任务卡。
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
EXP = ROOT / "实验一"
VERIFY_NAME = "verify_thinking.py"
REPORT_NAME = "make_report.py"


def build_sandbox(tmp: Path) -> Path:
    dst = tmp / "exp1"
    dst.mkdir(parents=True)
    shutil.copytree(EXP / "data", dst / "data")
    for p in EXP.glob("*.py"):
        shutil.copyfile(p, dst / p.name)
    for p in EXP.glob("思考题_*.md"):
        shutil.copyfile(p, dst / p.name)
    return dst


def run_verify(sandbox: Path):
    r = subprocess.run([sys.executable, str(sandbox / VERIFY_NAME)],
                       cwd=str(sandbox), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    lines = {}
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"\s*\[(OK|!! )\]\s*(\S+)\s+(.+?)(?:\s{2,}实测值.*)?$", ln)
        if m:
            lines[m.group(2)] = ("PASS" if m.group(1) == "OK" else "FAIL")
    if not lines and (r.stdout or "").strip() == "":
        print("      !! 脚本无输出，stderr：")
        print("      " + "\n      ".join((r.stderr or "").splitlines()[-5:]))
    return r.returncode, lines, r.stdout or ""


def sub_in(sandbox: Path, fname: str, old: str, new: str, count=0):
    p = sandbox / fname
    src = p.read_text(encoding="utf-8")
    assert old in src, f"{fname} 里找不到待替换片段，变异定义失效：{old[:40]!r}"
    p.write_text(src.replace(old, new, count) if count else src.replace(old, new),
                 encoding="utf-8")


D_SENT = "脑电图检查未见异常放电，患者无意识障碍，不伴明显头痛"
D_AFTER = "脑电图检查未见异常放电患者无意识障碍不伴明显头痛"


# --------------------------------------------------------------- 变异定义 ---
def mut_fake_sentence(s):
    """把 D 组真例句换回虚构的「未见异常放电；否认胸痛」——复现本轮的原错误"""
    sub_in(s, REPORT_NAME, D_SENT, "未见异常放电；否认胸痛")
    sub_in(s, REPORT_NAME, D_AFTER, "未见异常放电否认胸痛")


def mut_semicolon_back_to_c(s):
    """把「；」重新安到 C 组头上——复现本轮的原错误"""
    sub_in(s, REPORT_NAME,
           "实测 C 组的「，」「：」全转成半角", "实测 C 组的「，」「：」「；」全转成半角")


def mut_wrong_after_form(s):
    """粘连形态写错：只删第一个逗号"""
    sub_in(s, REPORT_NAME, D_AFTER,
           "脑电图检查未见异常放电患者无意识障碍，不伴明显头痛")


def mut_wrong_number(s):
    """把实测字符数改错——确认原有的数字检查仍在生效"""
    sub_in(s, REPORT_NAME, "只剩 35 个字符", "只剩 38 个字符")


def mut_fake_field(s):
    """编造字段名——确认 FAB 守卫仍在生效"""
    sub_in(s, REPORT_NAME, "原始文本另存一份，不原地覆盖。",
           "原始文本另存一份，不原地覆盖，orderId 也要保留。")


def mut_drop_bom_branch(s):
    """把 decode_bytes 回退成「按顺序试到不报错为止」。

    危险之处：gb18030 能硬解 utf-16 字节而不抛异常，D 组于是被解成乱码，
    语料里查不到原句 → QUO 失效。这条验证 BOM 分支是必需的。
    注意只有 QUO 受影响：Q1.7 走的是 collect() 里按文件硬编码的 utf-16 读取，
    不经 decode_bytes——这是刻意分工（那里写死编码，让编码错了当场炸出来）。
    """
    sub_in(s, VERIFY_NAME,
           'if raw[:2] in (b"\\xff\\xfe", b"\\xfe\\xff"):', "if False:")


MUTATIONS = [
    ("例句换成虚构的「未见异常放电；否认胸痛」", mut_fake_sentence, ["Q1.7", "Q1.8", "QUO"]),
    ("把全角分号重新安到 C 组头上", mut_semicolon_back_to_c, ["GRP"]),
    ("粘连形态写错（只删第一个逗号）", mut_wrong_after_form, ["Q1.8"]),
    ("实测字符数改错 35 -> 38", mut_wrong_number, ["Q2.3"]),
    ("编造字段名 orderId", mut_fake_field, ["FAB"]),
    ("回退掉 BOM 优先的解码", mut_drop_bom_branch, ["QUO"]),
]

# 变异 1 期望变红的项里，Q1.7/Q1.8 是数据驱动例句检查，QUO 是通用例句守卫；
# 三条同时红才说明"虚构例句"这件事无路可逃——只红一条仍可能是巧合。


def main():
    print("=" * 74)
    print("变异测试：思考题 QUO / GRP / Q1.7 / Q1.8 守卫有效性")
    print("=" * 74)

    with tempfile.TemporaryDirectory() as td:
        s0 = build_sandbox(Path(td) / "base")
        code0, lines0, out0 = run_verify(s0)
        fails = [k for k, v in lines0.items() if v == "FAIL"]
        print(f"\n[基线] 副本未变异 -> 退出码 {code0}，失败 {len(fails)} 项"
              + (f"：{fails}" if fails else "（全绿，符合预期）"))
        if code0 != 0 or fails:
            print("!! 基线就不绿，后面的「变异被抓」没有意义。先修基线。")
            return 1
        print(f"       守卫覆盖：{sorted(k for k in lines0 if k in ('FAB', 'QUO', 'GRP'))}")

    bad = 0
    for i, (name, fn, expect) in enumerate(MUTATIONS, 1):
        with tempfile.TemporaryDirectory() as td:
            s = build_sandbox(Path(td) / f"m{i}")
            fn(s)
            code, lines, out = run_verify(s)
            hit = [k for k in expect if lines.get(k) == "FAIL"]
            caught = code != 0 and set(hit) == set(expect)
            print(f"\n  [{i}/{len(MUTATIONS)}] {name}")
            print(f"        期望变红：{expect} -> {'抓到了' if caught else '漏了'}")
            if not caught:
                bad += 1
                red = [k for k, v in lines.items() if v == "FAIL"]
                print(f"        实际退出码 {code}，变红的项：{red or '无'}")

    print("\n" + "=" * 74)
    if bad:
        print(f"结果：{len(MUTATIONS) - bad}/{len(MUTATIONS)} 个变异被抓，{bad} 个漏网。")
    else:
        print(f"结果：基线全绿，{len(MUTATIONS)}/{len(MUTATIONS)} 个变异全部被抓。")
    print("=" * 74)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
