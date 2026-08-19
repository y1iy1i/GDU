# GDU SourceReader-Orchestrator 接线 v0

状态：实现候选，尚未冻结；使用 Fixed Adapter，不包含模型 API。

## 1. 大白话说明

之前 Builder 和 SourceReader 分别能工作，但还没有连起来。现在每个检查点必须先按预登记计划申请物理页，SourceReader 返回受控 `SourcePacket`，Fixed Adapter 只能通过这个包查看来源。

修正轮次不使用普通检查点计划，而是直接使用 Gap 批准的页范围。因此“再读一下”不能悄悄扩大成重读全文。

## 2. 接线规则

- BuilderRunSpec 必须恰好定义 CP1 至 CP6 六个 SourceRequest；
- SourceReader 的 PDF 路径和身份必须与 Builder 输入一致；
- SourceReader 读取失败与 Adapter 调用失败共享整次运行唯一一次技术重试；
- Adapter 收到 SourcePacket 和 WorkingGDU 的隔离副本，不获得 PDF 路径，也不能直接修改 Builder 内部状态；
- Candidate evidence 必须位于本次 SourcePacket 的权威 PDF 文本中；
- evidence 的 fragment SHA-256 在提升前复算；
- navigation_text 即使被传入，也不能满足 evidence 权威检查；
- 修正 SourcePacket 只包含 Gap 的 source_scope；
- 未授权证据在提升和 ID 分配之前被拒绝，因此不会污染工作状态。

## 3. 真实 Pilot 接线验证

Pilot 03 的真实 237 页 PDF 已完成端到端临时烟雾运行：

```text
真实 PDF -> PypdfBackend -> SourcePacket
         -> Fixed Adapter -> 六检查点 Builder
         -> gdu.json + build_log.jsonl + ARTIFACTS.sha256
```

结果为 `frozen_complete`，语义修正 0 次，技术重试 0 次，三文件包通过完整 Validator。输出位于临时目录并已自动清理，没有改写 Pilot。

## 4. 教学示例兼容性边界

严格接线首次运行时正确发现：冻结的 `gdu.example.json` 是 Schema 教学实例，其中部分表格 excerpt 是人工合并的摘要，而不是 PDF 文本层中的连续原句。

处理原则：

- 不修改冻结示例；
- 不放宽 SourceReader 的连续文本证据规则；
- 真实接线测试只在内存中用同页真实文本层片段替换教学摘录并重算哈希；
- 未来真实 Builder 必须生成可由 SourceReader 逐页核验的 excerpt。

这不表示教学示例 Schema 无效；它表示“Schema 合法示例”和“严格 Reader 往返夹具”承担不同职责。

## 5. 仍未解决

- 六检查点 SourceRequest 目前由人预登记，不会自动选页；
- 没有目录索引、chunk、PageIndex、MinerU 或向量检索；
- 没有视觉表格、图片、公式或 OCR；
- Fixed Adapter 不理解新文章；
- 没有真实模型 API 或 API Key 需求。

## 6. 下一步建议

在引入长文档自动选页前，先为 BuilderRunSpec 建立可保存、可校验的运行配置文件和命令行入口，使固定 Adapter 的一次运行可以脱离测试代码复现。完成后再冻结“确定性 Builder 基础设施候选”。
