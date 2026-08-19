# GDU v0 Schema 基线冻结说明

> 冻结日期：2026-08-19  
> 上游依据：`GDU_V0_DESIGN_BASELINE.md` 及 `GDU_V0_DESIGN_BASELINE.sha256`  
> 性质：可机械检查的格式基线，不是 Builder、Reader 或效果实验结论。

## 冻结范围

- `gdu.schema.json`：JSON Schema Draft 2020-12 格式规则。
- `gdu.example.json`：真实年报片段的规范化 JSON 正例。
- `GDU_V0_BASELINE_ERRATA.md`：上游冻结样例的外部勘误。
- `GDU_SCHEMA_V0_VALIDATION_REPORT.md`：正例、跨对象检查和反例测试结果。

以上文件及本说明的 SHA-256 记录在 `GDU_SCHEMA_V0_BASELINE.sha256`。

## 状态说明

`gdu.example.json` 的 GDU 对象状态为 `provisional`，因为它是局部教学实例而非完整文档冻结理解；该 JSON 文件作为 Schema 回归测试输入则被冻结。对象状态与测试文件状态承担不同职责。

## 已验证

- Schema 元规范和真实 JSON 正例通过。
- 引用闭包、物理树、关系端点、页码范围和片段哈希的一次性检查通过。
- 七种违反关键条件的反例均被 Schema 拒绝。
- Plan 不能直接保存 Evidence 引用。

## 尚未完成

- 尚无可重复运行的正式 GDU 验证器程序。
- 尚未定义 `build_log.jsonl` 的独立 Schema。
- 尚未实现 Builder 或 Reader。
- 尚未进行与 Chunk/RAG、PageIndex 等体系的效果对照。

## 变更规则

本 Schema 基线不原位修改。后续发现格式问题时，先记录问题并创建新候选版本；通过正例、反例和上游逻辑一致性复查后，再生成新的基线与哈希清单。
