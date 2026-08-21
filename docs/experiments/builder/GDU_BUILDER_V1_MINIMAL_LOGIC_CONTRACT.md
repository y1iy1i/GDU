# GDU Builder V1 最小逻辑契约

> 版本：V1.1  
> 日期：2026-08-21  
> 作用：约束 Builder 如何从原文生成可追溯、可冲突、可继续计算的命题

## 1. 核心边界

Builder 不判断命题的客观真伪。它只编译：

1. 原文提出了什么命题；
2. 命题采用肯定形式还是逻辑否定形式；
3. 哪些原文位置支持、反对或限制该命题；
4. 在当前图和当前版本中，论证系统如何计算命题状态。

因此，`polarity` 只表示命题内容是 `P` 还是 `not P`，不是可信度，也不是最终结论。命题的当前状态由两个横向结果共同表达：

| 信息情况 | Belnap 状态 | 论证状态可能值 |
|---|---|---|
| 尚无正反信息 | `NEITHER` | `undecided` |
| 只有支持信息 | `TRUE_ONLY` | `accepted/rejected/undecided` |
| 只有反对信息 | `FALSE_ONLY` | `accepted/rejected/undecided` |
| 正反信息同时存在 | `BOTH` | `accepted/rejected/undecided` |

这里的 `TRUE_ONLY/FALSE_ONLY` 是既有接口名称，只表示收到的信息方向，不表示绝对真理。回答时应使用“当前支持、当前反对、存在冲突、待定”等表述。

## 2. 理论取舍

### 2.1 命题状态

- [Dung 论证框架](https://www.sciencedirect.com/science/article/pii/000437029400041X)用于根据攻击和防御关系计算 `accepted/rejected/undecided`；
- Belnap–Dunn 四值思想用于区分只有正面信息、只有反面信息、双方同时存在和双方都缺失；
- 两者不合并成一个真假分数：前者计算论证可接受性，后者保存原始信息是否冲突或缺失。

### 2.2 来源和位置

- [W3C PROV-O](https://www.w3.org/TR/prov-o/)支持区分引用、生成和派生来源；
- [W3C Web Annotation](https://www.w3.org/TR/annotation-model/)支持同时使用原文引用和位置选择器；
- [W3C Tabular Data Model](https://www.w3.org/TR/tabular-data-model/)支持分别描述表、行、列、单元格和元数据；
- [SEM-TAB-FACTS](https://aclanthology.org/2021.semeval-1.39/)将表格事实判断与证据单元格查找分开，说明表格命题必须保留单元格级证据。

这些理论只转化为当前必要字段，不引入完整 RDF、OWL 或外部本体。

## 3. 表格证据契约

每个表格 Evidence Block 同时保存：

```text
物理位置：physical_page + bbox + source_locator
表格位置：table_id + region_kind + row_range + column_range（行列均从 0 开始）
原文关系：describes / qualifies / defines_unit / refers_to
```

`region_kind` 区分标题、说明、表头、主体、脚注和单位说明。表格与正文之间使用带类型的 Evidence Relation 连接，不把周围正文直接拼进单元格文字。

一个命题可以引用多个证据块。例如“2025 年经营现金流为 100 万元”可以同时引用年份表头、数据单元格、单位说明和解释该表格的正文。

## 4. 数值契约

Quantity 分开保存：

```text
surface              原文数值写法
normalized_value     可计算的规范数值
unit                 规范单位
unit_surface         原文单位写法，可来自另一证据块
normalization_rule   从原文到规范值所用规则
```

校验比较规范数值和单位，不要求数值与单位必须在原文中连续出现；但数值表面、单位表面和转换规则都必须可以追溯。转换规则使用有限白名单，并检查规范数值确实能从原始数值中得到，不能由模型自由描述转换。负数属于 Quantity，不自动改变命题的逻辑否定形式。

## 5. 比较契约

比较关系分成三个问题族：

| 类型 | 结构 | 示例 |
|---|---|---|
| `threshold` | metric + operator + threshold + unit | 时长不少于 2 秒 |
| `relative` | metric + operator + reference_metric | 本期低于上期 |
| `extremum` | metric + min/max + reference_set | 候选模型中验证损失最低 |

只有固定阈值比较必须连接 Quantity。相对比较不能伪造数值阈值，集合最值不能把“其他对象”写进 threshold。

## 6. 当前实现边界

当前代码已经实现：

- 表格区域坐标和表格—正文证据关系；
- 数值与单位分处不同证据块时的规范化校验；
- 阈值、相对和集合最值三类比较；
- 旧版 Representation Candidate 的兼容读取。

命题支持、攻击、限制和最终接受状态仍由既有“三层逻辑主干＋两个横向模块”处理，不在 Representation Compiler 中提前决定。

## 7. 回归结果

- 完整测试：`244 passed, 5 skipped`；
- 使用首轮已保存的模型响应离线重放，没有产生新的模型调用；
- 确定性校验接受数由 `8/14` 提高到 `9/14`；
- 精确结构匹配由 `7/14` 提高到 `8/14`。

这一点只证明已确认的表头/数值误伤得到修复。命题作用域和比较类型能否提高模型的新输出质量，仍需使用未见变体进行第二次盲测。
