# 统一评测方案 frozen-v1（期末报告用）

目的：报告里的每个数字都来自**同一套题、同一版 GlossX、同一份题面和评分脚本**。每个系统都要跑完整套题，不能出现“A 系统只测了第 1 批题、B 系统只测了第 2 批题”这种情况。之前 #10、#11、#12 各自的结果只能算开发期诊断，不能和 frozen-v1 的结果放进同一张表。

## 1. 冻结的代码版本

- GlossX 代码版本：分支 `eval/frozen-v1` 的提交 `99ded17`，在 `glossX-dev` 的基础上把 #10、#11、#12、#13 合在一起（465 个后端测试、29 个前端测试全部通过）。各 PR 本身仍然没有合并。这个提交之后，分支上只会增加文档、数据和结果，不再改代码。
- 跑之前执行 `git checkout 99ded17`，并把 `git rev-parse HEAD` 的输出写进 manifest。
- 题面和评分统一用 `protocol=answer-fields-v2`（来自 #10）。评分只用 `eval/glossx_eval` 里的同一套函数。

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

## 3. 系统 × 模型矩阵（每一格都跑 C+Q+X+I+D 全集）

| 模型配置 | 系统 | 负责人 |
| --- | --- | --- |
| `gpt-6.2-sol`，medium（Codex CLI 账号） | GlossX、Codex CLI（**重新跑，不复用旧结果**） | aWslaWms |
| 同上，只跑 C+Q+X | 消融：`glossx-noverify`、`glossx-noreflect`；基线：`gloss-chat`（B0） | aWslaWms |
| `deepseek-flash`（同一个 API） | GlossX、DeepSeek Harness（DSH） | rosey0126 |
| GlossX，`gpt-6.2-sol` | R：Route-100 全部 100 条 | aWslaWms |

- 每格跑 1 次。如果时间够，再从全集按 seed 0 抽 20 条，每格重复 3 次，用来估计方差。
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
- （11 月 25 日更新：人工抽检暂缓，先只做自动判定，结果标注“未经人工核查”。）
- 引用支持度：先用 `glossx_eval.judge` 自动判定，再从所有引用里按 seed 0 抽 20%，由两个人（kenn1CC 和 Max）独立标注，计算 Cohen's κ 和评审模型与人工的一致率，写进 `eval/reports/frozen-v1/human-audit.md`。

## 6. 时间表（香港时间）

| 截止时间 | 事项 |
| --- | --- |
| 11 月 25 日 12:00 | 所有题集、gold、PDF 交齐，题集冻结 |
| 11 月 25 日 18:00 | 所有原始结果和 trace 交齐 |
| 11 月 25 日 20:00 | 总表和人工核查完成，写入报告 |
| 11 月 25 日 23:59 | 提交 |

如果某一格在 18:00 前跑不完，就照实报告这一格缺失，不能拿旧结果补上。
