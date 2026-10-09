"""Dump every data file byte-exactly: raw bytes (hex head) + decoded text per encoding.

Purpose: establish ground truth for the report. No assumptions about content.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA = Path(r"D:\深技大课程学习\AI time\实验一\材料\实验课讲义+数据\实验一\实验一\data")
STOP = Path(r"D:\深技大课程学习\AI time\实验一\材料\实验课讲义+数据\实验一\实验一\stopwords.txt")

files = sorted(DATA.glob("*.txt")) + [DATA / "任务表.csv", STOP]

for p in files:
    if not p.is_file():
        print(f"!!! MISSING {p}")
        continue
    b = p.read_bytes()
    print("=" * 78)
    print(f"FILE: {p.name}   ({len(b)} bytes)")
    print(f"first 24 bytes hex: {b[:24].hex(' ')}")
    print("-" * 78)
    for enc in ("utf-8", "utf-8-sig", "gb18030", "utf-16"):
        try:
            t = b.decode(enc)
            print(f"[{enc}] OK  repr(first line)={t.splitlines()[0][:120]!r}")
            if enc == ("utf-16" if p.name.endswith("_utf16.txt") else
                       "gb18030" if p.name.endswith("_gb18030.txt") else
                       "utf-8-sig" if p.name.endswith("_utf8sig.txt") else "utf-8"):
                print(f"--- decoded text ({enc}) ---")
                print(t)
                print("--- end ---")
            print()
        except UnicodeError as e:
            print(f"[{enc}] FAIL {type(e).__name__}: {e}")
            print()
