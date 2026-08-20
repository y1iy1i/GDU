# Qwen 3.7 Plus 远程 CP1 实验报告

日期：2026-08-20

状态：第一次真实 CP1 候选被本地字段 Schema 拒绝；未进入 Builder。

## 大白话

模型已经能读到两个授权页面并交回合法 JSON，但其中一个结构字段写错了形状。它把页码范围写成 `[1, 237]`，GDU 规范要求 `{"start": 1, "end": 237}`。因此结果没有混入现有 GDU，也没有自动重试。

## 实验设置

- 服务：阿里云百炼 Token Plan；
- 模型：`qwen3.7-plus`；
- 输入：Pilot 03 年报物理页 1 和 8；
- 阶段：CP1，仅允许 evidence 与 physical_structure 候选；
- 外部知识：禁止；
- 最大调用次数：1；
- 实际调用次数：1；
- 自动重试：0。

## 分层结果

1. 地址、鉴权与模型路由：通过；
2. 原生 JSON Mode：通过；
3. Adapter response v1 Schema：通过；
4. GDU `physical_structure` 字段 Schema：失败；
5. 原文片段逐字接地检查：因上一步失败而未完成；
6. Builder 接纳与发布：未执行。

首个确定错误：

```text
invalid physical_structure at page_range:
[1, 237] is not of type 'object'
```

## 研究意义

这次失败不是“接口没接上”，而是第一次观察到真实模型在 Adapter 粗粒度 JSON 合法之后、GDU 细粒度字段契约之前的偏差。它支持保留双层验证：仅依赖 JSON Mode 不足以保证候选能进入 Builder。

## 离线修正

- 在 CP1 指令中加入 evidence 与 physical_structure 的准确字段形状示例；
- 明确 `page_range` 必须是带 `start/end` 的对象，禁止数组；
- 后续运行先把候选和失败原因保存到 Git 忽略的 `tmp/`，再抛出技术失败；
- 本次不重试。下一次真实调用必须重新获得用户授权。
