"""实验二入门实例：词典分词与B/M/E/S转换。"""
import jieba

text = "动态心电图提示房性早搏"
tokenizer = jieba.Tokenizer()
baseline = list(tokenizer.cut(text, HMM=False))
tokenizer.add_word("动态心电图", freq=100, tag="nz")
tokenizer.add_word("房性早搏", freq=100, tag="nz")
custom = list(tokenizer.cut(text, HMM=False))
print("基线：", "/".join(baseline))
print("加词典：", "/".join(custom))
assert custom == ["动态心电图", "提示", "房性早搏"]

tags = []
for token in custom:
    if len(token) == 1:
        tags.append("S")
    elif len(token) == 2:
        tags.extend(["B", "E"])
    else:
        tags.extend(["B"] + ["M"] * (len(token) - 2) + ["E"])
assert len(tags) == len(text)
print("B/M/E/S：", " ".join(tags))
print("demo passed")
