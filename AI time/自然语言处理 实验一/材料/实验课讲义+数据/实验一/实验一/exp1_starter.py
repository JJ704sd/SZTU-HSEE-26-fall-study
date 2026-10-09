#!/usr/bin/env python3
"""实验一学生模板。运行示例：python exp1_starter.py data/input_C_gb18030.txt"""
import csv, hashlib, json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

PROTECTED = {"无", "未", "不伴", "不得", "否认"}

def read_text_checked(path):
    failed=[]
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "utf-16"):
        try:
            return Path(path).read_text(encoding=encoding).lstrip("\ufeff"), encoding, failed
        except UnicodeError as error:
            failed.append({"encoding": encoding, "error": type(error).__name__})
    raise UnicodeError(f"不能识别编码：{path}")

def normalize_text(text):
    # TODO 1：NFKC、换行、空白规范化。
    raise NotImplementedError

def mask_privacy(text):
    # TODO 2：手机号和邮箱掩码，返回掩码文本及命中数。
    raise NotImplementedError

def tokenize(text):
    pattern=r"患者|建议|进行|不伴|否认|不得|无|未|[A-Za-z]+|\d+(?:\.\d+)?|[\u4e00-\u9fff]"
    return re.findall(pattern,text)

def main():
    path=Path(sys.argv[1])
    raw,encoding,failed=read_text_checked(path)
    normalized=normalize_text(raw)
    masked,privacy=mask_privacy(normalized)
    tokens=tokenize(masked)
    frequency=Counter(tokens)
    # TODO 3：读取停用词，但不得删除PROTECTED中的词。
    # TODO 4：依次运行A—D；共写不少于6条断言，且每组至少有1条专门断言。
    # TODO 5：生成clean_text.txt、stage_stats.json、token_frequency.csv。
    print("识别编码：",encoding)
    print("失败候选：",failed)
    print("隐私命中：",privacy)
    print("Top-10：",frequency.most_common(10))

if __name__=="__main__": main()
