#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格核对本地 HEAD 与 GitHub 远端 main 的每一棵树。

比对方式是「路径 + git blob SHA」逐条对齐，而不是比数量：
数量相等但内容不同、或路径改名而数量不变，都必须抓出来。
"""
import json
import subprocess
import sys
import urllib.request
import os
import base64

REPO = "JJ704sd/SZTU-HSEE-26-fall-study"
LOCAL = r"D:\深技大课程学习"


def run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    if p.returncode != 0:
        sys.exit("git failed: %s\n%s" % (args, p.stderr.decode("utf-8", "replace")))
    return p.stdout.decode("utf-8", "replace")


def gh(path):
    """走 gh CLI 拿 JSON，避免自己处理 token。"""
    out = subprocess.run(["gh", "api", path], capture_output=True)
    if out.returncode != 0:
        sys.exit("gh api failed: %s\n%s" % (path, out.stderr.decode("utf-8", "replace")))
    return json.loads(out.stdout.decode("utf-8", "replace"))


# ---------- 本地：git ls-tree -r HEAD ----------
local = {}
for line in run(["git", "ls-tree", "-r", "HEAD"], cwd=LOCAL).splitlines():
    meta, path = line.split("\t", 1)
    mode, otype, sha = meta.split()
    assert otype == "blob", (path, otype)
    local[path] = sha

# ---------- 远端：git tree API（递归，分页取全） ----------
remote = {}
truncated = False
sha_main = gh("repos/%s/branches/main" % REPO)["commit"]["sha"]
tree = gh("repos/%s/git/trees/%s?recursive=1" % (REPO, sha_main))
truncated = tree.get("truncated", False)
for e in tree["tree"]:
    if e["type"] == "blob":
        remote[e["path"]] = e["sha"]

# 截断时不能下结论，必须重取
if truncated:
    sys.exit("远端 tree 被 GitHub 截断，本次比对无效，需重取")

# ---------- 逐条比对 ----------
only_local = sorted(set(local) - set(remote))
only_remote = sorted(set(remote) - set(local))
diff_sha = sorted(p for p in (set(local) & set(remote)) if local[p] != remote[p])

print("local  HEAD   : %s" % run(["git", "rev-parse", "HEAD"], cwd=LOCAL).strip())
print("remote main   : %s" % sha_main)
print("local  blobs  : %d" % len(local))
print("remote blobs  : %d" % len(remote))
print()

ok = True
if local and remote and not (only_local or only_remote or diff_sha):
    print("[OK] 路径集合与 blob SHA 全部一致，共 %d 个文件逐字节相同" % len(local))
else:
    ok = False
    if only_local:
        print("[!] 本地有、远端没有（%d）:" % len(only_local))
        for p in only_local[:20]:
            print("      - %s" % p)
    if only_remote:
        print("[!] 远端有、本地没有（%d）:" % len(only_remote))
        for p in only_remote[:20]:
            print("      - %s" % p)
    if diff_sha:
        print("[!] 同名但内容不同（%d）:" % len(diff_sha))
        for p in diff_sha[:20]:
            print("      ~ %s\n          local=%s\n          remote=%s" % (p, local[p], remote[p]))

# ---------- 额外安全检查 ----------
print()
print("--- 安全检查 ---")
leaks = [p for p in remote if "__pycache__" in p or p.endswith((".pyc", ".pyo"))]
print("远端 __pycache__/.pyc : %d %s" % (len(leaks), leaks[:5] if leaks else ""))

big = [(p, s) for p, s in ((e["path"], e.get("size", 0))
                           for e in tree["tree"] if e["type"] == "blob") if s > 50 * 1024 * 1024]
print("远端 >50MB 文件        : %d %s" % (len(big), [b[0] for b in big] if big else ""))

# 远端 README 首行，确认不是我以为的那个
readme = gh("repos/%s/contents/README.md" % REPO)
txt = base64.b64decode(readme["content"]).decode("utf-8", "replace")
print("远端 README 首行       : %s" % txt.splitlines()[0] if txt.strip() else "(空)")

sys.exit(0 if ok else 1)
