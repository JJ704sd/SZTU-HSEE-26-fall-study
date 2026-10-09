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
  5. make_shots.py      运行结果截图
  6. make_report.py     生成实验报告 DOCX + PDF
  7. validate_docx.py   DOCX 结构自检
  8. verify_report.py   报告数字与真实结果一致性核验

任何一个环节非零退出都会立即报错，不会带着错误继续往下跑。
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
    ("主流程 A-J + 断言", BASE / "exp1_starter.py"),
    ("调试记录复现", BASE / "debug_record.py"),
    ("现场任务卡核验", BASE / "onsite_check.py"),
    ("选做/必做对比", BASE / "compare_groups.py"),
    ("生成运行截图", BASE / "make_shots.py"),
    ("生成实验报告", BASE / "make_report.py"),
    ("DOCX 结构自检", TOOLS / "validate_docx.py"),
    ("报告数字一致性核验", BASE / "verify_report.py"),
]


def main():
    print("=" * 74)
    print("实验一 · 一键复现")
    print("=" * 74)
    failed = []
    for i, (name, script) in enumerate(STEPS, 1):
        print(f"\n[{i}/{len(STEPS)}] {name}  ->  {script.name}")
        t0 = time.time()
        r = subprocess.run([sys.executable, str(script)], cwd=str(BASE),
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
            failed.append(name)
        else:
            print(f"      [OK] {dt:.1f}s")

    print("\n" + "=" * 74)
    if failed:
        print(f"以下环节失败：{failed}")
    else:
        print(f"全部 {len(STEPS)} 个环节全部通过。")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
