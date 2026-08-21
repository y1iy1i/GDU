# GDU Builder V1 表示层编译器报告

## 1. 实验意义

证据接口解决了“原文在哪里”，表示层编译器开始解决“这段原文提出了什么可检查的命题”。

本层的输出是 Evidence 和来源 Claim 组成的种子图。它不生成 Inference 和 Conflict，也不判断命题最终是否应被接受。

## 2. 理论筛选

本次检索的标准是：某项理论只有能直接变成字段、校验规则或实验指标时才进入 Builder。

### 2.1 采用：PropBank 的谓词—角色骨架

[PropBank](https://propbank.github.io/) 将基本语义命题表示为谓词与参与者角色。GDU 不复制其英语词框库，只采用一个结构约束：

```text
一个 Claim = 一个主谓词 Atom + 一组显式语义角色
```

它直接变成 `atom` 和 `semantic_arguments`。这可以阻止 Builder 用一个不可计算的长摘要代替命题。

### 2.2 采用：MinIE 的语义注释分离

[MinIE](https://aclanthology.org/D17-1278/) 将 polarity、modality、attribution 和 quantity 从抽取句的表面文字中分离成语义注释。GDU 将这一思路转化为：

- `polarity`：肯定或否定；
- `epistemic_status`：确定或可能；
- `normative_force`：无、义务、禁止、许可或建议；
- `attribution`：这个说法由谁提出；
- `quantities`：原文表面值、规范化值和单位。

这一分离对论文中的“可能”和标准中的“应/不应”尤其重要。

### 2.3 采用：Nanopublication 的最小断言与来源分离

[Nanopublication Guidelines](https://nanopub.net/guidelines/working_draft/) 将 assertion、assertion provenance 和 publication information 分开。GDU 不在 V1 强制使用 RDF，但采用它的两个原则：

- Claim 保持尽可能小的可引用断言；
- Claim 内容与“它怎么生成”的来源记录分开。

### 2.4 采用：W3C PROV 的来源关系

[W3C PROV-O](https://www.w3.org/TR/prov-o/) 区分了 `wasQuotedFrom`、`wasGeneratedBy`、`wasDerivedFrom` 等关系。当前 Representation Compiler 只产生来源 Claim：

- `quoted_from` 必须指向已验证 Evidence Block；
- `generated_by` 记录哪个 Builder/模型配置提出了该候选；
- 派生 Claim 将在 Argument Compiler 中通过 Inference 生成，不在本层伪装成原文断言。

### 2.5 未引入的方法

- 完整 RDF/OWL：能提高互操作性，但不直接解决当前的命题抽取错误；
- 完整 AMR：表示力强，但会让中英文、表格和规范文本的转换链更长；
- 通用本体库：三个现有领域没有一套共用本体能同时覆盖，现在强行统一会提前引入映射错误。

这些方法没有被否定，只是当前没有足够的净收益证据。

## 3. 已实现的候选结构

模型或规则提取器只能提交 Representation Candidate，不能直接修改正式图。候选必须包含：

- 一个 Atom 和一组不重复的语义角色；
- 空间、时间、公司口径、文档或场景等 Context；
- 原文引文与 Evidence Block ID；
- 极性、可能性、规范力、来源归属和数值；
- 提出候选的 compiler/model 身份。

Candidate ID 和哈希由本地程序根据全部内容生成，不接受模型自报的 ID。

## 4. 确定性拦截规则

当前程序可确定性拦截：

- 引文不在所指 Evidence Block 中；
- 命题中出现了原文引文没有的数字；
- 命题中的数字没有对应 Quantity 注释；
- 否定、可能性、规范力或来源归属没有原文 cue；
- Context 缺失、时间区间无效或集合为空；
- Atom 非法、语义角色缺失或重复；
- 候选内容被改写后 ID/哈希不一致。

通过后，编译器将候选变成与当前 AIF-like 接口兼容的 Evidence 和 asserted Claim。相同 Evidence Block 被多个 Claim 引用时只写入一次。

## 5. 三领域接口验证

| 领域 | 关键问题 | 当前表示 |
|---|---|---|
| 财务 | 数字、单位、年度和合并口径不能改写 | Quantity + Context + 原文数值对账 |
| 论文方法 | `may` 不能被编译成确定事实 | `epistemic_status=possible` + cue |
| 规范标准 | “不应少于2秒”不是普通否定句 | `polarity=positive` + `normative_force=obligation` + Quantity |

三种情况可由同一候选契约和同一编译函数处理，没有为任一领域写专用图结构。

## 6. 当前结论与边界

已经证明：Representation Candidate 可以被隔离、定位、校验并编译成当前三层＋两模块的表示层输入。

还没有证明：小模型能从长文档中稳定提出高质量候选。确定性规则能检测来源、数字和结构错误，但不能单独证明一句话在语义上真的只包含一个事实。

因此下一个有效实验不是增加更多字段，而是让模型在不读取 Gold 的情况下提交候选，测量：

- 原子 Claim 精确率与召回率；
- 数值、可能性、规范力和 Context 保留率；
- 确定性校验的拦截率和漏检率；
- 人工修正量和模型费用。
