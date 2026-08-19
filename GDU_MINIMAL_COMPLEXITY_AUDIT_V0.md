# GDU v0 最小逻辑结构复杂度审计草案

> 状态：审计完成，作为 GDU v0 设计基线冻结。  
> 日期：2026-08-19  
> 审计对象：`GDU_MINIMAL_LOGICAL_SPEC_V0.md`  
> 冻结规则：本文件由外部 `GDU_V0_DESIGN_BASELINE.sha256` 校验；后续修改必须创建新版本。

## 1. 审计目标

检查候选结构是否存在重复事实源、可重算字段、条件字段过宽、对象职责重叠或没有三轮 Pilot 支持的复杂机制。

## 2. 初步结论

- 四层主干、七个逻辑块、单文档根 GDU、五问式 Plan、Evidence 独立复用及独立 build log 均有三轮产物支持，暂不建议删除。
- 当前未发现需要新增顶层块、领域 Profile、子 GDU、任意扩展字段、概率置信度或完整推理图的实证依据。
- 发现 5 项可明确减重、2 项建议保留、2 项需要澄清条件字段。

## 3. 待审查减重项

### C-001 语义单元—判断双向引用｜已确认

- 当前候选：semantic unit 保存 `assertion_refs`，assertion 同时保存 `semantic_unit_refs`。
- 风险：同一归属关系保存两次，修改时可能不一致。
- 建议：只在 assertion 保存可选 `semantic_unit_refs`；semantic unit 的关联判断列表由反向索引重算。语义单元仍保留主要/次要功能引用，因为功能优先级不能由普通反向索引推出。
- 决定：采纳。普通判断归属以 assertion 为唯一事实源；Reader 或索引层按需生成语义单元的反向判断列表。

### C-002 assertion 理由重复｜已确认

- 当前候选：所有 assertion 有共同 `rationale`，分析解释又要求“公开综合理由”。
- 风险：同一理由重复两次。
- 建议：只保留共同 `rationale`；分析解释额外保存 `basis_assertion_refs`，不再新增第二个理由字段。
- 决定：采纳。`rationale` 是唯一理由字段；分析解释仅通过 `basis_assertion_refs` 增加依据来源。

### C-003 解释组候选列表重复｜已确认

- 当前候选：同时保存候选列表、当前工作解释和备选列表。
- 风险：候选列表等于当前解释与备选的并集，是可重算字段。
- 建议：统一保存 `member_refs`，竞争模式可选 `preferred_ref`；并行模式不设首选。删除重复候选/备选数组。
- 决定：采纳。解释成员只保存一次；`preferred_ref` 仅表达竞争模式下当前较优解释，不代表永久结论或概率排序。

### C-004 Evidence 的 `source_ref`｜已确认

- 当前范围：v0 只允许单篇文档根 GDU，外部知识和多来源融合暂缓。
- 风险：每条 Evidence 重复引用唯一来源。
- 建议：Evidence 默认继承 Manifest 中唯一权威文档，不保存 `source_ref`；未来进入多来源 GDU 时再新增。
- 决定：采纳。该删除只对单篇权威源文档的 v0 有效；多来源融合不直接沿用此约束。

### C-005 relation 的 `derived` 来源｜已确认

- 当前候选尚未限制 relation 可用的认识论来源。
- 风险：确定性计算应先形成 derived assertion，关系本身不存在独立的“计算来源”，开放三类会增加无用组合。
- 建议：relation 只允许 `source_attributed` 或 `analytic_interpretation`；计算结果先进入 assertion，再参与关系。
- 决定：采纳。relation 不使用 `derived`；所有确定性计算先形成包含输入引用与公式的 derived assertion。

## 4. 建议保留项

### C-006 `assessment_complete`｜已确认

- 表面上正式冻结版中该值总为 true，但 provisional 快照需要区分“未检查”和“检查后不确定”。
- 建议：保留，不与 `evidence_status` 合并。
- 决定：采纳。该字段记录审查流程是否完成，`evidence_status` 记录审查结果，二者语义不同。

### C-007 relation 的 `description` 与 `rationale`｜已确认

- `description` 说明连接具体表达什么；`rationale` 说明为什么认为连接成立。
- 建议：二者职责不同，保留，但都限制为简短文本且不得藏入新的独立命题。
- 决定：采纳。`description` 说明关系语义，`rationale` 说明成立依据；新增独立命题必须另建 assertion。

## 5. 待澄清项

### C-008 assertion 的语义单元归属｜已确认

- 来源内局部判断通常属于一个单元；跨章节 derived 或 analytic assertion 可能引用多个单元；全局 plan assertion 可能不直接属于任何单元。
- 建议：`semantic_unit_refs` 为可选数组；function assertion 必须且只能引用一个目标单元；其他类型允许 0..n。
- 决定：采纳。数量约束由 assertion kind 决定，不强迫全局或跨单元判断伪装成单一局部判断。

### C-009 relation 的来源归因条件字段｜已确认

- 来源有时明确建立关系，更多关系由 Builder 综合形成。
- 建议：`source_attributed` relation 必须保存归因主体和直接/蕴含模式；`analytic_interpretation` relation 保存基础判断和理由。
- 决定：采纳。两类来源使用各自必需的条件字段，并共同接受独立证据审查。

## 6. 审查顺序

按 C-001—C-005 确认减重，再确认 C-006—C-009 的保留与条件规则。全部完成后才回写逻辑规格草案并做三轮 Pilot 无损映射检查。

## 7. 最终审计结果

- C-001—C-009 均已由用户逐项确认，并已统一回写逻辑规格草案。
- 三轮 Pilot 的来源、结构、局部功能、判断、关系、计划、证据及关键修订均存在明确承载位置。
- 混合类别、混合认识论身份和旧证据状态仍需人工规范化；这属于迁移判断，不是表示能力缺口。
- 详细记录见 `GDU_PILOT_MAPPING_AUDIT_V0.md`。
- 当前不创建 JSON Schema 或实现代码；先验证一个极小人类可读实例。
