# GDU v0 极小人类可读实例

> 对象状态：`provisional` 教学与结构检验实例；不是 JSON、JSON Schema 或 Builder 实现。  
> 文件状态：作为 GDU v0 设计基线冻结，由外部哈希清单校验；后续修改必须创建新版本。  
> 来源：江苏利通电子股份有限公司 2025 年年度报告中的“归母净利润—扣非净利润—非经常性损益”片段。  
> 目的：用一个真实片段同时检验七块、三种认识论来源、限制关系、Evidence 定位和五问式 Plan。

## 1. Manifest

### GDU 身份

- GDU ID：`gdu-example-litong-profit-v0`
- 逻辑规格：`gdu-minimal-logical-v0-draft`
- 产物版本：`0.1.0-example`
- 状态：`provisional`
- 构建完成时间：`2026-08-19T15:45:52+0800`

### 来源身份

- 文档 ID：`litong-2025-annual-report`
- 标题：江苏利通电子股份有限公司2025年年度报告
- 语言：`zh-CN`
- 文档类型：上市公司年度报告
- 原始文件名：`paper.pdf`
- PDF SHA-256：`fbb9875c7eca1f921ca0635cabbe53727b7ff57658750fa0eeefd92402730c59`
- PDF 物理页数：237
- 文本提取物 SHA-256：`d3258943647ba57408471fd43ece8d52415e75ec4f39df16c63861d4af450c9a`
- 提取说明：文本只用于定位，PDF 是唯一权威内容来源

### 构建身份

- 来源 Builder 协议：`gdu-builder-protocol-v2`
- 协议 SHA-256：`072d827ea6b8cba103af6ffbd3767a4094fc2f4825e51dedc8d921fa513be041`
- 来源运行模型：`gpt-5.6-sol`
- 来源运行推理档位：`high`
- 本实例处理：按 C-001—C-009 对冻结 Pilot 03 对象进行人工规范化投影
- 构建日志：本文件第 9 节的示例事件；正式产物时应独立为 `build_log.jsonl`

## 2. Physical structure

### `PS-001`

- 父节点：无（文档根）
- 类型：`document`
- 原文标签：江苏利通电子股份有限公司2025年年度报告
- 顺序：1
- PDF 物理页：1–237
- 结构证据：`E-001`

### `PS-002`

- 父节点：`PS-001`
- 类型：`section`
- 原文标签：第二节 公司简介和主要财务指标
- 顺序：2
- PDF 物理页：8–12
- 结构证据：`E-004`
- 观察说明：本极小实例只展开其中与 2025 年利润及非经常性损益有关的连续范围

## 3. Semantic unit

### `U-001`：利润及非经常性损益解释单元

- 物理结构引用：`PS-002`
- PDF 连续范围：9–11
- Evidence：`E-002`、`E-003`
- 局部概览：并列披露归母净利润、扣非归母净利润和非经常性损益合计，使读者能够区分利润总量与非经常部分。
- 主要功能 assertion：`A-006`
- 次要功能 assertions：无

此处不保存普通 assertion 列表。需要时由各 assertion 的 `semantic_unit_refs` 反向得到 `A-001`—`A-006`。

## 4. Assertions

### `A-001`：2025 年归母净利润

- kind：`content`
- statement：公司 2025 年归属于上市公司股东的净利润为 292,589,095.99 元。
- semantic_unit_refs：`U-001`
- epistemic_origin：`source_attributed`
- 归因主体：江苏利通电子股份有限公司
- 表达模式：`explicit`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`
- rationale：年报主要会计数据表直接列示该金额。

### `A-002`：2025 年扣非归母净利润

- kind：`content`
- statement：公司 2025 年归属于上市公司股东的扣除非经常性损益后的净利润为 235,942,443.22 元。
- semantic_unit_refs：`U-001`
- epistemic_origin：`source_attributed`
- 归因主体：江苏利通电子股份有限公司
- 表达模式：`explicit`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`
- rationale：年报主要会计数据表直接列示该金额。

### `A-003`：2025 年非经常性损益合计

- kind：`content`
- statement：公司 2025 年非经常性损益合计为 56,646,652.77 元。
- semantic_unit_refs：`U-001`
- epistemic_origin：`source_attributed`
- 归因主体：江苏利通电子股份有限公司
- 表达模式：`explicit`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-003`
- rationale：年报非经常性损益表直接列示合计金额。

### `A-004`：非经常性损益占归母净利润比例

- kind：`content`
- statement：2025 年非经常性损益约占归母净利润的 19.36%。
- semantic_unit_refs：`U-001`
- epistemic_origin：`derived`
- input_assertion_refs：`A-003`、`A-001`
- formula：`56,646,652.77 ÷ 292,589,095.99 × 100%`
- 舍入说明：未舍入结果约 19.360480%，四舍五入到小数点后两位
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：输入金额均已由原文证据接地，计算为确定性除法。

### `A-005`：利润口径限制

- kind：`constraint`
- statement：不能把 2025 年归母净利润全部解释为经常性经营成果。
- semantic_unit_refs：`U-001`
- epistemic_origin：`analytic_interpretation`
- basis_assertion_refs：`A-001`、`A-002`、`A-003`、`A-004`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：归母净利润中约 19.36% 被报告划分为非经常性损益，而扣非净利润另有明确口径。

### `A-006`：语义单元主要功能

- kind：`function`
- function_tag：`constrain`
- statement：本单元通过并列利润口径和计算非经常性占比，限制读者把归母净利润直接等同于经常性经营成果。
- semantic_unit_refs：`U-001`（必须且仅有一个目标）
- epistemic_origin：`analytic_interpretation`
- basis_assertion_refs：`A-001`—`A-005`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：该连续范围不仅报告利润总量，还专门披露扣非口径与非经常性损益明细。

### Interpretation groups

无。当前片段存在口径限制，但没有两种仍有根据且会改变主旨的竞争解释，不为展示字段而虚构解释组。

## 5. Relations

### `R-001`：非经常性损益构成归母净利润的一部分

- 端点层级：`assertion`
- from_ref：`A-003`
- to_ref：`A-001`
- type：`composes`
- description：非经常性损益是归母净利润与扣非归母净利润之间的组成差额。
- epistemic_origin：`source_attributed`
- 归因主体：江苏利通电子股份有限公司
- 表达模式：`entailed`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：A-002 与 A-003 之和恰等于 A-001，且三个金额由同一年度报告口径披露。

### `R-002`：非经常性占比限制利润解释

- 端点层级：`assertion`
- from_ref：`A-004`
- to_ref：`A-005`
- type：`supports`
- description：计算出的非经常性占比支持对归母净利润口径施加解释限制。
- epistemic_origin：`analytic_interpretation`
- basis_assertion_refs：`A-001`—`A-004`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：19.36% 不是可忽略的零值，因此总净利润与经常性经营成果不能无条件画等号。

### `R-003`：口径限制作用于利润总量判断

- 端点层级：`assertion`
- from_ref：`A-005`
- to_ref：`A-001`
- type：`limits`
- description：A-005 限定 A-001 可以支持的经营质量解释范围。
- epistemic_origin：`analytic_interpretation`
- basis_assertion_refs：`A-001`—`A-005`
- assessment_complete：`true`
- evidence_status：`supported`
- Evidence：`E-002`、`E-003`
- rationale：A-001 的金额真实成立，但仅凭该金额不能判断其中全部来自经常性经营活动。

## 6. GenerativePlan

### `purpose`

- 简短综合：让读者看见公司 2025 年归母净利润总量，并辨认其中非经常性部分。
- 引用：`U-001`、`A-006`

### `core_meaning`

- 简短综合：归母净利润为 2.9259 亿元，其中约 19.36% 属于非经常性损益；利润总量和经常性经营成果需要分开阅读。
- 引用：`A-001`—`A-005`、`R-001`—`R-003`

### `content_selection`

- 简短综合：选择归母净利润、扣非归母净利润、非经常性损益合计及其占比，形成最小充分解释集合。
- 引用：`A-001`—`A-004`、`E-002`、`E-003`

### `organization`

- 简短综合：先列两个原文利润口径，再计算占比，最后施加解释边界。
- 引用：`R-001`、`R-002`

### `constraints`

- 简短综合：解读 A-001 的利润总量时，必须保留 A-005 所表达的口径限制。
- 引用：`A-005`、`R-003`

## 7. Evidence

片段哈希均对下列“短摘录”所显示的 UTF-8 字符串逐字计算；不是整页或整份 PDF 的哈希。

### `E-001`

- modality：`text`
- PDF 物理页：1
- locator：封面标题
- 短摘录：`江苏利通电子股份有限公司2025年年度报告`
- fragment SHA-256：`6bedfc3d9907a169b112f70e848381156ce8b1485a8fdedb423e3c5913ebdfe9`

### `E-002`

- modality：`table`
- PDF 物理页：9
- locator：第二节“近三年主要会计数据和财务指标”之“主要会计数据”表，2025 年列
- 短摘录：`归属于上市公司股东的净利润 292,589,095.99；归属于上市公司股东的扣除非经常性损益后的净利润 235,942,443.22。`
- fragment SHA-256：`415a9b8e6f79645cb91b19f99b9abee725f6aa46ba6d5734a72508db2623fa0e`

### `E-003`

- modality：`table`
- PDF 物理页：11
- locator：第二节“非经常性损益项目和金额”表，2025 年合计行
- 短摘录：`非经常性损益合计 56,646,652.77 元。`
- fragment SHA-256：`f1eb75014819a643910f24667ee597f4f62a2251ad6586f0cfa5f8cadc49c2a7`

### `E-004`

- modality：`text`
- PDF 物理页：8
- locator：章节起始标题
- 短摘录：`第二节 公司简介和主要财务指标`
- fragment SHA-256：`4568e5a4e7a9ba0507bafa2831f6f80d5e73f87b1994b76ee4c79023a4d334a6`

三条 Evidence 都继承 Manifest 的唯一源文档，不重复保存 `source_ref`。

## 8. 机械检查结果

- 七个逻辑块齐全：通过。
- ID 唯一、引用均存在：通过。
- function assertion 恰有一个目标 unit：通过。
- 其他 assertions 的 unit 归属为合法的 0..n：通过。
- derived assertion 具有输入和公式：通过。
- source-attributed relations 具有主体、表达模式和 Evidence：通过。
- analytic relations 具有基础判断、理由和 Evidence：通过。
- relation 两端同为 assertion：通过。
- 五问式 Plan 齐全且未建立第二套事实：通过。
- 当前是 provisional 实例：不要求 `freeze` 事件或 `ARTIFACTS.sha256`。

## 9. Build log 示例

### `EV-001` — checkpoint

- 逻辑时间：1
- 阶段：来源与局部对象
- 公开理由：已定位 PDF 物理页 9 和 11 的三项同口径利润数据。
- 对象引用：`E-002`、`E-003`、`U-001`

### `EV-002` — revision

- 逻辑时间：2
- change_type：`replace`
- 修改前：旧 Pilot A-008 在一条判断中混合来源金额、Builder 算术和分析结论。
- 修改后：拆为 `A-001`—`A-005`，分别标记 source-attributed、derived 和 analytic-interpretation。
- 触发证据：`E-002`、`E-003`
- 受影响对象：旧 `A-008`；新 `A-001`—`A-005`
- 仍有效备选：无
- 公开理由：不同认识论来源必须分开接受证据与公式检查。

### `EV-003` — checkpoint

- 逻辑时间：3
- 阶段：证据审查与机械检查
- 公开理由：所有持久判断和关系均已完成证据审查，引用闭包与条件字段检查通过。
- 对象引用：`A-001`—`A-006`、`R-001`—`R-003`

本实例不写 `freeze` 事件，因为它仍是用于发现设计问题的 provisional 样例。

## 10. 实例暴露并已处理的两个文字层问题

1. relation 的“基础 assertion 引用”不能是所有来源的共同必填字段；它只应由 `analytic_interpretation` relation 强制要求。`source_attributed` relation 使用主体、表达模式和 Evidence。
2. `GenerativePlan` 的简短综合文字必须被明确限制为对象的语言压缩，不能加入引用对象中不存在的新数字、因果关系或外部事实。

第 1 项已按 C-009 修正；第 2 项已由用户确认并写入逻辑规格。两个问题均已处理。
