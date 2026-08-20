# GDU Understanding Adapter v1 契约验证报告

日期：2026-08-20

状态：请求/响应 Schema、离线 Transcript 和远程接线通过；Qwen 完成接口与机械验证但未通过章节边界任务；DeepSeek V4 Flash 0731 已在同条件下通过 CP1 边界实验。

## 1. 已实现

- `adapter-request-v1.schema.json`：限定检查点、SourcePacket、公开 WorkingGDU、修正请求和费用策略；
- `adapter-response-v1.schema.json`：限定候选对象、mutation、revision 和停止门；
- `src/gdu/adapter_v1/structured_adapter.py`：Builder 数据类与结构化 JSON 之间的转换与验证；
- `TranscriptTransport`：按预登记顺序离线重放响应，不访问网络或模型。
- `OpenAICompatibleRemoteTransport`：默认关闭，只在安全门全部通过时具备发送能力。
- 阿里云百炼正式配置：使用用户指定的北京区 Token Plan 地址和模型 ID `deepseek-v4-flash-0731`，单次运行上限 1 次，采用原生 JSON Mode 加本地校验；Qwen 配置保留作对照。

## 2. 新增测试

20 项 Adapter v1 测试覆盖：

- request 不包含 PDF 路径，且付费远程调用和外部知识均为 false；
- response 阶段必须与 request 一致；
- CP6 不能夹带新候选对象；
- 失败的停止门必须有具体 Gap；
- Transcript 耗尽稳定转为技术失败；
- 六份离线结构化响应能推动冻结 Builder v0 产生 frozen 三文件包。
- 默认关闭、HTTPS 限制、配置哈希、显式授权、Key 缺失时不触网、调用上限和畸形响应拒绝。

## 3. 全项目结果

- Conda `gdu`（Python 3.12.13）：共运行 115 项，111 项通过，4 项因公开仓库不含本地 Pilot 原文而跳过；
- compileall：通过；
- `GDU_BUILDER_V0_BASELINE.sha256`：28 项全部 OK；
- 阿里云 Token Plan API 调用：1 次最小连接测试，成功且未重试；
- Qwen CP1 API 调用：1 次；Adapter response Schema 通过，但 GDU physical_structure 字段 Schema 拒绝，未重试；
- Qwen CP1 第二次运行：1 次请求在 120 秒读取超时，未自动重试；
- Qwen CP1 第三次运行：关闭思考模式后成功，4 个对象通过 Adapter Schema、GDU 字段 Schema 和原文逐字接地检查；
- Qwen CP1 边界运行：输入扩大至物理页 1、8–12，机械检查继续通过，但模型仍只引用第 1、8 页并输出第二节 8–8，未通过边界语义验收；
- DeepSeek CP1 边界运行：同样输入物理页 1、8–12，返回 9 个对象，通过三层机械检查；第二节识别为 8–12，并在第 12 页识别出第三节起点，语义验收通过；
- DeepSeek CP2 运行：初始生成因自行编造对象引用被拒绝，第一次修正因功能断言漏字段被拒绝，第二次修正返回 1 个语义单元、3 条内容断言和 1 条功能断言，通过字段与预登记语义验收；
- DeepSeek CP3 运行：初始生成因在字段内自行分配规范 ID 被拒绝；第一次修正生成 4 条断言和 1 个并行解释组。修正本地验收器对否定句的误判后，同一原始结果离线通过多解释与不确定性验收，无额外 API 调用；
- DeepSeek CP4 运行：初始生成因来源关系条件字段错误被拒绝，第一次修正因候选外层漏 `source_authority` 被拒绝，第二次修正生成 5 条预登记关系并通过字段与语义验收；
- DeepSeek CP5 运行：首次生成产生五段局部计划并通过结构、引用、范围和不确定性检查；本地验收器最初错误要求摘要逐字出现“扣非”，修正为“摘要压缩 + 引用保真”后同一结果离线通过，无额外 API 调用；
- DeepSeek CP6 运行：首次生成即正确返回 coverage、cross_carrier、cross_section 失败与三个具体 Gap，拒绝将第二节局部原型冻结为完整文档 GDU；
- 本地生成模型调用：0。

## 4. 结论边界

可以得出：当前地址、Key、模型 ID 和原生 JSON Mode 已连通；模型未来只要能稳定返回完整契约 JSON，就可以在不修改 Builder v0 的情况下接入。

不能得出：接口连通或机械 Schema 通过，不等于模型已完成指定的文档理解任务。

第一次真实 CP1 进一步证明：原生 JSON Mode 只能保证输出可解析，不能替代 GDU 字段级验证。

第三次 CP1 可以得出：Qwen 3.7 Plus 在明确字段形状、关闭长思考并限制来源页后，能够提交机械合格且逐字接地的 CP1 候选。随后的扩大页包实验表明，它没有据此识别完整章节终点。DeepSeek 在同条件输入下识别出第二节 8–12 和第 12 页的第三节起点，因而成为后续正式实验默认模型。
