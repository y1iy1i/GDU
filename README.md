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

项目已经完成三次提问驱动生长：财务数字闭合、论文来源冲突和国家标准规范合规判断。三者共用同一个通用晋升事务层。当前全仓测试结果为 `227 passed, 5 skipped`。

## 阅读入口

只需先读 [GDU V1 研究路径](docs/current/GDU_RESEARCH_PATH_V1.md)，其中已统一当前研究目标、三层逻辑主干＋两个横向模块、Builder 最小架构、成长轮次方法和 V1 完成判据。

需要核对某项结论时，再查看 [实验导航](docs/experiments/README.md)。全部 Markdown 和截图中旧文件的用途见 [文档导航](docs/README.md)。

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
- `src/gdu/builder_v1/`：统一 Evidence Block、来源验证、解析器适配和最小 Document Map；
- `src/gdu/growth_v01.py` 与 `growth_pgkd_v01.py`：财务与论文方法的领域验证规则；
- `src/gdu/growth_ai_labeling_v01.py`：GB 45438-2025 规范义务与合规检查规则；
- `scripts/run_growth_promotion_v01.py`：从固定输入重放 v0.2 生长事件。
- `scripts/build_evidence_manifest_v1.py`：从 PDF 物理页生成可重放的 V1 证据清单和文档地图。

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

第三领域实验表明，通用逻辑、答案和晋升事务层无需修改，但新领域的规则抽取和节点构建仍需较多手工代码。当前最明确的瓶颈是通用 Builder，而不是图的生长事务或答案执行。
