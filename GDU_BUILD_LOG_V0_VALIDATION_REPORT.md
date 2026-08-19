# GDU v0 build log Schema 验证报告

> 日期：2026-08-19  
> 状态：验证通过，作为 GDU v0 Build Log 基线冻结。

## 1. 产物

- `build_log.schema.json`：针对 JSONL 中单条事件的 Draft 2020-12 Schema。
- `build_log.example.jsonl`：覆盖 checkpoint、technical、revision 和 freeze 的五行正例。
- `tests/test_build_log_schema.py`：单条事件反例与跨行顺序测试。
- `GDU_BUILD_LOG_V0.md`：字段语义、顺序和禁止内容说明。

## 2. 正例结果

- Schema 元规范：通过。
- 五条 JSONL 事件逐行验证：通过。
- 四种事件类型覆盖：通过。
- 事件 ID 唯一、逻辑时间严格递增、单一 freeze 且位于末行：通过。

## 3. 反例结果

以下错误均被拒绝或被顺序检查发现：

- revision 缺少触发 Evidence；
- technical 混入 revision 专用字段；
- freeze 的稳定度停止门失败；
- freeze 使用 `../` 或反斜杠路径指向哈希清单；
- 逻辑时间没有严格递增；
- 事件 ID 重复；
- freeze 不是最后一条事件。

## 4. 三轮 Pilot 映射

- Pilot 01：技术恢复映射 technical；主干降格和竞争解释映射 revision；六个检查点映射 checkpoint；最终停止门映射 freeze。
- Pilot 02：PDF 工具回退映射 technical；REV-001—004 映射 revision；阶段与停止门映射 checkpoint/freeze。
- Pilot 03：解析依赖回退映射 technical；REV-001—006 映射 revision；六个检查点与最终停止门映射 checkpoint/freeze。

未发现必须新增第五种事件类型的实证需求。

## 5. 最小性决定

- checkpoint 只增加检查名称、结果和摘要；
- technical 只增加组件、问题、影响、处置和结果；
- freeze 只增加最终版本、三项停止门和外部哈希清单引用；
- 不加入成本账本、完整运行命令、概率、内部思维或任意扩展字段。

## 6. 尚未自动化的部分

单条事件 Schema 无法检查整个 JSONL 的追加性、跨行唯一性、逻辑时间顺序和 freeze 位置。本次用测试辅助函数验证；正式能力需要创建 Validator 的新候选版本，不能修改已冻结的 Validator v0。

## 7. 结论

四类事件足以承接三轮 Pilot 的关键过程信息，正例和反例测试通过，没有出现新增事件类型或复杂治理字段的需要。当前已冻结为 Builder 输出日志与下一版 Validator 的共同契约。
