# GDU Builder v0 最小骨架说明

状态：Builder v0 确定性基础设施已冻结；不包含真实模型 Adapter 或长文档自动选页。

## 1. 大白话说明

目前已经写出的不是“会自己读年报的完整 GDU Builder”，而是 Builder 的规则机器。

它现在能够用固定测试 Adapter 模拟文章理解过程，并严格执行：输入检查、六个检查点、最多两次内容修正、整次运行最多一次技术重试、日志记录、冻结判断、文件哈希和三文件发布。

因此我们已经验证“流水线管理员会不会守规矩”，还没有验证“真实模型能不能把大文档读懂”。

## 2. 实现文件

| 文件 | 作用 |
|---|---|
| `src/gdu/builder_v0/types.py` | 运行配置、Gap、停止门、候选包、修正请求和运行结果 |
| `src/gdu/builder_v0/id_allocator.py` | 确定性规范 ID 分配及本地句柄引用改写 |
| `src/gdu/builder_v0/log_writer.py` | revision/checkpoint/technical/freeze 四类事件构造 |
| `src/gdu/builder_v0/artifact_writer.py` | 暂存、Schema 验证、哈希和原子发布 |
| `src/gdu/builder_v0/orchestrator.py` | 六检查点状态机、次数控制、停止门与结束状态 |
| `src/gdu/builder_v0/testing.py` | Fixed Adapter 和确定性时钟 |
| `src/gdu/builder_v0/source_reader.py` | PDF 身份、物理页和权威文本片段读取 |
| `src/gdu/builder_v0/config.py` | 运行配置、安全路径和文件哈希验证 |
| `src/gdu/builder_v0/fixture_adapter.py` | 已验证 GDU 夹具的六检查点重放 |
| `src/gdu/builder_v0/cli.py` | 可脱离测试调用的命令行入口 |
| `tests/test_builder_v0.py` | P0、P1、对象操作、来源接线与异常页范围测试 |
| `tests/test_builder_config_cli_v0.py` | 配置、Fixed Adapter、CLI 与字节级复现测试 |

## 3. 已实现能力

- 预检冻结 Schema、Build Log Schema 和 Protocol 的 SHA-256；
- 拒绝缺失输入、放宽修正上限、允许外部知识、多 Builder 和危险输出位置；
- 严格按 CP1–CP6 推进；
- Adapter 只提交候选对象，规范 ID 由 Builder 分配；
- 无效候选不能消耗 ID 或污染已提升工作状态；
- replace、downgrade、retain alternative 和 withdraw 能以事务方式改变工作状态；
- 修正对象和新增证据页必须处在 Gap 允许范围内；
- Adapter 不能在运行或技术重试中静默更换模型、推理等级或配置哈希；
- 仅有导航文本的材料不能提升为 PDF evidence；
- SourceReader 已接入状态机；Adapter 只能接收预授权 SourcePacket 和 WorkingGDU 隔离副本；
- 语义修正最多两次，并从 Gap 指向的最早检查点开始；
- 技术重试是整次运行共享的一次额度；
- frozen 只有在停止门全通过时产生；
- provisional 也产生 GDU、日志和哈希，但没有 freeze；
- freeze 唯一且为最后事件；
- 所有产物先在隔离暂存目录完成，通过验证后再原子发布；
- 发布后的 GDU 或日志被修改时，Validator 能发现哈希不一致。

## 4. 当前没有实现的能力

- 没有模型 API，不需要 API Key；
- 有最小 PDF 文本层 SourceReader，但没有 OCR、视觉表格、自动分段、PageIndex 或 MinerU；
- Fixed Adapter 的内容来自已验证示例，不会重新理解文章；
- CP1–CP5 的完整语义质量仍由固定剧本保证，最终包才运行完整 GDU Validator；
- 没有视觉 Reader、数据库、界面或与其他知识系统的效果对照。

## 5. 如何运行验证

当前工作机的系统 `/usr/bin/python3` 没有 `jsonschema`；项目已有的 Anaconda Python 包含所需依赖。当前验证命令为：

```bash
/opt/anaconda3/bin/python3 -m unittest discover -s tests -v
```

如果在独立环境中运行，先按 `requirements-validator.txt` 安装依赖，再使用该环境的 Python。

## 6. 下一阶段建议

Builder v0 基础设施已冻结。下一步把真实模型 Adapter 和长文档选页/分段作为新的、可替换研究变量，不原位修改本基线。
