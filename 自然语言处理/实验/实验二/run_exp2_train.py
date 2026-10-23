# -*- coding: utf-8 -*-
"""实验二小样本训练与双向/单向受控消融。

训练集 8 句（P01、P03、P04、P06、P07、P08、P09、P10），验证集 2 句（P02、P05）。
词表只由训练集建立（PAD=0、UNK=1）；每轮在验证集算边界 F1，只在创新高时保存快照。
固定 seed 后同机重复运行数值一致。
"""
import json
import sys
from pathlib import Path

import torch
from torch import nn

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from exp2_starter import (  # noqa: E402
    BiLSTMTagger,
    bmes_to_tokens,
    load_jsonl,
    make_alignment_rows,
    masked_tag_loss,
    tokens_to_bmes,
)

DATA = BASE / "data"
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

SEED = 20261016
TRAIN_IDS = ["P01", "P03", "P04", "P06", "P07", "P08", "P09", "P10"]
VALID_IDS = ["P02", "P05"]
EPOCHS = 120
TAG2ID = {"B": 0, "M": 1, "E": 2, "S": 3}
ID2TAG = {v: k for k, v in TAG2ID.items()}


def boundaries(tokens):
    """除句末外的字符边界集合。"""
    result, pos = set(), 0
    for token in tokens[:-1]:
        pos += len(token)
        result.add(pos)
    return result


def prf(pred, gold):
    pb, gb = boundaries(pred), boundaries(gold)
    tp = len(pb & gb)
    p = tp / len(pb) if pb else 0.0
    r = tp / len(gb) if gb else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def build(rows):
    """词表只由训练集建立，句子补齐到批内最大长度。"""
    train = [r for r in rows if r["id"] in TRAIN_IDS]
    valid = [r for r in rows if r["id"] in VALID_IDS]
    vocab = {ch: i + 2 for i, ch in enumerate(
        sorted({c for r in train for c in r["text"]}))}
    return train, valid, vocab


def encode(rows, vocab):
    """补齐到批内最大长度；训练集之外的字符一律映射到 UNK=1。"""
    max_len = max(len(r["text"]) for r in rows)
    ids, tags = [], []
    for row in rows:
        ids.append([vocab.get(c, 1) for c in row["text"]] + [0] * (max_len - len(row["text"])))
        tag = [TAG2ID[t] for t in tokens_to_bmes(row["gold"])]
        tags.append(tag + [-100] * (max_len - len(tag)))
    return torch.tensor(ids), torch.tensor(tags)


def predict(model, row, vocab):
    ids = torch.tensor([[vocab.get(c, 1) for c in row["text"]]])
    model.eval()
    with torch.no_grad():
        logits = model(ids)
    pred_tags = [ID2TAG[int(t)] for t in logits.argmax(dim=-1)[0, :len(row["text"])]]
    tokens, repairs = bmes_to_tokens(row["text"], pred_tags)
    return tokens, repairs


def run(bidirectional, epochs=EPOCHS):
    torch.manual_seed(SEED)
    rows = load_jsonl(DATA / "bilstm_practice.jsonl")
    train, valid, vocab = build(rows)
    x, y = encode(train, vocab)
    vx, vy = encode(valid, vocab)

    model = BiLSTMTagger(len(vocab) + 2, embedding_dim=64, hidden_size=64,
                         bidirectional=bidirectional)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3)
    best_f1, best_epoch, best_state = -1.0, 0, None
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        logits = model(x)
        loss = masked_tag_loss(logits, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        # 训练集边界 F1
        model.eval()
        with torch.no_grad():
            pred_ids = model(x).argmax(dim=-1)
        train_f1 = 0.0
        for i, row in enumerate(train):
            tags = [ID2TAG[int(t)] for t in pred_ids[i][:len(row["text"])]]
            toks, _ = bmes_to_tokens(row["text"], tags)
            train_f1 = train_f1 + prf(toks, row["gold"])[2]
        train_f1 /= len(train)

        # 验证集边界 F1（语料级 micro：先汇总 TP/FP/FN 再算一次，与 2.2 节口径一致）
        with torch.no_grad():
            v_pred = model(vx).argmax(dim=-1)
        tp = fp = fn = 0
        for i, row in enumerate(valid):
            tags = [ID2TAG[int(t)] for t in v_pred[i][:len(row["text"])]]
            toks, _ = bmes_to_tokens(row["text"], tags)
            pb, gb = boundaries(toks), boundaries(row["gold"])
            tp += len(pb & gb)
            fp += len(pb - gb)
            fn += len(gb - pb)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        val_f1 = 2 * p * r / (p + r) if p + r else 0.0

        history.append({"epoch": epoch, "train_loss": float(loss.detach()),
                        "train_f1": train_f1, "val_f1": val_f1})
        if val_f1 > best_f1:
            best_f1, best_epoch = val_f1, epoch
            best_state = {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    sample_outputs = {}
    for row in valid:
        toks, rep = predict(model, row, vocab)
        sample_outputs[row["id"]] = {"tokens": toks, "repairs": rep,
                                     "prf": list(prf(toks, row["gold"]))}
    return {
        "bidirectional": bidirectional,
        "params": sum(p.numel() for p in model.parameters()),
        "best_epoch": best_epoch, "best_val_f1": best_f1,
        "history": history, "valid_outputs": sample_outputs,
        "vocab_size": len(vocab) + 2,
    }


def main():
    bi = run(True)
    uni = run(False)
    payload = {"seed": SEED, "epochs": EPOCHS,
               "train_ids": TRAIN_IDS, "valid_ids": VALID_IDS,
               "bidirectional": bi, "unidirectional": uni}
    path = OUT / "exp2_train.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    for name, res in (("双向", bi), ("单向", uni)):
        print(f"{name}: 参数量 {res['params']} 最佳 epoch {res['best_epoch']} "
              f"最佳 val F1 {res['best_val_f1']:.4f}")
        print("   ", res["valid_outputs"])
    print(f"结果已写入 {path}")


if __name__ == "__main__":
    main()
