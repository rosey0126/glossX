# 报告里待填的结果：谁负责、填什么

报告源文件（相当于 Overleaf）：本分支的 [`report/latex/main.tex`](../report/latex/main.tex)，同步自报告主分支 `claude/project-thread-27yj55` 的 `abb8d2d`。编译方法：`cd report/latex && latexmk -pdf main.tex`，或者把整个 `report/latex/` 目录上传到 Overleaf。红色粗体的 `[...]` 就是 `\TBD{}`，表示还没填的地方。用 `grep -n TBD report/latex/main.tex` 可以列出全部待填位置。

**怎么填**：只改自己负责的 `\TBD{}`，数字要和 `eval/reports/frozen-v1/summary.json` 一致。改完后向 `eval/frozen-v1` 提 PR，我们再同步回报告主分支。其他段落请不要改，避免和正在改写的报告冲突。没跑的格子写 `n/a`，并在 PR 里说明原因，不要用旧结果补。

| 位置 | 内容 | 数据来源（谁跑） | 谁填进报告 | 截止（香港时间，11 月 25 日） |
| --- | --- | --- | --- | --- |
| 主表 `tab:main`，gpt-6.2-sol 这组列 | 所有 agent 并排放在一张表里，按底座模型分组。gpt-6.2-sol 组的列依次是 GlossX、Codex CLI、−verify、−reflect、Gloss chat；表里只填点估计 | aWslaWms | kenn1CC（统一评分） | 20:00 |
| 主表下的分析段 | 5 点分析：配对差、去掉 verify 的影响、去掉 reflect 的影响、相对 Gloss chat 的提升、注入结果。每点 1–2 句 | aWslaWms 起草 | kenn1CC 核对数字 | 21:00 |
| 主表 `tab:main`，deepseek-flash 这组列 | GlossX 和 DSH 两列 | rosey0126 | kenn1CC（统一评分） | 20:00 |
| 附录 `app:ci` | 主表每一格的 95% bootstrap 区间、组内配对差，以及按类型分列的失败情况 | — | kenn1CC | 20:00 |
| 新增 agent | 如果还想并排加别的 agent，必须在**同一组模型**下、跑**完整的题集**，在主表的对应组里加一列，并在这里登记负责人 | 待定 | 待定 | 18:00 |
| §5.2 DSH 对比的分析段 | 重试策略有没有补上执行成功率的差距；两边都跑完的题上，质量有没有差别 | rosey0126 | rosey0126 | 21:00 |
| §5.3 路由 | Route-100 中选对了几条、准确率，按工作流分列错误 | aWslaWms | kenn1CC | 20:00 |
| 表 4 非功能指标 | C+Q 上 GlossX 和 Codex 的延迟及比值、X 的延迟、I 中被注入成功的条数 | 来自主表 | kenn1CC | 20:00 |
| §5.7 错误分析 | 每组挑 1–2 个失败的题，写明题号、错在哪、trace 路径 | 各自的跑分人 | aWslaWms、rosey0126 | 21:00 |
| 实验设置里的方差 | 如果跑了 20 题 × 3 次重复，就写结果；没跑就删掉这句 | aWslaWms | aWslaWms | 20:00 |
| §5.1 人工核查 | 已暂缓。如果补做了抽检，就填 n、κ 和一致率；否则删掉这段 | Max | Max | 21:00 |
| 贡献 | 每人写一到两行，说明自己负责了什么 | 每位成员 | 每位成员 | 21:00 |
| 摘要、结论 | 用最终结果写一句结论 | — | 报告主笔 | 22:00 |
