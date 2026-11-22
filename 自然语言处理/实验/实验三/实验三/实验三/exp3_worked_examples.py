#!/usr/bin/env python3
"""实验三CPU入口：TF-IDF/SVM与小型中文BERT微调，在同一完整测试集评价。"""
from __future__ import annotations
import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from exp3_starter import BASE,HERE,LABELS,SEED,write_json,sha256,load_splits,evaluate_predictions


def resolve_torch_device(requested='cpu'):
    import torch
    if requested != 'cpu':
        raise ValueError('本实验固定CPU运行')
    return torch.device('cpu')

def group_for_digit(last_digit):
    if last_digit not in range(10):
        raise ValueError("学号尾号必须为0—9")
    return (
        "A"
        if last_digit in (0, 1, 2, 3)
        else "B" if last_digit in (4, 5, 6) else "C"
    )

def bert_forward(model, inputs, labels=None):
    """展开BertForSequenceClassification的主要计算步骤。"""
    import torch.nn.functional as F

    encoded = model.bert(**inputs, return_dict=True)
    hidden = encoded.last_hidden_state  # [B, L, H]：每个token的上下文表示
    pooled = encoded.pooler_output  # [B, H]：CLS经线性层与tanh后的表示
    logits = model.classifier(model.dropout(pooled))  # [B, 11]
    loss = None if labels is None else F.cross_entropy(logits, labels)
    return hidden, pooled, logits, loss

def fit_bert(
    train,
    valid,
    model_path,
    device_name,
    epochs,
    batch_size,
    inspection_frame=None,
    learning_rate=3e-4,
):
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoTokenizer, BertForSequenceClassification

    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = BertForSequenceClassification.from_pretrained(
        model_path,
        num_labels=len(LABELS),
        local_files_only=True,
        label2id={label: i for i, label in enumerate(LABELS)},
        id2label={i: label for i, label in enumerate(LABELS)},
    )
    device = resolve_torch_device(device_name)
    model.to(device)
    initial_traces = []
    if inspection_frame is not None:
        _, initial_traces = predict_bert(
            model, tokenizer, inspection_frame, device, batch_size=2
        )
    encodings = tokenizer(
        train["query"].tolist(),
        padding="max_length",
        truncation=True,
        max_length=64,
        return_tensors="pt",
    )
    targets = torch.tensor([LABELS.index(x) for x in train["label"]])
    items = [
        {**{k: v[i] for k, v in encodings.items()}, "labels": targets[i]}
        for i in range(len(train))
    ]
    train_loader = DataLoader(
        items,
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(SEED),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    history, best_state, best_score, best_epoch = [], None, -1.0, 0
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        total_examples = 0
        total_loss = 0.0
        # BEGIN BERT_TRAIN
        for batch in train_loader:
            labels = batch["labels"].to(device)  # [B]，真实类别编号
            inputs = {
                k: v.to(device) for k, v in batch.items() if k != "labels"
            }
            optimizer.zero_grad()  # 清除上一批次的梯度
            hidden, pooled, logits, loss = bert_forward(model, inputs, labels)
            loss.backward()  # 计算编码器与分类头的梯度
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()  # 更新模型参数
            losses.append(float(loss.detach().cpu()))
            total_loss += float(loss.detach().cpu()) * labels.shape[0]
            total_examples += labels.shape[0]
        # END BERT_TRAIN
        valid_predictions, _ = predict_bert(
            model, tokenizer, valid, device, batch_size
        )
        score = evaluate_predictions(valid["label"], valid_predictions)[
            "macro_f1"
        ]
        history.append(
            {
                "epoch": epoch,
                "train_loss": total_loss / total_examples,
                "valid_macro_f1": score,
            }
        )
        print(history[-1])
        # BEGIN BERT_SELECT
        if score > best_score:
            best_score, best_epoch = score, epoch
            best_state = {
                k: v.detach().cpu().clone()
                for k, v in model.state_dict().items()
            }
    model.load_state_dict(best_state)  # 完成验证集选择后，恢复最佳参数
    # END BERT_SELECT
    return model, tokenizer, device, history, best_epoch, initial_traces

def predict_bert(model, tokenizer, frame, device, batch_size=4):
    import torch

    model.eval()
    predictions, traces = [], []
    with torch.no_grad():
        for offset in range(0, len(frame), batch_size):
            part = frame.iloc[offset : offset + batch_size]
            inputs = tokenizer(
                part["query"].tolist(),
                padding=True,
                truncation=True,
                max_length=64,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            hidden, pooled, logits, _ = bert_forward(model, inputs)
            indices = logits.argmax(dim=-1).cpu().tolist()
            predictions.extend(LABELS[i] for i in indices)
            for i, row in enumerate(part.itertuples(index=False)):
                traces.append(
                    {
                        "sample_id": row.sample_id,
                        "query": row.query,
                        "token_count_before_truncation": len(tokenizer(row.query,truncation=False)["input_ids"]),
                        "truncated": len(tokenizer(row.query,truncation=False)["input_ids"])>64,
                        "tokens": tokenizer.convert_ids_to_tokens(
                            inputs["input_ids"][i].tolist()
                        ),
                        "input_ids": inputs["input_ids"][i].tolist(),
                        "attention_mask": inputs["attention_mask"][i].tolist(),
                        "batch_input_shape": list(inputs["input_ids"].shape),
                        "hidden_shape": list(hidden.shape),
                        "pooled_shape": list(pooled.shape),
                        "logits": logits[i].cpu().tolist(),
                        "prediction": LABELS[indices[i]],
                    }
                )
    return predictions, traces

def summarize_pair_trace(pair):
    """压缩习题四记录：两行预测/长度摘要、批量形状和四个关键位置。"""
    before = pair["before_finetuning"]
    after = pair["after_finetuning"]
    if len(before) != 2 or len(after) != 2:
        raise ValueError("习题四需要同一组前两条记录")
    samples = []
    for initial, final in zip(before, after):
        if initial["sample_id"] != final["sample_id"]:
            raise ValueError("微调前后样本顺序不一致")
        mask = final["attention_mask"]
        samples.append({
            "sample_id": final["sample_id"],
            "tokens_before_truncation": final["token_count_before_truncation"],
            "valid_tokens": sum(mask),
            "pad_tokens": len(mask) - sum(mask),
            "truncated": final["truncated"],
            "prediction_before": initial["prediction"],
            "prediction_after": final["prediction"],
        })
    first = after[0]
    shapes = {
        "input_ids / attention_mask": first["batch_input_shape"],
        "hidden": first["hidden_shape"],
        "pooled": first["pooled_shape"],
        "logits": [len(after), len(first["logits"])],
    }
    # Select one padded sentence; keep CLS, first text token, SEP and first PAD.
    example = next((row for row in after if 0 in row["attention_mask"]), first)
    valid = sum(example["attention_mask"])
    positions = [0, 1, valid - 1]
    if valid < len(example["attention_mask"]):
        positions.append(valid)
    key_tokens = [{
        "sample_id": example["sample_id"], "position": i,
        "token": example["tokens"][i], "token_id": example["input_ids"][i],
        "mask": example["attention_mask"][i],
    } for i in dict.fromkeys(positions)]
    return {"samples": samples, "shapes": shapes, "key_tokens": key_tokens}


def padding_mask_probe(model, tokenizer, text="失眠应该挂什么科", padded_length=16):
    """固定问句的PAD键掩码对照；不更新模型，不计入正式测试指标。"""
    import torch
    model.eval()
    plain = tokenizer(text, return_tensors="pt")
    if plain["input_ids"].shape[1] >= padded_length:
        raise ValueError("padded_length应大于原序列长度")
    padded = tokenizer(text, padding="max_length", truncation=True,
                       max_length=padded_length, return_tensors="pt")
    wrong = {k: v.clone() for k, v in padded.items()}
    wrong["attention_mask"] = torch.ones_like(wrong["attention_mask"])
    with torch.no_grad():
        reference = bert_forward(model, plain)[2]
        correct = bert_forward(model, padded)[2]
        unmasked = bert_forward(model, wrong)[2]
    rows = []
    for setting, encoded, logits in [
        ("unpadded", plain, reference),
        ("correct_padding_mask", padded, correct),
        ("all_ones_mask", wrong, unmasked),
    ]:
        rows.append({
            "setting": setting,
            "input_shape": list(encoded["input_ids"].shape),
            "input_ids": encoded["input_ids"][0].tolist(),
            "attention_mask": encoded["attention_mask"][0].tolist(),
            "valid_positions": int(encoded["attention_mask"].sum()),
            "logits": logits[0].tolist(),
            "max_abs_logit_diff": float((logits-reference).abs().max()),
            "prediction": LABELS[int(logits.argmax(-1).item())],
        })
    return {"query": text, "padded_length": padded_length,
            "scope": "固定控制例题；不加入391条正式评价", "records": rows}

def main():
    import importlib.metadata
    import platform
    import torch
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--last-digit',type=int,choices=range(10),required=True,
                   help='学号最后一位数字，取0—9；用于确定A/B/C过程分析组')
    p.add_argument('--bert-model',type=Path,default=BASE/'models/chinese_bert_tiny')
    p.add_argument('--device',choices=['cpu'],default='cpu')
    p.add_argument('--threads',type=int,default=2)
    p.add_argument('--epochs',type=int,default=3)
    p.add_argument('--batch-size',type=int,default=16)
    p.add_argument('--learning-rate',type=float,default=3e-4)
    p.add_argument('--baseline-only',action='store_true',help='调试用；不算完整实验')
    p.add_argument('--output',type=Path,default=BASE/'outputs_formal')
    args=p.parse_args()
    if args.epochs<1 or args.batch_size<1 or args.threads<1 or args.learning_rate<=0:
        p.error('训练参数必须大于0')
    if args.bert_model.resolve() in [args.output.resolve(),*args.output.resolve().parents]:
        p.error('输出不得覆盖模型目录')
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED)
    if not args.baseline_only and not (args.bert_model/'config.json').exists():
        p.error('本地模型缺失；请完整解压包含models/chinese_bert_tiny的学生资源包，或用--bert-model指定已提供的模型目录。')
    if args.output.exists() and any(args.output.iterdir()):p.error('输出目录非空；请用新的--output目录')
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    parts,manifest=load_splits(BASE/'data/prepared')
    train,valid,test=[parts[k] for k in ['train','valid','test']]
    group=group_for_digit(args.last_digit)
    tasks=pd.read_csv(BASE/'data/prepared/group_tasks.csv',encoding='utf-8-sig')
    assigned=tasks[tasks.group==group]
    analysis=test.set_index('sample_id').loc[assigned.sample_id].reset_index()
    table=test.copy();summary=[];search=[];subgroups=[]
    threshold=int(train['query'].str.len().median())
    def export(name,predictions):
        result=evaluate_predictions(test.label,predictions)
        table[name]=predictions
        write_json(out/f'{name}_metrics.json',result)
        pd.DataFrame(result['confusion_matrix'],index=LABELS,columns=LABELS).to_csv(
            out/f'{name}_confusion.csv',encoding='utf-8-sig')
        pd.DataFrame({k:result['classification_report'][k] for k in LABELS}).T.to_csv(
            out/f'{name}_per_class.csv',encoding='utf-8-sig')
        wrong=test.assign(prediction=predictions)
        wrong[wrong.label!=wrong.prediction].to_csv(out/f'{name}_errors.csv',index=False,encoding='utf-8-sig')
        summary.append({'method':name,'n_test':len(test),
            **{k:result[k] for k in ['accuracy','macro_f1','weighted_f1']}})
        for name_group,mask in [('short',test['query'].str.len()<=threshold),('long',test['query'].str.len()>threshold)]:
            cut=table.loc[mask]
            subgroups.append({'method':name,'group':name_group,'threshold_from_train':threshold,
                'support':len(cut),'accuracy':float((cut.label==cut[name]).mean()) if len(cut) else None,
                'note':'文本长度切片；非人口属性公平性证明'})
        return result
    best,best_score,best_c=None,-1.0,None
    tf_start=time.perf_counter()
    for c in [0.5,2.0]:
        baseline=Pipeline([('tfidf',TfidfVectorizer(analyzer='char',ngram_range=(2,4))),
                           ('classifier',LinearSVC(C=c,random_state=SEED,max_iter=5000))])
        baseline.fit(train['query'],train['label'])
        score=evaluate_predictions(valid.label,baseline.predict(valid['query']))['macro_f1']
        search.append({'C':c,'valid_macro_f1':score})
        if score>best_score:best,best_score,best_c=baseline,score,c
    export('tfidf',best.predict(test['query']).tolist())
    tf_seconds=time.perf_counter()-tf_start
    vectorizer=best['tfidf'];clf=best['classifier'];xx=vectorizer.transform(analysis['query'])
    write_json(out/'tfidf_trace.json',{'sample_ids':analysis.sample_id.tolist(),'shape':list(xx.shape),
        'nonzero_features':xx.getnnz(axis=1).tolist(),'classes':clf.classes_.tolist(),
        'scores':clf.decision_function(xx).tolist()})
    write_json(out/'validation_search.json',search)
    config_info={'status':'SKIPPED','reason':'仅调试基线，不构成完整实验'}
    if not args.baseline_only:
        b_start=time.perf_counter()
        model,tokenizer,device,history,best_epoch,before=fit_bert(
            train,valid,args.bert_model,'cpu',args.epochs,args.batch_size,
            inspection_frame=analysis.head(2),learning_rate=args.learning_rate)
        write_json(out/'padding_mask_probe.json',padding_mask_probe(model,tokenizer))
        predictions,traces=predict_bert(model,tokenizer,test,device,args.batch_size)
        export('bert',predictions)
        _,after=predict_bert(model,tokenizer,analysis.head(2),device,batch_size=2)
        pair={'before_finetuning':before,'after_finetuning':after}
        write_json(out/'bert_pair_trace.json',pair)
        write_json(out/'bert_pair_summary.json',summarize_pair_trace(pair))
        write_json(out/'bert_trace.json',traces)
        config_info={'status':'COMPLETED','epochs':args.epochs,'batch_size':args.batch_size,
            'learning_rate':args.learning_rate,'max_length':64,'best_epoch':best_epoch,'history':history,
            'config':model.config.to_dict(),'elapsed_seconds':time.perf_counter()-b_start,
            'parameter_count':sum(x.numel() for x in model.parameters()),
            'model_path':str(args.bert_model.resolve()),
            'model_files':{p.name:sha256(p) for p in sorted(args.bert_model.iterdir()) if p.is_file()}}
        model.save_pretrained(out/'bert_checkpoint',safe_serialization=True)
        tokenizer.save_pretrained(out/'bert_checkpoint')
    table.to_csv(out/'predictions.csv',index=False,encoding='utf-8-sig')
    table[table.sample_id.isin(analysis.sample_id)].to_csv(out/'personal_analysis.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(summary).to_csv(out/'metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(subgroups).to_csv(out/'subgroup_metrics.csv',index=False,encoding='utf-8-sig')
    run={'seed':SEED,'group':group,'last_digit':args.last_digit,'device':'cpu','threads':args.threads,
        'python':platform.python_version(),'platform':platform.platform(),
        'versions':{x:importlib.metadata.version(x) for x in ['torch','transformers','numpy','pandas','scikit-learn']},
        'data':manifest,'analysis_ids':analysis.sample_id.tolist(),'label_order':LABELS,
        'tfidf':{'C':best_c,'valid_macro_f1':best_score,'feature_count':len(vectorizer.vocabulary_),
                 'elapsed_seconds':tf_seconds},'bert':config_info,
        'code_hashes':{p.name:sha256(p) for p in [Path(__file__),BASE/'exp3_starter.py']},
        'elapsed_seconds':time.perf_counter()-started,
        'files':{str(p.relative_to(out)):sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write_json(out/'run.json',run)
    print(pd.DataFrame(summary).to_string(index=False))
    print('分类评价：完整测试集',len(test),'条；过程分析组',group,'：',len(analysis),'条')
    print('输出：',out.resolve())

if __name__=='__main__':main()
