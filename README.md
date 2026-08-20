# GDU — Generative Document Understanding

GDU（Generative Document Understanding，生成式文档理解单元）是一个面向长文档理解与知识持久化的研究项目。

项目文档统一采用“简介、机制说明、结果解读、执行规则”等正式栏目名称。少量已冻结基线中的早期口语化标题仅为保持哈希与实验可复现性而保留，不代表当前写作规范。

它研究的不是“怎样把文档切得更碎”，而是：

> 怎样让系统逐步形成、核验、修正并保存对整份文档的理解，同时让重要判断能够回到原文证据。

## 系统分工

- **Builder**：离线读取文档，通过六个检查点形成并修正理解。
- **GDU**：冻结后的持久表示，保存文档结构、语义单元、断言、关系、整体生成计划与证据。
- **Reader**：在查询阶段读取冻结 GDU；它是后续对照实验的测量工具。

当前采用“四层主干＋贯穿机制”：原文与结构、局部理解、关系理解、整体生成理解；证据接地、不确定性/多解释和全局—局部修正贯穿其中。

## 当前完成状态

- 已冻结 GDU v0 设计、Schema、离线 Validator 和 Build Log v0 基线；
- 已在两篇英文 NLP 论文和一份 237 页中文上市公司年报上完成三轮 Pilot；
- 已实现确定性 Builder v0 候选：六检查点、有限修正、全局技术重试、证据授权、日志、停止门和原子发布；
- 已实现最小 PDF 文本层 SourceReader、可验证的运行配置、Fixed GDU Adapter 和 CLI；
- 当前 101 个唯一测试已在独立 Conda `gdu` 环境中全部通过；
- 已建立 Adapter v1 结构化契约、离线 Transcript 与受限远程 Transport；
- 远程 API 的 Schema、提供商样例和使用规则统一位于 `configs/api/`；
- 第一次 Qwen CP1 真实候选通过 Adapter JSON 契约，但因 `page_range` 字段形状错误被 GDU Schema 拒绝，未进入 Builder；
- Qwen CP1 在补充字段形状后通过三层机械验证，但扩大到第 8–12 页后仍把章节范围写为 8–8，没有完成边界理解目标；
- 后续正式远程实验默认切换为 `deepseek-v4-flash-0731`，Qwen 结果保留作模型对照；
- DeepSeek 已在相同第 1、8–12 页输入上返回 9 个机械合格对象，正确识别第二节 8–12 及第 12 页的第三节起点；
- CP2 已在第 8–12 页完成首个局部语义单元实验：模型在两次有界定向修正后，把归母净利润、扣非净利润和非经常性损益组织成 1 个语义单元、3 条内容断言和 1 条功能断言；
- CP3 已在第 9–12 页完成并行解释实验：模型在一次定向修正后，同时保存“经营改善”和“投资公允价值变化”两个解释，并用 `undetermined` 约束明确禁止无证据的贡献排序；
- Pilot 03 已用“配置 + CLI”完成真实 PDF 到 frozen 三文件包的临时往返。

当前的 Fixed Adapter 只重放已验证内容，它证明 Builder 基础设施可运行、可复现，不证明真实模型已会自动理解任意长文档。

## 七块存储结构

GDU v0 使用七个规范化存储分工（不等于七层理解架构）：

- `manifest`
- `physical_structure`
- `semantic_units`
- `assertions`
- `relations`
- `generative_plan`
- `evidence`

## 快速入口

- [`GDU_V0_DESIGN_BASELINE.md`](GDU_V0_DESIGN_BASELINE.md)：冻结设计基线；
- [`gdu.schema.json`](gdu.schema.json)：当前冻结 Schema；
- [`gdu.example.json`](gdu.example.json)：最小人工 GDU 实例；
- [`GDU_VALIDATOR_V0.md`](GDU_VALIDATOR_V0.md)：离线验证器；
- [`BUILDER_PROTOCOL_V2.md`](BUILDER_PROTOCOL_V2.md)：Builder 协议；
- [`GDU_BUILDER_SKELETON_V0.md`](GDU_BUILDER_SKELETON_V0.md)：Builder 实现说明；
- [`GDU_BUILDER_RUNNER_V0.md`](GDU_BUILDER_RUNNER_V0.md)：配置、Fixed Adapter 和 CLI；
- [`GDU_DISCUSSION_LOG_V2.md`](GDU_DISCUSSION_LOG_V2.md)：完整研究决策记录。

## 本地验证

```bash
conda activate gdu
python -m pip install -r requirements-test.txt
PYTHONPATH=src python -m unittest discover -s tests -v
```

当本地已放置 Pilot 03 的预登记 PDF 和提取文本时，可运行：

```bash
PYTHONPATH=src python -m gdu.builder_v0.cli run \
  --config builder-run-pilot03.example.json
```

运行前请确保配置中的输出目录尚不存在。公开仓库不必附带第三方原始 PDF，可通过配置中的 SHA-256 核对本地文件。

## 当前不作出的主张

本项目目前不声称：

- GDU 已在公平实验中优于 Chunk/RAG、PageIndex、知识图谱或其他知识存储体系；
- Fixed Adapter 的成功等于真实模型理解成功；
- 当前纯文本 SourceReader 已解决 OCR、图像、表格视觉结构或公式；
- 强模型上的可行性可直接推广到小模型。

Builder v0 确定性基础设施已冻结。下一个研究节点是将真实模型 Adapter 和长文档选页/分段作为独立变量开始实验。
