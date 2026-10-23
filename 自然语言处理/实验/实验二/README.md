# 实验二运行说明（CPU版）

## 1. 环境要求

- 64位Python 3.11；
- jieba 0.42.1；
- pandas 2.x；
- PyTorch 2.11.0 CPU版。

实验二统一使用CPU。`exp2_starter.py`是课堂程序，`data/`存放实验数据，`outputs/`保存个人输出。请在本目录执行命令，避免相对路径错误。

## 2. 创建独立环境

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-exp2.txt
python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
```

Linux：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-exp2.txt
python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
```

本实验不需要`torchvision`和`torchaudio`。

## 3. 检查环境

```bash
python -c "import jieba,pandas,torch; print('jieba',jieba.__version__); print('pandas',pandas.__version__); print('torch',torch.__version__); print(torch.tensor([1,2,3]) + 1)"
```

只要三个包能导入并输出`tensor([2, 3, 4])`，环境即通过。

## 4. 题目数据分配

- 习题1：所有学生完成6句语料级评价和P01—P10全部分析；
- 习题2：尾号0选P10，尾号1—9分别选P01—P09；
- 习题4、5：所有学生统一使用P01和P06；
- 习题7：所有学生统一使用`患者服药`公共示例；
- 习题6按指导书规则选择关键词文章。

## 5. 运行顺序

先按照指导书在交互环境或自己的实验文件中调用`exp2_starter.py`提供的函数。教师完整核验需回到`final_release`目录执行：

```bash
python teacher_resources/可复现实验/code/verify_exp2_exercises.py
```

核验程序应显示入门例题、习题1—8及习题9选做全部通过。

## 6. 常见问题

| 现象 | 原因与处理 |
|---|---|
| 文件不存在 | 确认当前目录为`student_resources/实验二` |
| 指标与答案不同 | 检查jieba版本、`HMM=False`、词典路径和是否使用语料级micro统计 |
| `make_practice_batch`返回值数量错误 | 新版返回`input_ids, tag_ids, vocab, selected`四项 |
| loss与答案不同 | 固定`torch.manual_seed(20261016)`并确认使用P01/P06 |
| PAD梯度不是0 | 检查标签PAD是否为`-100`以及`ignore_index=-100` |
| 中文CSV乱码 | 保存时使用`encoding="utf-8-sig"` |

## 7. 官方参考

- PyTorch本地安装：https://pytorch.org/get-started/locally/
- PyTorch历史版本：https://pytorch.org/get-started/previous-versions/

## 8. 公开版本与选题参数

公开脚本不保存完整学号。`run_exp2_report.py` 通过环境变量 `LAB_STUDENT_LAST_DIGIT` 读取选题数字，默认值为 `3`，保持现有 P03 对齐表和 article_01.txt 的实验选择。需要调整时，在 PowerShell 执行 `$env:LAB_STUDENT_LAST_DIGIT = "3"` 后运行脚本。结果 JSON 中的 CSV 路径使用项目内相对路径；本次脱敏未重新训练或修改原有指标。
