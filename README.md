# GDU — Generative Document Understanding

GDU（生成式文档理解单元）研究如何把长文档转换为可追溯、可推理、可修复并能持续生长的知识结构。

它不以 Chunk 作为最终知识单元。原文分段只负责证据读取和缺口回查；正式回答来自通过逻辑检查的外显论证路径。

## 当前系统

当前采用“三层逻辑主干＋两个横向模块”：

- 表示层：AIF-like 证据、命题、推理和冲突节点；
- 论证层：ASPIC+-like 严格推理与可废止推理；
- 接受层：Dung grounded semantics；
- 信息状态：Belnap 四值状态；
- 维护与追溯：TMS 依赖维护和 W3C PROV-style 来源记录。

已经完成的核心闭环：

```text
用户问题
→ 查询规划
→ 可接受论证路径搜索
→ 缺口检测
→ 受约束邻域扩散
→ 原文回查
→ 候选隔离与验证
→ 生成新版 GDU
→ 可审计回答
```

项目已经完成两次提问驱动生长：一次是财务数字闭合，一次是论文正文、流程图与算法之间的来源冲突。两者已共用同一个通用晋升事务层，冻结的实验输出保持不变。当前全仓测试结果为 `209 passed, 5 skipped`。

## 阅读入口

建议按以下顺序了解当前研究：

1. [研究目标](docs/current/GDU_REASONING_GRAPH_OBJECTIVE_V1.md)
2. [候选逻辑架构](docs/current/GDU_CANDIDATE_LOGIC_ARCHITECTURE_V0_1.md)
3. [真实文档逻辑实验](docs/current/GDU_LOGIC_REAL_DOCUMENT_REPORT_V0_1.md)
4. [可审计回答实验](docs/current/GDU_ANSWER_EXECUTION_REPORT_V0_1.md)
5. [查询规划理论与实验](docs/current/GDU_QUERY_PLANNER_THEORY_AND_EXPERIMENT_V0_1.md)
6. [第一次正式生长闭环](docs/current/GDU_FIRST_CLOSED_LOOP_GROWTH_REPORT_V0_1.md)
7. [第二次非财务生长实验](docs/current/GDU_SECOND_NONFINANCIAL_GROWTH_REPORT_V0_1.md)
8. [通用生长晋升框架](docs/current/GDU_GENERIC_PROMOTION_FRAMEWORK_REPORT_V0_1.md)

完整文档导航见 [docs/README.md](docs/README.md)。

## 仓库结构

```text
docs/current/             当前研究主线
docs/experiments/         可复现实验计划与报告
docs/archive/v0/          已冻结或已被后续主线取代的 v0 资产
docs/history/             讨论记录、交接说明和早期研究材料
src/gdu/                  GDU 实现
tests/                    自动测试
research_inputs/          冻结输入、Gold 和版本化真实图
scripts/                  实验与重放脚本
configs/api/              API 配置样例，不保存密钥
schemas/                  辅助 Schema
```

根目录只保留运行入口、Schema、依赖文件和仍被代码直接引用的 `BUILDER_PROTOCOL_V2.md`。

## 当前主要实现

- `src/gdu/logic_v01.py`：逻辑接口、论证编译、接受语义和局部失效重算；
- `src/gdu/answer_v01.py`：从被接受的论证生成可审计答案；
- `src/gdu/query_planner_v01.py`：问题结构、Context、目标命题和缺口规划；
- `src/gdu/promotion_v01.py`：通用候选包络验证和原子化晋升事务；
- `src/gdu/growth_v01.py` 与 `growth_pgkd_v01.py`：财务与论文方法的领域验证规则；
- `scripts/run_growth_promotion_v01.py`：从固定输入重放 v0.2 生长事件。

## 本地验证

```bash
conda activate gdu
python -m pip install -r requirements-test.txt
PYTHONPATH=src:. pytest -q
```

旧 Builder 流程仍可使用：

```bash
PYTHONPATH=src python -m gdu.builder_v0.cli run \
  --config builder-run-pilot03.example.json
```

## 当前边界

目前已经证明一个真实财务文档切片能够被完整对账、推理、阻错、修复和版本化生长，但尚未证明：

- GDU 在多个领域稳定优于强 Chunk RAG 或其他知识图方案；
- 长文档可以在很少人工参与的情况下稳定建出同等质量的图；
- 当前两跳扩散适合大规模图；
- 当前结构中的每个模块都不可进一步删除。

下一项研究是用第三类文档任务测量新领域的接入成本，判断通用晋升框架是否真正降低了 GDU 的迁移复杂度。
