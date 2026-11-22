# 实验三运行说明

默认已有Python 3.11—3.13及依赖。主流程见实验三指导书.pdf，环境配置见文末附录A。模型权重已随包提供。

```bash
python exp3_starter.py check
python exp3_starter.py prepare
python exp3_worked_examples.py --last-digit 6 --output outputs_formal
```

示例学号2024012306的末位为6，对应B组，因此参数为--last-digit 6。参数取实际学号最后一位数字：0—3为A，4—6为B，7—9为C。A/B/C仅分配9条过程分析问句；所有方案统一评价完整391条测试集。输出目录须为空。

“模型微调”指更新预训练模型及分类头参数；CPU仅为本实验执行设备。运行后生成微调记录、逐类指标、混淆矩阵、分组结果及padding_mask_probe.json，分别对应指导书4.1—4.8的练习。预处理结果与实验输出由程序生成。

chinese_bert_tiny来源uer/chinese_roberta_L-2_H-128，revision=151f4204cbb5784c4126a89a94ef0bb044273ac0。数据来源及使用边界见DATA_SOURCE.json。完整模型目录包含配置、词表和权重，无需联网下载。

习题四读取bert_pair_summary.json：两行长度与预测、批量形状、四个关键token；完整轨迹位于bert_pair_trace.json，供需要时追溯。
