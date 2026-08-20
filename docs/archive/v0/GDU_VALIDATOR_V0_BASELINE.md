# GDU v0 Validator 基线冻结说明

> 冻结日期：2026-08-19  
> 上游依据：冻结的 GDU v0 设计基线与 Schema 基线  
> 性质：本地机械验证工具，不是 Builder、Reader 或语义评价器。

## 冻结范围

- `src/gdu/validator_v0.py`：新七块 v0 的命令行验证器。
- `tests/test_validator_v0.py`：正例、反例、冻结包与退出码测试。
- `requirements-validator.txt`：唯一额外依赖 `jsonschema`。
- `GDU_VALIDATOR_V0.md`：安装、命令和验证边界说明。
- `GDU_VALIDATOR_V0_VALIDATION_REPORT.md`：测试与实现验证结果。

以上文件及本说明的 SHA-256 记录在 `GDU_VALIDATOR_V0_BASELINE.sha256`。

## 冻结时结果

- 新 v0 验证器测试：15 个通过。
- 旧 v0.1 历史回归测试：8 个通过。
- 合计：23 个测试通过。
- `gdu.example.json`：命令行验证通过。
- 默认 Python 若缺少 `jsonschema`：明确返回工具错误，不静默跳过。

## 负责范围

验证器负责 Schema、ID、引用、物理树、页码、功能回指、关系端点、解释组首选、Evidence 哈希/bbox，以及 frozen 包的最小完整性检查。

它不负责事实真值、证据充分性、关系语义、最佳单元边界、Plan 内容忠实性或 GDU 的效果优越性。

## 已知边界

`build_log.jsonl` 尚无独立 Schema，因此当前只检查逐行 JSON 对象和 frozen 包中存在 `event_type=freeze`。四类事件的条件字段必须在后续阶段单独规范化。

## 变更规则

本基线不原位修改。任何新检查、错误码变化或命令行变化都创建新候选版本，并重跑新旧全部测试后再冻结。
