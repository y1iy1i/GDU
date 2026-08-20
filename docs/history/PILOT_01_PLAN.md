# GDU Pilot 01：真实文档表示可行性

> 状态：待实现  
> 日期：2026-08-14  
> 目标：验证一份真实长文档能否进入GDU v0.1内核，并从同一内核生成Agent与人类视图

## 1. 冻结样本文档

首个真实样本选择`AMD_2022_10K`。

选择依据只使用离线资产与覆盖信息，不使用旧方法的实验得分：

- 121页，处于46份完整缓存文档的中等长度范围；
- 220个Chunk；
- 42个PageIndex节点，其中6个顶层节点；
- Embedding形状为`(220, 1024)`，与Chunk行数一致；
- FinanceBench中有7道现成事实问题，便于检查事实能力是否回退；
- PDF、`manifest.json`、`tree.json`、`chunks.jsonl`和`embeddings.npy`均存在。

缓存目录：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/cache/documents/467ab8e1fc3a57394a5d/
```

PDF：

```text
<local-pageindex-workspace>/experiments/retrieval_benchmark/data/raw/financebench/pdfs/AMD_2022_10K.pdf
```

该样本仅用于验证表示、出处和视图流程，不用于声称统计提升。

## 2. 本轮输入与输出

输入保持只读，不复制Embedding，不改变旧Chunk顺序。

预期输出：

```text
artifacts/pilot_01_amd_2022_10k/
├── gdu.json
├── human_view.md
├── agent_view.json
├── validation.json
└── BUILD_MANIFEST.json
```

所有输出均为可重新生成的实验产物，不作为源代码提交对象。

## 3. 实现步骤

1. 编写旧`manifest/tree/chunks`的只读适配器；
2. 计算并记录PDF、树和Chunk文件哈希；
3. 将Chunk映射为`source_units`，将PageIndex层级映射为初始`sections`；
4. 只使用可追溯原文生成少量`fact`、`purpose`、`main_idea`和`section_function`主张；
5. 对高阶主张明确区分`explicit`、`entailed`、`inferred`和`hypothesis`；
6. 运行JSON Schema与语义验证器；
7. 从同一`gdu.json`渲染Human View和Agent View；
8. 使用7道已有FinanceBench题做事实回归检查；
9. 人工编写并双人审查少量跨章节与章节功能题后，再评价高阶能力。

## 4. 付费调用门

适配器、哈希、结构映射、Schema验证和视图渲染全部先离线完成。

若需要LLM生成目的、主体思想、章节功能或高阶问题，必须先提交：

- 使用的模型与提示版本；
- 输入页数或Token估算；
- 预计请求数和费用；
- 可否先用更小章节样本验证；
- 用户明确授权记录。

未经授权，不运行该步骤。

## 5. 完成条件

- `gdu.json`同时通过JSON Schema和语义验证；
- 220个Chunk均保持稳定引用且页码有效；
- 42个PageIndex节点均有明确映射或排除说明；
- 人类视图与Agent视图引用相同内核ID；
- 所有事实数字可回到原始Chunk和PDF页码；
- 7道现有事实题有逐题回归结果；
- 构建时间、Token、费用和存储体积均被记录；
- 不修改旧项目缓存与原始PDF。
