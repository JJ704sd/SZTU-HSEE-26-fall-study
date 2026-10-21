"""UTF-8-safe extraction of the lab tar archive (Windows bsdtar mangles CJK names)."""
import sys
import tarfile
from pathlib import Path

SRC = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path("实验课讲义+数据.tar").resolve()
DST = Path(__file__).resolve().parents[1] / "材料"

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
