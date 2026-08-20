# GDU v0 build log 最小规范

> 状态：GDU v0 Build Log 基线已冻结。  
> 事件 Schema：`build_log.schema.json`  
> JSONL 正例：`build_log.example.jsonl`
> 冻结规则：由外部 `GDU_BUILD_LOG_V0_BASELINE.sha256` 校验；后续修改必须创建新版本。

## 1. 大白话说明

`gdu.json` 保存“现在认为文章是什么”，`build_log.jsonl` 保存“哪些重要认识后来发生了变化，以及为什么变化”。它不是聊天记录，也不保存模型完整思考过程。

每一行都是一个独立 JSON 事件。新事件只能追加到文件末尾，不能回头覆盖旧事件。

## 2. 四类事件

### `revision`

记录理解发生了实质变化：修改前是什么、修改后是什么、属于晋升/替换/降格/保留备选/撤回中的哪一种、由哪些 Evidence 触发、影响哪些对象、还有哪些备选继续有效。

### `checkpoint`

记录一个阶段检查已经完成或停止门检查通过/失败。它保存检查名称、结果和简短结果摘要；如果检查由特定来源证据触发，可以引用 Evidence。

### `technical`

只记录会影响复现或正式产物的技术事件，例如解析工具不可用、发生了什么影响、怎样处理，以及最终是解决、绕过还是仍未解决。普通命令执行不进入日志。

### `freeze`

只有覆盖度、证据度和稳定度全部通过才能写入。它记录最终产物版本，并指向外部 `ARTIFACTS.sha256`；不把 GDU 或 build log 自身的最终哈希写回日志，避免循环引用。

## 3. 共同字段

- `event_id`：稳定事件 ID；
- `logical_time`：严格递增的整数时间；
- `timestamp`：RFC 3339 时间；
- `event_type`：四类事件之一；
- `stage`：构建阶段；
- `object_refs`：与事件有关的对象引用，可为空；
- `rationale`：公开、简短、可审计的记录理由。

## 4. 顺序规则

单行 JSON Schema 之外还必须检查：

- 事件 ID 在同一日志中唯一；
- `logical_time` 按文件顺序严格递增，不要求连续；
- provisional 日志可以没有 freeze；
- frozen 日志必须恰有一个 freeze；
- freeze 必须是最后一条事件，后续变化创建新版本和新日志。

## 5. 引用边界

build log 可以引用后来被撤回、替换或只存在于旧版本中的对象，因此不能要求所有历史 `object_refs` 和 `affected_refs` 都出现在最终 `gdu.json`。`trigger_evidence_refs` 应指向触发当时版本中的 Evidence；跨版本核对留给未来版本工具。

## 6. 明确禁止

- 逐 Token 思考或隐藏推理；
- 全部未晋升临时候选；
- 每次搜索、每条命令或普通文件读取；
- 重复保存完整 GenerativePlan；
- Gold、评分答案或与构建无关的任务对话；
- 在 freeze 事件中制造自哈希或循环哈希。

## 7. 当前验证方式

使用包含 `jsonschema` 的 Python 环境执行全部测试：

```bash
python -m unittest discover -s tests -v
```

当前 32 个测试全部通过，其中 9 个针对 build log Schema 与顺序规则。

当前冻结的 Validator v0 只粗略检查 JSONL 与 freeze 事件；由于其文件已冻结，本阶段不原位修改。下一版 Validator 才会接入事件 Schema和完整顺序规则。
