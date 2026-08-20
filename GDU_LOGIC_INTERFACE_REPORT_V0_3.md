# GDU 候选逻辑接口调试报告 v0.3

> 日期：2026-08-20  
> 本轮问题：Context不同的两个Claim是否能够构成rebut  
> 结论：Context关系已显式化；只有命题相反且Context完全对齐时才能直接rebut。

## 1. 为什么不能只比较标签

下面三组陈述都可能看起来方向相反，但逻辑性质不同：

```text
2025全年盈利 vs 2025第四季度亏损
合并报表亏损 vs 母公司盈利
同一口径同一期间盈利 vs 亏损
```

只有第三组可以直接作为相反命题处理。前两组可以同时成立。

## 2. Context关系

v0.3为多维Context计算六种关系：

- `equal`：所有维度相同；
- `contains`：左侧范围包含右侧；
- `contained_by`：左侧被右侧包含；
- `overlaps`：有交集但互不包含；
- `disjoint`：至少一个维度互斥；
- `incomparable`：缺少可证明的比较规则。

当前支持：

- 时间区间；
- 显式集合范围；
- 普通类别维度。

对于普通类别，值不同不会被擅自解释成包含或互斥。例如`consolidated`和`parent_company`被视为不可比较，而不是假设合并报表结论可以投影到母公司。

## 3. rebut进入条件

一次直接rebut现在必须同时满足：

1. 两个Claim具有同一规范化atom和相反polarity，或引用一条显式contrary规则；
2. 两个Claim的Context关系为`equal`。

否则分别报告：

| 情况 | 问题代码 |
|---|---|
| 时间包含或部分重叠 | `rebut_context_projection_required` |
| Context互斥 | `rebut_context_disjoint` |
| 口径不可比较 | `rebut_context_incomparable` |
| 命题本身并不相反 | `rebut_not_contrary` |
| 时间区间等Context格式错误 | `invalid_context` |

## 4. 范围对齐方式

范围不同不能靠在Conflict上添加一个布尔值后强行对齐。正确过程是：

```text
范围特定的原文证据
→ 有规则ID的Inference
→ 生成目标范围的新Claim
→ 新Claim与另一Claim Context相同
→ 才允许rebut
```

例如，年度盈利不能直接反驳第四季度亏损。只有取得第四季度的独立数据并形成“第四季度盈利”Claim后，才能与“第四季度亏损”构成rebut。

## 5. 测试结果

通过的新增案例包括：

- 全年区间`contains`第四季度；
- 第四季度`contained_by`全年；
- 第一季度与第四季度`disjoint`；
- 年度Claim直接反驳季度Claim被拒绝；
- 合并口径与母公司口径直接反驳被拒绝；
- 从同季度证据生成对齐Claim后允许rebut；
- 不相关atom即使Context相同也不能rebut；
- 起止日期颠倒被报告为Context错误而不是使验证器崩溃。

## 6. 当前边界

Context比较目前仍是最小代数，不包含：

- 会计口径之间的正式转换规则；
- 模糊时间表达；
- 地理范围本体；
- 同一指标不同单位的换算；
- 聚合值向子范围的统计推断。

这些内容以后只能以显式Inference规则加入，不能隐藏在Context比较器中。这样可以避免系统因为“范围看起来相关”就制造不存在的逻辑蕴含。

## 7. 当前判断

第二项接口问题已在最小案例上解决。Context现在不仅是元数据，也实际约束攻击图的生成。

下一项是验证TMS局部重算与完整重算是否等价。只有结果等价，GDU在节点增长或修订时才可以安全地只更新受影响子图。

