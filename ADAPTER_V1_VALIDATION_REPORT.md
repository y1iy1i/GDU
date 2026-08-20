# GDU Understanding Adapter v1 契约验证报告

日期：2026-08-20

状态：请求/响应 Schema、离线 Transcript 和默认关闭的远程接线通过；尚未调用真实生成模型。

## 1. 已实现

- `adapter-request-v1.schema.json`：限定检查点、SourcePacket、公开 WorkingGDU、修正请求和费用策略；
- `adapter-response-v1.schema.json`：限定候选对象、mutation、revision 和停止门；
- `src/gdu/adapter_v1/structured_adapter.py`：Builder 数据类与结构化 JSON 之间的转换与验证；
- `TranscriptTransport`：按预登记顺序离线重放响应，不访问网络或模型。
- `OpenAICompatibleRemoteTransport`：默认关闭，只在安全门全部通过时具备发送能力。

## 2. 新增测试

15 项 Adapter v1 测试覆盖：

- request 不包含 PDF 路径，且付费远程调用和外部知识均为 false；
- response 阶段必须与 request 一致；
- CP6 不能夹带新候选对象；
- 失败的停止门必须有具体 Gap；
- Transcript 耗尽稳定转为技术失败；
- 六份离线结构化响应能推动冻结 Builder v0 产生 frozen 三文件包。
- 默认关闭、HTTPS 限制、配置哈希、显式授权、Key 缺失时不触网、调用上限和畸形响应拒绝。

## 3. 全项目结果

- Conda `gdu`（Python 3.12.13）：共运行 110 项，106 项通过，4 项因公开仓库不含本地 Pilot 原文而跳过；
- compileall：通过；
- `GDU_BUILDER_V0_BASELINE.sha256`：28 项全部 OK；
- 付费 API 调用：0；
- 本地生成模型调用：0。

## 4. 结论边界

可以得出：真实模型未来只要能稳定返回契约 JSON，就可以在不修改 Builder v0 的情况下接入。

不能得出：任何本地或远程模型已经具备这种结构化生成能力。
