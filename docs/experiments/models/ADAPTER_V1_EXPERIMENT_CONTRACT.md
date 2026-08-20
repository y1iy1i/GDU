# GDU Understanding Adapter v1 实验契约

日期：2026-08-20

状态：草案，不修改已冻结 Builder v0。

## 1. 它是什么

专业说法：Adapter v1 是“理解模型”与“确定性 Builder”之间的结构化边界。

机制简介：Builder 不直接接纳模型生成的自然语言内容。它只把当前允许读取的原文片段和已公开的工作结果交给 Adapter，Adapter 必须返回可验证的 JSON。

## 2. 请求边界

`adapter-request-v1.schema.json` 规定 Adapter 只能看到：

- 契约版本、propose/revise 模式和当前检查点；
- 锁定的模型/配置身份；
- SourceReader 授权的 SourcePacket；
- Builder 的公开 WorkingGDU 副本；
- 修正时的有界 CorrectionRequest；
- 禁止外部知识，并明示远程调用权限与单次运行次数上限的策略字段。

请求不包含 PDF 文件路径、API Key、Gold 答案或未授权页面。

## 3. 响应边界

`adapter-response-v1.schema.json` 规定 Adapter 只能交回：

- 当前检查点和结果摘要；
- 使用临时 handle 的候选对象；
- CP1 manifest 或 CP5 GenerativePlan；
- 修正阶段的对象操作和 revision 记录；
- CP6 停止门、具体 Gap 和来源范围；
- Adapter 实际观察到的运行身份。

Adapter 不能自行分配规范 ID，不能在 CP6 暗改对象，propose 不能携带 mutation/revision。

## 4. 实验顺序

1. 先用 Transcript Transport 验证 JSON 边界和 Builder 接线；
2. 再用人工错误响应验证拒绝路径；
3. 再接本地生成模型，或经用户明确授权的受限远程 Transport；
4. 真实模型首轮只做小文档/小页包，不直接读 237 页年报；
5. 未通过结构契约前，不评价语义优劣。

## 5. 当前不作出的结论

建立 Adapter 契约不等于已经实验过真实模型，也不等于本地小模型可以产生合格 GDU。

## 6. 远程接线边界

`configs/api/remote-adapter-v1.schema.json` 只兼容 HTTPS 上的 OpenAI-style Chat Completions JSON 接口。真正发出请求前必须同时通过：启用配置、配置哈希、当次显式授权、请求策略、API Key 环境变量和双重调用次数上限。当前只用假响应测试，未发起网络请求。

当前正式远程候选为阿里云百炼 Token Plan 的 `deepseek-v4-flash-0731`，配置见 `configs/api/aliyun-token-plan-deepseek-v4-flash-0731.example.json`。该模型使用原生 JSON Mode，返回内容仍由本地 Schema 严格校验；配置文件本身不会触发请求。此前的 `qwen3.7-plus` 配置和结果仅保留作可复现实验对照。
