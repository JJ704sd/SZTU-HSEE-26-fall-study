# -*- coding: utf-8 -*-
"""实验二主脚本：驱动习题一至八与选做扩展，输出 exp2_results.json 与对齐表 CSV。

所有分词、边界评价、标签转换、探针与 padding 对照均调用教师提供的
exp2_starter.py 中的函数，本脚本不改动其任何实现。
"""
import json
import os
import sys
from pathlib import Path

import jieba
import pandas as pd
import torch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from exp2_starter import (  # noqa: E402
    BiLSTMTagger,
    boundaries,
    bmes_to_tokens,
    corpus_prf,
    direction_context_probe,
    extract_keywords,
    load_jsonl,
    make_alignment_rows,
    make_practice_batch,
    masked_tag_loss,
    prf,
    student_example_id,
    tokens_to_bmes,
)

DATA = BASE / "data"
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

LAST_DIGIT = int(os.environ.get("LAB_STUDENT_LAST_DIGIT", "3"))
SEED = 20261016

RESULTS = {}


def counts(pred, gold):
    """返回 (TP, FP, FN)，用于逐句明细表。"""
    bp, gb = boundaries(pred), boundaries(gold)
    return len(bp & gb), len(bp - gb), len(gb - bp)


def record(name, payload):
    RESULTS[name] = payload
    print(f"[记录] {name}: {json.dumps(payload, ensure_ascii=False)[:200]}")


# ---------------------------------------------------------------- 习题一
def exercise1():
    """A：6 条句子语料级 micro 指标；B：P01—P10 逐句对照。"""
    gold_rows = load_jsonl(DATA / "gold_segmentation.jsonl")
    golds = [row["gold"] for row in gold_rows]

    baseline = jieba.Tokenizer()
    custom = jieba.Tokenizer()
    custom.load_userdict(str(DATA / "medical_terms.txt"))

    base_pred = [list(baseline.cut(r["text"], HMM=False)) for r in gold_rows]
    dict_pred = [list(custom.cut(r["text"], HMM=False)) for r in gold_rows]

    base_total = corpus_prf(base_pred, golds)
    dict_total = corpus_prf(dict_pred, golds)
    # 对照：误用“逐句 F1 算术平均”的数值
    base_avg = sum(prf(p, g)[2] for p, g in zip(base_pred, golds)) / len(golds)
    dict_avg = sum(prf(p, g)[2] for p, g in zip(dict_pred, golds)) / len(golds)

    sentences = []
    for row, bp, dp in zip(gold_rows, base_pred, dict_pred):
        bp_prf = prf(bp, row["gold"])
        dp_prf = prf(dp, row["gold"])
        sentences.append({
            "id": row["id"], "text": row["text"], "gold": row["gold"],
            "base_pred": bp, "base_prf": bp_prf,
            "base_counts": counts(bp, row["gold"]),
            "dict_pred": dp, "dict_prf": dp_prf,
            "dict_counts": counts(dp, row["gold"]),
        })

    # P01—P10 逐句
    practice = load_jsonl(DATA / "bilstm_practice.jsonl")
    p_rows = []
    for row in practice:
        bp = list(baseline.cut(row["text"], HMM=False))
        dp = list(custom.cut(row["text"], HMM=False))
        bp_prf = prf(bp, row["gold"])
        dp_prf = prf(dp, row["gold"])
        if dp_prf[2] > bp_prf[2] + 1e-9:
            change = "改善"
        elif dp_prf[2] < bp_prf[2] - 1e-9:
            change = "变差"
        else:
            change = "不变"
        p_rows.append({
            "id": row["id"], "text": row["text"], "gold": row["gold"],
            "focus": row.get("focus", ""),
            "base_pred": bp, "base_f1": bp_prf[2],
            "dict_pred": dp, "dict_f1": dp_prf[2], "change": change,
        })

    record("习题一_语料级汇总", {
        "baseline": base_total, "dict": dict_total,
        "baseline_macro_avg_f1": base_avg, "dict_macro_avg_f1": dict_avg,
        "gold_boundary_total": base_total["tp"] + base_total["fn"],
    })
    record("习题一_逐句", sentences)
    record("习题一_P01到P10", p_rows)
    return base_total, dict_total, base_avg, dict_avg, sentences, p_rows


# ---------------------------------------------------------------- 习题二
def exercise2():
    """按学号尾号生成 B/M/E/S 电子对齐表并回转验证。"""
    rows = load_jsonl(DATA / "bilstm_practice.jsonl")
    example_id = student_example_id(LAST_DIGIT)
    sample = next(row for row in rows if row["id"] == example_id)
    alignment = make_alignment_rows(sample["text"], sample["gold"])
    csv_path = OUT / f"{example_id.lower()}_alignment.csv"
    pd.DataFrame(alignment).to_csv(csv_path, index=False, encoding="utf-8-sig")
    recovered, repairs = bmes_to_tokens(
        sample["text"], [r["tag"] for r in alignment])
    record("习题二_对齐表", {
        "example_id": example_id, "text": sample["text"], "gold": sample["gold"],
        "alignment": alignment, "recovered": recovered, "repairs": repairs,
        "csv": csv_path.relative_to(BASE).as_posix(), "match": recovered == sample["gold"],
    })
    return example_id, sample, alignment, recovered, repairs


# ---------------------------------------------------------------- 习题三
def exercise3():
    """双向上下文探针：右文不同。"""
    result = direction_context_probe("研究生命起源", "研究生命科学", target_index=3)
    record("习题三_探针", result)
    return result


# ---------------------------------------------------------------- 习题四
def exercise4():
    """固定 P01/P06 追踪张量形状；再把 hidden_size 改成 32 复跑。"""
    rows = load_jsonl(DATA / "bilstm_practice.jsonl")
    input_ids, tag_ids, vocab, selected = make_practice_batch(rows)

    torch.manual_seed(SEED)
    model = BiLSTMTagger(len(vocab) + 2, embedding_dim=64, hidden_size=64)
    embedded = model.embedding(input_ids)
    sequence, _ = model.encoder(embedded)
    logits = model.classifier(sequence)

    shapes = {
        "input_ids": list(input_ids.shape),
        "tag_ids": list(tag_ids.shape),
        "embedded": list(embedded.shape),
        "sequence": list(sequence.shape),
        "logits": list(logits.shape),
        "valid_tags": int(tag_ids.ne(-100).sum()),
        "vocab_size": len(vocab) + 2,
        "samples": [{"id": r["id"], "text": r["text"], "len": len(r["text"]),
                     "gold": r["gold"]} for r in selected],
        "input_ids_tensor": input_ids.tolist(),
        "tag_ids_tensor": tag_ids.tolist(),
    }

    torch.manual_seed(SEED)
    model32 = BiLSTMTagger(len(vocab) + 2, embedding_dim=64, hidden_size=32)
    emb32 = model32.embedding(input_ids)
    seq32, _ = model32.encoder(emb32)
    log32 = model32.classifier(seq32)
    shapes["hidden32"] = {
        "sequence": list(seq32.shape), "logits": list(log32.shape),
        "params_64": sum(p.numel() for p in model.parameters()),
        "params_32": sum(p.numel() for p in model32.parameters()),
    }

    # 未训练模型直接 argmax 的观察
    with torch.no_grad():
        pred_ids = logits.argmax(dim=-1)
    id2tag = {0: "B", 1: "M", 2: "E", 3: "S"}
    untrained = {}
    for i, row in enumerate(selected):
        tags = [id2tag[int(t)] for t in pred_ids[i][:len(row["text"])]]
        toks, rep = bmes_to_tokens(row["text"], tags)
        p, r, f = prf(toks, row["gold"])
        untrained[row["id"]] = {
            "tags": tags, "tokens": toks, "repairs": rep, "prf": [p, r, f],
        }
    # logits 是否概率：四类分数之和
    sums = logits[0, :4].sum(dim=-1).tolist()
    probs = torch.softmax(logits[0, :4], dim=-1).sum(dim=-1).tolist()
    shapes["untrained_argmax"] = untrained
    shapes["logit_sum_check"] = {"raw_sums": sums, "softmax_sums": probs}

    record("习题四_形状", shapes)
    return shapes


# ---------------------------------------------------------------- 习题五
def exercise5():
    """正确与错误 padding 设置的 loss 与梯度对照。"""
    rows = load_jsonl(DATA / "bilstm_practice.jsonl")
    input_ids, tag_ids, vocab, selected = make_practice_batch(rows)
    torch.manual_seed(SEED)
    model = BiLSTMTagger(len(vocab) + 2, embedding_dim=64, hidden_size=64)
    with torch.no_grad():
        logits = model.classifier(model.encoder(model.embedding(input_ids))[0])

    # 复刻 exp2_starter.padding_contrast 的等价计算（同一 mask 逻辑）
    from exp2_starter import padding_contrast
    result = padding_contrast(logits, tag_ids)
    record("习题五_padding对照", result)
    return result


# ---------------------------------------------------------------- 习题六
def exercise6():
    """按学号末位选一篇文章，比较 TF-IDF 与 TextRank Top-5。"""
    # 末位 1/3/5 -> article_01；2/4/6/8 -> article_02；0/7/9 -> article_03
    digit = LAST_DIGIT
    if digit in (1, 3, 5):
        article = "article_01.txt"
    elif digit in (2, 4, 6, 8):
        article = "article_02.txt"
    else:
        article = "article_03.txt"
    text = (DATA / article).read_text(encoding="utf-8").strip()
    tfidf, textrank = extract_keywords(
        text, str(DATA / "stopwords.txt"), str(DATA / "medical_terms.txt"))
    # 完整排序，便于说明差异词的排名
    jieba.load_userdict(str(DATA / "medical_terms.txt"))
    jieba.analyse.set_stop_words(str(DATA / "stopwords.txt"))
    tfidf_all = jieba.analyse.extract_tags(text, topK=30, withWeight=True)
    textrank_all = jieba.analyse.textrank(
        text, topK=30, withWeight=True,
        allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn"))
    tokenizer = jieba.Tokenizer()
    tokenizer.load_userdict(str(DATA / "medical_terms.txt"))
    tokens = list(tokenizer.cut(text, HMM=False))
    record("习题六_关键词", {
        "article": article, "text": text, "tokens": tokens,
        "tfidf_top5": tfidf[:5], "textrank_top5": textrank[:5],
        "tfidf_all": tfidf_all, "textrank_all": textrank_all,
    })
    return article, text, tokens, tfidf, textrank


# ---------------------------------------------------------------- 习题七
def exercise7():
    """非法与合法 B/M/E/S 序列解码对照。"""
    illegal_tags = ["M", "E", "B", "E"]
    legal_tags = ["B", "E", "B", "E"]
    illegal = bmes_to_tokens("患者服药", illegal_tags)
    legal = bmes_to_tokens("患者服药", legal_tags)
    record("习题七_标签解码", {
        "illegal": {"tags": illegal_tags, "tokens": illegal[0], "repairs": illegal[1]},
        "legal": {"tags": legal_tags, "tokens": legal[0], "repairs": legal[1]},
    })
    return illegal, legal


# ---------------------------------------------------------------- 习题八
def exercise8():
    """加入冲突词前后的切分与 F1。"""
    text = "高血压患者需要规律监测血压"
    gold = ["高血压", "患者", "需要", "规律", "监测", "血压"]
    normal = jieba.Tokenizer()
    conflict = jieba.Tokenizer()
    conflict.add_word("高血压患者", freq=100000, tag="nz")
    pred_normal = list(normal.cut(text, HMM=False))
    pred_conflict = list(conflict.cut(text, HMM=False))
    record("习题八_冲突词", {
        "text": text, "gold": gold,
        "normal": {"pred": pred_normal, "prf": list(prf(pred_normal, gold))},
        "conflict": {"pred": pred_conflict, "prf": list(prf(pred_conflict, gold))},
    })
    return pred_normal, pred_conflict


# ---------------------------------------------------------------- 选做
def optional():
    """反向设计左上下文探针。"""
    r1 = direction_context_probe("研究生命起源", "探索生命起源", target_index=3)
    r2 = direction_context_probe("研究生命起源", "讨论生命起源", target_index=3)
    record("选做_左上下文探针", {"探索生命起源": r1, "讨论生命起源": r2})
    return r1, r2


def main():
    exercise1()
    exercise2()
    exercise3()
    exercise4()
    exercise5()
    exercise6()
    exercise7()
    exercise8()
    optional()
    path = OUT / "exp2_results.json"
    path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"结果已写入 {path}")


if __name__ == "__main__":
    main()
