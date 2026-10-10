# -*- coding: utf-8 -*-
"""变异测试：verify_report.py 第【8】项（4.3 表「停用词删除」列）是否真的会红。

这一列此前是全表唯一没有任何门禁覆盖的数据单元格（其余列都比 阶段统计 CSV），
所以新加的检查必须证明自己不是永远绿。
"""
import pathlib
import shutil
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent
SRC = BASE / "实验一" / "make_report.py"
BACKUP = BASE / "_mut_backup.py"

sys.stdout.reconfigure(encoding="utf-8")

# (说明, 旧串, 新串)
MUTATIONS = [
    ("A 组少写一次患者（与、患者×2 → 与/患者）",
     '"与/患者×2"', '"与/患者"'),
    ("D 组漏掉「进行」", '"与/建议/患者×2/进行"', '"与/建议/患者×2"'),
    ("C 组凭空多一个停用词", '"0 / 0", "与/患者",', '"0 / 0", "与/患者/建议",'),
]


def run(script):
    return subprocess.run([sys.executable, script], cwd=str(script.parent),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


shutil.copy2(SRC, BACKUP)
try:
    text = BACKUP.read_text(encoding="utf-8")
    print("=== 基线（未变异）===")
    run(SRC)
    r = run(BASE / "实验一" / "verify_report.py")
    print(f"  exit={r.returncode}  {'全绿 OK' if r.returncode == 0 else '基线不绿'}")
    if r.returncode != 0:
        print(r.stdout[-800:])
        sys.exit(1)

    print("\n=== 注入变异，要求每个都被第【8】项抓到 ===")
    failed = []
    for label, old, new in MUTATIONS:
        if old not in text:
            failed.append(f"{label}：源串 {old!r} 不存在")
            print(f"  [跳过] {label}")
            continue
        SRC.write_text(text.replace(old, new), encoding="utf-8")
        run(SRC)
        r = run(BASE / "实验一" / "verify_report.py")
        caught = r.returncode != 0
        detail = [ln.strip() for ln in r.stdout.splitlines() if "停用词删除" in ln]
        print(f"  [{'抓到了' if caught else '漏放!!'}] {label}")
        for dl in detail:
            print(f"        {dl}")
        if not caught:
            failed.append(label)

    print("\n=== 结论 ===")
    if failed:
        print("未被全部抓住：")
        for f in failed:
            print("  -", f)
        sys.exit(1)
    print(f"{len(MUTATIONS)} 个变异全部被抓。")
finally:
    shutil.copy2(BACKUP, SRC)
    BACKUP.unlink(missing_ok=True)
    run(SRC)
    print("\n已恢复 make_report.py 并重建基线")