"""UTF-8-safe extraction of the lab tar archive (Windows bsdtar mangles CJK names)."""
import sys
import tarfile
from pathlib import Path

SRC = Path(r"C:\Users\Administrator\.minimax\v2\assets\2026\10\09"
           r"\09-22-19-559-asset_20261009-092219-559_cfba835818a7_9d75e442-实验课讲义+数据.tar")
DST = Path(r"D:\深技大课程学习\AI time\实验一\材料")

if DST.exists():
    pass  # keep existing; overwrite files below

with tarfile.open(SRC, "r:*") as tf:
    members = tf.getmembers()
    for m in members:
        # normalize name from raw bytes if python decoded with surrogates
        name = m.name
        if any("\ud800" <= ch <= "\udfff" for ch in name):
            name = m.name.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        m.name = name
    tf.extractall(DST, members=members, filter="data")

for p in sorted(DST.rglob("*")):
    if p.is_file():
        print(f"{p.relative_to(DST)}  ({p.stat().st_size} bytes)")
