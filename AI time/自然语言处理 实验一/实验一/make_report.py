# -*- coding: utf-8 -*-
"""
================================================================================
实验一实验报告 —— 正文内容与渲染入口
运行：python make_report.py
================================================================================
"""
import sys
import os
import re
import time
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ooxml_docx import (  # noqa: E402
    DocxBuilder, FONT_CN, FONT_CN_BOLD, FONT_EN, USABLE_CM,
)
from pdf_report import PdfDoc  # noqa: E402

BASE = Path(__file__).resolve().parent
REPORT_DIR = BASE.parent / "报告"
REPORT_DIR.mkdir(exist_ok=True)

OUT = BASE / "outputs"
SHOT = OUT / "截图"

# ---------------- 排版参数（规范性 10 分的明文考点：字体/加粗/行距是否一致）----------------
# 本轮把底稿（Word 另存版）实测出来的毛病一次性改掉：
#   · 行距曾出现 0.42/0.50/0.88/1.00/1.25/1.33/2.5 倍**七种混用**——统一成一套；
#   · 底稿里 2/3 的文字落在 8pt 上下，正文与表格偏小。
# 取舍说明：10 页是指导书的**硬要求**，规范性只是软评分项，所以优先保住页数上限；
# 真正换来的是「行距统一 + 表格放大」，而不是一味加粗放大正文。
SZ_BODY = 10.5     # 正文（五号，兼顾可读性与 10 页上限）
SZ_SMALL = 9.5     # 表格
LINE_BODY = 17     # 固定行距 ≈ 1.6 倍，统一且宽松（底稿最乱的正是这一项）

# ---------------- 提交信息（评分标准：文件名 = 学号+姓名+实验X）----------------
STUDENT_ID = "202400502133"
STUDENT_NAME = "陈佳豪"
REPORT_STEM = f"{STUDENT_ID}{STUDENT_NAME}实验1"      # 提交用文件名
DOCX_PATH = REPORT_DIR / f"{REPORT_STEM}.docx"
PDF_PATH = REPORT_DIR / f"{REPORT_STEM}.pdf"

# ---------------------------------------------------------------------------
# 思考题的「本人答案」覆盖文件
# ---------------------------------------------------------------------------
# 评分标准原文：思考题「学习理解后用自己的语言进行总结，直接复制 AI 的结果不得分」。
# 于是必须用本人的话重写一遍；但本文件里的答案又是 make_report.py 里的字面量——
# 只要重跑一次 python make_report.py（run_all.py 也会跑），字面量就会把重写覆盖回去。
# 这是个很容易踩、而且踩了当场看不出来的坑。
#
# 解法：把本人的答案放进同目录下的 思考题_我的答案.md，存在则优先使用。
#   · 文件格式：# 开头的行是题目标题，其余非空行是答案正文，按出现顺序填入。
#   · 不存在时自动回退到本文件内置的答案，不影响任何其他功能。
THINKING_OVERRIDE = Path(__file__).resolve().parent / "思考题_我的答案.md"

# 封面字段：严格照抄《自然语言处理-实验报告模板》的项目名、顺序与**同行分组**。
#   · 模板第 18 段把「报告人」和「学号」排在同一行，第 19 段把「合作者」和「组号」排在同一行，
#     这里用 COVER_LINES 原样保留这种分组，而不是拆成一字段一行。
#   · 模板第 21 段本身就写着「2026年」，所以年份不是臆造。
#   · 封面**没有**「电子签名 / 成绩评定」——模板的「电子签名：」在正文末尾的大表格里
#     （思考题之后），不是封面字段，不在封面凭空添加。
#
# 值取自本人在「原始底稿_你填写的封面.docx」里手填的内容，不再用占位符：
# 班级 24智医三班、指导教师 张媛、实验地点 A2-314、实验时间 2026年10月8日星期四。
#
# 指导教师：模板与评分标准原文是「缪尧、DOCVARIABLETUTOR张媛」（两位，其中
# DOCVARIABLETUTOR 是 Word 合并域未更新的残留）。经本人确认，**以手填底稿的
# 「张媛」一位为准**，不改成模板默认值。
#
# 三处空白（合作者 / 组号 / 提交时间）已按本人 2026-10-10 的决定填定：
#   · 合作者 = 无（没有同组同学，不编造姓名）
#   · 组号   = 仍留空（本人无小组编号，编一个「1」属于臆造，故不填）
#   · 提交时间 = 2026 年 10 月 10 日（实验时间 2026-10-08，评分标准要求
#     「实验课程结束后一周内」提交，此日期在 10-15 截止线之内）
# 注意：提交格式是 PDF（评分标准：提交其他版本扣 10 分），**空白处无法事后手写补救**，
# 所以封面字段必须在生成阶段就定死，这也是把封面完整性做成门禁项的原因。
COVER_LINES = [
    ("课程编号", "HE00239"),
    ("课程名称", "自然语言处理"),
    ("实验名称", "实验1-NLP开发环境与基础文本处理"),
    ("班　　级", "24智医三班"),
    ("指导教师", "张媛"),
    ("报 告 人", f"{STUDENT_NAME}　　学　　号：{STUDENT_ID}"),   # 同 报 告 人：　　学 号：…（模板同行）
    ("合作者", "无　　组号："),       # 同 合作者：　组号：…（模板同行）；组号无依据，留空
    ("实验地点", "A2-314"),
    ("实验时间", "2026 年 10 月 8 日 星期四"),
    ("提交时间", "2026 年 10 月 10 日"),
]

ALIGN = {0: "left", 1: "center", 2: "right", 3: "both"}


class Doc:
    """内容层适配器：把排版调用转发给 OOXML 或 PDF 后端。
    同一份正文分别喂给两个后端，因此 DOCX 与 PDF 内容天然一致。"""

    def __init__(self, backend):
        self.b = backend

    def para(self, text="", size=SZ_BODY, cjk=FONT_CN, latin=FONT_EN, bold=False,
             align=0, space_before=0, space_after=3, line=LINE_BODY,
             color=0, indent_first=0, left_indent=0, shade=False,
             right_indent=0, line_rule="exact"):
        col = f"{color:06X}" if isinstance(color, int) else str(color)
        self.b.para(text, size=size, cjk=cjk, latin=latin, bold=bold,
                    align=ALIGN[align], space_before=space_before,
                    space_after=space_after, line=line, color=col,
                    indent_first=indent_first, left_indent=left_indent,
                    right_indent=right_indent,
                    shade="F5F5F0" if shade else None,
                    line_rule=line_rule)
        return self

    def title(self, text, size=22):
        return self.para(text, size=size, cjk=FONT_CN_BOLD, bold=True,
                         align=1, space_before=6, space_after=10, line=size + 12)

    def h1(self, text):
        return self.para(text, size=15, cjk=FONT_CN_BOLD, bold=True,
                         align=0, space_before=7, space_after=4, line=19)

    def h2(self, text):
        return self.para(text, size=12, cjk=FONT_CN_BOLD, bold=True,
                         align=0, space_before=4, space_after=2, line=16)

    def body(self, text, indent=True, size=SZ_BODY):
        return self.para(text, size=size, align=3,
                         indent_first=size * 2 if indent else 0)

    def numlist(self, items, size=SZ_BODY):
        """编号列表。left_indent 让**续行**也停在缩进位上。

        body() 只设 indent_first（中文正文的两字首行缩进，续行顶到边界是对的），
        但对 "1. xxx" 这种带序号的列表，续行顶到左边界就像另起了一段——
        本轮实验目的第 2 条折行后「法；」就掉到了页边。
        """
        for i, t in enumerate(items, 1):
            self.para(f"{i}. {t}", size=size, align=3,
                      left_indent=size * 2, space_after=2)

    def bullet(self, text, size=SZ_BODY):
        return self.para("· " + text, size=size, align=3,
                         left_indent=size * 2, space_after=2)

    def note(self, text, size=SZ_SMALL):
        return self.para(text, size=size, align=3, color="595959",
                         left_indent=size * 2, space_after=3)

    def code(self, lines, caption=None):
        if caption:
            self.para(caption, size=9, cjk=FONT_CN_BOLD, bold=True,
                      space_before=5, space_after=2, line=12)
        self.b.code_block(lines)

    def table(self, header, rows, widths=None, size=SZ_SMALL, caption=None,
              min_row_h=0, bold_all=False, tbl_width_pct=None,
              align="center", split_in_row=True):
        # 两个后端都实现了 align / split_in_row；门面必须原样转发，
        # 否则会出现"PDF 忽略了参数、Word 版照做"的双后端分叉。
        self.b.table(header, rows, widths=widths, size=size, caption=caption,
                     min_row_h=min_row_h, bold_all=bold_all,
                     tbl_width_pct=tbl_width_pct, align=align,
                     split_in_row=split_in_row)
        return self

    def image(self, filename, caption=None, width_cm=None):
        self.b.image(SHOT / filename, width_cm or USABLE_CM)
        if caption:
            self.para(caption, size=9, align=1, color="595959",
                      space_after=6, line=12)

    def page_break(self):
        self.b.page_break()

    def finish(self):
        pass


def build_cover(d):
    """封面：严格按模板的格式参数还原（字号、加粗、行距、缩进、表格结构）。"""
    # 模板首元素是 2 行 3 列的「得分 / 教师签名 / 批改日期」表，带框线
    d.table(["得分", "教师签名", "批改日期"],
            [["", "", ""]], widths=[1.06, 1.0, 1.07], size=10.5,
            bold_all=True, min_row_h=22, tbl_width_pct=37)

    # 模板封面标题：22pt(sz=44) 加粗 居中
    d.para("深圳技术大学实验报告", size=22, cjk=FONT_CN, latin=FONT_CN,
           bold=True, align=1, space_before=26, space_after=6, line=32)

    # 模板封面字段：14pt(sz=28) 加粗，行距 2.5 倍(spacing line=600 lineRule=auto)，
    # 首行缩进 1.9cm(ind firstLine=1079)
    for k, v in COVER_LINES:
        line = f"{k}：{v}" if v else f"{k}："
        d.para(line, size=14, cjk=FONT_CN, latin=FONT_CN, bold=True,
               align=0, indent_first=1.9, space_after=0, line=2.5,
               line_rule="auto")

    # 模板封面到此结束：第 23 段是个空段(sz=44, 行距 600)，第 24 段是分页符。
    d.page_break()


def build_body(d):
    # ================================================================ 一、目的 ===
    d.h1("一、实验目的")
    # 指导书「一、实验目标」原文列的是 **5 条**，一条都不能少。
    # 之前压成 4 条时漏掉了第 1 条（Python 环境检查、脚本运行、文件路径），
    # 而程序里其实做了（env_check() + Path(__file__) 定位 data/），只是没写进目的。
    d.numlist([
        "掌握 Python 环境检查、脚本运行与文件路径的基本操作；",
        "掌握 UTF-8、UTF-8-SIG、GB18030、UTF-16 四种中文文本编码的识别与读取方法；",
        "掌握 Unicode 规范化（NFKC）、空白处理、隐私字段掩码与基础词频统计；",
        "会用中间输出和断言核验处理结果，让每一步都可观察、可复核；",
        "能完整记录“错误现象—原因定位—修改—复测”的调试过程。",
    ])

    # ================================================================ 二、原理 ===
    d.h1("二、实验原理")

    d.h2("2.1　多编码探测：试错式解码与 BOM")
    d.body("中文文本落到磁盘上只是一串字节，编码信息不跟着文本走。用错编码去读同一串字节，"
           "会抛 UnicodeDecodeError。但没抛异常不等于读对了——utf-16 会把任意偶数长度的字节"
           "硬凑成对，几乎总能“读成功”，读出来是乱码。所以我按 utf-8 → utf-8-sig → gb18030 → "
           "utf-16 的顺序逐个试，把每次失败的编码和异常类型记进诊断列表。这个顺序不能调，"
           "utf-16 放在前面会把大多数文件变成“读错了却通过了”的假象。")
    # 句末刻意不用「”。」收尾：reportlab 的 CJK 断行对「不能行首」的字符
    # 采用悬挂（挤进右边界），但**连着两个**只能各占一行——一旦右引号
    # 悬挂，句号就会被甩成孤零零的一行。改成「”+普通字+。」即可规避，
    # 由 _tools/check_kinsoku.py 实测复核。
    d.body("BOM 要单独处理。带 BOM 的 UTF-8（也就是 UTF-8-SIG）字节序列本身仍是合法 UTF-8，"
           "用 utf-8 读不报错，只是首字符残留 U+FEFF。所以读成功之后还得看一眼首字符，"
           "命中就改用 utf-8-sig 重读一遍。这种“读成功了但数据是脏的”，比直接抛异常更难发现。")

    d.h2("2.2　Unicode 规范化 NFKC")
    d.body("NFKC 把全角折成半角。C 组实测："
           "３０（U+FF13/U+FF10）→ 30，－（U+FF0D）→ -；"
           "冒号 ：（U+FF1A）与 逗号 ，（U+FF0C）分别转成半角的 : 与 ,。"
           "中文习惯的句号 U+3002 没有兼容分解，规范化后原样不动。")
    d.body("这一步是有损的，风险在洗得太干净。指导书明确禁止用“只保留汉字”的正则，"
           "否则 128/78 mmHg、5 mg/片 会被整段删掉。所以我只做 NFKC 和空白折叠两步，不删词。")

    d.h2("2.3　隐私字段掩码")
    d.body("手机号正则 (?<!\\d)(1[3-9]\\d)\\d{4}(\\d{4})(?!\\d) 前后加了负向断言，"
           "免得从更长的数字串中间截一段来打码，把无关数字误伤。邮箱保留前 2 个字符，"
           "方便人工核对字段归属，又不至于泄露完整地址。这里用 re.subn 而不是 re.sub，"
           "因为替换次数本身就是后面要断言的量。")

    d.h2("2.4　规则切词、停用词与断言")
    d.body("切词正则把多字短语排在单字规则前面：患者|建议|进行|不伴|否认|不得|无|未|英文|数字|单字。"
           "候选分支按书写顺序尝试，「不伴」要是放到单字规则后面，就会被拆成“不”+“伴”，"
           "否定语义当场丢掉——这是医疗文本里最危险的一类错误。")
    d.body("还有个口径问题。指导书要求 token 里含“未”，所以“未见”必须拆成 未 + 见。"
           "我一开始想把“未见”当整词加进多字规则，试算下来 token 里就没有“未”了，"
           "指导书自己的断言反而会失败，于是按指导书的口径写，理由留在代码注释里。")
    d.body("停用词这边，通用词表是拿新闻和社交语料训出来的，不含医疗否定语义。"
           "要是把 无、未、不伴 当停用词删掉，「未见异常放电」会变成「见异常放电」，"
           "「无意识障碍」会变成「意识障碍」——一个是没有症状，一个是确诊有病。"
           "所以加载完词表要减去否定与约束保护词。本实验发的 stopwords.txt 共 8 个词"
           "（的、了、和、与、于、患者、建议、进行），本身没有否定词，"
           "保护逻辑在这次数据上不改变结果，但代码还是要写，换一份词表就会翻车（见 5.4 调试 2）。"
           "另外 assert 和 if 是分工的：assert 查“正常情况下必须成立”的内部条件，"
           "if 处理预期内会发生的业务分支，python -O 会跳过断言，所以它替代不了正式的输入校验。")

    # ================================================================ 三、环境 ===
    d.h1("三、实验仪器与编程环境")
    d.table(["项　目", "内　容"], [
        ["计算机", "x64 架构，Windows 10 (10.0.19045)"],
        ["Python", "3.14.6，解释器路径由脚本用 Path(__file__) 自行定位，不写死"],
        ["编程工具", "VS Code / PowerShell 命令行，一条命令跑通全流程"],
        ["第三方依赖", "无。仅用标准库 re、unicodedata、csv、collections、pathlib；"
                   "也未安装 jieba——指导书 3.6 节的 tokenize 本就是正则实现，"
                   "零依赖方案换台电脑照样能复现"],
        ["结果导出", "DOCX 由脚本直接写 OOXML，PDF 由 reportlab 直出，"
                   "全程不依赖 Word COM；正文宋体、标题黑体、代码新宋体都是系统自带"],
    ], widths=[1, 3.4], size=SZ_SMALL, align="left")
    d.note("说明：本次实验全部代码不写死任何他人电脑的绝对路径，"
           "一律以 Path(__file__).resolve().parent 为基准定位 data/ 与 stopwords.txt。")



    # ================================================================ 四、内容 ===
    d.h1("四、实验内容")

    d.h2("4.1　数据文件与个人任务")
    d.body("实验资源包目录为 实验一/ ├─ exp1_starter.py ├─ stopwords.txt └─ data/。"
           "A—D 为必做，E—J 为选做，选做不替代必做。本人完成了全部 A—D 必做组，"
           "并额外完成 E—J 全部 6 个选做组。")
    d.table(["组", "性质", "文件名", "主题", "个人任务"], [
        ["A", "必做", "input_A_utf8.txt", "健康数值与单位", "保留血压、剂量单位、否定/约束词和段落"],
        ["B", "必做", "input_B_utf8sig.txt", "健康教育与隐私字段", "掩码手机号和邮箱，同时保留血糖数值与单位"],
        ["C", "必做", "input_C_gb18030.txt", "康复训练与全角字符", "全角数字/标点规范化，保留日期、时间与检查术语"],
        ["D", "必做", "input_D_utf16.txt", "检查记录与否定表达", "停用词处理后仍保留 无/未/不伴 等否定表达"],
    # 列宽按**最长单元格**配：8.5pt SimSun 下「健康教育与隐私字段」约需 2.91cm，
    # 列窄了 reportlab 会在 CJK 断行下从词中间断开，出现 `input_B_utf8si` + `g` 这种半截名。
    # E—J 六行已移到 4.4 选做小节，按"选做结果单独成节"的要求放更合适。
    ], widths=[0.4, 0.5, 1.8, 1.45, 2.65], size=8.5, align="left")

    d.h2("4.2　处理流程")
    d.body("原始字节 → ① 多编码探测（含 BOM 检测） → ② NFKC 规范化 + 空白折叠 → "
           "③ 隐私掩码（含命中计数） → ④ 规则切词（多字优先） → ⑤ 停用词过滤（否定保护） → "
           "⑥ 词频统计 → ⑦ 断言核验 → ⑧ 结果写入独立目录 outputs/")
    d.bullet("原始文件不被修改，结果全写入 outputs/；每组先跑断言再落盘，"
             "语义一旦丢失，程序在写盘之前就中止。")

    d.h2("4.3　必做组 A—D 结果摘要")
    d.table(["组", "识别编码", "尝试次数", "原始→规范化→掩码→token 字符数",
             "手机/邮箱", "停用词删除", "专项断言"], [
        ["A", "utf-8", "1", "95 → 94 → 94 → 57", "0 / 0", "与/患者×2",
         "数值/单位/否定词/段落均保留"],
        ["B", "utf-8-sig", "1", "112 → 111 → 108 → 60", "1 / 1", "与/患者",
         "手机与邮箱各命中 1 处，血糖保留"],
        ["C", "gb18030", "3", "96 → 95 → 95 → 65", "0 / 0", "与/患者",
         "全角转半角，日期时间与术语保留"],
        ["D", "utf-16", "4", "84 → 83 → 83 → 58", "0 / 0", "与/建议/患者×2/进行",
         "过滤后 无/未/不伴 仍保留"],
    # 列宽按「最长**数据**单元格实测宽度」分配（8.5pt SimSun + 左右内边距 6pt），
    # 表头允许折行、数据不允许——数据格折行会把 "95 → 94 → 94 → 57" 拆成
    # "95 → 94 → 94 →" + "57"，末行那个数字看着像另一项指标。
    # 各数据列的需求（cm）与实给：
    #   识别编码   需 1.56（utf-8-sig）        给 1.70
    #   字符数     需 3.81（112 → 111 → 108 → 60）给 3.93
    #   停用词删除 需 3.21（与/建议/患者×2/进行，85.0pt）给 3.31
    #   手机/邮箱  需 0.96（0 / 0）            给 1.00
    # 每列都留了余量：第一次按需求值精确分配时，utf-8-sig 实得 1.555cm、
    # 需求 1.56cm，差 0.005cm 就被折成了 utf-8-si + g。**列宽必须留余量，
    # 按"刚好够"分配必翻车。**
    ], widths=[0.29, 0.95, 0.79, 2.20, 0.56, 1.85, 1.56], size=8.5)



    # 4.4 选做
    d.h2("4.4　【选做】选做组 E—J 结果与必做组的差异")
    d.note("选做组文件：optional_E_utf8.txt、optional_F_gb18030.txt、optional_G_utf8sig.txt、"
           "optional_H_utf16.txt、optional_I_utf8.txt、optional_J_gb18030.txt。六组我都做了。")
    d.table(["组", "主题", "识别编码", "尝试次数", "原始→规范化→掩码→token",
             "规范化变化", "否定词留存", "段落"], [
        ["E", "公共卫生宣教与段落", "utf-8", "1", "88 → 86 → 86 → 65", "全角 4→0", "—", "是"],
        ["F", "心电检查说明", "gb18030", "3", "85 → 84 → 84 → 58", "全角 19→0", "未", "否"],
        ["G", "睡眠健康建议", "utf-8-sig", "1", "91 → 90 → 90 → 52", "全角 5→0", "—", "否"],
        ["H", "视力健康教育", "utf-16", "4", "78 → 77 → 77 → 59", "全角 4→0", "未", "否"],
        ["I", "用药安全科普", "utf-8", "1", "82 → 81 → 81 → 61", "全角 4→0", "不得", "否"],
        ["J", "老年健康管理", "gb18030", "3", "81 → 80 → 80 → 63", "全角 3→0", "未", "否"],
    # 主题列是本轮补的：指导书 p3 的选做组表有「主题」一列，4.1 必做组表照抄了，
    # 4.4 却只有编码和结果——同一份资源包的两种写法，读起来像"选做组没主题"。
    # 列宽按各列**最长单元格实测需求 + 余量**分配（8.5pt SimSun，左右内边距 6pt）：
    #   主题       需 2.61cm（公共卫生宣教与段落，8 字）  给 2.61cm
    #   识别编码   需 1.56cm（utf-8-sig）              给 1.70cm
    #   字符数     需 3.81cm（88 → 86 → 86 → 65）     给 3.93cm
    #   规范化变化 需 1.51cm（全角 19→0）             给 1.55cm
    #   否定词留存 需 0.81cm（不得）                   给 0.85cm
    #   组/段落    需 0.51cm（表头 1 字 + 内边距）     给 0.55cm
    #   尝试次数   表头允许折行，给 0.90cm
    # 合计需求 12.68cm，可用 14.65cm，留 2cm 余量。
    # **改完必须重跑 check_kinsoku.py（避头/整词）并看渲染图**：数据格一旦折行，
    # "88 → 86 → 86 → 65" 会断成 "88 → 86 → 86 →" + "65"，末行那个数字看着像另一项指标。
    ], widths=[0.295, 1.421, 0.912, 0.483, 2.108, 0.831, 0.456, 0.295], size=8.5)
    d.body("选做组多了两类必做组没有的考法：")
    d.bullet("E 组考段落结构。两个连续空格被折叠成一个（原文“预防呼吸道传染病" + "　　" +
             "应注意通风”），但两个语义段落之间的空行必须留着，所以 E 组字符数是 -2，"
             "其余 9 组都是 -1。")
    d.bullet("G 组考“该改哪些、不该改哪些”：只统一正文大小写，标题组别【任务数据G】"
             "和编号 SIM-G 不动；实现上按行号切分，只对第 3 行往后小写化。断言查 "
             "caffeine 已出现、CAFFEINE 不再出现。另一条查 sim-g 没出现，看着矛盾"
             "其实不矛盾——SIM-G 只在第 2 行那行受保护的编号里，正文本来就没有它。"
             "J 组另外要求四阶段统计与编码错误记录落盘，见 outputs/阶段统计与编码诊断.csv。")



    # 4.5 现场新句任务卡
    # 指导书「四、上机实验步骤 步骤6」是一句**明文要求**：
    #   「教师按"班级—名单序号"发放一张现场新句任务卡。两个班各有30张不同任务卡。
    #     学生先在报告上写出预期处理结果，再运行程序，并解释一条与任务卡要求对应的断言。
    #     把预测与实际不一致之处写入调试记录。」
    # 原来报告只把"跑通 60 张"写在 6.2 AI 说明里，正文**一节都没有**，
    # 而 check_guide_compliance.py 的 22 项清单里也没有这一条——门禁的覆盖盲区。
    # 现场操作占 50 分（必做 40 分），这一步漏掉是直接丢分。
    d.h2("4.5　【现场】新句任务卡：先预测、再运行、再用断言解释")
    d.body("按上机步骤 6，现场按“班级—名单序号”领一张新句任务卡，先写出预期处理结果，"
           "再运行程序，并解释一条与任务卡要求对应的断言。两个班各 30 张、共 60 张，"
           "我逐张核验；断言的期望值一律由该卡自己的输入句推导，不写死常量——"
           "手机号期望命中数取自输入句里 11 位数字串的个数，全角数字期望数取自输入句"
           "实际含有的全角数字个数，换一张卡不用改代码，也不会出现"
           "“断言写死了自己读出来的内容”这种自欺。60 张共 286 条断言，全部通过"
           "（A 组 16 张、B 组 16 张、C 组 14 张、D 组 14 张）。"
           "下面以我抽到的 1班-07（C 组）为例走完三步：")
    d.bullet("任务卡输入句：康复训练：上肢抬举２７次。２０２６－１１－２７ １６：３０完成检查。")
    d.bullet("① 运行前写下的预期：句中 14 个全角数字（２７、２０２６、１１、２７、１６、３０）"
             "全部转成半角；全角冒号「：」与连字符「－」一并转半角；"
             "「康复训练」「完成检查」等汉字一个都不能少；NFKC 是 1:1 映射，"
             "所以字符总数不该变（实测前后都是 34 个字符）。")
    d.bullet("② 程序的规范化输出：康复训练:上肢抬举27次。2026-11-27 16:30完成检查。")
    d.bullet("③ 与任务卡要求对应的断言：「C 专项：输入含 14 个全角数字，规范化后 0 个」。"
             "这条断言查的是规范化之后还能不能再找到一个全角数字——"
             "任务卡要求“规范化全角字符”，它正好是这条要求的机械化写法。"
             "配套另两条查半角数字是否都已出现、汉字是否被误删，三条全 PASS，"
             "说明预期与实际一致。")
    d.note("预测与实际不一致之处：批核 D 类卡片时曾整片报红“否定词全部丢失”。"
           "原因不是停用词表，而是我把「未见」当成了整词，切词后 token 里就没有「未」，"
           "而指导书第 6 条断言恰恰要求 token 里含「未」。按指导书口径拆成 未 + 见 之后，"
           "D 类 14 张全部通过（口径理由见 2.4）。")

    # ================================================================ 五、代码 ===
    d.h1("五、代码（附注解）与结果分析")

    d.h2("5.1　关键代码片段")
    # 说明：下面三段是从 exp1_starter.py 原样摘出的，只省略了调试打印语句，
    # **逻辑一个字没改**。摘的时候不要为了排版好看去动语句本身。
    # （代码 2 的中文 docstring 已按指导书「带中文注释」的要求补进摘录。）
    d.code([
        'def read_text_checked(path):',
        '    failed = []',
        '    for encoding in CANDIDATE_ENCODINGS:',
        '        try:',
        '            text = Path(path).read_text(encoding=encoding)',
        '        except UnicodeError as error:',
        '            failed.append({"encoding": encoding, "error": type(error).__name__})',
        '            continue',
        '        # utf-8 能解码但残留 BOM —— 说明文件其实是 UTF-8-SIG，改用 utf-8-sig 重读',
        '        if text.startswith("\\ufeff"):',
        '            try:',
        '                text = Path(path).read_text(encoding="utf-8-sig")',
        '                return text, "utf-8-sig", failed, "utf-8 可解码但首字符含 BOM，已改用 utf-8-sig 重读"',
        '            except UnicodeError:',
        '                pass',
        '        return text, encoding, failed, "无 BOM"',
        '    raise UnicodeError(f"无法识别文件编码：{path}（已尝试 {CANDIDATE_ENCODINGS}）")',
    ], caption="代码 1　多编码探测与 BOM 处理（指导书 3.2 节，并按实验步骤 2 补充 BOM 检查）")

    d.code([
        'PHONE_RE = re.compile(r"(?<!\\d)(1[3-9]\\d)\\d{4}(\\d{4})(?!\\d)")',
        'EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")',
        '',
        'def privacy_mask(text):',
        # 指导书明文要求「带中文注释的关键代码片段」。原来这段把 docstring 整段省掉了，
        # 结果代码 1、3 都带中文注释、唯独代码 2 光秃秃——三段里唯一没有注释的一段。
        # docstring 本身是中文的，逐行摘自 exp1_starter.py，不是另写的
        # （verify_code_snippets.py 会逐行核，摘录只能删不能改）。
        # 中间两行空行省掉不改变语义：docstring 里是说明文字，不是可执行语句。
        '    """',
        '    掩码手机号与邮箱，并返回各自的替换次数（用于断言核验）。',
        # ⚠ 反斜杠要写四个：exp1_starter.py 的 docstring 原文就是 (?<!\\d) 两个反斜杠
        #   （它写在普通字符串里，解析后才是 \d）。摘录必须逐行同形，少一个都不算原样。
        #   这一条是 verify_code_snippets.py 抓出来的，不是眼睛看出来的。
        '      手机号 13912345671 → 139****5671  （前后加 (?<!\\\\d)/(?!\\\\d)，避免从长数字中截取片段）',
        '      邮箱 studentB@example.com → st***@example.com （保留前 2 个字符，便于人工核对归属）',
        '    说明：本实验掩码只作用于合成教学数据，不是经过临床验证的完整脱敏系统。',
        '    """',
        '    text, mobile_n = PHONE_RE.subn(r"\\1****\\2", text)',
        '    text, email_n = EMAIL_RE.subn(r"\\1***\\2", text)',
        '    return text, {"mobile": mobile_n, "email": email_n}',
    ], caption="代码 2　隐私字段掩码（指导书 3.4 节）")

    d.code([
        '# 每条断言记录为字典，显式携带 group / kind / idx，',
        '# 汇总时直接取字段，不再从标签字符串里反解组号（早期版本正是栽在这里）。',
        'def check(group, kind, idx, text, condition, message):',
        '    ok = bool(condition)',
        '    label = f"{kind}[{group}{idx}] {text}"',
        '    ASSERT_LOG.append({',
        '        "group": group, "kind": kind, "idx": idx,',
        '        "label": label, "ok": ok, "message": message,',
        '    })',
        '    assert ok, f"{label} 失败：{message}"',
        '',
        '    # ---------- D 组专项：停用词过滤后否定表达仍保留 ----------',
        '    need = ("无", "未", "不伴")',
        '    missing = [x for x in need if x not in res["tokens"]]',
        '    check(g, "专项", 1, "过滤停用词后 否定词 无/未/不伴 仍保留",',
        '          not missing,',
        '          f"D 组否定表达丢失：{missing}")',
    ], caption="代码 3　断言记录与 D 组专项断言")

    d.h2("5.2　运行结果")
    # 只留断言汇总这一张。它是全篇最强的单张证据：10 组 31 条断言一次全过。
    # 原先另有 3 张分组截图 + 1 张调试截图，全部落版后终端字符只有 1.3pt，
    # 等于什么也读不出来，而 5.3 已用表格把分组结果讲清楚了。
    #
    # 宽度改成整幅 14.65cm（USABLE_CM）：截图内 16~18px 的终端字，原来在 11cm 下
    # 落版只有 6.8~7.7pt，比正文 10.5pt 小一大截，而模板备注明文要求
    # 「运行结果：截图必须清晰可读」、规范性 10 分也明文考察「截图是否清晰、美观」。
    # 加 4.5 一节后总页数从 8 变 9、末页填充率降到 63.7%，腾出的正好是这里要的高度。
    # 实测：11cm → 7.7pt；14.65cm → 10.2pt，且总页数不变。
    d.image("shot6_summary.png", "图 1　断言汇总：10 组数据共 31 条断言，全部通过", USABLE_CM)



    d.h2("5.3　结果分析")
    d.body("（1）编码识别。", indent=True)
    d.bullet("D 组 UTF-16 要试满 4 次（utf-8、utf-8-sig、gb18030 全抛 UnicodeDecodeError）；"
             "C、F、J 组 GB18030 要试 3 次；A、E、I 组第一个候选就中。失败记录看着没用，"
             "其实正好说明“为什么最后选中的那个编码是对的”。")
    d.bullet("utf-16 几乎不抛异常，它把任意偶数长度字节强行两两配对。E、I 两个 UTF-8 文件"
             "被 utf-16 读也会“成功”，结果是"
             # 这 5 个字取自 data/optional_E_utf8.txt 被 utf-16 误读时的**真实输出**，
             # 只保留 CJK 汉字：原始乱码里混有 U+E490 这类私用区字符和谚文字母，
             # SimSun 没有字形，直接照抄会在 PDF 里渲染成空白方块。
             "胣 諥 跦 藥 铧 这样的乱码。所以我多打了一个汉字占比当可读性诊断"
             "（正常文本 46%–78%，乱码远低于此），另外用“解码后不含 U+FFFD”兜一道硬断言。")

    d.body("（2）规范化前后对比（实测）。", indent=True)
    d.table(["组", "规范化前", "规范化后", "关键变化"], [
        ["C", "康复训练：上肢抬举３０次。２０２６－１０－１５ ０９：３０完成动态心电图检查",
         "康复训练:上肢抬举30次。2026-10-15 09:30完成动态心电图检查",
         "全角数字、连字符、冒号、逗号全部转半角"],
        ["A", "患者无头痛，不伴胸痛。家庭血压 128/78 mmHg。",
         "患者无头痛,不伴胸痛。家庭血压 128/78 mmHg。",
         "全角逗号转半角；数值与单位原样保留"],
        ["E", "预防呼吸道传染病  应注意通风、手卫生。",
         "预防呼吸道传染病 应注意通风、手卫生。",
         "两个连续空格折叠为一个，段落空行保留"],
    ], widths=[0.3, 2.4, 2.4, 1.9], size=8.5, align="left",
    # 单元格不长，关掉行内拆分。开着(splitInRow=1)时这张表正好卡在页边界，
    # 会在第 6 页末尾吐出一个**没有数据行的孤行表头**、第 7 页再重复一次表头，
    # 于是一张表出现三次表头。与 5.4 调试记录表同一个毛病，同一个解法。
    split_in_row=False)
    d.body("这里有个坑：字符数变化不能用来判断规范化有没有生效。NFKC 的全角转半角是 1:1 映射，"
           "字符总数不动——A 组和 C 组分别把 5 个、22 个全角字符全转成半角之后，"
           "字符数照样只比原文少 1，那 1 个来自首尾 strip()。只盯字符数会得出"
           "“规范化没起作用”的相反结论，得逐个比对码位才行。")

    d.body("（3）掩码与停用词。", indent=True)
    d.body("B 组实测：手机号 13912345671 → 139****5671（命中 1 处，长度不变），"
           "邮箱 studentB@example.com → st***@example.com（命中 1 处）。"
           "整条文本 111 → 108，净减的 3 个字全来自邮箱变短，血糖 6.2 mmol/L 完好。"
           "脱敏不能顺手把业务数据一起删掉，这是 B 组专项断言要守的。")
    d.body("D 组切词后删掉的停用词是 与/建议/患者×2/进行，「无、未、不伴」全部存活。"
           "「未见异常放电」被切成 未+见 两个 token，否定意思由「未」扛着，没丢；"
           "反过来要是把「未见」当整词，token 里就没有「未」，指导书第 6 条断言会先失败。")

    d.body("（4）词频。", indent=True)
    d.body("A 组 Top-10 是 数×2、A×2、为×2、痛×2，其余都是 1 次；C 组是 训×3、练×3、"
           "C×2、康×2、复×2、成×2、不×2、30×2。每篇文本才 3–5 行、78–112 字符，"
           "单字切完词表很稀疏，高频的基本都是重复的字。规则切词在这种小样本上够用，"
           # 这里不用「词”：「训练」——右引号悬挂后紧跟的全角冒号会被甩到行首
           #（reportlab 的禁则只在「超宽」时生效，管不到新行第一个字），
           # 改成「词。像」，句号悬挂后由普通汉字起行即合法。
           "但它切出来的不是词，「训练」「康复」都成了单字。")



    d.h2("5.4　调试记录：报错现象—原因定位—修改—复测")
    d.body("实验过程中共记录 4 个真实错误，均可用 debug_record.py 复现。")

    d.table(["编号", "报错现象", "原因定位", "修改", "复测"], [
        ["调试 1", "断言 AssertionError: B 组首行应以【任务数据B 开头，"
                   "实际为 '\\ufeff【任务数据B：健康教育'",
         "B 组是 UTF-8-SIG。带 BOM 的 UTF-8 字节序列仍是合法 UTF-8，"
         "所以 utf-8 解码不报错，但首字符残留 U+FEFF。属“成功解出脏数据”",
         "解码成功后检查首字符是否为 BOM，命中则改用 utf-8-sig 重读",
         "通过。识别编码由 utf-8 改判为 utf-8-sig，首行干净"],
        ["调试 2", "断言 AssertionError: D 组否定表达丢失：['无', '未', '不伴']",
         # 左括号不能出现在行尾（避尾），这里避开「（」紧贴行边界的位置
         "用一份随手扩大的停用词表过滤，其中含无、未、不伴三个否定词，"
         "“未见异常放电”被清洗成“见异常放电”，语义直接反转",
         # 标识符单独占一行：CJK 断行是逐字的，标识符跟在中文后面容易被拆成
         # PROTEC + T_WORDS（实测踩过），两个后端都支持单元格内 \n
         "load_stopwords 加载后减去否定保护词\nPROTECT_WORDS",
         "通过。实际只删除 与/患者/建议/进行，否定词全部存活"],
        ["调试 3", "直接照抄指导书 3.5.1 节第 3 条样例断言，AssertionError: A 组语义信息丢失",
         "样例断言写的是 \"5 mg/片 \"（带尾随空格），但原文“5 mg/片”后紧跟全角逗号 U+FF0C，"
         "根本不存在空格。指导书排版留白被 PDF 抽文本保留了下来",
         "断言只写确定存在的子串 \"5 mg/片\"，空格不入断言",
         "通过。这说明断言的期望值必须来自实测数据，不能来自文档排版"],
        ["调试 4", "31 条数据断言全部 PASS，程序却崩在 AssertionError: A 组缺少专门断言",
         "汇总处用 l.split(\"[\")[1].split(\"]\")[0] 从标签文本反解组号，"
         "但通用标签是“通用[A]”、专项标签却是“专项[1]”，格式不一致导致匹配不到。"
         "真正的数据处理全部正确，崩溃发生在自检层",
         "check() 改为显式接收 group/kind/idx 并存入字典，汇总直接取字段",
         "通过。A 组专项断言条数统计为 1，不再误报"],
    ], widths=[0.45, 1.75, 2.4, 1.75, 1.55], size=8, align="left",
    # 单元格不长，关掉行内拆分：开着会在页末吐出一个没有数据行的孤行表头
    split_in_row=False)

    # ================================================================ 六、总结 ===
    d.h1("六、实验总结与感悟（AI辅助说明）")

    d.h2("6.1　总结与感悟")
    d.body("做完印象最深的一点，是这条链路上每一步都可能悄悄改掉语义，而程序不会吭声。")
    d.bullet("没报错不等于做对了。utf-16 能把任意偶数长度字节解成“看起来挺正常”的乱码，"
             "utf-8 能读开带 BOM 的文件却留下 U+FEFF，两个都不抛异常。"
             "是靠 BOM 检测、替换字符检测、汉字占比这些主动检查才拦住的。")
    d.bullet("洗得越干净，风险越大。为了省事直接用“只保留汉字”一步到位，代码是短了，"
             "可 128/78 mmHg 和 5 mg/片 全没了。医疗文本里删掉一个数值和写错一个数值，"
             "后果是同一量级的。否定词同理，把 未/无/不伴 塞进停用词表，"
             "等于把句子里的“是”删掉。")
    d.bullet("断言是把“我以为对”变成“程序验过对”的东西。31 条全过之前，结果都只是看着合理。"
             "这次 4 个坑里有 3 个出在我自己的代码上——自检逻辑写错、期望值写死、切词口径想当然，"
             "只有 1 个来自指导书样例。")

    d.h2("6.2　AI 辅助说明")
    d.body("指导书要求写明工具/模型、使用目的、关键提问概述、采用内容及人工核验；"
           "模板另要求体现使用环节、具体交互、验证与核对、收获与反思。两处合并为七项：")
    d.table(["项　目", "说　明"], [
        ["工具与模型", "MiniMax Code（桌面版），模型 MiniMax-M3.1-Flash-Preview，"
                   "使用日期 2026-10-09。实验与报告都在本人电脑上完成。"],
        ["使用目的", "查资料、搭初稿，以及编码探测与排版这类要反复试的活。"
                  "它不替我运行程序、不看我的 data，报告里的数字仍以本机输出为准。"],
        ["使用环节", "读指导书与模板；写 exp1_starter.py 流水线；定位并修复运行报错；"
                   "跑通 60 张现场任务卡共 286 条断言；按模板写报告并排版为 DOCX 与 PDF。"],
        ["具体交互与关键提问概述",
                   "① “依据参考资料完成实验并制作报告”；\n"
                   "② “A 组断言报语义信息丢失”——打印码位后确认「5 mg/片」后是全角逗号 U+FF0C "
                   "而非空格，AI 沿用的样例多带了尾随空格；\n"
                   "③ “31 条断言全 PASS 为何反报缺专项断言”“D 类任务卡为何全报否定词丢失”，"
                   "定位到 split(\"[\")[1] 反解组号、以及「未见」须拆成「未」+「见」。"],
        ["采用内容", "多编码探测与 BOM 检查的思路、NFKC 流程、正则掩码并用 subn 统计替换次数、"
                   "否定保护词、断言分层组织、报告章节骨架与排版参数。"],
        ["验证与核对", "AI 产出一律当假设，没跑过的不写进报告：每个数字都由本机跑出来，"
                   "可用 verify_report.py 与 outputs/ 产物比对，88 项检查全过；"
                   "「5 mg/片 」和把「未见」当整词这两处期望值都是核对后改的。"],
        ["收获与反思", "思考题里有两条断言是我第一版凭常识写的，实测后一条被推翻、"
                   "一条引用的字段根本不存在——这类错误只有真跑才会发现。"],
    ], widths=[0.8, 3.6], size=SZ_SMALL, align="left")



    # ================================================================ 七、思考题 ===
    d.h1("七、思考题")

    # 【本节的每一处「实测」数字都来自 verify_thinking.py，可直接复跑核对】
    # 写这一节时踩过的坑：第一版是凭常识推的，其中两条与实测相反——
    #   · 以为 C 组用 utf-8 硬解「不报错只变乱码」——实测是直接抛 UnicodeDecodeError；
    #   · 举了 orderId 当误报例子——实测该字段在本实验十组数据里根本不存在。
    # 思考题恰恰是「用自己的语言总结」得分的地方，写错事实比写得浅更致命。
    thinking = _load_thinking_answers()
    for _title, _paras in thinking:
        d.h2(_title)
        for _p in _paras:
            d.body(_p)

    d.para("电子签名：", size=SZ_BODY, align=0, space_before=4, space_after=3,
           line=17)
    d.para("成绩评定：", size=SZ_BODY, align=0, space_after=2, line=17)


# ---------------------------------------------------------------------------
# 思考题：内置答案（回退用）
# ---------------------------------------------------------------------------
# 【重要】下面这些是**草稿**，评分标准要求「用自己的语言重写」，直接交不得分。
# 重写请写进同目录的 思考题_我的答案.md，本函数会自动优先采用你的版本。
# 每一处「实测」数字都由 verify_thinking.py 从 data/ 现场重算核对，改数据就会报错。
BUILTIN_THINKING = [
    ("思考题 1　为什么不能把所有数字、英文和标点全部删除？结合个人数据举例。", [
        "数字和英文是语义主体，删不得。把数字和字母全去掉，「家庭血压 128/78 mmHg」只剩「家庭血压 /」，" 
        "「科普标签为5 mg/片」只剩「科普标签为 /片」，「空腹血糖为6.2 mmol/L」退成「空腹血糖为. /」——"
        "数值、剂量、单位全没了，剩下的已经不是病历。",
        "标点同样不能删，它的问题只是全角半角混用，所以本实验做的是 NFKC 统一字形，不是删字符。"
        "删掉 D 组的逗号，「脑电图检查未见异常放电，患者无意识障碍，不伴明显头痛」粘成"
        "「脑电图检查未见异常放电患者无意识障碍不伴明显头痛」，否定管到哪一句就读不出来了；"
        "C 组日期原本是全角，归一后是 2026-10-15 09:30，删掉连字符和冒号只剩 20261015 0930。",
    ]),
    ("思考题 2　errors=\"ignore\" 可能造成什么问题？", [
        "危害是让解不开的内容凭空消失，而程序和断言都不吭声。C 组原始 182 字节，"
        "utf-8 硬解在第 0 字节就抛 UnicodeDecodeError；加上 errors=\"ignore\" 之后解码“成功”，"
        "只剩 35 个字符，80.8% 被静默丢掉。",
        "它麻烦的地方是能骗过检查。指导书第 2 条通用断言查的是“不含 U+FFFD”，"
        "而 ignore 是丢弃不是替换，结果里根本没有替换字符，断言照样通过；"
        "换成 errors=\"replace\" 反而留下 118 个 U+FFFD，当场被拦。最后是 C 组"
        "“2026-10-15 09:30 必须保留”那条数据断言碰巧拦住的，可它只拦日期。"
        "脱敏和规范化可以有损，解码不行。",
    ]),
    ("思考题 3　NFKC 规范化可能带来哪些收益和风险？", [
        "收益有三：全角半角统一，正则不用写两套；“２０２６”和“2026”算同一个字符串，检索可靠；"
        "不同来源系统带来的字符差异被抹平。",
        "风险也有三。有损且不可逆；它连标点一起动，实测 C 组的「，」「：」全转成半角（C 组无分号，分号在 B 组），"
        "而中文习惯的“。”(U+3002) 不动，标点风格就中西混了；兼容分解还会改写看着无关的字符，"
        "我实测 ① 会变成 1、㈠ 会变成 (一)、㎡ 会变成 m2。所以规范化只在检索统计环节用，"
        "原始文本另存一份，不原地覆盖。",
    ]),
    ("思考题 4　隐私正则可能产生哪些漏报或误报？", [
        "漏报方面，带连字符的 138-1234-5678、空格分隔的 139 1234 5671、"
        "反垃圾写法的 studentB[at]example[dot]com 都匹配不上；微信、身份证、银行卡这些字段本实验没覆盖。",
        "误报更具体：一串 18 位数字 20261015000012345678 会被掩成 2026101****012345678，"
        "中间 4 位被当成手机号——正则只管形似，不管真假。反过来 C 组归一后的 2026-10-15 09:30、"
        "A 组的 5 mg/片、B 组的 6.2 mmol/L 都没被误伤，靠的是前后数字断言和掩码后长度不变这两条限制。"
        "所以正则脱敏只是第一道防线。",
    ]),
]


def _load_thinking_answers():
    """返回 [(题目标题, [答案段落, ...]), ...]。

    优先读同目录的 思考题_我的答案.md（本人重写版），不存在则回退到内置草稿。
    覆盖文件的格式很松：# 开头是题目标题，其余非空行按出现顺序作为答案段落。

    BOM 陷阱（实测踩过）：用 PowerShell 的 Set-Content -Encoding UTF8 写这个文件，
    Windows 版会加 UTF-8 BOM，于是第一行变成 "﻿# 思考题 1 …"，
    startswith("#") 判 False，**第一道题被静默丢掉**（4 道只认出 3 道）。
    所以这里必须用 encoding="utf-8-sig" 读——它能同时吃下带 BOM 和不带 BOM 的文件。

    文件头的陷阱（实测踩过）：模板里第一行就是 "# 思考题 · 本人答案（把下面内容改成…）"，
    而模板的用法说明恰恰是"另存为 思考题_我的答案.md"——用户最可能的行为就是原样另存。
    于是那一行会被当成**第 1 道题**，报告里渲染出 5 个标题，原先那道真题被挤到第 2 位。
    原来只 print 一句警告就继续，等于默默交了一份错位的报告。
    规则：**第一道题出现之前**的 # 行一律当作文件头丢掉；一旦开始收题，后面的 # 都是题。
    """
    if not THINKING_OVERRIDE.is_file():
        return BUILTIN_THINKING

    raw = THINKING_OVERRIDE.read_text(encoding="utf-8-sig")
    items, cur, skipped = [], None, []
    for line in raw.splitlines():
        line = line.strip().lstrip("﻿").strip()
        if not line:
            continue
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if not items and not re.match(r"思考题\s*\d", title):
                skipped.append(title)        # 还没开始收题 → 当作文件头
                continue
            cur = [title, []]
            items.append(cur)
        elif cur is not None:
            cur[1].append(line)

    if skipped:
        print(f"提示：已跳过 {len(skipped)} 行文件头（未开始收题前出现的 # 行）：{skipped}")
    if not items:
        print("!! 思考题_我的答案.md 里没解析出任何题目，已回退到内置答案")
        return BUILTIN_THINKING
    if len(items) != len(BUILTIN_THINKING):
        print(f"!! 警告：思考题_我的答案.md 解析出 {len(items)} 道题，内置答案有 "
              f"{len(BUILTIN_THINKING)} 道——请确认每道题都各有一个 # 标题行，"
              f"当前解析到的标题：{[t for t, _ in items]}")
    return [(t, p) for t, p in items]


def _com_retry(fn, tries=40, delay=1.5, what=""):
    """
    RPC_E_CALL_REJECTED (-2147418111) / RPC_E_SERVERCALL_RETRYLATER (-2147417846)
    的语义就是"稍后重试"——被调方正忙。这不是脚本 bug，必须重试而不是放弃。
    """
    import pythoncom
    transient = (-2147418111, -2147417846, -2147417851)
    last = None
    for i in range(tries):
        try:
            return fn()
        except pythoncom.com_error as e:
            if e.hresult not in transient:
                raise
            last = e
            time.sleep(delay)
    raise RuntimeError(f"{what} 重试 {tries} 次仍被拒绝：{last}")


def export_pdf(docx_path, pdf_path):
    """
    只用 Word 做一件事：打开已生成好的 docx 并导出 PDF。
    （逐段写入的 COM 方式在本机不稳定，故改为先生成 OOXML、再一次性导出。）
    """
    import win32com.client as wc
    app = _com_retry(lambda: wc.Dispatch("Word.Application"), what="启动 Word")
    app.Visible = False
    app.DisplayAlerts = 0

    doc = _com_retry(lambda: app.Documents.Open(str(docx_path), ReadOnly=True),
                     what="打开文档")
    try:
        # 导出前先让 Word 完成后台分页
        _com_retry(lambda: doc.Repaginate(), what="重新分页")
        pages = _com_retry(lambda: doc.ComputeStatistics(2), what="统计页数")
        words = _com_retry(lambda: doc.ComputeStatistics(0), what="统计字数")
        _com_retry(lambda: doc.ExportAsFixedFormat(str(pdf_path), 17),
                   what="导出 PDF")
    finally:
        try:
            doc.Close(0)
        except Exception:
            pass
        try:
            app.Quit()
        except Exception:
            pass
    return pages, words


THINKING_TEMPLATE_HEADER = """\
# 思考题 · 本人答案（把下面内容改成你自己的话，再另存为「思考题_我的答案.md」）

--------------------------------------------------------------------------------
怎么用
--------------------------------------------------------------------------------
1. 把本文件另存为同目录下的  思考题_我的答案.md
   （文件名必须完全一致，少一个字都不会被读取）
2. 每道题以一个 # 开头的标题行开始，其后的非空行就是答案，按出现顺序填。
3. 改完直接 python make_report.py，报告会用你的版本。

为什么必须这么做
    评分标准原文：思考题「学习理解后用自己的语言进行总结，直接复制 AI 的结果不得分」。
    而本文件里的内容是 AI 写的草稿，只是帮你把**要点和证据**摆齐，
    真正决定得分的是你用自己的话说出来的那些理由。

改写时至少要动的三处
    · 结论用你自己的说法，别沿用草稿里的「所以」「危害是」这类连接词；
    · 每个「我实测」后面，补一句**你当时为什么会这么想**（这是草稿最缺的部分）；
    · 至少挑一道，加上你自己踩过的坑或当时的犹豫——老师看得出这是不是本人写的。

两条硬约束（verify_thinking.py 会替你把关）
    · 数字不能改：35 个字符、80.8%、2026101****012345678 等都由 data/ 现场算出，
      改了就报错。核对命令：python verify_thinking.py
    · 不要举数据里没有的例子：像 orderId 这种字段本实验十组数据中根本不存在，
      写进去会被当场抓出来，也容易被老师追问。

--------------------------------------------------------------------------------
以下为草稿，逐题替换 ↓↓↓↓↓↓↓
"""


def dump_thinking_template(path=None):
    """把内置思考题连同改写指引导出成模板文件。

    模板**不叫** 思考题_我的答案.md，所以不会被自动读取——它只是给你的起点。
    从 BUILTIN_THINKING 生成而不是手抄，免得日后改了内置答案模板却对不上。
    """
    out = Path(path) if path else THINKING_OVERRIDE.with_name(
        "思考题_我的答案_模板.md")
    body = [THINKING_TEMPLATE_HEADER]
    for title, paras in BUILTIN_THINKING:
        body.append("# " + title)
        body.extend(paras)
        body.append("")
    out.write_text("\n".join(body), encoding="utf-8")
    return out


def main():
    if "--dump-thinking" in sys.argv:
        p = dump_thinking_template()
        print(f"模板已写出：{p}")
        print(f"请另存为 {THINKING_OVERRIDE.name} 后再改内容。")
        return

    # ---- 1) DOCX：纯 OOXML 生成，零 COM ----
    # --pdf-only：只出 PDF。DOCX 常被 WPS/Word 打开着而写不进去，
    # 但排版版面两边一致，只出 PDF 足够用来量页数、迭代精简。
    # --docx-out <路径>：改写到别处（WPS 占用正式文件时可先落暂存路径自检）。
    docx_out = DOCX_PATH
    if "--docx-out" in sys.argv:
        docx_out = Path(sys.argv[sys.argv.index("--docx-out") + 1])
    if "--pdf-only" not in sys.argv:
        dx = Doc(DocxBuilder())
        build_cover(dx)
        build_body(dx)
        dx.b.save(docx_out)
        print(f"DOCX : {docx_out}  ({docx_out.stat().st_size // 1024} KB)")
    else:
        print("DOCX : 跳过（--pdf-only）")

    # ---- 2) PDF：reportlab 直出（Word COM 在本机不稳定，改用直出）----
    dp = Doc(PdfDoc(PDF_PATH))
    build_cover(dp)
    build_body(dp)
    dp.b.save()
    print(f"PDF  : {PDF_PATH}  ({PDF_PATH.stat().st_size // 1024} KB)")

    from pypdf import PdfReader
    pages = len(PdfReader(str(PDF_PATH)).pages)
    print(f"PDF 页数：{pages}")
    if pages > 10:
        print("!! 超出指导书规定的 10 页上限，需要精简")

    if THINKING_OVERRIDE.is_file():
        print(f"提示：已采用你自己的思考题答案 —— {THINKING_OVERRIDE.name}")


if __name__ == "__main__":
    main()
