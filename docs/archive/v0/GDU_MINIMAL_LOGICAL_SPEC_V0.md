# GDU 最小逻辑规格 v0 草案

> 状态：GDU v0 设计基线已冻结；不是 JSON Schema，不修改旧 Schema，也不是 Builder 实现。  
> 日期：2026-08-19  
> 依据：三轮盲 Builder 实验、冻结 Gold 对照及 V2-154—V2-183 用户确认决策。
> 冻结规则：本文件由外部 `GDU_V0_DESIGN_BASELINE.sha256` 校验；后续修改必须创建新版本，不原位覆盖。

## 1. 目标与边界

本规格定义单篇文档根 GDU 的最小持久语义，以及与其配套的轻量构建日志。目标是支持：

- 原文与版本可追溯；
- 局部内容与局部功能分离；
- 可独立核验的原子判断；
- 跨部分关系；
- 五问式整体生成理解；
- 来源证据展开；
- 不确定性、冲突和竞争解释保留；
- 后期证据对前期理解的关键差分记录。

v0 不包含领域 Profile、子 GDU、任意顶层扩展、外部知识融合、增量局部重建、Human View、查询历史、平台数据库或完整审核治理。

## 2. 四层主干与七个逻辑块

| 四层理解主干 | 持久逻辑块 |
|---|---|
| 原文与结构 | `manifest`、`physical_structure` |
| 局部理解 | `semantic_units`、`assertions` |
| 关系理解 | `relations` |
| 整体生成理解 | `generative_plan` |
| 贯穿全部层级 | `evidence` |

七块是规范化存储分工，不是七层认知架构。关键构建过程保存于独立 `build_log.jsonl`。

## 3. 冻结包

```text
gdu.json
build_log.jsonl
ARTIFACTS.sha256
```

- `gdu.json` 保存当前有效的冻结理解或明确标记的暂定快照。
- `build_log.jsonl` 追加记录关键修订、检查点、技术事件和冻结事件。
- `ARTIFACTS.sha256` 在前两项完成后记录其最终哈希，避免自哈希和循环引用。
- 原始 PDF 与文本提取物独立保存，通过 Manifest 中的身份和哈希连接，不复制进 GDU。

## 4. `manifest`

### 4.1 GDU 身份

- GDU ID；
- Schema 版本；
- 产物版本；
- `frozen` 或 `provisional` 状态；
- 构建完成时间。

### 4.2 来源身份

- 文档 ID、标题、语言和文档类型；
- 原始文件名；
- 原文 SHA-256；
- PDF 物理页数；
- 文本提取物 SHA-256；
- 影响证据定位的解析器或提取版本。

### 4.3 构建身份

- Builder 协议名称、版本和哈希；
- 模型标识和推理档位；
- 构建配置或提示哈希；
- `build_log` 的文件名或逻辑标识。

Manifest 不保存自身最终文件哈希、完整修订历史、详细成本、Gold、评价结果或查询历史。

## 5. `physical_structure`

每个可观察结构节点最少包含：

- 稳定 ID；
- 父节点 ID；
- 节点类型；
- 原文标题或标签；
- 原文顺序；
- 1-based PDF 物理页起止；
- 结构证据引用；
- 可选观察说明。

只保存原文真实可观察的标题、层级、顺序和范围。隐含逻辑大纲进入关系与 `GenerativePlan`。表格、图像和公式通常由 Evidence 定位，只有明确参与导航时才成为结构节点。

## 6. `semantic_units`

语义单元是锚定连续原文范围的局部理解卡，不是 Chunk。最少包含：

- 稳定 ID；
- 物理结构引用；
- 证据引用；
- 简短局部概览；
- 一个主要功能 assertion 引用；
- 最多两个次要功能 assertion 引用。

普通判断归属只在 assertion 的 `semantic_unit_refs` 保存；某单元的普通判断列表由 Reader 或索引层反向生成。局部概览不是第二套事实源；新的独立判断必须进入 `assertions`。远距离内容拆为多个单元后以关系连接。完整原文和计算 Chunk 不复制进语义单元。

### 6.1 局部功能标签

- `orient`
- `define`
- `motivate`
- `propose`
- `operationalize`
- `evidence`
- `interpret`
- `constrain`

功能判断属于 `analytic_interpretation`，必须附当前文档中的作用说明及证据。

## 7. `assertions`

### 7.1 共同字段

- 稳定 ID；
- 单一 `kind`；
- 原子化 `statement`；
- 可选 `semantic_unit_refs`；
- `epistemic_origin`；
- `assessment_complete`；
- `evidence_status`；
- Evidence 引用；
- 唯一的简短公开 `rationale`。

`function` assertion 必须且只能引用一个目标 semantic unit；其他 assertion 类型允许引用零个、一个或多个 semantic units，以表达全文级、局部或跨单元判断。

### 7.2 五种语义类型

- `content`：事实、定义、方法、结果及其他来源内容；
- `function`：语义单元的局部或全文作用；
- `plan`：目标、核心意义、内容选择、组织逻辑或整体解释；
- `constraint`：范围、时间、证据强度、推广、鉴证或允许推断的边界；
- `absence`：完成限定检查后仍未发现的重要内容。

每条 assertion 只有一个主要类型。复杂句通过原子化拆分和关系连接，不使用“内容/限制”等任意多标签组合。

### 7.3 三种认识论来源

- `source_attributed`：原文主体明确表达或较确定蕴含；条件字段为归因主体与 `explicit|entailed`。
- `derived`：由已接地输入通过公开公式或确定性规则计算；条件字段为输入 assertion、公式及可选单位/舍入说明。
- `analytic_interpretation`：Builder 的功能、综合、边界或显著缺失判断；额外条件字段为 `basis_assertion_refs`，理由统一写入共同 `rationale`。

不保存未经校准的统一数值置信度。

### 7.4 解释组

`assertions` 块内部允许轻量 `interpretation_groups`，最少保存：

- 组 ID；
- 高影响争议问题；
- `competing|parallel`；
- 统一 `member_refs`；
- 竞争模式下可选的 `preferred_ref`；
- 采用理由与未排除原因；
- 影响范围。

`parallel` 不设置首选；`competing` 的首选只是当前较优解释，不代表永久真值或概率排序。被证据推翻且不再合理的旧判断只留在构建日志。

## 8. `relations`

每条关系最少包含：

- 稳定 ID；
- `semantic_unit|assertion` 端点层级；
- `from_ref` 与 `to_ref`；
- 固定关系族；
- 当前文档中的具体说明；
- 认识论来源；
- `assessment_complete` 与 `evidence_status`；
- Evidence 引用；
- 简短公开理由。

### 8.1 八个关系族

- `elaborates`
- `supports`
- `limits`
- `depends_on`
- `motivates`
- `composes`
- `conflicts_with`
- `alternative_to`

`conflicts_with` 与 `alternative_to` 为对称关系；其余关系必须明确方向。Evidence 不作为关系端点。两端分别成立不等于连接成立，关系必须独立接地。

relation 的认识论来源只允许：

- `source_attributed`：必须保存归因主体、`explicit|entailed` 模式和 Evidence 引用；
- `analytic_interpretation`：必须保存 `basis_assertion_refs`，成立依据写入共同 `rationale`。

relation 不使用 `derived`。确定性计算先形成带输入 assertion 引用和公式的 derived assertion，再作为关系端点参与连接。关系的具体说明回答“连接表达什么”，`rationale` 回答“为什么认为连接成立”；两者均不得藏入新的独立命题。

## 9. `generative_plan`

固定包含五个部分：

- `purpose`
- `core_meaning`
- `content_selection`
- `organization`
- `constraints`

各部分引用 assertion、semantic unit、relation 和必要解释组，并允许简短综合文字。简短文字只能压缩、重组或组织被引用对象已经表达的内容，不得新增未在 assertions 中接地的数字、因果关系、外部事实或其他独立命题。Plan 不复制第二套事实或原文证据；新的独立命题必须先进入 assertion。

## 10. `evidence`

每条 Evidence 最少包含：

- 稳定 ID；
- 文本、表格、图像、公式或混合模态；
- 1-based PDF 物理页码；
- 页内文本位置或稳定定位；
- 受限短摘录；
- 片段哈希。

Evidence 继承 Manifest 中唯一权威源文档，不逐条保存 `source_ref`。表格按需增加区域、行列名或单元格定位；图像和公式按需增加页面区域或对象编号；跨页连续对象允许多个定位片段。同一证据集中保存一次并被多个对象引用。进入多来源 GDU 研究时必须重新设计来源引用。

## 11. 最小证据状态

- `assessment_complete=false`：尚未完成证据检查，不得填写最终结论。
- `supported`：支持当前表达。
- `partially_supported`：只支持部分范围或必须保留重要限定。
- `contested`：同时存在实质支持与挑战或来源冲突。
- `undetermined`：已经检查但证据仍不足以确定。

正式冻结版中的持久 assertion 与 relation 必须完成证据检查。未检查候选只留 Builder 工作状态；已被否定且不再是有效备选的对象只留构建日志。

## 12. `build_log.jsonl`

采用追加式关键事件日志，只保存：

- `revision`
- `checkpoint`
- `technical`
- `freeze`

共同字段包括事件 ID、逻辑时间、时间戳、事件类型、构建阶段、对象引用和公开理由。

`revision` 额外保存修改前/后简述、`promote|replace|downgrade|retain_alternative|withdraw`、触发证据、受影响对象和仍有效备选。日志不保存逐 Token 思考、隐藏推理、全部临时候选、每次搜索命令或重复完整 Plan 快照。

## 13. 自适应分支

文档触发的深入分析通过增加 semantic units、assertions、relations 和必要解释组表达，并由 Plan 引用；分支触发原因进入构建日志。v0 不开放任意顶层扩展字段或领域 Profile。

只有某类结构在多份同领域文档中反复出现，且现有对象无法有效查询、比较或验证时，才考虑升级为 Profile。

## 14. 最小机械验证

验证器可以检查：

- 七块、版本、必需字段和枚举；
- ID 唯一与引用闭包；
- 物理树无循环及页码范围；
- 语义单元功能数量；
- assertion 类型、来源及条件字段；
- assertion 的语义单元归属数量约束；
- Evidence 定位格式；
- relation 端点层级、方向、对称规则及来源条件字段；
- 五问式 Plan 完整性；
- 正式冻结对象的证据检查状态；
- 构建日志 freeze 事件；
- 外部产物哈希。

验证器不能判断现实真值、证据语义充分性、最佳语义边界、功能/关系准确性、主旨覆盖或隐蔽过度推断。

## 15. 复杂度审计结果

在创建任何 JSON Schema 前，已逐项检查：

1. 是否存在重复事实源；
2. 是否有能由引用或关系重算的字段；
3. 条件字段是否可以进一步收紧；
4. 三轮 Pilot 是否都能无损映射；
5. 是否能够构造一个最小示例而不依赖领域专用字段；
6. 是否仍能对 `GenerativePlan`、关系和定向回查做消融；
7. 是否清楚区分 GDU、Builder 日志和 Reader 临时状态。

C-001—C-009 已全部确认，三轮 Pilot 在表示能力层面的无损映射已通过。旧 Markdown 到新结构仍需进行类别拆分、认识论来源拆分、功能判断建立和证据状态归一，不能视为机械自动迁移。

下一步先构造一个极小的人类可读实例，检查全部条件能否同时落地；实例通过后，才讨论新的 JSON Schema。
