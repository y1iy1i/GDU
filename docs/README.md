# GDU 文档导航

文档按“当前主线、实验证据、历史材料、冻结档案”分开。了解项目不需要从头阅读全部 Markdown。

## 最短阅读路径

1. [GDU V1 研究路径](current/GDU_RESEARCH_PATH_V1.md)：当前目标、三层逻辑主干＋两个横向模块、Builder 架构、成长方法和评价判据；
2. [实验导航](experiments/README.md)：需要核对某项结论时再读具体报告；
3. [v0 档案说明](archive/v0/README.md)：只在复现早期 Builder、Schema 或 Validator 时阅读。

## 目录用途

| 目录 | 用途 | 是否代表当前方案 |
|---|---|---|
| `docs/current/` | V1 当前研究主线 | 是 |
| `docs/experiments/` | 实验计划、过程、对照和结果 | 否，它们是证据 |
| `docs/history/` | 讨论记录、交接、过渡方案和早期计划 | 否 |
| `docs/archive/v0/` | 已冻结或已被后续主线取代的 v0 资产 | 否 |
| `research_inputs/` | 各次实验的来源冻结、Gold、场景和重放图 | 只对应具体实验 |

## 常见文件名的意义

| 名称特征 | 作用 |
|---|---|
| `*_PLAN.md` | 实验方法、输入、指标和执行顺序 |
| `*_REPORT.md` | 已运行实验的结果与边界 |
| `*_BASELINE.md` | 用于重放或对照的冻结基线 |
| `*_VALIDATION_REPORT.md` | 对某个规格、实现或基线的检查结果 |
| `*_DRAFT.md` | 历史形成过程，不作为当前接口 |
| `GOLD_*.md` | 独立评价所用的参考答案或标注 |
| `SOURCE_FREEZE.md` | 记录实验来源、版本和哈希 |
| `*.sha256` | 文件完整性校验值，不是需要阅读的报告 |

## 截图中那些文件的用途

截图中以下名称都来自早期 v0 研究，现位于 `docs/archive/v0/` 或 `docs/history/`：

| 文件簇 | 历史用途 |
|---|---|
| `GDU_FEASIBILITY_*` | 早期可行性进入条件与对照结果 |
| `GDU_MINIMAL_*` | v0 最小逻辑规格、人工示例和复杂度审计 |
| `GDU_PILOT_MAPPING_*` | 早期 Pilot 映射是否丢失信息的检查 |
| `GDU_RESEARCH_*` | 早期研究规格或讨论记录 |
| `GDU_SCHEMA_*` | v0 JSON Schema 基线与验证结果 |
| `GDU_SOURCE_READER_*` | v0 原文读取器设计与检查 |
| `GDU_SOURCE_WIRING_*` | 原文读取器与 Builder 的连接实验 |
| `GDU_VALIDATOR_*` | v0 校验器、基线和验证报告 |
| `GDU_V0_*` | v0 整体设计基线和勘误 |
| `NEXT_PROJECT_*` | 阶段交接记录 |
| `PILOT_*_PLAN.md` | 对应早期实验的执行计划 |

这些文件没有删除，因为它们仍可用于重现早期实验、检查决策演变和验证哈希。它们不再与 V1 主线并列。

## 根目录保留项

仓库根目录只保留：

- `README.md`：项目首页；
- `BUILDER_PROTOCOL_V2.md` 及其哈希：旧 Builder 代码仍直接引用的冻结运行协议；
- 依赖、配置、Schema 和运行入口。

## 维护原则

- `docs/current/` 只保留当前主线；
- 实验报告只移动、不反向改写当时结论；
- 冻结基线与哈希不做静默修改；
- 新的总体方向写入 V1 主线，具体结果写入对应实验目录。
