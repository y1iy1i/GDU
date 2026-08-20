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

## 第二次运行

- 用户随后授予持续调用许可，不再要求逐次确认费用；
- 使用已补充字段形状的提示重新请求 1 次；
- 连接建立后在 120 秒读取超时，没有收到可验证响应；
- Transport 未自动重试，无法确认服务端是否已计入该请求的 Credits；
- 后续离线把 Qwen 思考模式设为 `disabled`，减少结构化小任务的延迟与消耗。

## 第三次运行

- 配置：原生 JSON Mode、`thinking_mode=disabled`、单次调用上限 1；
- 结果：成功，返回 4 个规范化对象；
- 对象：2 个 physical_structure、2 个 evidence；
- 三层验证：Adapter response Schema、GDU 字段 Schema、授权 PDF 片段逐字接地全部通过；
- 本地结果：`tmp/remote_cp1_qwen37/retry_02.json`（Git 忽略）；
- 结果 SHA-256：`23096e2585b7e9bd052a877fbce4a83c93e0473d4a661cb9e81ee860a308d72d`。

### 内容审查

- 文档节点正确识别为“江苏利通电子股份有限公司2025年年度报告”，范围 1–237；
- 第二节标题正确识别为“公司简介和主要财务指标”；
- 两份 evidence 均完整复制物理页 1、8 的授权片段与哈希；
- 第二节范围被写为 8–8。这与当前只提供第 8 页一致，但不能代表完整章节终点；冻结参考范围为 8–12。

结论：第三次 CP1 已达到机械接纳标准，但只是局部页包结果。下一次应扩展观察至 8–12 页，专门验证章节边界。
