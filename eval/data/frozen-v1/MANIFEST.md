# frozen-v1 题集清单（已冻结）

冻结时间：2026-11-24 19:50 UTC（香港时间 11 月 25 日 03:50）。题集来自 #14、#15、#16，三个 PR 已合入 `eval/frozen-v1`。从这时起，题目、标准答案和 PDF 都不再改动。

运行用的代码版本仍然是 `99ded17`（见 `eval/UNIFIED_PROTOCOL.md`）。只有本文件列出的 `frozen-v1.jsonl` 计入主结果表。

| 子集 | 文件 | 条数 | sha256 |
| --- | --- | ---: | --- |
| C | `C35.jsonl` | 35 | `215eef197c8bf0335918689941aa3c110f43a0b621e6f1a7dda3572ba91c94e3` |
| Q | `Q20.jsonl` | 20 | `b370cc1be6b4711a5ba5439700c1d24b88a7a0ed7ad3fa416e8270fc7850e377` |
| X | `x10.jsonl` | 10 | `82992c804b47315ffccb1cb3e83f2230c4bb8cf6db492bb04aeabc5737753213` |
| I | `I10.jsonl` | 10 | `e172c332e651218ef1bfce1e2cb893e099463e4029122b322f6ee372433f80b7` |
| D | `d-deepseek.jsonl` | 40 | `796c1c2192477d0c2adc5e5257686876856ddddc5ba9feee2002bdb81baa7b99` |
| 合计 | `frozen-v1.jsonl` | 115 | `493d198ed39f4ae850bb925a165235e5c54950de3afcee800a8d34861cc9a5a7` |

共 115 题（claim 55 题，qa 60 题），用到 115 个 PDF。另有 R：`eval/data/route100.jsonl`，共 100 条，只评 GlossX。

I10 是 C35、Q20 中 10 题的注入变体，题干与原题相同、PDF 不同，属于预期内的重合，单独报告。`pr11-50.jsonl` 只作开发期存档，不在 frozen-v1 里。

## PDF 哈希

| 文件 | sha256 |
| --- | --- |
| `papers/1512.03385v1.pdf` | `1e0651b6810ecba34a3dbc5b5b0209226f889004607c1f203540a48d64e5a93a` |
| `papers/1606.05250v3.pdf` | `5169f9424ad6078815b99f5aa83724f42fa6826cedfb8ae303a8091d15c8450c` |
| `papers/1608.06993v5.pdf` | `b55aa1adbdf07f731daa84b94d23103d1eb22d1821a556b80212debee69b096d` |
| `papers/1705.03122v3.pdf` | `6db054c83fbd890c97b482c381dc4a8fd4f80e64794414eb871bb451cde645bb` |
| `papers/1706.03762v7.pdf` | `bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697` |
| `papers/1806.03822v1.pdf` | `c69190f82a892d2502a0610e5957a17f19ec1145875a974aaac4e26d400edb0e` |
| `papers/1810.04805v2.pdf` | `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e` |
| `papers/1907.11692v1.pdf` | `76a3872d244793563a5b000b818cbaf0ca8972ab1145d32be474c05b2a8f3070` |
| `papers/2010.11929v2.pdf` | `8ce7b83971a14508ca711a27c875c9b6914c4f6767cf3150fb1ca6c07aa056d6` |
| `papers/2012.12877v2.pdf` | `a0fbdd27c115594326fd75b3a0f569fb94cbf0b5c34c84fdc204d993064188bb` |
| `papers/D-qasper-21548433abd21346659505296fb0576e78287a74-01-1909.13104.pdf` | `9a57c6b53a02980c6fdecd66606d281f3c8e11b3b5e23cb411f2a2666c7b02ab` |
| `papers/D-qasper-22b740cc3c8598247ee102279f96575bdb10d53f-01-1801.10293.pdf` | `7827e8cffe2ddc82eb0d6a68652fc5877f4249bd6b029f1f4d8abc6665292916` |
| `papers/D-qasper-3611a72f754de1e256fbd25b012197e1c24e8470-01-1610.09225.pdf` | `0aae70ca3ed89775102b370fcd147ca5d573c129984211f355f02baf27bc22ce` |
| `papers/D-qasper-63c3550c6fb42f41a0c93133e9fca12ac00df9b3-01-1804.00720.pdf` | `828cd6bc134f942db7edf6723425873a17a9fe3c29c8cffa20c37fde612333e9` |
| `papers/D-qasper-6becff2967fe7c5256fe0b00231765be5b9db9f1-01-1503.00841.pdf` | `ba5e89bb97c1cc33ccfc7facfeb5be55b61661d89c9a03016b2f1db08bccb455` |
| `papers/D-qasper-6cd25c637c6b772ce29e8ee81571e8694549c5ab-01-1804.07789.pdf` | `51a9d0f69db038a0ae6267c940aaad1dcdede37b8c495e699beb26971a6c87c7` |
| `papers/D-qasper-72ce05546c81ada05885026470f4c8c218805055-01-2003.11563.pdf` | `3e60189047193d7dd3094fde1d2c5576f600839bb91b4860e4c1d1ddda193035` |
| `papers/D-qasper-bc730e4d964b6a66656078e2da130310142ab641-01-1912.00667.pdf` | `1fb95f687a7a9b827dc63add8d82f275c52d6b4f8a0e74e85c74fcba18d91331` |
| `papers/D-qasper-fb1227b3681c69f60eb0539e16c5a8cd784177a7-01-1703.10344.pdf` | `7cd4c8f77a2975742d77865e8ed7c75a7f7d3f64aa86dc69ae27ab49d339d233` |
| `papers/D-research-budget-03-01-source_1.pdf` | `2850cbff8ef8155d16fc7014272d01baa2895d0d8bb51c677ac43e51f7e63531` |
| `papers/D-research-budget-03-02-source_2.pdf` | `1acfb8c62d971f8a2dee9edde63c51ca086e0cbf08d2b8495bfaca38c45447da` |
| `papers/D-research-budget-03-03-source_3.pdf` | `3fa44ae35e8e12439285a79e2151645d3e5a597b283d25e7854c7c01c719856c` |
| `papers/D-research-budget-05-01-source_1.pdf` | `2cec5a486545481379a37b073085b8a284d633068d2376e9389923f6001c0fd8` |
| `papers/D-research-budget-05-02-source_2.pdf` | `9a0e1ac7bf295fb53fea0e5adccf17a46d5f07fef35d587835f498ea45a97249` |
| `papers/D-research-budget-05-03-source_3.pdf` | `8193f728ad0ec93dd64e726c9ae328cca9de6946bc36670bc4924d306db5cc24` |
| `papers/D-research-claim-02-01-source_1.pdf` | `ce0de422e90d54211af7d3aeac00580a962aba87783dfe8edcf6d5643d83c41c` |
| `papers/D-research-claim-02-02-source_2.pdf` | `f530426e65c6f8294827ff112794a7655db6dcb49562b698d1a9f1e02f4ee547` |
| `papers/D-research-claim-02-03-source_3.pdf` | `d55592f5cd9f1102a885676d2953ee8b833992ade8a46354385a3bef9f3cf812` |
| `papers/D-research-composition-04-01-source_1.pdf` | `5dedb0d9002249293d35754df3d3599f019272d8743e9057538ccf3c050f1607` |
| `papers/D-research-composition-04-02-source_2.pdf` | `ecda44fa6a8c6f8a42ceaa6b591f992bd8ac1cc5c64541fe498a91b7a1c1a1c3` |
| `papers/D-research-composition-04-03-source_3.pdf` | `52a4f00f5c487ec5336a4823c7a5c3d715d8ebc869859389672b9b470d68096c` |
| `papers/D-research-composition-05-01-source_1.pdf` | `4c5f35c4ed6e2d5553bf8b88d986c93d016e423ef42a1a87cd5183f8192352e7` |
| `papers/D-research-composition-05-02-source_2.pdf` | `6053e3ac19608c3ed608d401129335e7143731f60d31306e39168b6ec6536841` |
| `papers/D-research-composition-05-03-source_3.pdf` | `87b2f4801545815c7afb1df5e31b32fc03ac8b544597ce07341ea9ab1ca50e19` |
| `papers/D-research-injection-03-01-source_1.pdf` | `8c8e5e2fe781ab1bc4bab6934e8d9b6b5a4a89f0805d0723360c2dcc9362cec5` |
| `papers/D-research-injection-03-02-source_2.pdf` | `332c2a9a69f743e346cdf1955e8b351a71a84928c9e712d498e67f8709d5a71e` |
| `papers/D-research-injection-03-03-source_3.pdf` | `fbc32ee135d56650e6f4fe7a1e2bd87937dec64baf743cf6ff21434b270ab29a` |
| `papers/D-research-injection-05-01-source_1.pdf` | `e17f3b6f5d804474566ae6862ca3edcbcb4144c0f0e996d9735c08f02cd1bd6a` |
| `papers/D-research-injection-05-02-source_2.pdf` | `f95994641029f3c9b77405d95e0b03a2d7ea21e9c57d60d47ca8c37b17671167` |
| `papers/D-research-injection-05-03-source_3.pdf` | `29b12bfa4f11758923a3c36763537a0b45e97d7b55a31f455b87faea0eca73cf` |
| `papers/D-research-leakage-03-01-source_1.pdf` | `885de4a634cd857da9310dca9811480f9c2df027b8d18e68037c40759f9b598b` |
| `papers/D-research-leakage-03-02-source_2.pdf` | `c8428d4bb72e2d1dd4050b6a5ac6cf65cda198adfd510015f8a24f43ebff0f80` |
| `papers/D-research-leakage-03-03-source_3.pdf` | `55648c28553fbca6a6f2c16a999e1774c58a1d0b7cdc2d5f6ee93cc00161f4c4` |
| `papers/D-research-leakage-04-01-source_1.pdf` | `43f8fabbda99941cea51712fa9a083b65745b07c8ca5dc0fd0ae43bf4001012b` |
| `papers/D-research-leakage-04-02-source_2.pdf` | `34fd6daa5d4810c5d082fa58666ce41d88e5b210eaf8d1f4155a8796408d0c64` |
| `papers/D-research-leakage-04-03-source_3.pdf` | `e23eed000f1a890a07e861b96e5e3202008410a5fd480fd34ff2fa9e331f2af9` |
| `papers/D-research-metrics-04-01-source_1.pdf` | `d10709b28e61b6e09dc81a690e73ff428dbbd24c9ac357e957561fe32c9efcbc` |
| `papers/D-research-metrics-04-02-source_2.pdf` | `d1a3850de3215453e70bf9b7cb3f39a3fcf3f02e2e5af23e9c9127055ac9e2dd` |
| `papers/D-research-metrics-04-03-source_3.pdf` | `8d4a73c59333719659eba15f68b30be0af1b87a4b21974bb5397ec37716d54cd` |
| `papers/D-research-metrics-05-01-source_1.pdf` | `38f4f753c3202f767ad449c1ac12e54222766589ac94a937560df2bd3738fee7` |
| `papers/D-research-metrics-05-02-source_2.pdf` | `59b1046aef6119002d9b1edeb5006ca52e5613d0505f6b4237b3045bbbb4e12e` |
| `papers/D-research-metrics-05-03-source_3.pdf` | `79cd8a749b4cd6da97dc204a5654a9d62a91c3fb93aa64c9edd3c2f928539982` |
| `papers/D-research-missing-03-01-source_1.pdf` | `680c8b182996d2d076617903fb7bb73fd27e62396f44bb4e4b14745e291beb29` |
| `papers/D-research-missing-03-02-source_2.pdf` | `0d35529b11ef713c29ae2405337bf01e2c52c3996df84065d2756970b6bbadf9` |
| `papers/D-research-missing-03-03-source_3.pdf` | `3494fac0ab049bc06f9021387e3625acd1172c16852edbbd3282a8a99779ce94` |
| `papers/D-research-missing-04-01-source_1.pdf` | `08db472aa3f8e92dd1351ce5350ac1239149530899076e3c8c66664b6df42454` |
| `papers/D-research-missing-04-02-source_2.pdf` | `e5fab9f07cb500215d3edfaf4a8bed7a72718b9b9eab94db9791d48a75559fc1` |
| `papers/D-research-missing-04-03-source_3.pdf` | `256ff713661331ea33d42498728032fd8fad6026b1a67636c40deb1ecd868a49` |
| `papers/D-research-multiplicity-03-01-source_1.pdf` | `513daaf7a685bd6c2c9c531d79aa8c3e1294ffb5dd4832cbd8d0c941e924c929` |
| `papers/D-research-multiplicity-03-02-source_2.pdf` | `ae502bbeea4333b40e9cfb75853f64962c0a800ddf95ece7a7e0c600f1107aa5` |
| `papers/D-research-multiplicity-03-03-source_3.pdf` | `cbb7b07eaf36b533c09302a8e4a57e9dc12f4a99291b90e6f61128fe476e6cc3` |
| `papers/D-research-multiplicity-05-01-source_1.pdf` | `3319b9364808a770d0855913abf3d5f1595217147edd72408ba9210a3b7aab00` |
| `papers/D-research-multiplicity-05-02-source_2.pdf` | `b8af1a50428d5a45d9f0bc40b4528704fafcc134f5c9b85a5001e86ab71b1623` |
| `papers/D-research-multiplicity-05-03-source_3.pdf` | `947a92075a275c36310788b23472bbdc182572255787ba08c73e7563a52b22a6` |
| `papers/D-research-replication-03-01-source_1.pdf` | `cf387737ec69529ed803e65c2b49ae6861e4c07b20c3949b81fa019ec389738e` |
| `papers/D-research-replication-03-02-source_2.pdf` | `969c862733ea9540474554ae756828a0c54800294de8843cf2d51c7393cbaa95` |
| `papers/D-research-replication-03-03-source_3.pdf` | `0f3196423bdc1f2cdf5b5c1a0904e49b7356e2b9bb8efadf04dccd9becc4c140` |
| `papers/D-research-replication-04-01-source_1.pdf` | `1d06a9e6c8b7534ed9122b88e080b3ea3ab9a8bb479d6b3785216bf0c8acf39f` |
| `papers/D-research-replication-04-02-source_2.pdf` | `b5fde49f89f8c99942c3ca10589b2dbcea7819f400d71982dd7be890466729c1` |
| `papers/D-research-replication-04-03-source_3.pdf` | `e247a03db7361ef7bbc3588478047118548988951356b4f64b7f55a41f54f40a` |
| `papers/D-scifact-1207-01-18909530.pdf` | `5a576e7568a57cd48242da88a73caa525a73f528c4b857a2acf2810ce704313b` |
| `papers/D-scifact-1270-01-13900610.pdf` | `f9feaa583c897f990f14acf318b576c15ef9daf53a5454ec82508c21b7530069` |
| `papers/D-scifact-1290-01-4687948.pdf` | `8e012a8722fdc99faae07e406a9067d2974030245b4734ab0fb1cf712e0de0b0` |
| `papers/D-scifact-183-01-12827098.pdf` | `18fcfbcfa587935254e719d368007173b53bd8cb8ca441bbba61f4cf23744ae5` |
| `papers/D-scifact-380-01-19005293.pdf` | `a81fde2551d34a6052e73cb9bfea3f4a5bd955156a66b28f008c87d780a008de` |
| `papers/D-scifact-386-01-16495649.pdf` | `d89597099b4e2464c195ea3b36438699fa2fd49e43d80605642e0e7f0f333920` |
| `papers/D-scifact-431-01-28937856.pdf` | `271d4a94b8cc1b9c0c15c306da24492ea50cdd590209554552624092b80b80c2` |
| `papers/D-scifact-478-01-14767844.pdf` | `5efbe84b5b45677dc778830990a138144dc1641f0ee36575992340be88625f81` |
| `papers/D-scifact-507-01-30774694.pdf` | `c49f0b4cb879515917476d02d740c249cf9ed3749e5665dfbfad6debd470af6d` |
| `papers/D-scifact-528-01-5476778.pdf` | `d300c4cf3599c5b0a3aef34612b9d64b64ebd944409397dd76241cb7e8ddf40e` |
| `papers/D-scifact-53-01-45638119.pdf` | `ea91417860ac0dd7e753f85a26b1168cd9f7e267af1446a39d24e9a0ccc82412` |
| `papers/D-scifact-549-01-9433958.pdf` | `48f9a2b432243a2bf7faf6ebd5088033be54447da66c0ffc65e94233eee50040` |
| `papers/D-scifact-575-01-10300888.pdf` | `9877ffaaec4087fc83131a54b78c39f44a84f9b121093ee262bef462def6042b` |
| `papers/D-scifact-993-01-16472469.pdf` | `9a0efd6863508787779951b1782cf2166906def1cc028c8a9c125e8926ba0a23` |
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
