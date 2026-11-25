# GlossX 期末报告（草稿）

`latex/main.tex` 沿用 proposal 的 NeurIPS 2026 模板，`figures/` 和 `references.bib` 从 `proposal/latex/` 复制。

- 系统设计、工作流、实现部分按当前代码写实；可扩展性表格来自 `python -m glossx_eval.extensibility`。
- 所有还需要真实评测才能填的地方都用红色 `\TBD{...}` 标出：`grep -n TBD latex/main.tex` 可列出全部待填项。
- 课程的正式要求（页数、章节）到位后再调整结构。

编译：

```bash
cd latex && latexmk -pdf main.tex
```
