# Reproduce the D selection without inference

The candidate pool comes from the historical archive at
`eval/archive/deepseek-pilot-20261120/pilot-artifacts.tar.gz`. Extract it into
a separate directory. With Python 3.11 or later, run:

```sh
python eval/data/frozen-v1/build_d_subset.py --source /path/to/extracted-pilot --seed 0 --target 40 --plan-only
```

This reads task inputs and historical task IDs, without using scores or model
answers as selection criteria. It reproduces the 90 original IDs, 86 unique
content fingerprints, duplicate aliases, proportional quotas and 40 chosen IDs
recorded in `d-deepseek.manifest.json`. The pool sidecar keeps all 90 IDs so
that removed aliases remain auditable.

To render another copy, install ReportLab and supply a **new** output directory:

```sh
python eval/data/frozen-v1/build_d_subset.py --source /path/to/extracted-pilot --out /path/to/new-d-export --seed 0 --target 40
```

The original rendering used Arial regular/bold and Segoe UI Symbol on Windows;
their SHA256 hashes are recorded in the manifest. The CLI accepts `--font`,
`--bold-font`, and `--symbol-font`. Optional `--qa-python /path/to/python`
requires PyMuPDF there and Pillow in the authoring interpreter, and renders
every page for inspection. The delivered 74 PDFs / 146 pages passed text
retention, glyph and page-boundary checks and visual review.

Selection is reproducible from the public archive. Exact regenerated artifact
bytes are not promised: the archive reserializes/redacts historical JSON, and
font/environment choices affect PDF layout. Source-file hashes in the D
manifest describe original local inputs; sanitized archive member hashes are
in the archive's outer manifest. Compare IDs/fingerprints for selection and
the committed `files_sha256` for the actual delivered files.

## Scoring boundaries

Use the runtime code and scorers at `99ded17`, as required by the unified
protocol. Do not import historical structured-pass scores into new reports.

- Controlled claim tasks use the native label metric. Their additional
  numerical criteria remain available for audit but are not scored by it.
- Other controlled tasks use QA token-F1 against references derived from the
  old gold. It does not implement the old numerical-tolerance checker.
- The two D injection-family tasks are QA tasks. Their legacy canaries are
  preserved for inspection; they do not automatically produce the unified
  `injection_followed` metric and do not replace the separate I batch.
- Old evidence page/span locators are not verified positions in these newly
  rendered PDFs. These text renderings do not add original figure pixels.

Cross-batch deduplication and the final `frozen-v1.jsonl` / `MANIFEST.md` must
wait for C/Q/X/I. This contribution supplies D only, without declaring the
combined dataset frozen.
