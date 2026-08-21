# GDU 实验记录导航

本目录保存已运行或可重放的研究证据。实验报告记录当时的输入、方法、结果和边界，不与 [V1 研究路径](../current/GDU_RESEARCH_PATH_V1.md) 并列为系统规范。

## `logic/`

逻辑接口、真实文档映射、可审计回答、查询规划和自修复：

- `GDU_CANDIDATE_LOGIC_ARCHITECTURE_V0_1.md`：三层＋两模块的理论起点与接口约束；
- `GDU_LOGIC_INTERFACE_REPORT_V0_1—V0_4.md`：逻辑接口逐步验证；
- `GDU_LOGIC_REAL_DOCUMENT_REPORT_V0_1.md`：真实年报切片上的精确对账、阻错和失效重算；
- `GDU_ANSWER_EXECUTION_REPORT_V0_1.md`：从 accepted 论证生成带证据答案；
- `GDU_QUERY_PLANNER_THEORY_AND_EXPERIMENT_V0_1.md`：自然语言问题到目标 Atom 与缺口的映射；
- `GDU_SELF_REPAIR_EXPERIMENT_REPORT_V1.md`：错误发现、依赖失效和修复实验。

## `growth/`

问题驱动成长、隔离候选、通用晋升与三领域闭环：

- `GDU_QUERY_DRIVEN_GROWTH_EXPERIMENT_*`：早期查询驱动生长计划与实验；
- `GDU_FIRST_CLOSED_LOOP_GROWTH_REPORT_V0_1.md`：财务数字闭合；
- `GDU_SECOND_NONFINANCIAL_GROWTH_REPORT_V0_1.md`：论文正文、图与算法冲突；
- `GDU_GENERIC_PROMOTION_FRAMEWORK_REPORT_V0_1.md`：多领域共用的安全晋升事务；
- `GDU_THIRD_NORMATIVE_GROWTH_REPORT_V0_1.md`：规范义务、局部满足、违规和整体合规判断。

## `builder/`

Builder V1 从原文到逻辑结构的编译实验：

- `GDU_BUILDER_V1_EVIDENCE_INTERFACE_REPORT.md`：统一 Evidence Block、确定性验证、上游解析器适配和最小 Document Map。
- `GDU_BUILDER_V1_REPRESENTATION_COMPILER_REPORT.md`：命题表示理论筛选、隔离候选、数值/范围/来源校验与 AIF-like 种子图编译。
- `GDU_BUILDER_V1_REPRESENTATION_BLIND_01_SETUP.md`：三领域首次受约束盲抽取的冻结输入、隐藏 Gold、评分器和实际运行记录。
- `GDU_BUILDER_V1_REPRESENTATION_BLIND_01_REPORT.md`：首次 DeepSeek 真实响应、原始 50% 评分、逐候选审计、Gold 修正和四个一般问题族。
- `GDU_BUILDER_V1_MINIMAL_LOGIC_CONTRACT.md`：首轮盲测后确定的命题状态、表格位置、数值规范化和三类比较契约。

## `benchmarks/`

可行性门、外部复现、表示消融和 Chunk RAG 对照。这些文件用于回答“GDU 的净价值是什么”，不定义当前 Builder 接口。

## `models/`

Adapter 契约、远程模型检查点和横向模型运行记录。模型运行结果不自动成为 GDU 逻辑规格。

## 阅读原则

- 查找当前方向：读 `docs/current/GDU_RESEARCH_PATH_V1.md`；
- 核对某个实验结论：读对应 `REPORT`；
- 重现实验：同时检查 `research_inputs/`、`scripts/` 和测试；
- 报告中的历史测试数量保持当时记录，当前总数以根 `README.md` 为准。
