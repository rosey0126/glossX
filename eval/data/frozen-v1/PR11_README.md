# PR #11 Task Delivery (`X10` + 50-Task Set)

- **Contributor**: `kenn1CC`
- **Target branch**: `eval/frozen-v1` (data-only delivery; does not modify code or declare the combined `frozen-v1.jsonl` frozen)
- **Delivered files**:
  - `x10.jsonl` — 10 `cross-paper-qa` tasks (`cross-01`..`cross-10`), corresponding to **X10** in `eval/UNIFIED_PROTOCOL.md` (SHA-256: `82992c804b47315ffccb1cb3e83f2230c4bb8cf6db492bb04aeabc5737753213`)
  - `pr11-50.jsonl` — All 50 tasks from PR #11 (`cross-paper-qa` 10 + `scifact` 20 + `qasper` 20) in native `glossx_eval.tasks.Task` format (SHA-256: `196d76ec8f0076afe37dfda27d4bde0ad09b621543f59650454f160f9a1701f7`)
  - `papers/` — All 43 referenced PDFs (20 SciFact abstract PDFs + 23 full-paper arXiv PDFs; 0 filename collisions with PR #14 `D-*.pdf`)
  - `pr11-50.manifest.json` — Per-file SHA-256 checksums and upstream source IDs for deduplication

## Overlap Status with PR #12 (55 Tasks) and PR #14 (`D40`)

1. **Overlap with PR #12 (`C35` + `Q20`, 55 tasks)**: **Cannot be finalized yet because PR #12 has not uploaded its task JSONL** (only `eval/reports/glossx-vs-codex-55.md` is currently present on `feat/routing-short-answer` / `eval/frozen-v1`). Note that PR #12's report cites custom local IDs (e.g. `E40-12`), whereas our JSONL uses sequential local IDs (`scifact-01..20`, `qasper-01..20`) with full upstream metadata in `gold.source`. Once `aWslaWms` uploads C35/Q20 JSONL, deduplication should check **both** `id` and upstream `claim_id` / `question_id` / normalized `question` text.
2. **Overlap with PR #14 (`D40`, `d-deepseek.jsonl`)**: Checked against PR #14's 40 selected tasks by normalized question text, SciFact `claim_id`, and QASPER `question_id` — **0 overlaps**.

## Upstream IDs for Deduplication

### SciFact 20 (`scifact-01`..`scifact-20`, SciFact dev)

| Local ID | `claim_id` | `corpus_id` | Gold Label | PDF |
| --- | ---: | ---: | --- | --- |
| `scifact-01` | `921` | `1642727` | `SUPPORTED` | `papers/1642727.pdf` |
| `scifact-02` | `163` | `18872233` | `SUPPORTED` | `papers/18872233.pdf` |
| `scifact-03` | `239` | `14079881` | `SUPPORTED` | `papers/14079881.pdf` |
| `scifact-04` | `982` | `2988714` | `SUPPORTED` | `papers/2988714.pdf` |
| `scifact-05` | `436` | `14637235` | `SUPPORTED` | `papers/14637235.pdf` |
| `scifact-06` | `1012` | `9745001` | `SUPPORTED` | `papers/9745001.pdf` |
| `scifact-07` | `1298` | `11718220` | `SUPPORTED` | `papers/11718220.pdf` |
| `scifact-08` | `233` | `4388470` | `REFUTED` | `papers/4388470.pdf` |
| `scifact-09` | `1339` | `15482274` | `REFUTED` | `papers/15482274.pdf` |
| `scifact-10` | `212` | `22038539` | `REFUTED` | `papers/22038539.pdf` |
| `scifact-11` | `219` | `21366394` | `REFUTED` | `papers/21366394.pdf` |
| `scifact-12` | `54` | `49556906` | `REFUTED` | `papers/49556906.pdf` |
| `scifact-13` | `532` | `12991445` | `REFUTED` | `papers/12991445.pdf` |
| `scifact-14` | `1144` | `10071552` | `REFUTED` | `papers/10071552.pdf` |
| `scifact-15` | `128` | `8290953` | `NOT ENOUGH EVIDENCE` | `papers/8290953.pdf` |
| `scifact-16` | `1197` | `25649714` | `NOT ENOUGH EVIDENCE` | `papers/25649714.pdf` |
| `scifact-17` | `870` | `195689316` | `NOT ENOUGH EVIDENCE` | `papers/195689316.pdf` |
| `scifact-18` | `535` | `39368721` | `NOT ENOUGH EVIDENCE` | `papers/39368721.pdf` |
| `scifact-19` | `437` | `18399038` | `NOT ENOUGH EVIDENCE` | `papers/18399038.pdf` |
| `scifact-20` | `820` | `8646760` | `NOT ENOUGH EVIDENCE` | `papers/8646760.pdf` |

### QASPER 20 (`qasper-01`..`qasper-20`, QASPER v0.3 dev)

| Local ID | `question_id` | arXiv ID | PDF |
| --- | --- | --- | --- |
| `qasper-01` | `7561a968470a8936d10e1ba722d2f38b5a9a4d38` | `1605.06083` | `papers/1605.06083.pdf` |
| `qasper-02` | `b6ae8e10c6a0d34c834f18f66ab730b670fb528c` | `1609.00425` | `papers/1609.00425.pdf` |
| `qasper-03` | `a87a009c242d57c51fc94fe312af5e02070f898b` | `1609.00425` | `papers/1609.00425.pdf` |
| `qasper-04` | `9ee07edc371e014df686ced4fb0c3a7b9ce3d5dc` | `1704.06194` | `papers/1704.06194.pdf` |
| `qasper-05` | `d3aa0449708cc861a51551b128d73e11d62207d2` | `1704.06194` | `papers/1704.06194.pdf` |
| `qasper-06` | `113d791df6fcfc9cecfb7b1bebaf32cc2e4402ab` | `1708.01464` | `papers/1708.01464.pdf` |
| `qasper-07` | `55c8f7acbfd4f5cde634aaecd775b3bb32e9ffa3` | `1708.01464` | `papers/1708.01464.pdf` |
| `qasper-08` | `ef4dba073d24042f24886580ae77add5326f2130` | `1801.05147` | `papers/1801.05147.pdf` |
| `qasper-09` | `2df4a045a9cd7b44874340b6fdf9308d3c55327a` | `1801.05147` | `papers/1801.05147.pdf` |
| `qasper-10` | `bd5bd1765362c2d972a762ca12675108754aa437` | `1804.05918` | `papers/1804.05918.pdf` |
| `qasper-11` | `d9b6c61fc6d29ad399d27b931b6cb7b1117b314a` | `1809.04267` | `papers/1809.04267.pdf` |
| `qasper-12` | `18c5d366b1da8447b5404eab71f4cc658ba12e6f` | `1810.08699` | `papers/1810.08699.pdf` |
| `qasper-13` | `1f085b9bb7bfd0d6c8cba1a9d73f08fcf2da7590` | `1810.08699` | `papers/1810.08699.pdf` |
| `qasper-14` | `37861be6aecd9242c4fdccdfcd06e48f3f1f8f81` | `1811.00383` | `papers/1811.00383.pdf` |
| `qasper-15` | `7e62a53823aba08bc26b2812db016f5ce6159565` | `1811.00383` | `papers/1811.00383.pdf` |
| `qasper-16` | `891c2001d6baaaf0da4e65b647402acac621a7d2` | `1909.00512` | `papers/1909.00512.pdf` |
| `qasper-17` | `3d013f15796ae7fed5272183a166c45f16e24e39` | `1909.09067` | `papers/1909.09067.pdf` |
| `qasper-18` | `9a05a5f4351db75da371f7ac12eb0b03607c4b87` | `1912.01214` | `papers/1912.01214.pdf` |
| `qasper-19` | `31735ec3d83c40b79d11df5c34154849aeb3fb47` | `2002.03407` | `papers/2002.03407.pdf` |
| `qasper-20` | `c21b87c97d1afac85ece2450ee76d01c946de668` | `2002.03407` | `papers/2002.03407.pdf` |

### Cross-Paper QA 10 (`X10`: `cross-01`..`cross-10`)

| Local ID | Topic | Required Points | PDFs |
| --- | --- | ---: | --- |
| `cross-01` | WMT14 英译德 BLEU | 5 | `papers/1706.03762v7.pdf`, `papers/1705.03122v3.pdf` |
| `cross-02` | 机器翻译解码条件 | 5 | `papers/1706.03762v7.pdf`, `papers/1705.03122v3.pdf` |
| `cross-03` | 预训练任务与遮盖方式 | 5 | `papers/1810.04805v2.pdf`, `papers/1907.11692v1.pdf` |
| `cross-04` | 同一开发集的性能对照 | 4 | `papers/1810.04805v2.pdf`, `papers/1907.11692v1.pdf` |
| `cross-05` | 问答数据集扩展 | 5 | `papers/1606.05250v3.pdf`, `papers/1806.03822v1.pdf` |
| `cross-06` | 拒答与指标解释 | 4 | `papers/1606.05250v3.pdf`, `papers/1806.03822v1.pdf` |
| `cross-07` | CNN 跳连的结构差别 | 3 | `papers/1512.03385v1.pdf`, `papers/1608.06993v5.pdf` |
| `cross-08` | 视觉榜单的比较条件 | 4 | `papers/1512.03385v1.pdf`, `papers/1608.06993v5.pdf` |
| `cross-09` | 视觉模型训练数据条件 | 4 | `papers/2010.11929v2.pdf`, `papers/2012.12877v2.pdf` |
| `cross-10` | 视觉分类与蒸馏 token | 4 | `papers/2010.11929v2.pdf`, `papers/2012.12877v2.pdf` |
