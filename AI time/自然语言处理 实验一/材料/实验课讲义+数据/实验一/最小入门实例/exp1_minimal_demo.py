"""实验一入门实例：NFKC 规范化与手机号掩码。"""
import re
import unicodedata

text = "患者无发热，联系电话１３８１２３４５６７８。"
normalized = unicodedata.normalize("NFKC", text)
masked = re.sub(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)", r"\1****\2", normalized)
print("规范化：", normalized)
print("掩码后：", masked)
assert masked == "患者无发热,联系电话138****5678。"
print("demo passed")
