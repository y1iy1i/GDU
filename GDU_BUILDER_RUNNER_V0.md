# GDU Builder v0 可复现运行器

日期：2026-08-19

状态：实现候选，尚未冻结。

## 1. 大白话说明

以前的 Builder 只能在测试代码里被拼装起来。现在可以把一次实验需要的文件、哈希、六个阅读请求、固定 Adapter 和运行上限写进一份 JSON 配置，再用一条命令生成三文件 GDU 包。

这一层解决的是“别人能否按照同一设置重跑 Builder”，不是“模型是否已经会自动理解任意长文档”。

## 2. 专业定义

- `builder-run-v0.schema.json` 是运行配置的 JSON Schema；
- `config.py` 负责 Schema 验证、路径边界、文件哈希和运行对象构造；
- `fixture_adapter.py` 把已验证 GDU 夹具按 CP1–CP6 重放，但不向 Builder 直接提供规范 ID；
- `cli.py` 是可独立调用的命令行入口；
- `builder-run-pilot03.example.json` 是 Pilot 03 的实例配置。

## 3. 配置锁定的东西

- PDF 与预抽取文本的相对路径和 SHA-256；
- GDU Schema、Build Log Schema 和 Builder Protocol 的路径、版本与 SHA-256；
- Fixed GDU 夹具和 SHA-256；
- 模型/适配器身份三元组；
- CP1–CP6 恰好六个 SourceRequest；
- 两次语义修正、一次全局技术重试、单 Builder 和禁止外部知识。

配置文件中的路径必须相对于配置所在目录，不允许绝对路径或 `..` 越界。命令行显式给出的一次性输出目录除外。

## 4. Fixed Adapter 的诚实边界

Fixed Adapter 不调用模型，也不产生新理解。它的作用是用固定内容检验 Builder 的编排、证据授权、ID 分配、日志、停止门和产物发布。

Pilot 03 冻结示例里有两个表格 excerpt 是人工合并的教学摘要，不是 PDF 文本层中的连续字串。运行器不修改冻结示例，也不放宽证据规则；重放时会在内存中用同页的完整权威文本片段替换不连续摘要，并重算片段哈希。

## 5. 运行方式

项目的标准验证环境为 Conda `gdu`（Python 3.12）。安装 `requirements-builder.txt` 中的运行依赖后，在项目根目录执行：

```bash
PYTHONPATH=src python -m gdu.builder_v0.cli run \
  --config builder-run-pilot03.example.json
```

配置的输出目录必须不存在。临时实验可以使用 `--output-dir` 覆盖。

退出码：

- `0`：`frozen_complete`；
- `1`：Builder 已运行，但结果不是 frozen complete；
- `2`：配置、依赖或启动失败。

## 6. 当前不能得出的结论

- 不能证明 GDU 比现有知识库更好；
- 不能证明小模型能自动选页或读懂 237 页文档；
- 不能证明表格、图像、公式和 OCR 证据已被解决；
- 不能把 Fixed Adapter 的成功当成真实模型理解质量。
