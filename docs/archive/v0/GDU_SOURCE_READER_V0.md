# GDU SourceReader v0 最小实现说明

状态：已作为 Builder v0 确定性基础设施的一部分冻结。

## 1. 大白话说明

SourceReader 是“原文证据管理员”。它不负责理解文章，也不决定怎样切分长文档，只负责确认：

- 读的是不是预登记的那份 PDF；
- 请求的物理页是否存在；
- 一段文字是否真的出现在指定 PDF 页；
- 导航文本和 PDF 权威证据有没有混在一起；
- 最终证据片段的哈希能不能复算。

## 2. 当前实现

实现文件：`src/gdu/builder_v0/source_reader.py`。

核心对象：

- `SourceRequest`：读取目的、物理页范围、载体和定位提示；
- `SourceDocumentIdentity`：文档 ID、文件名、PDF 哈希、物理页数和抽取系统；
- `SourcePacket`：PDF 权威片段、单独存放的导航文本和读取说明；
- `PdfPageFragment`：页码、定位、摘录及与 GDU Validator 一致的 SHA-256；
- `PypdfBackend`：可选的真实 PDF 文本层读取后端。

## 3. 已落实规则

- PDF 页码一律使用从 1 开始的物理页；
- 重叠页范围按首次出现顺序去重；
- 页码越界、倒序或空请求直接拒绝；
- 可要求 PDF SHA-256 必须与预登记值一致；
- inspect 后 PDF 字节发生改变，后续读取立即停止；
- navigation text 只能帮助定位，不能进入 `pdf_fragments`；
- evidence excerpt 必须能在指定 PDF 页的文本层中找到；
- 摘录规范化后按 UTF-8 计算 SHA-256，可直接映射到 GDU evidence fragment；
- 没有文本层的页面明确记录“未尝试 OCR”；
- v0 只支持文本层，图像、表格视觉结构、公式和 mixed 请求不会被静默降级；
- 加密 PDF 在 v0 中明确拒绝。

## 4. 没有实现的能力

- 未实现 OCR；
- 未返回 bbox 或表格单元格坐标；
- 未渲染图片，也未做视觉核验；
- 未实现目录树、PageIndex、MinerU、chunk、向量检索或自动选页；
- 未决定长文档缓存和并发策略；
- 未接模型 API。

这些不是遗漏，而是为了让“证据读取能力”和“长文档策略”保持为两个可分别实验的变量。

## 5. 依赖边界

真实后端需要 `pypdf`，完整 Builder 验证还需要 `jsonschema`，记录在 `requirements-builder.txt`。

标准验证环境是 Conda `gdu`（Python 3.12.13）；直接依赖在 `requirements-builder.txt` 与 `requirements-test.txt` 锁定，完整环境记录在 `requirements-lock.txt`。实例运行配置还会校验提取后端身份 `pypdf 6.16.1`。

## 6. 下一步

SourceReader 已通过依赖注入接到 Orchestrator，并已由可保存配置和 CLI 完成字节级可复现往返。后续的自动选页、分段、OCR 和视觉读取必须作为新版本，不原位改动 v0。
