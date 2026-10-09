"""Verify environment + exact character facts the report will claim."""
import sys, importlib.util, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

print("--- python ---")
print("version:", sys.version)
print("executable:", sys.executable)
print("cwd:", Path.cwd())

print("\n--- jieba installed? ---")
print("jieba:", importlib.util.find_spec("jieba") is not None)

DATA = Path(r"D:\深技大课程学习\AI time\实验一\材料\实验课讲义+数据\实验一\实验一\data")

print("\n--- exact codepoints that matter (group C) ---")
c = DATA.joinpath("input_C_gb18030.txt").read_bytes().decode("gb18030")
line3 = c.splitlines()[2]
print("line3 repr:", repr(line3))
for i, ch in enumerate(line3):
    if not ("\u4e00" <= ch <= "\u9fff"):
        print(f"  pos {i}: {ch!r} U+{ord(ch):04X} {unicodedata.name(ch,'?')}")

print("\n--- NFKC effect on those ---")
n = unicodedata.normalize("NFKC", c)
print("NFKC line3 repr:", repr(n.splitlines()[2]))
print("'2026-10-15 09:30' in NFKC:", "2026-10-15 09:30" in n)
print("'３０' in NFKC:", "３０" in n)

print("\n--- group A: is there '5 mg/片 ' (trailing space)? ---")
a = DATA.joinpath("input_A_utf8.txt").read_bytes().decode("utf-8")
print("A repr lines:")
for L in a.splitlines():
    print("   ", repr(L))
print("contains '5 mg/片':", "5 mg/片" in a)
print("contains '5 mg/片 ':", "5 mg/片 " in a)
print("contains '128/78 mmHg':", "128/78 mmHg" in a)
print("contains '\\n\\n':", "\n\n" in a)

print("\n--- group B: phone/email ---")
b = DATA.joinpath("input_B_utf8sig.txt").read_bytes().decode("utf-8-sig")
print("B repr line3:", repr(b.splitlines()[2]))
print("contains '6.2 mmol/L':", "6.2 mmol/L" in b)

print("\n--- NFKC punctuation facts (used by minimal demo) ---")
s = "患者无发热，联系电话１３８１２３４５６７８。"
print("before:", repr(s))
print("after :", repr(unicodedata.normalize("NFKC", s)))
print("does NFKC map U+3002 。?", unicodedata.normalize("NFKC", "。"))
