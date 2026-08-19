# GDU v0 Schema 首次验证报告

> 日期：2026-08-19  
> Schema：`gdu.schema.json`  
> 正例：`gdu.example.json`  
> 状态：验证通过，作为 GDU v0 Schema 基线冻结。

## 1. 本阶段产物

- `gdu.schema.json`：JSON Schema Draft 2020-12；翻译七个逻辑块、字段、枚举、条件必填和禁止组合。
- `gdu.example.json`：由冻结的年报极小实例规范化得到的 JSON 正例。
- `GDU_V0_BASELINE_ERRATA.md`：记录冻结人类样例中的两项抄写/数据完整性错误，不修改冻结基线。

验证快照哈希：

| 文件 | SHA-256 |
|---|---|
| `gdu.schema.json` | `9a4384dd92e32a8bc8572c7776ac7a3b26ac9198eb54c8ae1b90e62c0c17692f` |
| `gdu.example.json` | `7f80577ff0cf3df838778ba4ff9ed1d23b5bdc645be7030bb895e64ca0145492` |
| `GDU_V0_BASELINE_ERRATA.md` | `b4d89d12e5882a01bbf476dc8a7f4bc8a1647d92c406989d19c005e65ac70999` |

## 2. 正例验证

- JSON 语法：通过。
- Draft 2020-12 Schema 元规范检查：通过。
- `gdu.example.json` 对 `gdu.schema.json`：通过。
- 引用闭包与跨对象检查：通过。
- 检查规模：2 个 physical nodes、1 个 semantic unit、6 个 assertions、0 个 interpretation groups、3 个 relations、4 个 Evidence 对象。
- 四条 Evidence 摘录的 UTF-8 片段哈希重算：通过。

## 3. 反例验证

以下七种故意制造的错误均被 Schema 拒绝：

1. function assertion 同时指向两个 semantic units；
2. relation 使用不允许的 `derived` 来源；
3. source-attributed relation 错误携带分析基础判断；
4. analytic relation 缺少基础判断引用；
5. `assessment_complete=false` 却填写最终 evidence status；
6. GenerativePlan 直接新增 Evidence 引用字段；
7. parallel interpretation group 设置首选解释。

## 4. Schema 可以机械保证的内容

- 七块齐全且禁止未声明顶层扩展；
- 基本字段类型、必填项、枚举和 ID/哈希格式；
- function assertion 的单一 unit 归属和功能标签；
- 三种 assertion 来源的互斥条件字段；
- 两种 relation 来源的互斥条件字段；
- evidence assessment 的“未检查/已检查”字段组合；
- frozen GDU 的持久 assertions 和 relations 必须完成 assessment；
- 五个 Plan 部分齐全，并且只能使用四类对象引用；
- Evidence 使用一个或多个定位片段，支持跨页对象。

## 5. 仍需专用验证器检查的内容

JSON Schema 本身不能完整保证：

- ID 在不同对象集合间全局唯一；
- 所有引用真实存在并指向正确对象类型；
- physical tree 恰有一个根、没有循环；
- 页码终点不小于起点且不超过 PDF 总页数；
- unit 的主要/次要功能引用确实是指回该 unit 的 function assertions；
- relation 两端属于声明的同一层级且不是自连接；
- `preferred_ref` 确实位于解释组成员中；
- bbox 坐标顺序与片段哈希正确；
- 外部 build log 的 freeze 事件和产物哈希清单存在。

本次使用一次性只读检查完成了上述适用于正例的项目，但尚未建立正式验证器文件。

## 6. 机器也不能代替的语义判断

- assertion 是否真实、原子化并且没有混合认识论来源；
- Evidence 是否语义充分，而不只是引用存在；
- relation 是否确实成立；
- semantic unit 边界是否合理；
- GenerativePlan 的文字是否暗中加入新事实；
- 整体理解是否覆盖文档主旨和关键边界。

这些仍需 Gold、人工抽查和后续对照实验，不能因 Schema 验证通过就宣称 GDU 理解正确。

## 7. 结论

Schema 已忠实覆盖冻结逻辑规格，并通过一个真实正例、跨对象检查和七个反例测试。它现已作为 GDU v0 Schema 基线冻结；下一阶段单独设计最小验证器，不在 Schema 中伪装完成语义判断。
