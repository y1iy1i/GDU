# 新项目Codex交接说明

> 来源项目：`<local-pageindex-workspace>`  
> 来源模块：`experiments/retrieval_benchmark`  
> 交接日期：2026-08-14  
> 新项目主题：生成式文档理解单元（GDU）  

## 1. 给新项目Codex的首要说明

新项目不是继续调节PageIndex的Top-K、Hybrid权重或全局兜底比例。旧项目的主要价值是提供：

- 可复用的长文档数据和证据标签；
- 已生成的PageIndex、Chunk和Embedding缓存；
- 检索、评分、成本统计和报告基线；
- 已发现的检索现象与失败类型；
- 新研究思想的完整论述。

新项目的核心研究问题是：

> 能否构建一种可生成、可阅读、可追溯的文档级知识表示，在保持原文证据问答精确性的同时，表达写作目的、主体思想、结构安排、体裁经验、章节功能和跨章节关系？

开始新项目时应首先阅读：

1. `experiments/retrieval_benchmark/reports/09_generative_document_unit_full_report.md`
2. `experiments/retrieval_benchmark/reports/08_generative_document_understanding_progress.md`
3. `experiments/retrieval_benchmark/README.md`
4. `experiments/retrieval_benchmark/reports/README.md`

## 2. 当前项目没有传统数据库

当前数据层是文件式存储，不是PostgreSQL、SQLite或向量数据库：

| 内容 | 格式 |
|---|---|
| FinanceBench问题与证据 | JSONL |
| PDF原文 | PDF |
| PageIndex树 | JSON |
| Chunk | JSONL |
| Embedding | NumPy `.npy` |
| 路由缓存 | JSONL |
| 逐题运行结果 | JSONL |
| 指标汇总 | CSV |
| 可视化报告 | HTML |

新项目可以直接读取这些格式，无需先部署数据库。如果之后引入数据库，应先写无损迁移与校验，不能破坏Chunk、Embedding、页码和证据标签的对应关系。

## 3. 可直接复用的数据资产

### 3.1 FinanceBench原始数据

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/raw/financebench/
```

当前状态：

- 150道FinanceBench问题；
- 84份PDF全部已下载；
- 原始数据约164MB；
- 没有缺失PDF。

标注文件：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/raw/financebench/data/financebench_open_source.jsonl
```

PDF目录：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/raw/financebench/pdfs/
```

注意：FinanceBench原始证据页码从0开始，项目内部评分使用PDF物理页码，从1开始。适配器同时保存两套页码。

### 3.2 已完成文档缓存

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/cache/documents/
```

当前状态：

- 46份文档完整缓存；
- 覆盖前150题中的92道题；
- 6,051页；
- 11,976个Chunk；
- 4,660个PageIndex节点；
- Embedding为本地Ollama `bge-m3:latest`生成的1024维归一化向量；
- 检查时没有缺失或损坏缓存。

每个哈希目录包含：

```text
manifest.json      文档ID、PDF路径、页数、Chunk数量
tree.json          PageIndex树
chunks.jsonl       原文Chunk、页码、节点绑定和section_path
embeddings.npy     与chunks.jsonl逐行对应的向量矩阵
```

重要约束：`embeddings.npy`第N行对应`chunks.jsonl`第N条。迁移或过滤时必须同步处理，不能单独重排Chunk。

### 3.3 独立PageIndex缓存

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/cache/pageindex/
```

当前共有46份树缓存，约8.3MB。文件名包含PDF名称、PDF内容哈希和模型设置哈希。树节点通常包含：

- `node_id`；
- `title`；
- `start_index`、`end_index`；
- `summary`；
- 嵌套`nodes`；
- `_benchmark.llm_usage`（仅后期重建且捕获到usage的缓存可能完整记录）。

这些树适合用作结构基线和证据定位，不应被当作新研究的最终理解表示。

### 3.4 路由缓存

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/cache/routes/
```

目前主要文件：

```text
stage1_fallback_financebench30_v1.jsonl
```

它用于冻结30题PageIndex路由、消除LLM随机性。只适合作为旧实验复现资产，不应直接训练新模型，因为样本量小且经过多次开发集分析。

## 4. 可直接复用的代码

代码根目录：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/benchmark/
```

### 4.1 建议直接迁移或引用

| 文件 | 可复用能力 |
|---|---|
| `dataset.py` | FinanceBench字段、证据页和PDF路径标准化 |
| `schemas.py` | Question、Chunk、RetrievalHit、RunResult数据结构 |
| `pdf_parser.py` | 按PDF物理页提取文本 |
| `chunker.py` | 保持页边界的段落感知Chunk切分 |
| `embedder.py` | Ollama批量Embedding、归一化和维度校验 |
| `retrievers.py` | BM25、Dense、Hybrid/RRF及候选过滤 |
| `metrics.py` | Recall、MRR、nDCG、证据覆盖与答案指标 |
| `reporting.py` | 离线HTML、CSV和成本可视化 |
| `io.py` | JSON、JSONL读写辅助 |
| `text.py` | Token与文本处理辅助 |

### 4.2 建议适配后复用

| 文件 | 原因 |
|---|---|
| `cache.py` | 当前缓存键包含Chunk、Embedding和树模型配置，新项目应拆分缓存层 |
| `pageindex_builder.py` | 可作为Full-PageIndex基线，不应成为新架构核心 |
| `tree.py` | 可复用节点展开与Chunk绑定，但数据模型可能扩展 |
| `tree_retriever.py` | 可作为旧PageIndex路由基线 |
| `reranker.py` | 可复用接口，但注意付费调用和Token记录 |
| `answerer.py` | 可作为证据约束回答基线 |
| `runner.py` | 当前围绕固定检索组编排，新项目建议保留结果格式而重构流程 |
| `route_cache.py` | 缓存思路可复用，但缓存键需反映新表示版本 |
| `diagnostics.py` | 可扩展为“检索失败、理解失败、证据失败、生成失败”诊断 |

### 4.3 不需要迁移的临时内容

- `__pycache__/`；
- 旧Python字节码；
- 临时终端文件；
- 无法说明来源的手工导出文件；
- API密钥文件。

## 5. 可复用的实验结果

输出目录：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/outputs/
```

约15MB，包含多个实验的：

```text
runs.jsonl
per_question.csv
summary.csv
report.html
```

重要实验：

- `financebench_smoke_30/`：30题初始基线；
- `experiment_01_top10_recall_30/`：Top-10深度；
- `financebench_ablate_nodes1_30/`、`nodes5_30/`：PageIndex节点数；
- `financebench_ablate_fallback*_30/`：全局兜底；
- `experiment_06_local_rerank_30/`：局部候选LLM重排；
- `experiment_06b_weighted_rerank_30/`：BM25:Dense权重。

当前最重要的开发集结果：

- PageIndex局部Dense Top-20经LLM Rerank后，30题Dense组R@5从56.7%提高到88.3%；
- 固定全局兜底可能降低召回；
- 纯Dense、BM25:Dense=1:2和1:3在候选覆盖上漏掉相同的三道Top-3路由失败题；
- 这些结论来自反复使用的30题开发集，不能作为新项目的无偏最终结论。

新项目应把它们当作检索基线和问题动机，而不是直接写成普适结论。

## 6. 冻结快照

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/snapshots/
```

约6.7MB，包含：

- `20260813_smoke30_retrieval_v1/`；
- `20260813_experiment01_top10_v1/`。

每个快照含`MANIFEST.md`、配置、`runs.jsonl`、CSV和HTML。若新项目需要引用旧实验结果，优先使用快照而不是可能继续变化的`outputs/`。

## 7. 文字实验报告

位置：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/reports/
```

可复用内容：

- `00_baseline_smoke30.md`：基线；
- `01_top10_depth.md`：返回深度；
- `02_03_route_nodes.md`：路由节点；
- `04_global_fallback.md`：兜底；
- `05_failure_diagnosis.md`：失败分层；
- `06_local_rerank.md`：局部Rerank；
- `06b_hybrid_weight.md`：Hybrid权重；
- `07_progressive_active_reading.md`：中间方向，已被后续思想部分修正；
- `08_generative_document_understanding_progress.md`：生成式理解阶段总结；
- `09_generative_document_unit_full_report.md`：新项目完整思想报告。

新项目应以08和09为主要思想来源，00至06B作为旧检索基线，07只作为思路演变记录。

## 8. 测试资产

测试目录：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/tests/
```

当前包含：

- Chunk与检索器测试；
- 配置继承与路径解析；
- 数据集、树绑定和Embedding测试；
- 失败诊断；
- 指标与报告；
- Reranker；
- 路由缓存；
- Hybrid权重筛选。

这些测试默认离线，不调用DeepSeek。新项目迁移基础能力时应同步迁移相关测试，避免页码、向量顺序和指标定义发生静默变化。

## 9. 环境

当前使用：

```text
Conda环境：ai_learning
Embedding服务：Ollama
Embedding模型：bge-m3:latest
Embedding维度：1024
LLM接口：LiteLLM + DeepSeek
```

实验额外依赖：

```text
numpy>=1.24
tiktoken>=0.7
PyYAML>=6.0
```

PageIndex主项目依赖仍来自仓库根目录`requirements.txt`。新项目不应只复制实验requirements而忽略PDF和PageIndex相关依赖。

## 10. API密钥与安全

项目根目录`.gitignore`包含：

```gitignore
.env*
```

不要复制或提交当前`.env`，不要在交接文档、配置、测试或新仓库历史中写入真实DeepSeek Key。新项目应自行创建被忽略的`.env`并在启动前确认：

```bash
git check-ignore -v .env
```

不要将API返回的敏感内容、私有文档或用户上传文件放入公开仓库。本次FinanceBench是公开研究数据，但新项目仍应检查数据集和原仓库许可证。

## 11. 当前Git状态

交接时当前工作树存在尚未提交的修改和新增文件，包括配置、运行入口、测试与报告。新项目不能假定这些内容已经在Git历史中。

在复制或迁移前，用户应自行审查：

```bash
git status --short
git diff --check
```

不要由新项目Codex擅自执行`git reset --hard`、覆盖或删除当前工作树。所有现有修改都应视为用户资产。

## 12. 推荐迁移顺序

### 第一批：研究定义

优先带走：

```text
reports/09_generative_document_unit_full_report.md
reports/08_generative_document_understanding_progress.md
NEXT_PROJECT_HANDOFF.md
```

### 第二批：最小数据与基线代码

带走数据适配、Schema、PDF解析、Chunk、Embedding、检索器、指标和测试。先保持旧基线可复现，再添加新研究能力。

### 第三批：小规模缓存

初期不必复制全部84份PDF。可以先选择少量已缓存文档，但必须同时迁移对应PDF、`manifest.json`、`tree.json`、`chunks.jsonl`和`embeddings.npy`。

### 第四批：正式评测资产

研究定义稳定后再引入全部FinanceBench数据、输出和快照。

## 13. 新项目第一阶段应避免的事情

- 不立即重新付费生成46份PageIndex；
- 不继续索引剩余38份文档，除非实验明确需要；
- 不直接训练复杂多Agent或强化学习系统；
- 不把流畅重写当作理解标签；
- 不只使用反复调试过的30题作为最终测试；
- 不将PageIndex摘要当作原文事实；
- 不将所有旧代码整体复制后直接大改，导致基线无法复现；
- 不复制`.env`或API Key；
- 不破坏`chunks.jsonl`与`embeddings.npy`的行顺序。

## 14. 新项目建议保留的基线

新项目至少应保留：

```text
BM25
Dense（bge-m3）
Hybrid/RRF
PageIndex
PageIndex + Dense/Hybrid
PageIndex + Dense + LLM Rerank
普通全文摘要
```

这些基线用于回答：生成式文档理解单元究竟比“更好的检索”或“更长的摘要”多提供了什么。

## 15. 给新项目Codex的工作原则

1. 讨论阶段不要修改文件，除非用户明确要求；
2. 付费API调用前必须说明预计调用范围和成本，并获得用户明确授权；
3. 所有批量任务先在小样本运行；
4. 任何新表示必须保留原文证据与页码；
5. 区分事实、结构推断和解释性假设；
6. 报告索引成本、查询成本、Token、延迟和存储；
7. 按文档划分训练、开发与测试，避免同一文档泄漏；
8. 新研究结论必须与旧PageIndex + Hybrid基线公平比较；
9. 不把旧30题开发集结果声称为普适结论；
10. 始终保留可复现的配置、原始逐题结果和冻结快照。

## 16. 建议的新项目启动提示词

用户可以在新项目中向Codex提供以下说明：

```text
请先阅读NEXT_PROJECT_HANDOFF.md和09_generative_document_unit_full_report.md。
本项目研究“生成式文档理解单元”：目标是在保持原文证据问答精度的同时，
保存文章的写作目的、主体思想、结构、体裁经验、章节功能和跨章节关系。
旧PageIndex项目只作为数据、检索和评价基线。未经我明确授权，不要修改文件、
复制密钥、调用付费API或批量处理文档。先核对可复用资产，再提出新项目边界。
```

## 17. 交接结论

旧项目最值得复用的不是某个PageIndex参数，而是：

- 公开长文档与证据标注；
- 46份已付费生成的完整索引缓存；
- 成熟的Chunk、Embedding和检索基线；
- 可复现的指标、成本与HTML报告；
- 已经形成的失败诊断经验；
- 从检索导航发展到生成式文档理解的研究论述。

新项目应把这些资产作为地基，而不是继续在旧目录中叠加越来越多实验分支。

