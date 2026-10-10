# -*- coding: utf-8 -*-
"""
================================================================================
实验一 · 一键复现入口
--------------------------------------------------------------------------------
用法：python run_all.py

依次执行：
  1. exp1_starter.py    主流程：A-J 十组数据 + 31 条断言 + 结果落盘
  2. debug_record.py    调试记录：4 个真实错误的复现与修复验证
  3. onsite_check.py    现场新句：60 张任务卡 + 286 条断言
  4. compare_groups.py  选做与必做对比表
  5. make_shots.py      运行结果截图（输入由第 1-4 步的 stdout 自动落盘，见 CAPTURE）
  6. make_report.py     生成实验报告 DOCX + PDF
  7. validate_docx.py   DOCX 结构自检（zip/必需部件/XML 良构/图片）
  8. audit_docx_layout.py  DOCX 版式一致性：表格与图片是否溢出正文宽度、
                          同一角色内字号与行距取值是否唯一（规范性 10 分明文考察项）
  9. verify_report.py   报告数字与真实结果一致性核验
 10. check_kinsoku.py   PDF 排版实测：行首避头、行尾避尾、整词完整性、.notdef 指纹
 11. compare_docx_pdf.py  DOCX 与 PDF 是两套独立后端，交叉核对内容逐字一致
 12. check_glyph.py     全文字形覆盖：问字体 cmap，而不是问 PDF 文本层
 13. verify_code_snippets.py  报告里的代码片段必须逐行来自 exp1_starter.py
 14. verify_thinking.py 思考题「实测断言」核验：数字可从 data/ 重算、无编造字段名
 15. check_guide_compliance.py  对照指导书 p9「报告必须包含」清单与模板备注逐条核，
                          并核报告总页数不超过 10 页

任何一个环节非零退出都会**立即中止**，不会带着错误继续往下跑。

为什么要单列一道"清单核对"：指导书把必备内容写成一串明文项（处理流程、规范化前后
对比、AI 说明的五个方面…），而报告正文是反复增删压缩的——压缩最容易压掉的正是
这类清单项。本轮就发生过：6.2 的 AI 说明为省版面从 6 行删到 5 行，"使用目的"
"关键提问概述""收获与反思"三项连同字样一起没了，14 道门禁却全绿。
清单式要求必须由机器对着原文核，靠人记等于没有。

CAPTURE 的由来：make_shots.py 是按标记（"【断言汇总】"、"调试 1"、"【汇总】"…）
从**真实运行输出**里切段来渲染终端截图的，它读的是 _tools/v_*.txt。
这些 .txt 曾是手工重定向存下来的，代价是：换一台电脑、或 _tools 被清理之后，
第 5 步会打印"跳过（源文件不存在）"然后生成 0 张图，而 run_all 依然报 [OK]——
一个静默的空产物。所以这里直接把第 1-4 步的 stdout 落盘，第 5 步永远不缺输入。
================================================================================
"""

import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
TOOLS = BASE.parent / "_tools"

STEPS = [
    # (名称, 脚本, 附加参数)
    ("主流程 A-J + 断言", BASE / "exp1_starter.py", []),
    ("调试记录复现", BASE / "debug_record.py", []),
    ("现场任务卡核验", BASE / "onsite_check.py", []),
    ("选做/必做对比", BASE / "compare_groups.py", []),
    ("生成运行截图", BASE / "make_shots.py", []),
    ("生成实验报告", BASE / "make_report.py", []),
    ("DOCX 结构自检", TOOLS / "validate_docx.py", []),
    ("DOCX 版式一致性", TOOLS / "audit_docx_layout.py", []),
    ("报告数字一致性核验", BASE / "verify_report.py", []),
    ("PDF 排版实测", TOOLS / "check_kinsoku.py", []),
    ("DOCX/PDF 内容交叉核对", TOOLS / "compare_docx_pdf.py", []),
    ("代码片段 ↔ 源程序核对", TOOLS / "verify_code_snippets.py", []),
    # --docx 是必需的：不带参数时它只打印用法并返回 2，会被误当成核验失败
    ("字体字形覆盖", TOOLS / "check_glyph.py", ["--docx"]),
    ("思考题实测断言核验", BASE / "verify_thinking.py", []),
    ("指导书必备内容核对", TOOLS / "check_guide_compliance.py", []),
]

# 第 1-4 步的 stdout 就是第 5 步的输入，这里一并落盘（见模块 docstring 的 CAPTURE）。
CAPTURE = {
    "exp1_starter.py": "v_main.txt",
    "debug_record.py": "v_debug.txt",
    "onsite_check.py": "v_onsite.txt",
    "compare_groups.py": "v_compare.txt",
}


def main():
    print("=" * 74)
    print("实验一 · 一键复现")
    print("=" * 74)
    for i, (name, script, extra) in enumerate(STEPS, 1):
        print(f"\n[{i}/{len(STEPS)}] {name}  ->  {script.name}"
              + (f" {' '.join(extra)}" if extra else ""))
        t0 = time.time()
        r = subprocess.run([sys.executable, str(script)] + list(extra),
                           cwd=str(BASE),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        dt = time.time() - t0
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
        for line in tail[-3:]:
            print("      " + line.strip())
        if r.returncode != 0:
            print(f"      !! 退出码 {r.returncode}")
            for line in (r.stderr or "").splitlines()[-6:]:
                print("      " + line)
            # 立即停，不要带着错误继续往下跑。
            # 这不是洁癖：第 6 步生成报告失败时，第 7 步会去"自检"磁盘上**上一版**
            # 的 DOCX 并报全部通过——那是一个假绿灯，比直接失败更难发现。
            print("\n" + "=" * 74)
            print(f"在第 {i}/{len(STEPS)} 步「{name}」失败，已中止；"
                  f"后续 {len(STEPS) - i} 个环节未执行。")
            print("=" * 74)
            return 1
        print(f"      [OK] {dt:.1f}s")
        if script.name in CAPTURE:
            cap = TOOLS / CAPTURE[script.name]
            cap.write_text(r.stdout or "", encoding="utf-8")
            n = len((r.stdout or "").splitlines())
            print(f"      已落盘 {cap.name}（{n} 行，供 make_shots.py 切片）")

    # 第 5 步"生成 0 张截图"也会返回 0，那是个静默的空产物，必须在这里拦掉。
    # 判据取自 make_shots.py 自己的输出文本，不去猜它内部状态。
    shots = sorted((BASE / "outputs" / "截图").glob("*.png"))
    if not shots:
        print("\n" + "=" * 74)
        print("产物为空：outputs/截图 下 0 张 PNG。"
              "make_shots.py 缺输入时会打印「跳过」并静默返回 0，"
              "所以必须由本编排器兜住。")
        print("=" * 74)
        return 1
    print(f"\n截图产物：{len(shots)} 张（outputs/截图/）")

    print("\n" + "=" * 74)
    print(f"全部 {len(STEPS)} 个环节全部通过。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
