# ESM Cambrian × fungi-cazyme-PLM 项目集成报告

**项目名称：** dbCAN-SF（fungal structure-aware CAZyme annotation and function decoding）  
**报告版本：** 1.0  
**日期：** 2026-07-21  
**状态：** 设计与证据审阅完成；模型训练尚未授权  
**目标读者：** 项目负责人、CAZyme/真菌生物信息学研究者、模型与数据工程人员

> 本报告回答一个具体问题：ESM Cambrian（ESMC）应当在 dbCAN-SF 中承担什么角色，怎样验证它确实比现有序列、结构和检索方法增加了可发表的生物学价值，以及在什么条件下应停止扩展。报告不把通用酶学结果外推为 CAZyme 结果，也不把模型解释当成实验注释。

---

## 1. 执行摘要

### 1.1 核心结论

1. **ESMC 值得进入项目，但不能绕过 Phase 0。** 当前仓库已经证明 fungal CAZyme family-instance 的 preliminary addressable gap 为 32.84%，高于预注册的 5% 阈值；同时还有 36 个不同序列的 canonical ID 冲突、独立边界金标准缺失、蛋白级功能标签缺失、2024 seed identity 未完成和 GPU ceiling probe 未完成。ESMC 只能提高表征能力，不能修复标签真实性、标识符冲突或数据泄漏。
2. **主路线应是 sequence-first，structure-selective。** 当前 CAZyme3D exact + 90/80 near-match 覆盖率仅为 29,671/524,926（5.6524%）。因此 ESMC 600M 应首先作为 frozen sequence encoder；结构预测和 SaProt 融合集中在 `<30%` identity、fam-0、难例和高价值候选，而不是全库先折叠。
3. **不能为所有任务指定同一层。** 论文和教程都显示功能、结构和稳定性信号在不同深度达到峰值。T1、T2、T3 必须分别进行 layer sweep；最终层只作为对照，不是默认最优层。
4. **ESMC 6B SAE 是最有价值的新基线。** 论文中的 layer-60、Top-K 64、16,384-codebook SAE 在低序列一致性检索上优于 dense ESMC、MMseqs2 和 Foldseek。它应被加入 B8，用于远缘家族、clan 和 fam-0 检索；自动生成的 feature description 只用于提出假设。
5. **ESMFold2 只做定向补充。** 它可提供 pLDDT、PAE、可选 MSA 和复合物推理，但不应替代项目已有的 PDB/CAZyme3D/AFDB 层级，也不应在 Phase 0 阶段进行全库预测。
6. **2026 发布修正了旧许可判断，但尚未自动解除项目许可门槛。** Biohub 当前模型页和官方仓库将当前 ESMC、ESMC SAE 和 ESMFold2 发布标为 MIT，并开放 Hugging Face 权重；legacy `*-2024-12` 产物仍必须按其自己的模型卡和历史条款审计。正式实验前必须固定精确 `model_id`、revision、权重哈希和许可证快照。
7. **本项目不是“第一个 CAZyme PLM”。** CAZyLingua 和 CAALM 已覆盖 sequence-only family annotation。项目的可发表贡献仍应是 fungal domain-level resolution、结构增量的可证伪位置、跨家族 function decoding 和 retrospective fam-0 discovery。

### 1.2 建议的模型分工

| 组件 | 项目角色 | 是否全库运行 | 晋级条件 |
|---|---|---:|---|
| ESMC 300M | 数据流、显存和吞吐 smoke test | 否 | 产物 schema、长序列和哈希验证通过 |
| ESMC 600M frozen | T1-T3 主要 sequence encoder；逐任务选层 | 是，选层后 | 在相同 split/head 下超过或达到 ESM-2 的性能-成本 Pareto 前沿 |
| ESMC 600M LoRA | frozen ceiling 后的有限适配 | 否，先 pilot | frozen 结果稳定且 hard-label gate 满足 |
| ESMC 6B dense | 上界与远缘小规模 benchmark | 否 | 仅在预注册子集评估，记录多 GPU 成本 |
| ESMC 6B SAE | B8 远缘检索、fam-0、解释 | 否，先 domain pilot | `<30%` identity / whole-clan 检索优于现有基线 |
| SaProt/Foldseek | 结构表示与诚实结构基线 | 结构可用子集 | 对 clan/remote/fam-0 有配对置信区间增益 |
| ESMFold2 | 缺失结构的定向补全 | 否 | 只进入高价值候选，保留 pLDDT/PAE |

---

## 2. 项目现状与不可绕过的约束

本报告以仓库 promoted Phase 0 结果为数值事实来源，不重新解释或手工重算这些数字。

| 项目事实 | 当前结果 | 对 ESMC 集成的约束 |
|---|---:|---|
| fungal truth family instances | 728,439 | 需要 domain/family 层评估，而不只是 protein binary |
| preliminary addressable instances | 239,217（32.84%） | 支持继续探索，但不是最终 go decision |
| normalized comparison rows | 1,980,140 | 全库嵌入前必须先做吞吐与存储预算 |
| weak HMM domains | 536,133 | 可训练 T1，但不能作为独立 boundary test |
| function mapping | 1,024 physical / 1,023 unique；390 families | 只能定义 vocabulary/weak labels |
| polyspecific families | 88 | 强制保留多标签和 family lookup baseline |
| local structure coverage | 5.6524% | 采用 sequence-first、按价值预测结构 |
| alias conflicts | 36 | 归零前不得建立正式 embedding/protein join |
| unresolved-genome records | 68,811 | taxonomy 未解决前不得进入 order holdout |
| official ESM-2 ceiling | 缺失 | ESMC 不能替代该连续性基线 |

### 2.1 Phase 0 的六个模型前置门槛

- `protein_alias_integrity`：36 个 canonical conflict 必须显式裁决或 namespace；禁止按 first/last row 静默覆盖。
- `seed_identity_2024`：完成 214,618 planned queries，并标明 reference release 是 2024 MSA。
- `ceiling_probe`：恢复 GPU 后完成 ESM-2 650M frozen cluster30 基线。
- `protein_level_function_labels`：获得 characterized protein-level substrate/EC 数据。
- `independent_boundary_gold`：获得 curated/PDB/独立结构解析边界；HMM envelope 只作 weak supervision。
- `licence_release_decision`：为将实际使用的 current/legacy encoder 固定模型卡、revision、哈希与许可证。

在这些门槛未全部满足时，可以运行 schema smoke test、吞吐 benchmark 和 weak-label feasibility；不得发表“边界优于 dbCAN”“跨家族功能泛化”或“fam-0 发现性能”的 headline claim。

---

## 3. ESMC 论文：哪些证据可用，哪些不能外推

论文为 2026-06-04 发布的 bioRxiv preprint，尚未经过同行评审。以下页码指用户提供的 111 页 PDF。

### 3.1 规模、训练语料与上下文

- ESMC 发布 300M、600M、6B 三个规模。Table S1（PDF p29）给出 30/36/80 层，隐藏维度 960/1152/2560，attention heads 15/18/40。
- 训练语料合计 2.806 billion sequences：UniRef 2023_02 156M、JGI 2.029B、MGnify 2023_02 621M（PDF p3）。这意味着 CAZy 蛋白很可能在无标签预训练中出现，temporal split 不能自动消除 PLM contamination。
- Stage 1 使用 512-token context 训练 1M steps；Stage 2 使用 2,048-token context 继续 500K steps（PDF p28-p29）。对 fungal multi-domain proteins 不能复制教程的固定 1,024 截断。
- ESMC 6B 的功能 kNN probe 在 layer 50-60 附近达到峰值，而 long-range contact 在后层、接近 penultimate layer 达峰（PDF p4）。因此“最后层统一用于所有任务”缺乏依据。

### 3.2 EC-CATH：支持远缘功能方向，但不是 CAZyme benchmark

EC-CATH 数据只保留长度 `<=512`、单一完整 EC、单一完整 CATH domain 的蛋白。最终包含 5,829 个 unique positive proteins、9,211 个 structure-matched negatives、73 个 leave-one-CATH-out tasks，覆盖 32 个 EC numbers 和 42 个 CATH topologies（PDF p30-p31）。6B 在 53/73 tasks 上排名第一（PDF p33）。

对本项目的正确解读是：

- ESMC latent space 可能含有跨 fold 保留的功能方向，支持 T3 whole-clan / whole-family pilot。
- 该数据刻意排除了多结构域、长蛋白和不完整标签，而这些正是 fungal CAZyme 的主要困难。
- 每个 task 选择最佳层和模型，并在 held-out topology 上调正则/选 seed；它的目标是发现表征方向，不是给出可直接部署的 EC classifier。
- 因此不能把“53/73 tasks”写成 ESMC 对 CAZyme 或真菌功能预测的胜率。

### 3.3 Stability：证明表征可被线性读取，不是本项目主任务

论文在 Megascale stability 数据上使用 mean-pooled penultimate-layer embeddings 和 ridge regression。ESMC 6B 对跨结构家族 global `ΔG` 的最佳 Spearman 约 0.68；在 25% identity-filtered FireProt 上，学习到的 stability direction 对 37 个 landscapes 的平均相关接近 0.5，而 pseudoperplexity 约 0.2（PDF p34）。

这支持“先 frozen probe，再决定 LoRA”的工程顺序，但 stability/`ΔΔG` 不属于 dbCAN-SF 的四个核心任务。Mutation scoring 只能作为未来 protein engineering extension，不能挤占 T1-T4 的数据与计算预算。

### 3.4 SAE：对 fam-0 最直接的新机会

论文分析的主 SAE 使用 ESMC 6B layer 60、Top-K 64、16,384-dimensional codebook（PDF p12、p73-p74）。它将每个 residue 的 dense representation 分解成 sparse features，再对 domain/protein 做 max pooling。

关键结果：

- 在 14,841 个至少有 10 个样本的 Pfam families 中，超过 88% 的 family median within-family Jaccard `>0.6`；100,000 个跨 family 随机对的 median 只有 0.177（PDF p95）。
- CATH S95 和 SwissProt full-EC 检索显示，在 `<40%` sequence identity 区间，SAE similarity 优于 mean-pooled ESMC、MMseqs2 和 Foldseek（PDF p95-p96）。
- 对 `<30%` identity 的 CATH true-homolog pairs，SAE cosine 的 near-perfect retrieval 约 70%，dense ESMC 约 64%，Foldseek 约 65%（PDF p96）。

这些结果直接支持新增 B8，但仍有三项限制：数据不是 CAZyme；CATH/EC benchmark 与 fungal taxonomy 分布不同；agent-generated descriptions 是数据库驱动的自动假设，不能写入 gold label。

---

## 4. 官方教程到项目实现的转换

| 教程 | 官方示例 | 本项目采用 | 本项目不照搬 |
|---|---|---|---|
| Embedding | API batch executor；all-layer mean hidden states；ADK layer 12 比 layer 30 更好 | 分任务 layer sweep；保存 layer/pooling/revision | 盲选最后层；只做全蛋白 mean pooling |
| Layer sweep | 593 SwissProt enzymes、4 个 EC3 classes、600M 37 states、5-fold stratified CV、MCC | 同一 probe 跨 layer 比较；MCC 保留为不平衡指标 | 随机 CV 作为主结果；在 test fold 上选择模型 |
| LoRA | `biohub/ESMC-300M`、CLS pooling、rank 8、alpha 16、dropout 0.01、1,024 truncation | rank/alpha/target modules 作为初始值；T1 改 token head，T2/T3 改 domain pooling | 直接采用 CLS 和 1,024 截断；1,000-step demo 当正式训练 |
| Mutation | leave-one-out mask、entropy、single-AA LLR | 未来候选位点的 compatibility 证据 | 把 LLR 当稳定性、活性或实验真值 |
| SAE | 6B layer60 k64 codebook16384、TF-IDF、max activation/prevalence、3D mapping | B8 domain retrieval；激活位置辅助解释 | 固定 feature ID 语义；忽略 sequence-structure alignment |
| ESMFold2 | `esmfold2-fast-2026-05`、loops/sampling、optional MSA、pLDDT/PAE | 定向缺失结构补全；保存 confidence/config | 全库折叠；用低 pLDDT 结构作为确定证据 |

### 4.1 教程中的 LoRA 初始参数

教程把 `out_proj` 作为 `target_modules`，把 `layernorm_qkv.weight`、`ffn.fc1_weight`、`ffn.fc2_weight` 作为 `target_parameters`，并保存 classifier。项目初始配置采用 `rank=8`、`alpha=16`、`dropout=0.01`。这些是复现实验起点，不是已优化超参数；任何调整只能用训练折和 validation fold，不能读取 test fold。

### 4.2 教程中的评估泄漏风险

Layer sweep 教程明确说明其结果主要用于比较层而不是 rigorous benchmark。本项目必须把层选择嵌套在 training/validation 内：外层 cluster30/order/temporal/family split 用于最终测试，内层只在训练数据中选择 layer、pooling 和 probe。随机 stratified CV 仅作为 tutorial reproduction 与 leakage sensitivity control。

---

## 5. T1-T4 的具体集成设计

### 5.1 T1 - residue-level CAZyme class 与边界

**输入：** full protein sequence；可选 structure token 与 residue-level pLDDT。  
**sequence branch：** ESMC 600M 每层 residue hidden states。  
**输出：** 每残基 `{non-CAZyme, GH, GT, PL, CE, AA, CBM}` 概率、boundary probability、连续 domain segments。

实施顺序：

1. 用 300M 在 fixture 和少量真实序列上验证 token/coordinate 对齐。
2. 600M layer sweep 只在 boundary-training subset 上运行；每层使用完全相同的 token head。
3. HMM envelopes 作为 weak training labels；curated/PDB/independent structure parse 只作 hard evaluation。
4. 后处理需要合并短 gap、移除低于 minimum length 的孤立段，并在 validation set 上冻结阈值。
5. 只有 frozen head 稳定后才启用 LoRA；LoRA 不改变 test split 或 boundary gold。

**主指标：** residue macro-F1、domain precision/recall at IoU 0.5/0.75、segment IoU、boundary F1 at ±5/10/20 aa、protein AUPRC。HMM-envelope test 只能报告 agreement，不得称为 independent accuracy。

### 5.2 T2 - domain family、clan 与 open-set

T2 不对整条多结构域蛋白做平均。对 T1 segment 或 gold/weak domain 坐标内的 token states 分别计算 mean、max、attention pooling，并在 validation fold 选择 pooling。

输出采用层级形式：

```text
CAZyme class -> clan -> family/subfamily
                     -> unknown/open-set score
                     -> nearest dense/SAE/sequence/structure neighbors
```

- abundant families 使用 calibrated classifier。
- rare/zero-shot families 使用 retrieval 与 prototype 路线。
- clan auxiliary head 是 Claim 1 的直接检验对象。
- unknown score 同时比较 energy、Mahalanobis、prototype distance、conformal score 和 neighbor consistency；选择只能在 retrospective benchmark 完成。

### 5.3 T3 - function decoder

每个 domain 输出结构化多标签，而不是自然语言自由生成：

```text
substrate polymer
linkage / anomeric specificity
EC level 1-4（允许 partial）
mechanism（retaining / inverting / unknown）
mode（endo / exo / processive / unknown）
```

训练标签分级：protein-level characterized > subfamily > family；后两者只作 weak supervision。characterized-only 与 whole-family holdout 是主评估，family-to-substrate lookup B6 必须与每个 headline number 同表出现。若 decoder 在 held-out families 和 characterized-only set 上不能超过 B6，Claim 2 判定失败。

SAE 可提供两个补充输入：domain max-pooled sparse vector，以及与候选功能 prototype 共享的 feature set。SAE description 不参与构造真值，不把自动描述反向写进 substrate/EC 标签。

### 5.4 T4 - fam-0 retrospective benchmark

用 CAZy release N 的 fam-0 作为 query，仅使用 release N 可得的训练数据；在 N+k 查询后续状态：仍未分配、进入已有 family、形成新 family。对每个 query 保存完整排序而非只保存命中。

比较：ESMC dense、ESMC SAE、MMseqs2、Foldseek、SaProt、CAALM。报告 Recall@k、MAP、nDCG、first-correct rank、assignment AUROC/AUPRC，以及新 family 的 pre-resolution clustering consistency。fam-0 永远不是 negative class。

---

## 6. 长序列、结构融合与产物设计

### 6.1 长序列策略

- 实际 residue budget 从 tokenizer/model config 读取：`max_position_embeddings - special_tokens`，不硬编码 2,048 residues。
- 不超过 budget 的蛋白整条编码；更长蛋白使用 256-aa overlap。
- T1 的重叠 token logits 使用中心权重融合；edge residue 的权重不得为 0。
- T2/T3 优先用完整 domain + 64-aa flank；若 domain 本身超过 budget，按相同窗口策略切分并在 domain 内汇总。
- 每条预测必须记录 window start/end、overlap、merge method 和是否覆盖完整 domain。
- 全库不保存所有层的 residue embeddings。layer sweep 子集可保存 all-layer pooled states；选层后全库保存 domain pooled embedding、最终 token logits 和必要的 selected-layer states。

### 6.2 pLDDT-aware structure fusion

结构来源优先级保持为 PDB -> CAZyme3D -> AFDB `>=90% identity / >=80% coverage` -> high-value prediction。fusion gate 输入 sequence state、structure state、per-residue pLDDT、structure source 和 missing mask。

必须报告三组：experimental/curated structure、predicted structure、no structure。结构被 mask 时模型性能不得显著低于独立 sequence-only 模型；否则不满足 graceful degradation，不能作为 run_dbCAN 可部署路线。

### 6.3 模型产物数据契约

新增 `schemas/model_artifact_manifest.schema.json`，核心字段包括：

- 身份：`artifact_id`、`run_id`、`task`、`artifact_uri`；
- 模型：`model_id`、`model_revision`、`code_revision`、`weights_sha256`、license snapshot；
- 表征：`layer_indices`、`pooling`、`embedding_dim`、`dtype`、SAE 名称/codebook；
- 生物对象：`canonical_id`、`sequence_sha256`、可选 `domain_index` 与 1-based inclusive coordinates；
- 上下文：最大 residue budget、overlap、window/merge policy；
- 结构：source、predictor revision、mean pLDDT threshold；
- 实验：split ID、seed、hardware、peak VRAM、GPU-hours、cache hit rate。

三类下游表分别为 residue predictions、domain predictions、retrieval results。它们通过 `canonical_id + sequence_sha256`，以及 domain 表的 `domain_index` 关联，不覆盖 `domains.parquet` 中的 weak/gold labels。

---

## 7. Split、污染与公平比较

### 7.1 主 split 层级

1. cluster30：主要远缘结果；同时报告 cluster40/50 sensitivity。
2. fungal order holdout：只使用 taxonomy 已解析记录。
3. temporal holdout：所有 baseline 降级或重建到相同 release N。
4. whole-family holdout：T3 的决定性测试。
5. whole-clan holdout：最强 extrapolation 和 Claim 1 测试。

每个 split 输出 leakage report：train-test maximum identity、shared sequence hashes/IDs/genomes/taxa/clusters、database version overlap、held-out family/clan 验证、PLM pretraining-contamination strata。

### 7.2 PLM contamination

ESMC 预训练包含截至 2023 的大规模 UniRef/JGI/MGnify；测试蛋白即使在 2025 才获得 CAZy 标签，也可能早已作为无标签序列进入 PLM。报告必须区分：

- label-time generalization：预训练可能见过序列，但没见过 CAZy 标签；
- sequence-time generalization：近似 PLM-unseen，按 UniProt first-seen/corpus cutoff 分层；
- family/clan generalization：训练监督数据中无该 family/clan。

不得用“temporal split”单独声称模型从未见过测试序列。

---

## 8. Baseline 与模型实验矩阵

### 8.1 Baseline

| ID | 方法 | 主要作用 |
|---|---|---|
| B0 | run_dbCAN V5 | T1-T3 primary comparator |
| B1 | DIAMOND/MMseqs2 label transfer | sequence homology floor |
| B2 | Foldseek vs CAZyme3D | honest structure baseline |
| B3 | CAZyLingua | published PLM comparator |
| B4 | CAALM | hierarchical/retrieval PLM comparator |
| B5 | dbCAN-sub | T3 substrate/EC comparator |
| B6 | dbCAN family -> substrate lookup | Claim 2 deciding baseline |
| B7 | composition/k-mer + gradient boosting | sanity floor |
| B8 | ESMC 6B SAE domain retrieval | remote/open-set/interpretable baseline |

### 8.2 模型阶段

| ID | 模型 | 结构 | 目的 |
|---|---|---:|---|
| M0 | ESM-2 650M frozen | no | continuity ceiling |
| M1a | ESMC 300M frozen | no | smoke/cost floor |
| M1 | ESMC 600M frozen layer sweep | no | sequence representation ceiling |
| M2 | ESMC 600M LoRA | no | T1/T2/T3 adaptation |
| M3/M4 | SaProt frozen/LoRA | yes | structure PLM |
| M5 | ESMC + SaProt pLDDT-gated fusion | optional | Claim 1 |
| M6 | M5 + function decoder | optional | Claim 2 |
| M7 | optional fungal adapter DAPT | optional | kill-criterion extension |

B8 不是 M6 的替代品：B8 检验 sparse representation 是否适合检索；M6 检验结构化功能属性能否跨 family 解码。

---

## 9. 评估、统计与晋级规则

| 任务 | 主指标 | 关键分层 |
|---|---|---|
| T1 | residue macro-F1；segment IoU；boundary F1 ±5/10/20；protein AUPRC | boundary evidence、length、single/multi-domain |
| T2 | macro-MCC/F1；top-1/3/5；hierarchical error；OOD AUROC/AUPRC/FPR95 | identity、clan、family size、taxon |
| T3 | macro-AUPRC；multi-label F1；tuple exact/partial；Brier/ECE | label level、whole-family/clan、polyspecificity |
| T4 | Recall@k；MAP；nDCG；first-correct rank；future-assignment AUROC | later family type、identity、structure availability |

- 使用 paired bootstrap 95% CI；比较模型时测试蛋白完全相同。
- 运行 3-5 个独立 cluster partitions；便宜时再报告初始化 seed variance。
- layer、pooling、threshold、LoRA 超参数都在 nested validation 内冻结。
- Structure branch 只有在 `<30%` identity / clan / fam-0 的预注册主指标下界高于 sequence-only 才晋级。
- ESMC 600M 只有在性能优于 ESM-2，或同等性能下显著降低成本/提高可部署性时晋级默认 encoder。
- Function decoder 未超过 B6，或 SAE 未超过 B1/B2/B4 时，按负结果报告并停止相应扩展。

---

## 10. met 服务器执行与可复现性

权威计算目录为：

```text
met.unl.edu:/array1/xinpeng/fungi-cazyme-PLM
```

2026-07-21 只读检查显示：8 × NVIDIA RTX A5500（每张约 24 GB）、约 2.0 TB `/array1` 可用空间、`uv`、Python 3.11/3.12 和 `tmux` 可用，未检测到 Slurm/PBS。服务器 system Python 3.10 不满足项目 `>=3.11`，必须通过 `uv` 建立 `.venv`。

### 10.1 推荐环境

```bash
ssh met.unl.edu
cd /array1/xinpeng/fungi-cazyme-PLM
git pull --ff-only
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest
```

### 10.2 长任务

使用 `scripts/remote/met_run.sh`，它默认拒绝 dirty Git tree，并为命令创建不可变 `logs/remote_runs/<run_id>/`，记录 command、commit、host、GPU、环境、stdout/stderr 和最终状态。

```bash
tmux new -s fcplm-esmc
cd /array1/xinpeng/fungi-cazyme-PLM
./scripts/remote/met_run.sh --name phase0-smoke --gpu 0 -- \
  .venv/bin/python -m fungi_cazyme_plm.cli smoke \
  --config tests/fixtures/config.yaml
```

离开 tmux 使用 `Ctrl-b d`；恢复使用 `tmux attach -t fcplm-esmc`。不要用 `nohup ... &` 代替 manifest wrapper，因为它通常丢失提交、参数和结束状态。

Cursor 已通过 Remote-SSH 连接时，确认左下角显示远端 `met`，打开该目录并运行 `Codex: Open Codex Sidebar`。Codex IDE 官方支持 Cursor-compatible editors；IDE 会使用当前编辑器所打开的远端工作区。Codex CLI 是另一条独立路径；当前服务器 PATH 未检测到 `codex`，但不影响已安装的 Cursor extension。

详细步骤见 `docs/remote_execution_met.md`。

---

## 11. 计算与存储 stop-loss budget

所有预算先由 1,000 和 10,000 protein benchmark 实测 `tokens/s`、peak VRAM 和 bytes/domain，再外推；严禁直接启动 524,926 proteins 的 all-layer residue extraction。

| 阶段 | 硬上限 | 超限处理 |
|---|---:|---|
| 300M schema/smoke | 4 GPU-hours | 修复数据流，不扩大样本 |
| 600M 10k throughput + layer pilot | 32 GPU-hours | 缩短候选层/只保留 pooled states |
| 600M selected-layer full extraction | 256 GPU-hours；500 GB | 改 on-the-fly head 或分片压缩 |
| LoRA pilot | 24 GPU-hours/config；最多 5 configs | 未超过 frozen 则停止 |
| 6B dense + SAE pilot | 128 GPU-hours；200 GB | 只保留 sparse domain summaries |
| targeted ESMFold2 | 10,000 sequences 或 256 GPU-hours | 按不确定性与价值进一步筛选 |

在新的人工批准前，总 stop-loss 为 800 GPU-hours。估算公式：

```text
GPU-hours = total_tokens / measured_tokens_per_second / 3600 * GPU_count
storage = rows * dimensions * bytes_per_value + index/metadata overhead
```

全库只保存 selected-layer domain pooled embeddings 和最终预测；all-layer token states 只保存在 layer-selection 子集。所有缓存以 `sequence_sha256 + model_revision + layer + window_policy` 为键，避免重复付费。

---

## 12. 风险登记与停止条件

| 风险 | 后果 | 控制/停止条件 |
|---|---|---|
| 论文是 preprint 且无 fungal CAZyme benchmark | 外推过度 | 所有结论必须在项目 split 重测 |
| CAZy/dbCAN 标签共同由 similarity 驱动 | 假性“超越” | low-identity、temporal、characterized-only |
| HMM boundary circularity | T1 虚高 | hard boundary set 未到位不做 headline |
| family substrate inheritance | T3 退化为 lookup | B6 与 whole-family holdout 决定 Claim 2 |
| PLM pretraining contamination | temporal claim 失真 | PLM-seen/unseen strata 与措辞限制 |
| fungal multi-domain/long proteins | truncation 与 pooling 错误 | window manifest、domain pooling、alignment tests |
| SAE 自动描述错误 | 把假设当注释 | descriptions 不进入 label table |
| taxonomy bias | 检索优先找近缘物种 | order holdout 和跨 taxon retrieval |
| 结构低覆盖/低置信 | fusion 实用价值低 | missing-mask、pLDDT gate、coverage-adjusted result |
| 24 GB 单卡限制 | 6B OOM/吞吐低 | 6B 限 pilot、多 GPU shard、记录 cost |
| current/legacy 许可混用 | 发布风险 | 每个 artifact 固定模型卡/revision/license |

---

## 13. 分阶段路线图

### Phase 0 - 先解除门槛

1. 裁决 36 alias conflicts。
2. 完成 2024 seed identity。
3. 恢复 ESM-2 ceiling probe。
4. 获得 independent boundaries、characterized function labels、clan map。
5. 固定 current/legacy ESMC license/revision snapshots。

### Phase 1 - Frozen ESMC

1. 300M fixture smoke。
2. 600M 全层 pooled sweep；T1 residue sweep 只在边界子集。
3. nested cluster30 selection；order/temporal/family 作为外层测试。
4. 与 M0 ESM-2 同 head、同 split、同统计比较。

### Phase 2 - Heads 与 LoRA

1. frozen linear/MLP/prototype heads。
2. T1 token head、T2 hierarchy/open-set、T3 multi-task function head。
3. 600M LoRA pilot；6B 不做 full fine-tuning。

### Phase 3 - SAE 与结构增量

1. B8 dense/SAE retrieval benchmark。
2. B2 Foldseek 与 SaProt 对照。
3. pLDDT-gated fusion 和 no-structure degradation。
4. 只对高价值缺失结构运行 ESMFold2。

### Phase 4 - Retrospective fam-0 与发布

1. release N -> N+k retrospective benchmark。
2. 选择 novelty score 与候选排序。
3. 输出模型卡、数据卡、license bundle、cost table 和可复现命令。

---

## 14. 最终建议

**建议继续，但采用窄而可证伪的 ESMC 集成：**

- 立即把 current ESMC 600M 加入 frozen layer-sweep 计划，把 300M 定为 smoke，把 6B SAE 定为 B8；不要立即做全库 6B 或 DAPT。
- 把 ESMC 与 ESM-2、MMseqs2、Foldseek、CAALM、SaProt 放在同一 split 下比较；ESMC 的主要价值假设是远缘 domain/function retrieval，而不是高同源 family softmax。
- 保持 structure-selective。只有 sequence-only/SAE 无法解决且有明确候选价值时才预测结构。
- 把 function decoder 是否超过 B6、structure fusion 是否在 `<30%` identity/clan/fam-0 上超过 sequence-only，作为两条主 claim 的停止条件。
- 先解决数据门槛，再扩大 GPU 使用。当前最有价值的下一步仍是 alias adjudication + complete seed identity，而不是训练更大的模型。

---

## 15. 主要来源

### ESMC 一手资料

1. Candido S. et al. *Language Modeling Materializes a World Model of Protein Biology*. bioRxiv, 2026. DOI: [10.64898/2026.06.03.729735](https://www.biorxiv.org/content/10.64898/2026.06.03.729735). 本地审阅 PDF：`/Users/xinpengzhang/Downloads/2026.06.03.729735v1.full.pdf`。
2. [Biohub/esm official repository](https://github.com/Biohub/esm) - current code, weights, SAE/ESMFold2 usage and license statement。
3. [ESMC model page](https://biohub.ai/models/esmc) - current version、intended use、MIT statement 和模型限制。
4. [Biohub tutorials](https://biohub.ai/resources/tutorials)。具体 notebooks：[embedding](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/embed.ipynb)、[layer sweep](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/esmc_layer_sweep.ipynb)、[LoRA](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/esmc_finetune.ipynb)、[mutation scoring](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/esmc_mutation_scoring.ipynb)、[SAE interpretation](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/esmc_sae_feature_interpretation.ipynb)、[ESMFold2](https://github.com/Biohub/esm/blob/main/cookbook/tutorials/esmfold2.ipynb)。
5. [Biohub model limitations](https://biohub.ai/resources/limitations) - 输出为 computational predictions，underrepresented lineages、short/disordered proteins 可靠性可能变化。

### CAZyme 项目与基线

6. [fungi-cazyme-PLM repository](https://github.com/Xinpeng021001/fungi-cazyme-PLM) 及仓库内 promoted Phase 0 artifacts。
7. Zheng J. et al. [dbCAN3: automated carbohydrate-active enzyme and substrate annotation](https://academic.oup.com/nar/article/51/W1/W115/7147496). *Nucleic Acids Research*, 2023。
8. [CAZyLingua article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10634757/) - sequence-only protein language model CAZyme classification comparator。
9. [CAALM module documentation](https://pipelines.tol.sanger.ac.uk/modules/caalm_caalm) - hierarchical PLM/FAISS family annotation comparator。

### Codex/Cursor 远端工作

10. [OpenAI Codex IDE extension](https://developers.openai.com/codex/ide) - VS Code-compatible editors，包括 Cursor。
11. [OpenAI Codex CLI](https://developers.openai.com/codex/cli) - 从项目目录运行 Codex 与 `codex exec` 自动化工作流。

