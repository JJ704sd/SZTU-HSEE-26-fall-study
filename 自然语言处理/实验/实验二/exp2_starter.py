#!/usr/bin/env python3
"""实验二学生起始代码：jieba 基线、关键词与 BiLSTM 序列标注。"""
import json
from pathlib import Path
import jieba
import jieba.analyse
import torch
from torch import nn

TAG2ID = {"B": 0, "M": 1, "E": 2, "S": 3}


def load_jsonl(path):
    """读取课堂练习数据。"""
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def boundaries(tokens):
    """返回除句末外的字符边界集合。"""
    result, pos = set(), 0
    for token in tokens[:-1]:
        pos += len(token)
        result.add(pos)
    return result


def prf(pred, gold):
    """根据字符边界计算Precision、Recall和F1。"""
    pred_boundaries, gold_boundaries = boundaries(pred), boundaries(gold)
    true_positive = len(pred_boundaries & gold_boundaries)
    precision = true_positive / len(pred_boundaries) if pred_boundaries else 0.0
    recall = true_positive / len(gold_boundaries) if gold_boundaries else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return precision, recall, f1


def corpus_prf(predictions, golds):
    """先汇总全部句子的TP/FP/FN，再计算语料级（micro）P/R/F1。"""
    if len(predictions) != len(golds) or not golds:
        raise ValueError("predictions与golds必须非空且句子数相同")
    true_positive = false_positive = false_negative = 0
    for pred, gold in zip(predictions, golds):
        pred_boundaries, gold_boundaries = boundaries(pred), boundaries(gold)
        true_positive += len(pred_boundaries & gold_boundaries)
        false_positive += len(pred_boundaries - gold_boundaries)
        false_negative += len(gold_boundaries - pred_boundaries)
    precision = (true_positive / (true_positive + false_positive)
                 if true_positive + false_positive else 0.0)
    recall = (true_positive / (true_positive + false_negative)
              if true_positive + false_negative else 0.0)
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def student_example_id(last_digit):
    """学号尾号1—9对应P01—P09，尾号0对应P10。"""
    digit = int(last_digit)
    if digit < 0 or digit > 9:
        raise ValueError("学号尾号必须是0—9")
    return "P10" if digit == 0 else f"P{digit:02d}"


def compare_sentence(text, gold, user_dict):
    baseline = jieba.Tokenizer()
    custom = jieba.Tokenizer(); custom.load_userdict(str(user_dict))
    pred_base = list(baseline.cut(text, HMM=False))
    pred_custom = list(custom.cut(text, HMM=False))
    print("baseline:", "/".join(pred_base), prf(pred_base, gold))
    print("custom_dict:", "/".join(pred_custom), prf(pred_custom, gold))
    return pred_base, pred_custom


def extract_keywords(text, stopwords, user_dict=None):
    if user_dict is not None:
        jieba.load_userdict(str(user_dict))
    jieba.analyse.set_stop_words(str(stopwords))
    tfidf = jieba.analyse.extract_tags(text, topK=8, withWeight=True)
    textrank = jieba.analyse.textrank(text, topK=8, withWeight=True,
                                     allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn"))
    return tfidf, textrank


class BiLSTMTagger(nn.Module):
    """字符级 B/M/E/S 序列标注模型。输入 [B,L]，输出 [B,L,4]。"""
    def __init__(self, vocab_size, embedding_dim=64, hidden_size=64,
                 num_tags=4, bidirectional=True):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.encoder = nn.LSTM(
            embedding_dim, hidden_size, batch_first=True,
            bidirectional=bidirectional
        )
        directions = 2 if bidirectional else 1
        self.classifier = nn.Linear(hidden_size * directions, num_tags)

    def forward(self, x):
        embedded = self.embedding(x)
        sequence, _ = self.encoder(embedded)
        return self.classifier(sequence)


def tokens_to_bmes(tokens):
    """将分词结果转为与字符等长的 B/M/E/S 标签序列。"""
    tags = []
    for token in tokens:
        if len(token) == 1:
            tags.append("S")
        elif len(token) == 2:
            tags.extend(["B", "E"])
        else:
            tags.extend(["B", *(["M"] * (len(token) - 2)), "E"])
    return tags


def make_alignment_rows(text, tokens):
    """生成可直接导出到电子实验报告的字符—标签—边界表。"""
    if "".join(tokens) != text:
        raise ValueError("tokens拼接后必须与text完全一致")
    tags = tokens_to_bmes(tokens)
    word_ends, pos = set(), 0
    for token in tokens:
        pos += len(token)
        word_ends.add(pos - 1)
    return [
        {"index": index, "char": char, "tag": tag,
         "word_end": "是" if index in word_ends else "否"}
        for index, (char, tag) in enumerate(zip(text, tags))
    ]


def bmes_to_tokens(text, tags):
    """将等长的B/M/E/S序列恢复为token列表。"""
    if len(text) != len(tags):
        raise ValueError("text与tags必须等长")
    tokens, current, repairs = [], "", 0
    for char, tag in zip(text, tags):
        if tag == "S":
            if current:
                tokens.append(current); current = ""; repairs += 1
            tokens.append(char)
        elif tag == "B":
            if current:
                tokens.append(current); repairs += 1
            current = char
        elif tag == "M":
            if not current:
                repairs += 1
            current += char
        elif tag == "E":
            if not current:
                repairs += 1
            tokens.append(current + char); current = ""
        else:
            raise ValueError(f"未知标签: {tag}")
    if current:
        tokens.append(current); repairs += 1
    return tokens, repairs


def masked_tag_loss(logits, tags, pad_tag=-100):
    """对 padding 位置使用 ignore_index，不让补齐字符进入损失。"""
    return nn.functional.cross_entropy(
        logits.reshape(-1, logits.size(-1)),
        tags.reshape(-1),
        ignore_index=pad_tag,
    )


def make_practice_batch(rows, example_ids=("P01", "P06")):
    """把固定的P01/P06编码并补齐；也允许教师显式传入其他编号。"""
    selected = [next(row for row in rows if row["id"] == item_id)
                for item_id in example_ids]
    vocab = {char: index + 2 for index, char in enumerate(
        sorted({char for row in rows for char in row["text"]}))}
    max_len = max(len(row["text"]) for row in selected)
    input_rows, tag_rows = [], []
    for row in selected:
        ids = [vocab[char] for char in row["text"]]
        tag_ids = [TAG2ID[tag] for tag in tokens_to_bmes(row["gold"])]
        input_rows.append(ids + [0] * (max_len - len(ids)))
        tag_rows.append(tag_ids + [-100] * (max_len - len(tag_ids)))
    return torch.tensor(input_rows), torch.tensor(tag_rows), vocab, selected


def direction_context_probe(text_a="研究生命起源", text_b="研究生命科学",
                            target_index=3, embedding_dim=16, hidden_size=8):
    """比较目标字相同的两个序列在正向/反向表示上的差异。"""
    if len(text_a) != len(text_b):
        raise ValueError("两条探针文本必须等长")
    if text_a[target_index] != text_b[target_index]:
        raise ValueError("两条文本在target_index处必须是同一个字")
    vocab = {char: index + 2 for index, char in enumerate(sorted(set(text_a + text_b)))}
    input_ids = torch.tensor([[vocab[c] for c in text_a],
                              [vocab[c] for c in text_b]])
    torch.manual_seed(20261020)
    model = BiLSTMTagger(len(vocab) + 2, embedding_dim, hidden_size)
    model.eval()
    with torch.no_grad():
        embedded = model.embedding(input_ids)
        sequence, _ = model.encoder(embedded)
    forward = sequence[:, target_index, :hidden_size]
    backward = sequence[:, target_index, hidden_size:]
    return {
        "texts": [text_a, text_b],
        "target_index": target_index,
        "target_char": text_a[target_index],
        "forward_shape": list(forward.shape),
        "backward_shape": list(backward.shape),
        "forward_max_abs_diff": float((forward[0] - forward[1]).abs().max()),
        "backward_max_abs_diff": float((backward[0] - backward[1]).abs().max()),
    }


def inspect_batch(model, input_ids, tag_ids):
    """打印实例批次的形状与有效标签数，用于习题核验。"""
    embedded = model.embedding(input_ids)
    sequence, _ = model.encoder(embedded)
    logits = model.classifier(sequence)
    print("input_ids:", tuple(input_ids.shape))
    print("embedded:", tuple(embedded.shape))
    print("sequence:", tuple(sequence.shape))
    print("logits:", tuple(logits.shape))
    print("valid_tags:", int(tag_ids.ne(-100).sum()))
    return logits


def padding_contrast(logits, tag_ids, s_tag_id=TAG2ID["S"]):
    """比较正确mask与把PAD误标为S时的loss及PAD梯度。"""
    pad_mask = tag_ids.eq(-100)
    correct_logits = logits.detach().clone().requires_grad_(True)
    correct_loss = masked_tag_loss(correct_logits, tag_ids)
    correct_loss.backward()

    wrong_tags = tag_ids.masked_fill(pad_mask, s_tag_id)
    wrong_logits = logits.detach().clone().requires_grad_(True)
    wrong_loss = masked_tag_loss(wrong_logits, wrong_tags)
    wrong_loss.backward()
    correct_pad_grad = correct_logits.grad[pad_mask]
    wrong_pad_grad = wrong_logits.grad[pad_mask]
    return {
        "valid_tags": int(tag_ids.ne(-100).sum()),
        "padding_positions": int(pad_mask.sum()),
        "correct_loss": float(correct_loss.detach()),
        "wrong_loss": float(wrong_loss.detach()),
        "correct_pad_gradient_values": correct_pad_grad.detach().tolist(),
        "wrong_pad_gradient_values": wrong_pad_grad.detach().tolist(),
        "correct_pad_gradient_l1": float(correct_pad_grad.abs().sum()),
        "wrong_pad_gradient_l1": float(wrong_pad_grad.abs().sum()),
    }
