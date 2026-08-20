# GDU 候选逻辑架构 v0.1

> 冻结日期：2026-08-20  
> 状态：接口实验候选，不替代既有冻结基线，不代表组合理论已经验证成功  
> 后续默认：所有新逻辑实验均以本文件为候选起点；修改必须创建新版本或勘误，不原位改写实验历史

## 1. 当前唯一目标

建立一套能够表达联合前提、严格与可废止推理、范围差异、反驳、推理攻击、缺失、矛盾和版本更新的统一逻辑结构，并验证各理论接口是否兼容。

本阶段不实现新 Builder，不扩展领域 Profile，不讨论生产数据库选型。

## 2. 总体结构

候选架构采用“三层逻辑主干＋两个横向模块”：

```text
                    TMS / PROV
             依赖、来源、版本、失效传播
                         │
                         ▼
AIF式表示 → ASPIC+式论证构造 → Dung式接受计算
    │
    └──────── Belnap四值信息状态
```

这不是五套理论的简单叠加。每个模块只承担一种职责，并通过显式接口交换结果。

## 3. 三层逻辑主干

### 3.1 表示层：AIF式信息节点与规则应用节点

信息节点保存：

- `Evidence`：原文证据；
- `Claim`：带对象、时间、口径和极性的命题。

规则应用节点保存：

- `Inference`：一次具体推理；
- `Conflict`：一次具体攻击；
- `Preference`：有明确依据时的优先比较，首轮接口实验暂不启用。

Claim 不使用无解释的直接逻辑边。多个前提通过一个 Inference 节点共同指向一个结论：

```text
Claim A ─premise_of─┐
                    ├→ Inference I ─concludes→ Claim C
Claim B ─premise_of─┘
```

理论依据：AIF区分信息节点与scheme application节点；Bex等人已研究AIF到ASPIC+的逻辑映射。

- https://www.arg-tech.org/wp-content/uploads/2011/09/aif-spec.pdf
- https://doi.org/10.1093/logcom/exs033

### 3.2 论证构造层：ASPIC+式结构化论证

Inference 必须声明：

- `strict`：前提保证结论，例如确定性计算、定义和明确表格规则；
- `defeasible`：前提只形成可被推翻的推定，例如经营解释、原因归纳和风险判断。

Conflict 必须声明攻击位置：

- `rebut`：攻击结论；
- `undermine`：攻击普通前提；
- `undercut`：攻击可废止推理的适用性。

原来的 `supports` 和 `composes` 统一改写为“前提—推理—结论”；原来的 `limits` 拆为范围约束或 `undercut`；原来的 `conflicts` 拆为三类攻击。

理论依据：https://doi.org/10.1080/19462166.2013.869766

### 3.3 接受计算层：Dung式论证语义

表示层和论证层只说明“有哪些论证以及怎样互相攻击”，接受计算层决定哪些论证当前可用于回答。

首轮采用保守、唯一的 grounded semantics，输出：

- `accepted`；
- `rejected`；
- `undecided`。

探索多个竞争解释时可以研究其他语义，但不进入v0.1默认接口。

理论依据：https://doi.org/10.1016/0004-3702(94)00041-X

## 4. 两个横向模块

### 4.1 Belnap四值信息状态

四值状态描述一个命题当前收到的正反信息，不等同于论证接受状态：

- `NEITHER`：没有正面或反面信息；
- `TRUE_ONLY`：只有正面信息；
- `FALSE_ONLY`：只有反面信息；
- `BOTH`：正反信息同时存在。

一个Claim可以处于`BOTH`信息环境，而具体支持它的论证仍由Dung语义分别得到accepted/rejected/undecided。两套状态是否都必要是接口实验问题，不预先假定答案。

四值逻辑与论证结合已有研究先例，但不等于与本实例化自动兼容：

- https://doi.org/10.1527/tjsai.19.83
- https://doi.org/10.3233/WEB-160331

### 4.2 TMS依赖维护与PROV来源追溯

TMS记录：

- 一个结论依赖哪些前提与推理；
- 前提失效后哪些推理和下游结论需要重算；
- 多条替代推理是否仍能维持同一结论。

PROV记录：

- `quoted_from`；
- `derived_from`；
- `revision_of`；
- `invalidated_by`；
- 生成或验证节点的活动与主体。

TMS/PROV只说明来源、依赖和变化，不决定论证是否可接受。

- https://doi.org/10.1016/0004-3702(79)90008-0
- https://www.w3.org/TR/prov-o/

## 5. 模块接口

### I1｜AIF → ASPIC+

输入：类型正确的信息节点和规则应用节点。  
输出：具有前提、子论证、顶层规则和结论的结构化论证。  
必须保持：多前提联合性、严格/可废止类型、攻击位置和Context。

### I2｜ASPIC+ → Dung

输入：结构化论证及rebut/undermine/undercut。  
输出：抽象论证与attack边，然后计算grounded标签。  
不得把“存在来源”直接当作“论证被接受”。

### I3｜Belnap ↔ Claim/Argument

输入：同一规范化命题的正面和反面信息。  
输出：四值信息状态。  
约束：不得用四值状态替代论证接受状态，也不得由`BOTH`推出无关结论。

### I4｜TMS/PROV → 重算

输入：新证据、失效节点或修订事件。  
输出：受影响的Inference、Claim和Argument集合。  
然后只对受影响论证子图重新计算；局部结果是否与全图重算一致必须实验验证。

## 6. v0.1结构不变量

1. 每个Inference至少一个前提，且只有一个结论；
2. 每个Inference声明`strict|defeasible`和规则ID；
3. 每个Conflict声明`rebut|undermine|undercut`及准确目标类型；
4. 不同Context的Claim默认不构成rebut，除非存在显式范围对齐；
5. 来源Claim必须能追溯到Evidence；派生Claim必须能追溯到Inference；
6. 验证不得原位修改输入图，只产生报告或新版本；
7. 信息状态与论证接受状态分别存储；
8. 前提失效不得删除历史节点，只在新快照中重算有效性；
9. 正式回答只能使用accepted且来源完整的推理路径；
10. `NEITHER`、`BOTH`和`undecided`不得被静默转换成确定结论。

## 7. 当前接口通过条件

首轮只测试六个最小案例：

1. 两个前提通过一个严格规则推出一个结论；
2. 正反命题同时存在时得到`BOTH`，且不会任意推出第三个命题；
3. 两个互相rebut的论证在grounded语义下保持undecided；
4. 一个有效undercut能够使目标可废止论证被拒绝；
5. 不同公司口径的命题不会被自动判为rebut；
6. 一个前提失效后，TMS定位下游推理；存在替代推理时结论继续有效，否则失效。

任一案例不能被无歧义表达或计算，即记录为接口缺陷，不通过增加自由文本绕过。

