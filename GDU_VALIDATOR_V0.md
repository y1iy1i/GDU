# GDU v0 最小验证器

> 状态：GDU v0 Validator 基线已冻结。  
> 入口：`src/gdu/validator_v0.py`  
> 适用 Schema：根目录冻结的 `gdu.schema.json`。
> 冻结规则：由外部 `GDU_VALIDATOR_V0_BASELINE.sha256` 校验；后续修改必须创建新版本。

## 1. 大白话说明

这个工具是 GDU 文件的“质检员”。它不读文章、不调用模型，也不判断理解是否正确；它只检查 GDU 的零件是否齐全、编号和引用能否对上、页码与哈希有没有明显错误。

## 2. 安装依赖

验证器只有一个额外 Python 依赖：

```bash
python -m pip install -r requirements-validator.txt
```

不需要 OpenAI API Key，也不会产生模型调用费用。

如果当前 Python 没有安装依赖，工具会明确报告 `schema_dependency_missing`，不会静默跳过 Schema 检查。

## 3. 验证 provisional GDU

```bash
python src/gdu/validator_v0.py gdu.example.json
```

成功输出：

```text
VALID: gdu.example.json
```

指定其他 Schema：

```bash
python src/gdu/validator_v0.py path/to/gdu.json --schema path/to/gdu.schema.json
```

## 4. 验证 frozen GDU 包

冻结对象必须同时提供构建日志和外部哈希清单：

```bash
python src/gdu/validator_v0.py path/to/gdu.json \
  --build-log path/to/build_log.jsonl \
  --artifacts path/to/ARTIFACTS.sha256
```

当前对 `build_log.jsonl` 只做最小检查：每个非空行必须是 JSON 对象，并且至少存在一个 `event_type: "freeze"` 事件。完整 build log 字段规则尚未建立独立 Schema。

## 5. 退出码

- `0`：全部机械检查通过；
- `1`：GDU 或冻结包无效；
- `2`：文件无法读取、JSON 损坏、Schema 本身无效或缺少验证依赖。

## 6. 当前检查范围

- JSON Schema Draft 2020-12；
- ID 跨对象全局唯一；
- 引用存在并指向正确对象类型；
- physical tree 单根、无循环、子页码位于父范围；
- 页码不超过 PDF 总页数；
- 语义单元的主要/次要功能与 function assertion 双向一致；
- assertion 输入、基础判断、Evidence 与 unit 引用闭包；
- relation 同层级端点、自连接和对称关系重复；
- interpretation group 的首选属于成员；
- GenerativePlan 四类引用闭包；
- Evidence 摘录 UTF-8 SHA-256、页码和 bbox 基本范围；
- frozen GDU 的 freeze 事件、哈希清单、必需文件和防路径穿越。

## 7. 明确不检查

- 原文事实是否真实；
- Evidence 是否足以支持判断；
- assertion 是否真正原子化；
- relation 是否在语义上成立；
- semantic unit 划分是否最佳；
- GenerativePlan 是否暗中增加新事实；
- GDU 是否比 Chunk/RAG 或 PageIndex 更有效。

机械验证通过只表示“格式和引用没有发现错误”，不表示“理解正确”。

## 8. 自动测试

使用包含 `jsonschema` 的 Python 环境运行：

```bash
python -m unittest discover -s tests -v
```

当前结果：23 个测试通过，其中 15 个针对新 v0 验证器，8 个为旧 v0.1 历史回归测试。新测试也覆盖命令行退出码 `0/1/2`。

## 9. 与旧验证器的关系

`src/gdu/validators.py`、`schemas/gdu-v0.1.schema.json` 和 `examples/gdu-minimal.example.json` 属于较早研究结构。它们保留用于历史回归，不与新的七块 v0 Schema 混用。
