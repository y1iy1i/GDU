# GDU v0 设计基线冻结说明

> 冻结日期：2026-08-19  
> 性质：研究设计基线，不是已完成的软件版本，也不是 GDU 效果优于现有知识存储体系的结论。

## 冻结范围

- `GDU_MINIMAL_LOGICAL_SPEC_V0.md`：最小逻辑规格。
- `GDU_MINIMAL_COMPLEXITY_AUDIT_V0.md`：C-001—C-009 复杂度审计。
- `GDU_PILOT_MAPPING_AUDIT_V0.md`：三轮 Pilot 表示能力映射审计。
- `GDU_MINIMAL_HUMAN_EXAMPLE_V0.md`：真实年报片段的极小人类可读实例。

以上文件及本说明的 SHA-256 记录在 `GDU_V0_DESIGN_BASELINE.sha256`。

## 已完成的门槛

- 四层主干与七个逻辑块已确认。
- 重复事实源与职责重叠已逐项审查。
- 两篇英文 NLP 论文和一份中文长篇年报均可映射。
- 极小实例同时容纳来源判断、派生计算、分析限制、关系、证据、Plan 与构建修订。
- GenerativePlan 被限制为已有对象的组织层，不能成为第二事实源。

## 尚未完成

- 尚未建立 JSON Schema、验证器、Builder 或 Reader 实现。
- 尚未完成 GDU 与 Chunk/RAG、PageIndex 或其他知识存储体系的正式对照实验。
- 尚不能宣称 GDU 有效、优越或适合生产环境。

## 变更规则

本基线文件不原位修改。任何语义、字段或约束变更都应：

1. 创建新的候选版本；
2. 记录变更原因和受影响对象；
3. 重新执行复杂度、Pilot 映射与最小实例检查；
4. 生成新的冻结哈希清单。

下一阶段可以基于本设计基线起草 JSON Schema；Schema 必须忠实翻译本基线，不得趁实现时偷偷新增理论结构。
