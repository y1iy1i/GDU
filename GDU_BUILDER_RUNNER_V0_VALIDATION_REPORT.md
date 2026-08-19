# GDU Builder v0 可复现运行器验证报告

日期：2026-08-19

状态：配置、Fixed Adapter、CLI 和真实 Pilot 03 往返通过，尚未冻结。

## 1. 验证结果

- Pilot 03 的 237 页 PDF 通过一份 JSON 配置和 CLI 完成六检查点运行；
- 结果为 `frozen_complete`；
- 语义修正 0 次，技术重试 0 次；
- 产生 `gdu.json`、`build_log.jsonl` 和 `ARTIFACTS.sha256`；
- 三文件包通过冻结 GDU Schema、Build Log Schema、语义 Validator 和产物哈希检查；
- 临时产物已清理，没有覆写 Pilot 正式文件。

## 2. 新增测试

新增 8 个配置与运行器测试，覆盖：

- 实例配置加载与六检查点请求构造；
- 父目录越界路径和绝对路径拒绝；
- CP1–CP6 精确集合；
- 冻结上限不可放宽；
- 反向页范围拒绝；
- 不连续表格摘要不能直接被当成 PDF 文本证据；
- 真实 Pilot 03 CLI 冻结三文件往返。

## 3. 全项目测试

当前共 92 个唯一测试。

| 运行方式 | 结果 |
|---|---|
| 新建 Conda `gdu`（Python 3.12.13） | 92 通过，0 失败，0 跳过 |
| Python compileall | 通过 |

环境依赖由 `requirements-test.txt` 统一声明：Builder 运行依赖加 ReportLab 测试依赖。

## 4. 环境备注

一次尝试在 Python 3.13 中直接加载 Python 3.12 的 ReportLab/Pillow 二进制依赖，出现 `_imaging` 导入错误。这是不同 Python ABI 的环境混用，不是 GDU 逻辑失败。为消除该变量，已新建独立 Conda `gdu` 环境，以 Python 3.12.13 安装匹配的 jsonschema、pypdf、ReportLab 和 Pillow，并在该单一环境中完整通过 92 项测试。

## 5. 结论边界

可以得出：确定性 Builder 的运行配置可保存、可机械验证，Fixed Adapter 完整流程可脱离单元测试复现。

不能得出：真实模型 Adapter、自动选页、长文档分段或视觉证据读取已经完成。
