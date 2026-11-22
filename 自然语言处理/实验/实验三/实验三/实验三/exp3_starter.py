#!/usr/bin/env python3
"""实验三：数据清洗、统一划分、模型评价及CPU环境自检。"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score,classification_report,confusion_matrix,f1_score
from sklearn.model_selection import train_test_split
BASE = Path(__file__).resolve().parent
HERE = BASE
SEED = 20261104
LABELS = ['病情诊断','病因分析','治疗方案','就医建议','指标解读','疾病表述',
          '后果表述','注意事项','功效作用','医疗费用','其他']

def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def clean_text(text):
    """保留否定词、数字与单位；不删除全部标点；返回脱敏后文本和命中数。"""
    text = unicodedata.normalize('NFKC', str(text)).replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text).strip()
    hits = {}
    patterns = [
        ('身份证', r'(?<!\d)\d{17}[\dXx](?!\d)', '[ID]'),
        ('邮箱', r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]'),
        ('手机', r'(?<!\d)1[3-9]\d{9}(?!\d)', '[PHONE]'),
    ]
    for name, pattern, replacement in patterns:
        text, hits[name] = re.subn(pattern, replacement, text)
    return text, hits

def prepare_data(raw_path, out_dir):
    """严格UTF-8-SIG解码；空值剔除、同文同标去重、冲突标签整组隔离。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = json.loads(Path(raw_path).read_text(encoding='utf-8-sig'))
    if not isinstance(records, list):
        raise ValueError('原始JSON必须是数组')
    rows, audit_rows, seen_ids = [], [], set()
    for row in records:
        if not isinstance(row,dict):
            raise ValueError('每条记录必须是对象')
        if not {'id', 'query', 'label'} <= row.keys():
            raise ValueError('每条数据必须包含id/query/label')
        if not isinstance(row['id'],str) or not isinstance(row['query'],(str,type(None))):
            raise ValueError('id必须是字符串，query必须是字符串或空值')
        sid = row['id'].strip()
        if not sid or sid in seen_ids:
            raise ValueError('源ID为空或重复')
        seen_ids.add(sid)
        label = '' if row['label'] is None else str(row['label']).strip()
        if label and label not in LABELS:
            raise ValueError('发现未知标签，请检查原始数据版本')
        text, hits = clean_text('' if row['query'] is None else row['query'])
        status = 'candidate' if text and label else 'empty_text_or_label'
        rows.append({'sample_id': sid, 'query': text, 'label': label})
        # 不把原始敏感内容写入清洗日志。
        audit_rows.append({'sample_id': sid, 'status': status,
                           'changed': text != row['query'], **hits})
    frame = pd.DataFrame(rows)
    logs = pd.DataFrame(audit_rows).set_index('sample_id')
    frame = frame[frame['query'].ne('') & frame['label'].ne('')].copy()
    conflict_texts = set(frame.groupby('query')['label'].nunique().loc[lambda s: s > 1].index)
    conflict = frame['query'].isin(conflict_texts)
    logs.loc[frame.loc[conflict, 'sample_id'], 'status'] = 'conflicting_labels'
    frame = frame[~conflict].sort_values('sample_id').copy()
    duplicates = frame.duplicated('query', keep='first')
    logs.loc[frame.loc[duplicates, 'sample_id'], 'status'] = 'duplicate_text'
    frame = frame[~duplicates].copy()
    logs.loc[frame['sample_id'], 'status'] = 'kept'
    if set(frame['label']) != set(LABELS):
        raise ValueError('清洗后缺失类别，请由教师检查数据')
    if frame['label'].value_counts().min() < 5:
        raise ValueError('类别样本太少，无法稳定分层划分')
    train, rest = train_test_split(frame, test_size=.4, stratify=frame['label'], random_state=SEED)
    valid, test = train_test_split(rest, test_size=.5, stratify=rest['label'], random_state=SEED)
    split_ids = {}
    for name, part in [('train', train), ('valid', valid), ('test', test)]:
        part = part.sort_values('sample_id')
        part.to_csv(out/f'{name}.csv', index=False, encoding='utf-8-sig')
        split_ids[name] = part['sample_id'].tolist()
    frame.to_csv(out/'cleaned.csv', index=False, encoding='utf-8-sig')
    logs.reset_index().to_csv(out/'cleaning_log.csv', index=False, encoding='utf-8-sig')
    distribution = pd.DataFrame({name: part['label'].value_counts() for name, part in
                                [('cleaned',frame),('train',train),('valid',valid),('test',test)]})
    distribution.reindex(LABELS).fillna(0).astype(int).to_csv(out/'label_distribution.csv', encoding='utf-8-sig')
    manifest = {'seed':SEED,'raw_sha256':sha256(raw_path),'encoding':'utf-8-sig (strict)',
                'split_note':'CBLUE公开dev数据重新划分为课程60/20/20；非官方榜单测试',
                'input_count':len(records),'clean_count':len(frame),
                'status_counts':logs['status'].value_counts().to_dict(),
                'privacy_hits':{k:int(logs[k].sum()) for k in ['身份证','邮箱','手机']},
                'splits':split_ids,
                'csv_sha256':{k:sha256(out/f'{k}.csv') for k in split_ids}}
    write_json(out/'split_manifest.json', manifest)
    tasks=[]
    ordered=test.sort_values('sample_id').reset_index(drop=True)
    for gi,group in enumerate(['A','B','C']):
        for row in ordered.iloc[gi*9:(gi+1)*9].to_dict('records'):
            tasks.append({'group':group,**row})
    pd.DataFrame(tasks).to_csv(out/'group_tasks.csv',index=False,encoding='utf-8-sig')
    return manifest

def load_splits(data_dir):
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir/'split_manifest.json').read_text(encoding='utf-8'))
    parts = {}
    for name in ['train','valid','test']:
        file = data_dir/f'{name}.csv'
        if sha256(file) != manifest['csv_sha256'][name]:
            raise ValueError(f'{name}文件与划分清单不匹配，请重新prepare')
        frame = pd.read_csv(file, encoding='utf-8-sig')
        if frame['sample_id'].tolist() != manifest['splits'][name]:
            raise ValueError('样本顺序或ID不匹配')
        parts[name] = frame
    for a,b in [('train','valid'),('train','test'),('valid','test')]:
        if set(parts[a]['query']) & set(parts[b]['query']):
            raise ValueError('发现跨集合重复文本')
    return parts, manifest

def privacy_demo():
    fictional = '测试：１３８００１３８０００，test@example.com；无发热，剂量５mg，血压１２０/８０mmHg'
    return {'input':'虚构教学字符串（完整原文见代码）','output':clean_text(fictional)[0],
            'hits':clean_text(fictional)[1],
            'limitation':'仅演示格式规则；姓名、地址及上下文可识别信息仍需人工复核'}

def evaluate_predictions(y_true,y_pred):
    truth=list(y_true);pred=list(y_pred)
    if not truth or len(truth)!=len(pred):
        raise ValueError('真值和预测应等长且非空')
    if set(truth)-set(LABELS) or set(pred)-set(LABELS):
        raise ValueError('出现11类以外的标签')
    report=classification_report(truth,pred,labels=LABELS,output_dict=True,zero_division=0)
    return {'accuracy':float(accuracy_score(truth,pred)),
        'macro_f1':float(f1_score(truth,pred,labels=LABELS,average='macro',zero_division=0)),
        'weighted_f1':float(f1_score(truth,pred,labels=LABELS,average='weighted',zero_division=0)),
        'classification_report':report,
        'confusion_matrix':confusion_matrix(truth,pred,labels=LABELS).tolist()}


def environment_check():
    import torch
    from transformers import BertConfig,BertForSequenceClassification
    if not (3,11)<=sys.version_info[:2]<=(3,13):
        raise RuntimeError('请使用64位Python 3.11—3.13；推荐3.11或3.12')
    torch.set_num_threads(2)
    config=BertConfig(vocab_size=16,hidden_size=16,num_hidden_layers=1,
                      num_attention_heads=2,intermediate_size=32,num_labels=11)
    model=BertForSequenceClassification(config).to('cpu')
    y=model(input_ids=torch.tensor([[1,2,3]]),attention_mask=torch.ones(1,3,dtype=torch.long)).logits
    assert y.shape==(1,11)
    result={'python':platform.python_version(),'platform':platform.platform(),
        'device':'cpu','torch':torch.__version__,'cuda_available':torch.cuda.is_available(),
        'small_random_model_forward':'PASS (仅检查环境，不是正式预训练模型结果)',
        'versions':{x:importlib.metadata.version(x) for x in
         ['numpy','pandas','scipy','scikit-learn','transformers','huggingface-hub','safetensors']}}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','prepare','privacy-demo'])
    p.add_argument('--raw',type=Path,default=BASE/'data/raw/KUAKE-QIC_dev.json')
    p.add_argument('--data-dir',type=Path,default=BASE/'data/prepared')
    args=p.parse_args()
    if args.command=='check':environment_check()
    elif args.command=='privacy-demo':print(json.dumps(privacy_demo(),ensure_ascii=False,indent=2))
    else:
        manifest=prepare_data(args.raw,args.data_dir)
        print(json.dumps({k:manifest[k] for k in ['input_count','clean_count','status_counts']},ensure_ascii=False))
        print({k:len(v) for k,v in manifest['splits'].items()})

if __name__=='__main__':main()
