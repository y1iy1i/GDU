# GDU v0 设计基线勘误记录

> 日期：2026-08-19  
> 原则：不修改已冻结文件或既有哈希；Schema 以冻结逻辑规格为规范来源。

## E-001 极小实例的 Plan 多写 Evidence 引用

- 位置：`GDU_MINIMAL_HUMAN_EXAMPLE_V0.md` 的 `GenerativePlan / content_selection`。
- 冻结文字：引用中包含 `E-002`、`E-003`。
- 规范规则：`GDU_MINIMAL_LOGICAL_SPEC_V0.md` 第 9 节规定 Plan 只引用 assertion、semantic unit、relation 和必要 interpretation group；Evidence 由这些对象间接展开。
- 处理：`gdu.schema.json` 不允许 Plan 直接保存 Evidence 引用；`gdu.example.json` 只引用 `A-001`—`A-004`。
- 性质：示例抄写错误，不改变 GDU v0 理论结构，因此不发布新的设计版本。

## E-002 极小实例的 E-002 片段哈希与摘录不匹配

- 位置：`GDU_MINIMAL_HUMAN_EXAMPLE_V0.md` 的 Evidence `E-002`。
- 冻结文字：摘录使用原文正确表述“扣除非经常性损益后的净利润”，但哈希来自少了“后”字的早期字符串。
- 正确 SHA-256：`cad66da0d2a64006ce8b9ee4b4cdd5b2990aed66a1b79a92c0cb123b902d6fb6`。
- 处理：`gdu.example.json` 保留正确摘录并使用正确哈希；机械验证直接对 JSON 字符串的 UTF-8 字节重算。
- 性质：示例数据完整性错误，不改变 Evidence 的字段设计或 GDU v0 理论结构，因此不原位修改冻结文件。
