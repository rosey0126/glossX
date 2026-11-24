# 报告里待填的结果：谁负责、填什么

**先看报告**：当前草稿的 PDF 在 [`report/GlossX_Final_Report_draft.pdf`](../report/GlossX_Final_Report_draft.pdf)。第 4 节介绍题集，第 5 节是实验设置，第 6 节是结果。红色粗体的 `[...]` 是待填的地方。先通读一遍，就知道你跑的实验最后会出现在报告的哪个位置。

报告源文件（相当于 Overleaf）：本分支的 [`report/latex/main.tex`](../report/latex/main.tex)，同步自报告主分支 `claude/project-thread-27yj55` 的 `8de8d7f`。编译方法：`cd report/latex && latexmk -pdf main.tex`，或者把整个 `report/latex/` 目录上传到 Overleaf。红色粗体的 `[...]` 就是 `\TBD{}`，表示还没填的地方。用 `grep -n TBD report/latex/main.tex` 可以列出全部待填位置。

**子集名称对照**：报告里不用单字母代号，而用完整名称，对应关系是 C = `Claim`、Q = `ShortQA`、X = `CrossPaper`、I = `Injection`、D = `Research`、R = `Route`。题集介绍在报告新增的第 4 节“Evaluation data”。

**怎么填**：只改自己负责的 `\TBD{}`，数字要和 `eval/reports/frozen-v1/summary.json` 一致。改完后向 `eval/frozen-v1` 提 PR，我们再同步回报告主分支。其他段落请不要改，避免和正在改写的报告冲突。没跑的格子写 `n/a`，并在 PR 里说明原因，不要用旧结果补。

| 位置 | 内容 | 数据来源（谁跑） | 谁填进报告 | 截止（香港时间，11 月 25 日） |
| --- | --- | --- | --- | --- |
| 主表 `tab:main`，gpt-6.2-sol 这组列 | 所有 agent 并排放在一张表里，按底座模型分组。gpt-6.2-sol 组的列依次是 GlossX、Codex CLI、PaperQA2、GPT Researcher、−verify、−reflect、Gloss chat。每列都要覆盖全部 115 题，表里只填点估计 | aWslaWms（GlossX、Codex、消融、Gloss chat）、kenn1CC（PaperQA2、GPT Researcher） | kenn1CC（统一评分） | 20:00 |
| §6.1 “General and research agents” 段 | GlossX 对 Codex、PaperQA2、GPT Researcher 的配对差，各自擅长哪些题、引用、注入、延迟 | aWslaWms（Codex）、kenn1CC（PaperQA2、GPT Researcher）一起起草 | kenn1CC 核对数字 | 21:00 |
| §6.1 “Ablations and the single-prompt baseline” 段 | 去掉 verify 和去掉 reflect 各自的影响，以及相对 Gloss chat 的提升 | aWslaWms | aWslaWms | 21:00 |
| 主表 `tab:main`，deepseek-flash 这组列 | GlossX 和 DSH 两列 | rosey0126 | kenn1CC（统一评分） | 20:00 |
| 附录 `app:ci` | 主表每一格的 95% bootstrap 区间、组内配对差，以及按类型分列的失败情况 | — | kenn1CC | 20:00 |
| 新增 agent | 如果还想并排加别的 agent，必须在**同一组模型**下、跑**完整的题集**，在主表的对应组里加一列，并在这里登记负责人 | 待定 | 待定 | 18:00 |
| §6.1 “Same model and API, different harness” 段 | 重试策略有没有补上执行成功率的差距；两边都跑完的题上，质量有没有差别 | rosey0126 | rosey0126 | 21:00 |
| §6.2 图表（成本、方差、分组细分）和附录 D（路由混淆、GlossX 内部统计） | 由 `python -m glossx_eval.analysis` 自动生成 `report/latex/generated/*.tex`，报告会自动引用，不用手填 | 全部原始结果（方差需要 E7 的重复运行） | kenn1CC 运行脚本并提交 `generated/` | 20:00 |
| §6.2 三段分析：Cost、Consistency、Failure types | 每段 1–2 句，再从 trace 里挑一个具体的失败案例 | — | kenn1CC 起草，aWslaWms 补 Codex 部分 | 21:00 |
| §6.3 路由 | 准确率填进正文，混淆矩阵自动生成，再写一句哪些工作流容易混淆 | aWslaWms | kenn1CC | 20:00 |
| §6.1 人工核查（**课程硬性要求**） | 至少抽 30 条引用，由一人标注，报告评审模型与人工的一致率 | Max | Max | 21:00 |
| 非功能指标表 | C+Q 上 GlossX 和 Codex 的延迟及比值、X 的延迟、I 中被注入成功的条数 | 来自主表 | kenn1CC | 20:00 |
| §6.7 错误分析 | 每组挑 1–2 个失败的题，写明题号、错在哪、trace 路径 | 各自的跑分人 | aWslaWms、rosey0126 | 21:00 |
| 实验设置里的方差（**课程硬性要求**） | 20 题 × 3 次重复的设置说明 | aWslaWms | aWslaWms | 20:00 |
| 贡献 | 每人写一到两行，说明自己负责了什么 | 每位成员 | 每位成员 | 21:00 |
| 摘要、结论 | 用最终结果写一句结论 | — | 报告主笔 | 22:00 |
