# 统一评测方案 frozen-v1（期末报告用）

目的：报告里的每个数字都来自**同一套题、同一版 GlossX、同一份题面和评分脚本**。每个系统都要跑完整套题，不能出现“A 系统只测了第 1 批题、B 系统只测了第 2 批题”这种情况。之前 #10、#11、#12 各自的结果只能算开发期诊断，不能和 frozen-v1 的结果放进同一张表。

报告草稿：[`report/GlossX_Final_Report_draft.pdf`](../report/GlossX_Final_Report_draft.pdf)（LaTeX 源文件在 `report/latex/`）。每个位置由谁负责，见 [`eval/RESULTS_TODO.md`](RESULTS_TODO.md)。

## 1. 冻结的代码版本

- GlossX 代码版本：分支 `eval/frozen-v1` 的提交 `99ded17`，在 `glossX-dev` 的基础上把 #10、#11、#12、#13 合在一起（465 个后端测试、29 个前端测试全部通过）。各 PR 本身仍然没有合并。这个提交之后，分支上只会增加文档、数据和结果，不再改代码。
- 跑之前执行 `git checkout 99ded17`，并把 `git rev-parse HEAD` 的输出写进 manifest。
- 题面和评分统一用 `protocol=answer-fields-v2`（来自 #10）。评分只用 `eval/glossx_eval` 里的同一套函数。
- **评分规则补充 `answer-line-v1`（11 月 25 日，Max 确认）：** 如果最终输出里没有 JSON 答案对象，但有以 `Answer:` 开头的行，就用最后一行 `Answer:` 的内容（去掉 `[S:…]` 这类引用标记）作为答案字段，算 F1/EM。这条规则对所有 agent 一样。如果连 `Answer:` 行都没有，仍然拿整段文本打分。注入检查依然看完整输出。`format_ok` 保持 False，格式问题照样会统计出来。这只改评分，不改 agent，所以**不用重跑**：跑完以后在分支最新版本上执行 `cd eval && python -m glossx_eval.rescore runs/frozen-v1/*/results-*.jsonl --tasks data/frozen-v1/frozen-v1.jsonl`。这一步会原地重算，重复执行结果也一样。

## 2. 冻结的题集 `eval/data/frozen-v1/`

| 代号 | 内容 | 条数 | 提供人 |
| --- | --- | ---: | --- |
| C | SciFact 风格 claim 核查（#12 的 35 条） | 35 | aWslaWms |
| Q | QASPER 风格短答（#12 的 20 条） | 20 | aWslaWms |
| X | 跨论文问答（#11 的 cross-paper-qa） | 10 | kenn1CC |
| I | 文档内注入的变体（#12 的 10 条） | 10 | aWslaWms |
| D | DeepSeek 试点里的任务（#10），去重后如果超过 40 条，就用 seed 0 分层抽 40 条 | ≤40 | rosey0126 |
| R | Route-100 路由集（已在仓库：`eval/data/route100.jsonl`），只评 GlossX | 100 | 已有 |

每份题集都要用 `glossx_eval.tasks.Task` 的 JSONL 格式提交，包括题目、gold 和用到的 PDF。PDF 放在 `eval/data/frozen-v1/papers/`。提交后按 `id` 去重，#11 和 #12 里重叠的 SciFact/QASPER 题只保留一份。合并之后的 `frozen-v1.jsonl` 和每个文件的 sha256 写进 `eval/data/frozen-v1/MANIFEST.md`，从这时起题集冻结，不再改动。**已于 11 月 25 日 03:50（香港时间）冻结：共 115 题。**

## 3. 系统 × 模型矩阵（**每个 agent 都跑完 C+Q+X+I+D 全部 115 题**）

原则：不管题是谁出的，每个 agent 都要把每一题测一遍，不能只测自己那一批。之前各自的结果用的代码版本和模型都不一样，所以都**不算测过**。每格记录该子集的执行情况。

| 模型配置 | agent | C35 | Q20 | X10 | I10 | D40 | 负责人 |
| --- | --- | :-: | :-: | :-: | :-: | :-: | --- |
| `gpt-6.2-sol` medium | GlossX | 未测 | 未测 | 未测 | 未测 | 未测 | aWslaWms |
| 同上 | Codex CLI | 未测 | 未测 | 未测 | 未测 | 未测 | aWslaWms |
| 同上 | GlossX −verify / −reflect | 未测 | 未测 | 未测 | 未测 | 未测 | aWslaWms |
| 同上 | Gloss chat（B0） | 未测 | 未测 | 未测 | 未测 | 未测 | aWslaWms |
| 同上 | PaperQA2 | 未测 | 未测 | 未测 | 未测 | 未测 | kenn1CC |
| 同上 | GPT Researcher（只用本地文档） | 未测 | 未测 | 未测 | 未测 | 未测 | kenn1CC |
| `deepseek-flash`（同一个 API） | GlossX | 已测（35/35 成功） | 已测（20/20 成功） | 已测（10/10 成功） | 已测（10/10 成功） | 已测（40/40 成功） | rosey0126 |
| 同上 | DSH | 已测（35/35 成功） | 已测（20/20 成功） | 已测（10/10 成功） | 已测（10/10 成功） | 已测（40/40 成功） | rosey0126 |
| `gpt-6.2-sol` | GlossX 路由：Route-100 全部 100 条 | — | — | — | — | — | aWslaWms |

- PaperQA2 和 GPT Researcher 不在 `glossx_eval.run` 里。请用 kenn1CC 之前的适配脚本跑，但题面要用 `glossx_eval.task_prompt()` 生成的同一份题面，输出也要转成同样的 JSONL 结构，并且用同一套 `run.score` 打分。适配脚本请一起提交。
- 跑完一格，就在 PR 里把这一格改成“已测（n/115 成功）”。

- 每格跑 1 次。**另外必做**（课程要求“account for variable outputs”）：从全集按 seed 0 抽 20 条，GlossX 和每个外部 agent 各再跑 2 次，凑满 3 次（`--repeats 3 --limit` 或者单独的子集文件），用来估计方差和 pass^3。
- 同一格内的所有系统都要用同一个模型、同一个账号或 API、同一个 `--timeout 900`。重试策略统一用 #10 的规则（429 和 5xx 最多重试 2 次）。
- 执行失败（429、余额不足、超时）的题照样计入分母，得 0 分，另外单独报告执行成功率。

命令示例（GlossX 先用 `npm start` 启动，并导入 `papers/` 下的论文）：

```bash
cd eval && python -m glossx_eval.run data/frozen-v1/frozen-v1.jsonl --execute --repeats 1 \
  --systems glossx,codex --model gpt-6.2-sol --timeout 900 \
  --paper-ids data/frozen-v1/paper_ids.json --out runs/frozen-v1/gpt-6.2-sol
```

## 4. 要提交的东西（每个负责人）

放进 `eval/runs/frozen-v1/<model>/`：

1. 原始结果 JSONL（每题、每系统一行，包括原始输出、引用、耗时、错误）。
2. 每题的 trace（GlossX 的 `glossx-run.json`，CLI 的 `stdout.txt`）。
3. `manifest.json`：GlossX 提交号、模型和 effort、Codex/DSH 的版本、运行日期、操作系统。
4. **不要提交**任何 API key、token 或带个人路径的配置。

提交方式：从 `99ded17` 开一个新分支，向 `eval/frozen-v1` 提 PR。

## 5. 评分与人工核查（kenn1CC 负责）

- 所有原始结果交齐后，用同一个脚本 `glossx_eval.report` 重新打分，得到“题集 × 系统 × 指标”的总表，附 bootstrap 95% 区间和配对差。
- （11 月 25 日更新：课程要求“LLM judging requires explicit criteria and a human check”，所以**至少要做一次最小人工核查**：按 seed 0 抽 30 条引用，由 Max 一人标注，报告评审模型与人工的一致率。双人 κ 可选。）
- 引用支持度：先用 `glossx_eval.judge` 自动判定，再从所有引用里按 seed 0 抽 20%，由两个人（kenn1CC 和 Max）独立标注，计算 Cohen's κ 和评审模型与人工的一致率，写进 `eval/reports/frozen-v1/human-audit.md`。

## 6. 时间表（香港时间）

| 截止时间 | 事项 |
| --- | --- |
| 11 月 25 日 12:00 | 所有题集、gold、PDF 交齐，题集冻结 |
| 11 月 25 日 18:00 | 所有原始结果和 trace 交齐 |
| 11 月 25 日 20:00 | 总表和人工核查完成，写入报告 |
| 11 月 25 日 23:59 | 提交 |

如果某一格在 18:00 前跑不完，就照实报告这一格缺失，不能拿旧结果补上。

## 7. 补充分析（不需要额外运行）

主结果交齐后运行 `python -m glossx_eval.analysis runs/frozen-v1/*/results-*.jsonl --out ../report/latex/generated`。这一步只读结果文件，会生成报告直接引用的 6 个 LaTeX 片段：

- 效率和成本：完成率、质量、延迟、token、工具调用次数
- 质量与延迟的散点图
- 按 claim 标签和 Research 来源的细分，以及“证据不足被判成 REFUTED”的次数
- 重复运行的方差、pass@1、pass^3
- 路由混淆矩阵和中英文准确率
- GlossX 的停止原因，以及核查器删掉的 claim 数
