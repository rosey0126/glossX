# PR 12 dataset contribution to frozen-v1

This contribution contains 35 claim tasks (C35), 20 short-answer tasks (Q20) and 10 paired document variants (I10).
The original question substance and answer keys are preserved, including the answer forms already present in the initial key.
The legacy Answer/Verdict formatting instructions were removed from the task question; the frozen answer-fields-v2 runner supplies a common prompt.
Variant IDs use the frozen runner's +inject suffix and retain the base task ID and canary in the gold metadata.
The historical E40-12 gold label is retained, including the interpretation caveat recorded in the prior report.

## PDF provenance

All 31 distinct PDF files are byte-for-byte copies of the materials assigned in PR 12, including the matched clean and variant copies.
These are the original evaluation paper extracts, not substitutions of full papers. Exact duplicate PDFs appear only once.
Paired PDFs have distinct basenames because the importer maps library IDs by basename. The gold evidence filenames are updated to match.
PR12-paper-map.jsonl records the original archive members and their SHA-256 digests.
The historical diagnostic received extracted page text rather than the PDF files through the frozen runner.

Source bundle SHA-256: `c80de9faa85b928583309d617d1ceb4e1f94609d29ee5ab6be3632547e704ccd`.

## Files

| Path relative to this directory | SHA-256 |
| --- | --- |
| `C35.jsonl` | `215eef197c8bf0335918689941aa3c110f43a0b621e6f1a7dda3572ba91c94e3` |
| `I10.jsonl` | `e172c332e651218ef1bfce1e2cb893e099463e4029122b322f6ee372433f80b7` |
| `papers/abstract-25649714.pdf` | `7f6a2d1675a24295a9e2e3d98e10fa131e5e0df49af1f742954105cb720f450a` |
| `papers/paper-1604.03114-G50-23-clean.pdf` | `19c966295977d3b9c8ade146631f7b74868d034e51e3f551a02cca6ab411f454` |
| `papers/paper-1604.03114-G50-23-variant.pdf` | `b999312d252bf8096dee50008aa701003e9649652a775a61dd51dc1412fc88bc` |
| `papers/paper-1604.03114.pdf` | `b036344af8cae27dce3980e93cb354ffd24e70ff22b70bea552dd339e1ba6ab6` |
| `papers/paper-1609.00425-G50-14-clean.pdf` | `349633f93d9a893bbccce46a27a9be037bf4c88353d49c7430519c2286b3e4ec` |
| `papers/paper-1609.00425-G50-14-variant.pdf` | `77ab5ead98d503de64876c9e7c780956970a956719a208a8bb31c49ebade0950` |
| `papers/paper-1609.00425.pdf` | `ff38f725984552164a25381efcfb6b4adef65770d4288f243619b8d940560b77` |
| `papers/paper-1802.07862-G50-11-clean.pdf` | `5cdd19d68e88cab5bd301c9c923cc72383d6bb02eeefabcb786f84ddd593068f` |
| `papers/paper-1802.07862-G50-11-variant.pdf` | `e501a8d57daf3e47cb4960b8b8ecc3ed0c2866b502c5aef0a144e8737926af08` |
| `papers/paper-1802.07862.pdf` | `b42f0e42bcaa323e38286bdb7c0ef518df5c6378905cf381cc3dc701cf7a5af1` |
| `papers/paper-1805.08241-G50-20-clean.pdf` | `a5f14de663d2f623af1ce9dd479f82d8743eac95fffdfd5ce5e1a40ca62ba3cc` |
| `papers/paper-1805.08241-G50-20-variant.pdf` | `a58b3b7362a1d558504ff0ef7dd6da54e52c3fea5ab88627c77c72126377bb66` |
| `papers/paper-1805.08241.pdf` | `45e93e0e15db54705ef9e707c60b64165858485abe33ab66973641578e396c95` |
| `papers/paper-1904.07904-G50-29-clean.pdf` | `053960925e56b75410e59d1a0eb8bedca638d9f57f3561da006a84d5be81c445` |
| `papers/paper-1904.07904-G50-29-variant.pdf` | `dca1a374d8728cb3cea2fb8f767b95687654f58bfee0a04afe665bca336a3ca4` |
| `papers/paper-1904.07904.pdf` | `2785ed778fee94661b4b98e5a0c382ccf0e5556bb60cabe532fce588fcf652f9` |
| `papers/paper-1909.02027-G50-41-clean.pdf` | `f268d4d7d1b5b5c948d4df744c15ab9f1516f102a698f74a6f74bd7f59adb462` |
| `papers/paper-1909.02027-G50-41-variant.pdf` | `e3367cbda228c29ac06112e2670ace3a6c0d0993bf410a08d7baf78004733268` |
| `papers/paper-1909.02027.pdf` | `08024b49eccba87b54a72fbeb305d4026f315b45b7f41d4ce44aed5ce0241b5f` |
| `papers/paper-1909.08089-G50-46-clean.pdf` | `55b7b79830d19f4131b9f10d5228960f06a9875834803810d14f3836f7e9477f` |
| `papers/paper-1909.08089-G50-46-variant.pdf` | `5ba770f8ff54bae989ea592f7327445e32a1337e66368c9bb0ccb5209b869930` |
| `papers/paper-1909.08089.pdf` | `19f61c7b1cc9b7f1c49493b5101fbbd99cd7cf170a4141a7707909ace3229d8b` |
| `papers/paper-1910.10781-G50-03-clean.pdf` | `d274314d9b175d9c4a0ee4c89bce794e9a88bbe8ad4dc7c926dcbfd09523cee2` |
| `papers/paper-1910.10781-G50-03-variant.pdf` | `58a8d3c5161998103e72efe96649eee07cb5c83781da352ff4dc36305a05a992` |
| `papers/paper-1910.10781.pdf` | `cff35d38d9bb1802e6396bac2dc60a7c8d47621eec2f039ac59e9cd93cf7ecc7` |
| `papers/paper-1912.08960-G50-44-clean.pdf` | `4c41f352c2bf0d610ea61c6f47f7d081f7382b0f5336561d4475c2d7a2d9d1f7` |
| `papers/paper-1912.08960-G50-44-variant.pdf` | `52a1f813d179c617ffb16957004547de7c24ede5eda26e583d1a32e506401673` |
| `papers/paper-1912.08960.pdf` | `5b60e5f4d82dece889d78437b93b6f3112d686a988c26c29e3eab1b3a93f40dd` |
| `papers/paper-2004.01853-G50-25-clean.pdf` | `60a567567a21cbeebac70efa0a3173502042882305bf73013887659c8fdd6bb4` |
| `papers/paper-2004.01853-G50-25-variant.pdf` | `3059522a2060a192653ec792e3728de47f6d954fe90a4b99e6789d54276aaf7d` |
| `papers/paper-2004.01853.pdf` | `4e4e458248a371cec6237a5b7547bb1c755be46386141fe3d69976bb31521477` |
| `PR12-paper-map.jsonl` | `8a25f90d959cef35d498717ec591f39ff94b265a92ff24802a73006748bc86af` |
| `Q20.jsonl` | `b370cc1be6b4711a5ba5439700c1d24b88a7a0ed7ad3fa416e8270fc7850e377` |

## Integration

These three JSONL files are inputs for the coordinator's final deduplicated dataset. The coordinator produces frozen-v1.jsonl and MANIFEST.md when the other contributions are complete.
The separate development archive is under eval/archive/pr12-gpt-6.2-sol/.
Do not include it in the frozen-v1 results table.
