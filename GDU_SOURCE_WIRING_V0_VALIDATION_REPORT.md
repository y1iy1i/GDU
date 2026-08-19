# GDU SourceReader-Orchestrator 接线验证报告

日期：2026-08-19

状态：接线与真实 Pilot 烟雾测试通过，尚未冻结。

## 1. 新增验证

Builder 接线测试覆盖：

- 六检查点均收到预登记 SourcePacket；
- Adapter 看不到 PDF 路径；
- WorkingGDU 以隔离副本交付；
- 修正包只含 Gap 页；
- 未授权证据不能提升且不消耗 ID；
- navigation_text 不能授权 evidence；
- SourceReader 失败使用全局技术重试；
- 第二次 Reader 失败在 Adapter 调用前结束；
- SourceReader 必须指向 Builder 的同一 PDF；
- 来源计划必须恰好包含 CP1 至 CP6；
- Pilot 03 真实 PDF 完成 frozen 三文件端到端往返。

## 2. 测试结果

当前共有 84 个唯一测试：

| 测试组 | 数量 |
|---|---:|
| Builder（含 P0、P1、修正和来源接线） | 40 |
| SourceReader | 12 |
| Build Log v0 | 9 |
| Validator v0 | 15 |
| 历史 v0.1 回归 | 8 |
| 合计 | 84 |

Anaconda 全套执行结果：82 通过，2 个需要 pypdf/reportlab 的真实 PDF 测试按设计跳过。

随后在具备 PDF 依赖的环境分别补跑：

- 两页临时 PDF 的 SourceReader 往返：通过；
- Pilot 03 的 SourceReader-Builder 端到端往返：通过。

因此 84 个唯一测试均已在具备各自依赖的环境中通过。

## 3. 其他检查

- Python compileall：通过；
- 四组冻结基线 SHA-256：全部通过；
- 网络、模型 API、付费服务：未使用；
- Pilot 正式文件：未修改。

## 4. 结论边界

可以得出：Builder 已经机械地限制 Adapter 只能消费预授权 PDF 文本包，来源读取故障、修正范围和 evidence 提升均受确定性规则控制。

不能得出：系统已经解决自动选页、长文档理解、视觉证据或真实模型生成质量。
