# GDU 文档导航

文档按用途分类，而不是全部堆放在仓库根目录。

## 当前主线

`current/` 只保留理解当前系统所必需的九份文档：

1. `GDU_REASONING_GRAPH_OBJECTIVE_V1.md`：研究目标和边界；
2. `GDU_CANDIDATE_LOGIC_ARCHITECTURE_V0_1.md`：三层逻辑主干与两个横向模块；
3. `GDU_LOGIC_REAL_DOCUMENT_REPORT_V0_1.md`：真实年报逻辑映射；
4. `GDU_ANSWER_EXECUTION_REPORT_V0_1.md`：可审计回答执行；
5. `GDU_QUERY_PLANNER_THEORY_AND_EXPERIMENT_V0_1.md`：问题到图查询的映射；
6. `GDU_FIRST_CLOSED_LOOP_GROWTH_REPORT_V0_1.md`：第一次正式数据库生长闭环。
7. `GDU_SECOND_NONFINANCIAL_GROWTH_REPORT_V0_1.md`：跨正文、图与算法冲突的非财务生长。
8. `GDU_GENERIC_PROMOTION_FRAMEWORK_REPORT_V0_1.md`：两个领域共用的生长安全事务层。
9. `GDU_THIRD_NORMATIVE_GROWTH_REPORT_V0_1.md`：GB 45438-2025 义务、违规和局部合规推理。

文件名中的 `V0_1` 表示对应接口或实验版本，不表示它属于已归档的旧 v0 设计。

## 实验记录

`experiments/` 保存计划、对照和阶段报告：

- `logic/`：逻辑接口与自修复实验；
- `growth/`：早期查询驱动增长实验；
- `benchmarks/`：外部复现、表示消融和 Chunk RAG 对照；
- `models/`：Adapter 及远程模型检查点实验。

这些文件是研究证据，不等于当前系统规范。

## v0 档案

`archive/v0/` 保存早期设计、Builder v0、Schema/Validator/Build Log 基线、草案及对应哈希文件。

归档原则：

- 不删除；
- 不静默修改冻结内容；
- 不把草案当作当前接口；
- 需要重现实验时按原文件名和哈希核对。

运行代码仍直接依赖的 `BUILDER_PROTOCOL_V2.md` 留在仓库根目录，没有移入档案。

## 历史材料

`history/` 保存讨论日志、项目交接、早期研究规格和 Pilot 计划。它们用于了解决策过程，不作为当前实现说明。

## 其他重要入口

- 当前真实图：`research_inputs/replication_01_lafang_2025/GDU_LOGIC_REAL_SLICE_V0_2.json`；
- 当前逻辑代码：`src/gdu/logic_v01.py`；
- 当前查询规划：`src/gdu/query_planner_v01.py`；
- 当前通用生长晋升：`src/gdu/promotion_v01.py`；
- 当前领域生长规则：`src/gdu/growth_v01.py` 与 `src/gdu/growth_pgkd_v01.py`；
- 当前规范生长规则：`src/gdu/growth_ai_labeling_v01.py`；
- 全部测试：`tests/`。
