# GDU Builder 状态机测试设计 v0（草案）

状态：P0 与 P1 内容已实现并通过，尚未冻结。

依据：

- `GDU_BUILDER_MINIMAL_DESIGN_V0_DRAFT.md`
- `GDU_BUILDER_INTERFACES_V0_DRAFT.md`
- 冻结的 GDU v0、Validator v0 与 Build Log v0 契约

## 1. 这轮测试究竟测什么

大白话：先用“按剧本回答的假模型”测试流水线管理员是否守规矩。

专业表述：通过可编程的 Fixed Adapter 和 Fake SourceReader，对 Builder 编排状态机进行确定性契约测试，隔离模型语义能力、长文档读取质量和外部 API 波动。

这轮测试回答：

- 六个检查点是否按顺序执行；
- 修正和技术重试是否严格受限；
- frozen、provisional、technical_failed 是否不会混淆；
- 日志、规范 ID、引用、哈希和原子发布是否正确；
- 输入隔离和固定配置是否不会被绕过。

这轮测试不回答：

- 模型是否真的理解文章；
- GDU 是否优于 RAG、普通摘要或其他知识库；
- 小模型怎样读取超长文档；
- 最合适的分段、OCR、检索或提示策略是什么。

## 2. 为什么先不用真实模型

真实模型会让两个变量同时变化：模型回答质量和 Builder 流程正确性。一旦测试失败，很难判断是谁的问题。

Fixed Adapter 按预设脚本返回候选、缺口或故障，因此同一测试每次都应得到相同的阶段轨迹和结束状态。先证明“规则机器”可靠，之后接真实模型时，新增的不确定性才主要来自模型和阅读方案。

## 3. 测试夹具

### 3.1 `ValidRunSpecFixture`

一份最小合法运行配置，包含固定来源身份、冻结 Schema 和协议哈希、固定模型标识、固定提示/配置哈希、两次语义修正上限、一次全局技术重试上限，以及隔离的临时输出目录。

模型字段使用明确的测试值，例如 `fixed-adapter-v0` 和 `not_applicable`，不伪装成真实模型。

### 3.2 `FakeSourceReader`

它不实现 OCR、分段或 PDF 理解，只按脚本返回带页码、定位、摘录和哈希的 `SourcePacket`。它记录所有调用，供测试检查 Adapter 是否扩大了来源范围。

来源权威规则仍被模拟：只有 `pdf_fragments` 可以提升为 evidence，`navigation_text` 单独出现时必须被拒绝。

### 3.3 `FixedUnderstandingAdapter`

它按测试剧本依次返回：

- 合法 `CandidateBundle`；
- 含指定语义缺口的合法候选；
- 结构损坏或无法解析的技术故障；
- 修正后的候选；
- 尝试越权的控制命令或越界来源请求。

它必须记录每次调用的阶段、输入范围、配置身份和修正轮次。

### 3.4 `DeterministicClock`

返回预设、严格递增且符合 date-time 格式的时间。Build Log 的因果顺序主要由 `logical_time` 决定，固定时钟使测试可重复。

### 3.5 `ValidCandidateScript`

将一份已通过冻结 Validator 的最小 GDU 对象拆成 CP1–CP5 候选包，并在 CP6 返回全通过结果。第一版可以从 `gdu.example.json` 派生，不要求真实模型重新生成内容。

单元测试验证状态机和契约，不声称示例内容重新获得了 PDF 语义核验。真实 PDF 往返属于后续集成测试。

### 3.6 故障注入器

允许在指定阶段制造一次或连续两次读取中断、Adapter 解析失败、写入失败、验证失败或发布失败。注入点必须明确，避免用随机故障造成不可复现测试。

## 4. 每个测试必须观察什么

测试不能只检查“没有报错”。最少观察以下结果：

```text
outcome
state_trace[]
checkpoint_call_trace[]
adapter_call_trace[]
source_request_trace[]
semantic_corrections_used
technical_retries_used
build_log_events[]
published_artifact_paths[]
validator_result
```

必要时还检查规范 ID 映射、引用闭包、文件字节哈希以及输出目录中是否出现半成品。

## 5. P0：首版必须通过的核心测试

P0 表示没有这些测试，Builder 骨架不能被认为可用。

### BSM-P0-01：主流程一次通过

剧本：CP1–CP5 均 completed，CP6 的三联门和三项强制子检查全部 passed。

预期：

- 阶段严格按 CP1、CP2、CP3、CP4、CP5、CP6 执行；
- 语义修正 0 次，技术重试 0 次；
- 结果为 `frozen_complete`；
- GDU 状态为 frozen；
- 三文件包存在；
- 日志有且只有一个 freeze，且它是最后一条。

### BSM-P0-02：一次定向修正后通过

剧本：第一次 CP6 的 evidence 失败，Gap 指向 CP3 的一个断言；第 1 次修正后 CP6 全通过。

预期：只请求受影响断言和指定来源范围；不从 CP1 重跑全文；使用相同配置；修正计数为 1；最终 frozen。

### BSM-P0-03：两次定向修正后通过

剧本：主构建失败，第 1 次修正仍失败，第 2 次修正后通过。

预期：修正计数正好为 2，不出现第 3 次；最终 frozen。

### BSM-P0-04：两次修正后仍未通过

剧本：三次 CP6 均报告具体 Gap。

预期：

- 结果为 `provisional_complete`；
- GDU 状态为 provisional；
- 仍产生三文件包；
- `ARTIFACTS.sha256` 覆盖 GDU 和日志；
- 日志没有 freeze；
- 未完成缺口可从最终 CP6 checkpoint 和进程结果复核；
- 不发生第 3 次修正。

### BSM-P0-05：一次技术故障后恢复

剧本：某次 Adapter 调用第一次中断，完全相同的调用重试成功。

预期：全局技术重试计数为 1；写入 resolved 或 workaround technical 事件；模型、参数、来源范围和阶段请求完全不变；主流程继续。

### BSM-P0-06：技术重试仍失败

剧本：同一调用连续两次发生技术故障。

预期：结果为 `technical_failed`；写 unresolved technical 事件；不继续后续检查点；没有完整合法快照时不伪造三文件包。

### BSM-P0-07：技术重试是全局额度

剧本：CP2 使用并成功完成唯一技术重试；CP5 后来再次出现技术故障。

预期：CP5 不再获得新的重试，直接 technical_failed。证明“一次”指整次运行，不是每个检查点各一次。

### BSM-P0-08：内容不足不能冒充技术故障

剧本：Adapter 返回结构合法但证据不足的候选。

预期：不消耗技术重试；进入 failed checkpoint、Gap 或语义修正路径。

### BSM-P0-09：损坏的结构化返回属于技术故障

剧本：Adapter 返回无法解析或不符合 CandidateBundle 外壳的内容。

预期：允许使用一次同请求技术重试；不得把损坏内容提升到 WorkingGDU。

### BSM-P0-10：非法输入在运行前拒绝

至少分别测试：PDF 缺失、来源哈希不符、Schema 哈希不符、修正上限被设置为 3、允许外部知识、`single_builder=false`、输出目录与受保护输入重叠。

预期：全部为 `input_rejected`；Adapter 未被调用；不生成正式包。

### BSM-P0-11：规范 ID 由编排器分配

剧本：不同阶段的候选都使用本地句柄，并故意复用相同局部名称。

预期：生成全局唯一规范 ID，所有局部引用被正确改写，结果通过引用闭包检查。

### BSM-P0-12：悬空候选句柄被拒绝

剧本：候选关系或功能断言引用不存在的本地句柄。

预期：该候选不能提升；不会污染 WorkingGDU；按返回外壳是否损坏区分技术故障或 checkpoint 内容失败。

### BSM-P0-13：CP2 功能断言 basis 闭合

剧本一：CP2 同时返回语义单元、功能断言和必要的最小 basis assertion。剧本二：功能断言缺少 basis。

预期：剧本一通过局部引用检查；剧本二不能完成 CP2。CP3 负责补全断言和评估，但不能修补一个被错误宣告完成的 CP2。

### BSM-P0-14：CP6 不能暗改前面对象

剧本：CP6 发现一个新事实并试图直接替换 CP3 断言。

预期：直接修改被拒绝；系统生成 Gap，回到定向修正；有新证据触发正式变更时写 revision。

### BSM-P0-15：frozen 日志边界

预期同时满足：事件逐行通过 Build Log Schema；事件 ID 唯一；logical_time 严格递增；freeze 唯一且最后；freeze 三联门全 passed；freeze 只引用外部清单路径。

### BSM-P0-16：provisional 日志边界

预期：所有事件合法且有失败 CP6 记录；不存在 freeze；仍能与 GDU 一起被哈希并通过 provisional 包验证。

### BSM-P0-17：哈希能发现事后修改

剧本：发布前验证通过；随后分别修改 GDU 或日志一个字节。

预期：重新验证时报告 artifact hash mismatch。

### BSM-P0-18：原子发布不泄漏半成品

剧本：分别在写 GDU、写日志、生成哈希和最终验证阶段注入失败。

预期：正式输出目录中不会出现看似完成的部分包；暂存内容不被当作正式产物返回。

## 6. P1：骨架稳定后补充的边界测试

### BSM-P1-01：多个 Gap 回到最早受影响点

CP6 同时发现 CP2 和 CP4 缺口。预期先回到 CP2，只重做受依赖影响的后续检查，不机械重跑无关 CP1。

### BSM-P1-02：修正不得扩大范围

Adapter 请求 Gap 以外的页面或对象。预期越界请求被拒绝或裁剪并留下公开结果；不能借修正重新阅读全文。

### BSM-P1-03：技术重试不得静默换配置

第二次调用改变模型 ID、推理等级、提示哈希或来源范围。预期立即拒绝，不能记为成功重试。

### BSM-P1-04：revision 必须由证据触发

没有非空 trigger evidence 的 revision 应被日志 Schema 拒绝；只有发现缺口时写 failed checkpoint，不伪造 revision。

### BSM-P1-05：有根据的替代解释被保留

修正把一个解释提升为 preferred，但另一个仍有证据。预期使用 retain_alternative 或适当 interpretation group 表达，不删除仍成立的可能性。

### BSM-P1-06：纯导航文本不能成为 evidence

候选只引用 extracted text 内容而无法回到 PDF fragment。预期不得提升为正式 evidence。

### BSM-P1-07：provisional 可包含未完成评估

合法 provisional 允许部分 assertion 或 relation 的 `assessment_complete=false`，且不得带 `evidence_status`；同一对象若标 frozen 必须被 Schema 拒绝。

### BSM-P1-08：时间戳与逻辑时间分工

即使测试时钟返回相同或非严格递增的现实时间，logical_time 仍必须严格递增；但 timestamp 自身必须是合法 date-time。

### BSM-P1-09：技术失败后的合法快照

若 CP1–CP5 已形成完整 Schema 合法工作状态而 CP6 因技术故障终止，可以按明确策略保留 provisional 包；若尚未完整则不生成虚假 GDU。两种分支都必须返回最后成功检查点。

### BSM-P1-10：发布后不可追加 frozen 日志

冻结包发布后再试图追加事件。预期当前版本拒绝写入；后续变化必须创建新 artifact version 和新日志。

## 7. 测试层次

### 7.1 单元测试

分别验证 ID 分配、引用改写、Gap 校验、停止门不变量、次数计数、事件构造、哈希格式和状态转移。

### 7.2 组件契约测试

用 FakeSourceReader 与 Fixed Adapter 组合，验证四个接口传递的数据只包含允许字段，错误分类稳定，配置身份不变。

### 7.3 包集成测试

在临时目录完成三文件暂存、现有 Validator v0 检查、Build Log Schema 逐行检查、顺序检查、哈希检查和原子发布。

### 7.4 真实模型测试

不属于本轮。只有固定 Adapter 骨架通过后才进入，而且必须作为新的实验层单独报告，不能替代状态机测试。

## 8. 第一版 Builder 骨架的验收门槛

建议采用以下共同门槛：

1. 18 个 P0 场景全部通过；
2. 现有 32 个冻结与历史回归测试继续全部通过；
3. 测试不访问网络，不需要 API Key；
4. 同一输入重复运行时，除显式时间字段外，状态轨迹、ID、事件逻辑顺序和结束状态一致；
5. 所有文件写入临时目录，测试结束不污染正式 Pilot 或冻结基线；
6. 不通过任何测试就不得接入真实模型来掩盖流程问题。

P1 的 10 个边界测试已经补齐并通过；实现还额外增加了 replace 与 withdraw 两个通用对象操作测试。

## 9. 对研究的意义

这套测试不会证明 GDU 有效，但能先排除一种常见混淆：实验结果差，到底是 GDU 思路不行，还是 Builder 偷换模型、无限返工、日志错乱或文件损坏。

只有规则机器稳定后，后续比较 GDU 与现有知识存储体系，才更接近比较“表示方式和生成过程”，而不是比较谁的工程事故更少。

## 10. 当前边界

- 本设计已落实为 `tests/test_builder_v0.py`；
- 已创建 `src/gdu/builder_v0/` 最小骨架；
- 未接入真实 PDF Reader 或模型；
- 未修改冻结 Schema、Validator、Build Log 或历史 v0.1 代码；
- 下一步应设计最小 SourceReader 契约测试；在此之前不实现长文档分段或接入模型 API。
