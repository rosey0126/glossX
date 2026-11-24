# D 旧诊断任务冻结子集

本子集从上一轮实际记录的 90 个旧 task IDs 中选择 40 题。旧实验仅用于诊断；本目录没有新实验结果，也不能将旧结果称为在这个 PDF 协议上的新测试结果。

本次只交付 D。C/Q/X/I 尚未交付或冻结，与未来 C/Q 的原 ID 及内容交叉去重尚不能执行，不能宣称全套题组已冻结。

实际原始候选池是合成控制任务 test 40 题、SciFact dev 30 题、QASPER dev v0.3 20 题，共 90 个旧 ID；合成任务每族第 1 个 dev 变体没有进入候选池。规范化去重与抽样只使用题面、材料内容、旧 ID 与层，不将 gold、胜负、分数或错误状态作为依据。仅对 controlled 删除用于编号的 `# Controlled research case research-*` 标题，并规范化 Trial-N 与 Evaluation record N 两个编号短语；保留真实数值与公共文献标题。在 Unicode、大小写和空白规范化之后，90 个原 ID 得到 86 个内容唯一任务，共 2 个重复组、4 个 alias。每组以字典序最小原 ID 代表，完整 alias 映射见 manifest 与 pool JSONL。合成题同族仍是相关的参数变体，不能视为彼此独立的科研场景。

抽样固定 seed=0。对去重后的 86 题，按 10 个 controlled family 加 scifact/qasper 共 12 个候选层比例分配，使用纯 Hamilton 最大余数法，不加事后每族保底。余数相同时先把按名称排序的层用 Random(seed).shuffle 打乱，固定打破平局；随后使用独立 Random(seed)，按层名顺序对排序后的 ID 抽样。结果抽中 11 层：SciFact 14、QASPER 9、controlled 17；citation 层去重后仅 1 题，在比例分配中配额为 0。保留原 task IDs；未根据模型表现筛题。

| 层 | 内容去重后旧池题数 | D 题数 |
| --- | --- | --- |
| budget | 4 | 2 |
| citation | 1 | 0 |
| claim | 3 | 1 |
| composition | 4 | 2 |
| injection | 4 | 2 |
| leakage | 4 | 2 |
| metrics | 4 | 2 |
| missing | 4 | 2 |
| multiplicity | 4 | 2 |
| qasper | 20 | 9 |
| replication | 4 | 2 |
| scifact | 30 | 14 |

`d-deepseek.jsonl` 使用原生 Task schema：id、suite、kind、question、papers、gold。题面保持原文。controlled claim 族转为 claim，INSUFFICIENT 映射 NOT ENOUGH EVIDENCE；其余 controlled 转为 qa，短参考答案从已有 decision 与数值构造，含适合单位的四舍五入变体。public 题保留原 kind 与 gold。这是格式转换，不是新真值。原始 gold 在 gold.original_gold 中；旧结构数值、决策与引文规则另保留于 legacy_structured_criteria，不作为原生评分规则。QA token-F1 只是短参考的词元重合度，不能替代科研正确性或语义证据审查。

每份选中 Markdown 单独渲染为 PDF，Task.papers 仅列 papers/ 中的 PDF；sidecars/ 保留原文字材料用于审查。所有 PDF 文件名都有 D 与 task ID 前缀。PDF 明示旧文件名，打印从 1 开始的页码。QASPER PDF 是发布的 S2ORC 文字与图表标题排版，SciFact PDF 是发布摘要排版，合成 PDF 是旧控制材料排版；都不是原 arXiv/出版商 PDF，未添加图表像素。没有复制下载的原论文 PDF。旧 source_*.md p1、段落标识或 SciFact 句索引保留为旧协议证据，不能自动当成新 PDF 页码或已核验的语义支持；详见 document-map。

`d-deepseek.manifest.json` 包含源文件 SHA256、90 题去重信息、12 层配额、固定选择 ID 与交付文件哈希；`d-deepseek.pool.jsonl` 列出整个旧池的内容指纹。金标只供评分与人工审阅，执行时仅将题面及 Task.papers 指定 PDF 交给代理，不能让代理读取本目录金标、manifest 或其他题材料。

来源与许可：SciFact claims/annotations 为 CC BY 4.0，摘要 corpus 为 ODC-By 1.0，见 https://github.com/allenai/scifact/blob/master/LICENSE.md 。QASPER 数据卡声明 CC BY 4.0，见 https://huggingface.co/datasets/allenai/qasper 。SciFact: Wadden et al., Fact or Fiction: Verifying Scientific Claims, EMNLP 2020。QASPER: Dasigi et al., A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers, NAACL 2021。S2ORC: Lo et al., S2ORC: The Semantic Scholar Open Research Corpus, ACL 2020。相应许可链接为 https://creativecommons.org/licenses/by/4.0/ 与 https://opendatacommons.org/licenses/by/1-0/ 。本冻结做了子集抽样、schema 转换和文字至 PDF 的排版转换；原来源不为本评测背书。
