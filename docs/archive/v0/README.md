# GDU v0 档案说明

本目录保存已冻结或已被 V1 主线取代的早期资产。当前研究入口为 [GDU V1 研究路径](../../current/GDU_RESEARCH_PATH_V1.md)。

## 文件分组

| 文件簇 | 用途 |
|---|---|
| `GDU_MINIMAL_*` | v0 最小逻辑规格、人工示例和复杂度审计 |
| `GDU_SCHEMA_*` | v0 Schema 基线与验证报告 |
| `GDU_VALIDATOR_*` | v0 Validator 设计、基线和验证报告 |
| `GDU_BUILD_LOG_*` | v0 Build Log 设计、基线和验证报告 |
| `GDU_SOURCE_READER_*` | v0 原文读取器与检查 |
| `GDU_SOURCE_WIRING_*` | Source Reader 与 Builder 的连接实验 |
| `GDU_BUILDER_*` | v0 Builder 接口、骨架、Runner、状态机和基线 |
| `BUILDER_PROTOCOL_V2_DRAFT.md` | Builder Protocol v2 的形成记录；正式冻结版位于仓库根目录 |
| `GDU_FEASIBILITY_*` | 早期可行性决策门 |
| `GDU_PILOT_MAPPING_*` | Pilot 到 v0 结构的无损映射检查 |
| `GDU_V0_*` | v0 整体设计基线和勘误 |

## 为什么保留

- 复现早期实验；
- 核对设计决策的演变；
- 验证历史哈希；
- 测试当前架构是否损失 v0 曾经覆盖的能力。

## 使用规则

- 不把本目录文件当作 V1 当前接口；
- 不修改带 `BASELINE` 的文件及对应 `.sha256`；
- 文件名中的 `DRAFT` 表示它是历史形成记录；
- 仓库根目录的 `BUILDER_PROTOCOL_V2.md` 仍被旧 Builder 代码直接引用，因此没有移入本目录。
