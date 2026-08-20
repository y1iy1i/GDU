# GDU v0 Build Log 基线冻结说明

> 冻结日期：2026-08-19  
> 上游依据：冻结的 GDU v0 设计、Schema 与 Validator 基线  
> 性质：Builder 关键过程事件契约，不是完整内部思维记录。

## 冻结范围

- `build_log.schema.json`：JSONL 单条事件 Schema。
- `build_log.example.jsonl`：覆盖四类事件的五行正例。
- `tests/test_build_log_schema.py`：事件条件和跨行顺序测试。
- `GDU_BUILD_LOG_V0.md`：事件语义、顺序、引用和排除边界。
- `GDU_BUILD_LOG_V0_VALIDATION_REPORT.md`：Pilot 映射及正反例结果。

以上文件及本说明的 SHA-256 记录在 `GDU_BUILD_LOG_V0_BASELINE.sha256`。

## 冻结时结果

- build log 专项测试：9 个通过。
- 新旧全项目测试：32 个通过。
- revision、checkpoint、technical、freeze 四类事件均有正例。
- 三轮 Pilot 的关键 BUILD_TRACE 信息均可映射，未发现第五种事件需求。

## Builder 约束

Builder 只能追加符合事件 Schema 的关键事件；不得记录逐 Token 思考、隐藏推理、全部临时候选、普通搜索命令或重复完整 Plan。

freeze 事件必须是 frozen 日志最后一行，只在覆盖度、证据度和稳定度全部通过后产生，并指向外部哈希清单，不内嵌循环哈希。

## 已知边界

冻结 Validator v0 尚未逐行调用本事件 Schema，也未检查完整逻辑时间顺序。该能力必须创建 Validator 新版本，不能原位修改已冻结实现。

## 变更规则

本基线不原位修改。新增事件类型、字段、顺序规则或日志语义必须创建新候选版本，并重新执行三轮 Pilot 映射和全部测试。
