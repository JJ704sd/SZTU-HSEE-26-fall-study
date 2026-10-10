# -*- coding: utf-8 -*-
"""变异测试：确认 check_guide_compliance.py 不是一道永远绿的门禁。

做法：临时改掉报告正文里的一项明文要求字样 → 重建 PDF → 跑核对脚本，
必须报红；然后从备份原样恢复并重建，基线必须全绿。

不用 git checkout 回滚：那是回到上一次提交，会把本轮全部改动一起丢掉。
备份用 shutil.copy2，最后无条件恢复（try/finally）。
"""
import pathlib
import shutil
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent
SRC = BASE / "实验一" / "make_report.py"
BACKUP = BASE / "_mut_backup.py"

sys.stdout.reconfigure(encoding="utf-8")

# 每个变异是一组 (旧串, 新串)，按顺序全局替换。
#
# 前两次跑这里都误判成"门禁有漏洞"，其实是变异设计不对，值得记下来：
# · 只把标题「规范化前后对比」改成「规范化对比」——对比表还在，要求仍然满足，判绿是对的；
# · 只改表格行标签——但 2.2 正文里还有「规范化后原样不动」、5.3 标题里还有
#   「规范化前后对比」，两个关键词都还在，一样是要求仍满足。
# 门禁只能核"要求的字样在不在"，核不了"语义上有没有一张对比表"——这是它的
# 天花板，如实说明而不是硬凑一个变异。可判的必须是**真正删掉全部字样**。
MUTATIONS = [
    ("收获与反思 → 收获（删掉模板备注点名的字样）", [("收获与反思", "收获")]),
    ("使用目的 → 目的", [("使用目的", "目的")]),
    ("关键提问概述 → 提问概述", [("关键提问概述", "提问概述")]),
    ("处理流程 → 流程", [("处理流程", "流程")]),
    ("删光全部「规范化前」「规范化后」字样",
     [("规范化前", "原文"), ("规范化后", "结果")]),
    ("报错现象 → 报错", [("报错现象", "报错")]),
    ("删掉「电子签名」", [("电子签名", "签名")]),
    # ---- 本轮新增要求项的变异（清单扩容后必须重新证明它们不是永远绿）----
    # 删掉指导书步骤6 的「新句任务卡」「任务卡要求」字样
    ("删掉「新句任务卡」", [("新句任务卡", "新句卡")]),
    ("删掉「任务卡要求」", [("任务卡要求", "任务卡对应")]),
    # 模板章节：把「五、代码（附注解）与结果分析」的标题字样改掉
    ("删掉「（附注解）」", [("（附注解）", "")]),
    # 评分重点：「关键代码片段」是 5.1 的标题
    ("删掉「关键代码片段」", [("关键代码片段", "代码")]),
    # 选做组主题（指导书 p3）：删一条就应报红
    ("删掉选做主题「睡眠健康建议」", [("睡眠健康建议", "健康建议")]),
    ("删掉选做主题「老年健康管理」", [("老年健康管理", "老年健康")]),
    # 封面完整性：把提交时间改回空白（规范性 10 分明文「封面内容是否完整」，
    # 且 PDF 无法事后手写补救）。这一条验证的是 cover 检查**不是**空转。
    ("封面「提交时间」清空",
     [('("提交时间", "2026 年 10 月 10 日")', '("提交时间", "")')]),
    ("封面「实验地点」清空",
     [('("实验地点", "A2-314")', '("实验地点", "")')]),
]


def build():
    return subprocess.run([sys.executable, str(SRC)], cwd=str(SRC.parent),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def check():
    r = subprocess.run([sys.executable, str(BASE / "_tools" / "check_guide_compliance.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "")


shutil.copy2(SRC, BACKUP)
try:
    text = BACKUP.read_text(encoding="utf-8")
    print("=== 基线（未变异）===")
    build()
    rc, out = check()
    print(f"  exit={rc}  {'全绿 OK' if rc == 0 else '基线就不绿，有问题'}")
    if rc != 0:
        print(out)
        sys.exit(1)

    print("\n=== 逐个注入变异，要求每个都被抓 ===")
    failed = []
    for label, pairs in MUTATIONS:
        mutated = text
        absent = []
        for old, new in pairs:
            if old not in mutated:
                absent.append(old)
            mutated = mutated.replace(old, new)
        if absent:
            failed.append(f"{label}：源码里找不到 {absent}，变异没生效")
            print(f"  [跳过] {label} —— 源串不存在 {absent}")
            continue
        SRC.write_text(mutated, encoding="utf-8")
        build()
        rc, out = check()
        caught = rc != 0
        missing_line = next((ln.strip() for ln in out.splitlines()
                             if "缺失项：" in ln), "")
        print(f"  [{'抓到了' if caught else '漏放!!'}] {label}")
        print(f"        {missing_line}")
        if not caught:
            failed.append(label)
    print("\n=== 结论 ===")
    if failed:
        print("变异未被全部抓住：")
        for f in failed:
            print("  -", f)
        sys.exit(1)
    print(f"{len(MUTATIONS)} 个变异全部被抓，门禁有效。")
finally:
    shutil.copy2(BACKUP, SRC)
    BACKUP.unlink(missing_ok=True)
    print("\n已恢复 make_report.py 并重建基线")
    build()