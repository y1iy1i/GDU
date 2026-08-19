# GDU Builder v0 最小骨架验证报告

日期：2026-08-19

状态：P0、P1 与对象修正操作验证通过，尚未冻结。

## 1. 验证对象

- `src/gdu/builder_v0/` 下七个最小骨架文件；
- `tests/test_builder_v0.py` 的 18 个 P0、10 个 P1 和 2 个对象操作场景；
- 既有 GDU v0、Build Log v0、Validator v0 与历史 v0.1 回归测试。

## 2. 验证环境

- Python：`/opt/anaconda3/bin/python3`，3.13.9；
- jsonschema：4.25.0；
- 网络：未使用；
- 模型 API：未使用；
- API Key：不需要。

系统 `/usr/bin/python3` 缺少 `jsonschema`，会按 Validator 的既有设计报告依赖缺失工具错误；这不是 Builder 状态机失败。

## 3. 验证结果

执行：

```bash
/opt/anaconda3/bin/python3 -m unittest discover -s tests -v
```

结果：62 个测试全部通过。

| 测试组 | 数量 | 结果 |
|---|---:|---|
| Builder v0 P0 | 18 | 全部通过 |
| Builder v0 P1 | 10 | 全部通过 |
| Builder 对象操作 | 2 | 全部通过 |
| Build Log v0 | 9 | 全部通过 |
| Validator v0 | 15 | 全部通过 |
| 历史 v0.1 回归 | 8 | 全部通过 |
| 合计 | 62 | 全部通过 |

另执行 Python `compileall`，通过。

## 4. 冻结基线完整性

重新校验以下清单，所有文件均为 OK：

- `GDU_V0_DESIGN_BASELINE.sha256`
- `GDU_SCHEMA_V0_BASELINE.sha256`
- `GDU_VALIDATOR_V0_BASELINE.sha256`
- `GDU_BUILD_LOG_V0_BASELINE.sha256`

本轮没有原位修改任何冻结文件。

## 5. P0 覆盖结论

已覆盖：

- 直接冻结、一次修正、两次修正和修正耗尽 provisional；
- 技术重试成功、失败及全局额度；
- 语义失败与技术故障分流；
- 非法输入预检；
- 规范 ID、本地句柄、悬空引用和 CP2 basis 约束；
- CP6 不得暗改前序对象；
- frozen/provisional 日志边界；
- 哈希篡改检测和原子发布失败。

## 6. 不应过度解读的地方

本报告只能说明 Builder 的确定性骨架满足当前 P0 规则，不能推出：

- Builder 已经能够读取真实 PDF；
- 模型能够生成合格 GDU；
- GDU 在效果或成本上优于现有知识存储体系；
- 长文档读取问题已经解决。

P1 与通用修正操作已经通过；本阶段当时尚未包含 SourceReader，后续结果见第 8 节。

## 7. P1 与对象操作结论

新增验证覆盖：

- 多 Gap 回到最早受影响检查点；
- 修正不能修改 Gap 范围外对象；
- Adapter 不能静默改变运行身份；
- revision 必须有触发证据；
- 有根据的替代解释可被保留；
- navigation-only 材料不能提升为 evidence；
- provisional 可诚实保留未完成评估；
- logical_time 在相同时间戳下仍提供严格因果顺序；
- CP6 技术失败时可保存已有完整 provisional 快照；
- freeze 后当前日志不可追加；
- replace、downgrade、retain alternative 与 withdraw 会实际改变工作对象，而不只是写文字日志。

## 8. 后续 SourceReader 接线验证

本报告形成后，最小 SourceReader 及其 Orchestrator 接线继续完成。Builder 测试增至 40 个，全项目增至 84 个唯一测试；真实 Pilot 03 PDF 的临时端到端 frozen 往返通过。详见 `GDU_SOURCE_READER_V0_VALIDATION_REPORT.md` 与 `GDU_SOURCE_WIRING_V0_VALIDATION_REPORT.md`。
