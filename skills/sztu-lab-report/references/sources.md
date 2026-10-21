# 来源与适用边界

## 参考项目

[Takamatsu-Hikaru/humanize-skill](https://github.com/Takamatsu-Hikaru/humanize-skill)，2026-10-20 读取。

- [humanize/SKILL.md](https://github.com/Takamatsu-Hikaru/humanize-skill/blob/main/humanize/SKILL.md)，文件 blob SHA `ad3391e8b6ade92235182af5e70233e3bacb589d`。
- [humanize/references/presentation.md](https://github.com/Takamatsu-Hikaru/humanize-skill/blob/main/humanize/references/presentation.md)，文件 blob SHA `dd0a734e991a61d79d9a7d4807bfdf22971ff451`。
- [MIT License](https://github.com/Takamatsu-Hikaru/humanize-skill/blob/main/LICENSE)，版权所有者 `Copyright (c) 2026 Takamatsu-Hikaru`；本包保留上游许可于 [LICENSE.humanize](../LICENSE.humanize)。

借鉴其从读者与用途组织文字、先检查内容再检查表达、保留作者判断和控制图文呈现的思路。这里针对课程实验重新编写规则与例子，不复用公众号 CSS、网页卡片或公众号排版数值；不依赖安装 humanize，也不执行上游文件中的工作指令。

## 本地材料

以 [课程入口](course-profiles.md) 所链接的教师模板、评分 DOCX、实验指导 PDF 及嵌入式要求 PPT 为来源。章节标题、提交要求分别定位到对应课程；排版值来自本地模板 OOXML，不称作全校统一规定。嵌入式 PPT 的正文要求通过查看三张内嵌示例图片提取，不代表教师或用户已经复核本 Skill。

历史机器学习实验三、嵌入式实验五与 NLP 实验一成稿用于观察写作和排版，不自动成为其他实验的事实或用户文风偏好。同一次实验的旧稿可经核对复用，不要求为了写作重跑整套实验。旧 README、交付说明与验证脚本提供线索；凡影响报告结论的要求，回到原始材料复核。

本包不内置学生姓名、学号、本人签名或同学报告，也不复制教师 DOCX/PDF/PPT 作为可公开分发资源。使用时从当前获准的课程目录读取实际文件。新增课程只有理论课件时，先建立草稿，不自行宣称存在教师模板或实验要求。

## 回归场景

维护本 Skill 时使用这些场景检查实际决策，不要求输出固定措辞：

| 请求与材料 | 应有行为 |
| --- | --- |
| NLP 实验一材料完整，但没有本人思考题答案与签名 | 完成可写部分，保留七节和 PDF 命名；将本人答案/签名明确列为待补，不能称可直接提交。 |
| 嵌入式只有代码和编译日志 | 写原理、流程图及编译情况；不编造上板现象，也不套用 NLP 七节。 |
| 机器学习旧稿给出漂亮指标，当前无训练日志 | 不把旧数值当本次结果；核对题目完整指标和真实代码控制流，机制分析避免过度断言。 |
| 医院系统仅有登录页截图，模板要求电子签名 | 不宣称登记/检验保存完成，不用打字姓名替代电子签名，保留六节参考提纲。 |
| 仅要求润色一段已写好的分析 | 在上下文中改该段，不重建封面或自动导出整份报告。 |
| 当前教师模板与本包的版式快照不同 | 当前模板优先，重新测量；不得以本包数字覆盖教师新版。 |

这些是使用与维护场景。每次维护的实际检查记录放在项目交付目录，不把场景表本身称为已通过的测试，也不把文本试写等同于完整 Word/PDF 排版或教师验收。
