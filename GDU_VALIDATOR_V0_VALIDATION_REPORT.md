# GDU v0 最小验证器验证报告

> 日期：2026-08-19  
> 实现：`src/gdu/validator_v0.py`  
> 状态：验证通过，作为 GDU v0 Validator 基线冻结。

## 1. 实现结果

- 新 v0 验证器与旧 `src/gdu/validators.py` 分离，避免把旧 claims/views 结构与新七块结构混用。
- 命令行不调用模型、网络或 API。
- Schema 依赖缺失时明确失败，不静默跳过结构检查。
- 退出码固定为：`0` 有效、`1` 输入无效、`2` 工具/文件/依赖错误。

候选快照哈希：

| 文件 | SHA-256 |
|---|---|
| `src/gdu/validator_v0.py` | `eea266731b385239cda1ff507e6c01847e66880908d50eae851da166c9a5f0aa` |
| `tests/test_validator_v0.py` | `d716c8b6f3f4e6045d10c9f9f2b726253e89614f724871b2d9c814a6e2d3d44c` |
| `requirements-validator.txt` | `4046ca1e3a64f4ea791fb4fb3d8566242086ff1c8e2431e2c349e1052ffc6ba0` |
| `GDU_VALIDATOR_V0.md` | `7c4ac41bda6122e0ecdab4cd94f77d2de746c757e278b7554142489d5257694a` |

## 2. 自动测试结果

- 总计：23 个测试全部通过。
- 新 v0 验证器：15 个。
- 旧 v0.1 历史回归：8 个，全部继续通过。
- Python 编译检查：通过。
- 冻结的 `gdu.example.json`：命令行输出 `VALID`。

新测试覆盖：

- 正例 Schema 与跨对象完整性；
- function 多目标的 Schema 拒绝；
- 跨类型重复 ID；
- physical parent 循环与越界页码；
- function 回指不一致；
- relation 端点层级错误；
- interpretation preferred 不属于成员；
- Evidence 摘录哈希不匹配；
- frozen GDU 缺少外部文件；
- 合法冻结包；
- 冻结后日志被修改导致哈希失败；
- 命令行退出码 `0/1/2`。

## 3. 冻结包检查边界

对 frozen GDU，工具要求同时提供 `build_log.jsonl` 和 `ARTIFACTS.sha256`，并检查：

- 日志为逐行 JSON 对象；
- 至少一个 `event_type=freeze`；
- 哈希清单格式、文件存在和 SHA-256；
- GDU 与 build log 都被清单覆盖；
- 禁止绝对路径、`..` 路径穿越、清单自引用和重复条目。

由于 build log 独立 Schema 尚未建立，当前不检查四类事件各自的完整条件字段。这一限制会明确保留到后续阶段。

## 4. 语义边界

验证器不会判断事实真值、Evidence 充分性、关系正确性、最佳语义单元、Plan 是否在语言层面偷加事实，或 GDU 是否优于其他知识体系。输出 `VALID` 只表示未发现已定义的机械错误。

## 5. 结论

最小验证器已完成冻结 Schema 之外的关键机械检查，并通过自动测试和旧代码回归，现已冻结为 v0 Validator 基线。下一步可补 build log Schema，再进入 Builder 最小实现设计。
