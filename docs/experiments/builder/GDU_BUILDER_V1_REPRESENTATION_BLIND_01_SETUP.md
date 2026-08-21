# Builder V1 表示层盲抽取实验 01

## 1. 实验目的

这是 Representation Compiler 的第一次真实模型抽取实验。它检查 `deepseek-v4-flash-0731` 能否在不读取现有 GDU 和 Gold 的情况下，从三类 Evidence Block 提交合格的原子 Claim 候选。

本轮使用闭合 Atom 词表，主要测试语义抽取和结构保留，不把它解释为开放知识发现能力。

## 2. 冻结输入

| 案例 | 原文位置 | Gold Claim | 主要问题族 |
|---|---|---:|---|
| 财务 | 年报物理第15页 | 4 | 年度列、金额、变动率、变化原因 |
| 论文 | PGKD 物理第3页 | 4 | 否定作用域、早停、模型选择、下一轮数据 |
| 标准 | GB 45438-2025 物理第7页 | 6 | 义务/许可、位置、可辨性、阈值和条件 |

总计 14 个 Gold Claim。

- `input.json` SHA-256：`11866467e620648fdc724ad8c58da3cf753879df5df34d322ee33127fb5edc3e`；
- `gold.json` SHA-256：`6ab5cf35ba4c6d2a881c6530e631bcaa86bd66b4b47a54636baf402fbc70926e`；
- 远程请求 SHA-256：`07da80d5442c4d849aa33c30512d7522f6218628cec264713662138592a88c3c`。

## 3. 盲测边界

运行脚本按以下顺序执行：

```text
读取 input.json
→ 生成经验证 Evidence Block
→ 构建不含 Gold 的远程请求
→ 最多调用1次模型
→ 固定原始响应
→ 此时才读取 gold.json
→ 本地校验和评分
```

请求包含 Evidence Block、版面说明、必须复制的 Context 和允许的 Atom，不包含 Gold 的极性、模态、规范力、数值规范化或比较答案。

## 4. 评分与问题族

评分器记录：

- 提交候选数、通过校验数和 Gold 数；
- 精确匹配的 Claim 数、精确率和召回率；
- 缺失、多余、重复和字段不匹配的 Atom；
- 校验失败所属的问题族。

问题族包括证据定位、数值保真、Context、极性作用域、可能性、规范力、比较方向、来源归属和原子结构。

## 5. 实际运行记录

2026-08-21 首次执行在发送 HTTP 请求前停止：当前任务环境中没有 `DASHSCOPE_API_KEY`。

- 远程调用数：0；
- API 费用：0；
- 原始模型响应：无；
- 模型精确率/召回率：没有产生，不以 0 分代替。

输入、请求、隔离校验器和评分器已完成。密钥进入当前 `gdu` 环境后，重放同一脚本即可生成模型结果，不需要修改实验输入或评分规则。

同日，用户在本地 `gdu` 终端中以隐藏输入方式注入 Key，原冻结请求成功运行：

- 远程调用数：1；
- 提交候选：14；
- 通过校验：8；
- 原始精确匹配：7；
- 原始精确率与召回率：50%。

完整审计见 [结果报告](GDU_BUILDER_V1_REPRESENTATION_BLIND_01_REPORT.md)。首次无 Key 停止记录作为技术边界保留，不与后续成功运行合并或删除。

## 6. 重放入口

```bash
PYTHONPATH=src:. python scripts/run_builder_v1_representation_blind_01.py
```

也可对已固定的原始响应离线重评，不产生新 API 调用：

```bash
PYTHONPATH=src:. python scripts/run_builder_v1_representation_blind_01.py \
  --replay-response /path/to/response.json
```
