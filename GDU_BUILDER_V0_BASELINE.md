# GDU Builder v0 基线冻结说明

冻结日期：2026-08-20

状态：已冻结。后续变更必须创建新版本，不原位修改本清单中的文件。

## 1. 冻结对象

本基线冻结“确定性 GDU Builder 基础设施”，包括：

- CP1–CP6 状态机、两次语义修正和整次运行一次技术重试；
- 候选对象、规范 ID、事务化修正、日志和原子发布；
- PDF 文本层 SourceReader 及授权 SourcePacket；
- 可机械验证的运行配置、Fixed GDU Adapter 和 CLI；
- 固定运行时间、文件哈希、提取后端身份和依赖版本；
- frozen/provisional/technical_failed/input_rejected 四类结束状态；
- 对应测试、说明与验证报告。

`GDU_BUILDER_V0_BASELINE.sha256` 对 28 份基线文件逐一保存 SHA-256。

## 2. 上游冻结契约

Builder v0 依赖但不重复纳入以下既有基线：

- `GDU_V0_DESIGN_BASELINE.sha256`；
- `GDU_SCHEMA_V0_BASELINE.sha256`；
- `GDU_VALIDATOR_V0_BASELINE.sha256`；
- `GDU_BUILD_LOG_V0_BASELINE.sha256`；
- `BUILDER_PROTOCOL_V2.sha256`。

冻结前重新校验了上述四组 GDU 基线，全部为 OK；未原位修改任何上游冻结文件。

## 3. 冻结前验收结果

- Conda 环境：`gdu`，Python 3.12.13；
- 全项目测试：95 通过，0 失败，0 跳过；
- Python compileall 与逐文件 py_compile：通过；
- `pip check`：通过；
- `requirements-lock.txt` 与 `pip freeze`：一致；
- Pilot 03 的 237 页 PDF 到 frozen 三文件包：通过；
- 同一配置重复两次的三文件包：逐字节一致；
- 预登记页范围越界：输入阶段拒绝；
- 修正页范围越界：有界技术失败，无未处理异常；
- 网络、模型 API、付费服务：未使用。

## 4. 未冻结的研究能力

本基线不包含：

- 真实生成模型 Adapter；
- 长文档自动选页、分段、工作记忆或检索策略；
- OCR、图像、视觉表格和公式读取；
- 真实模型的语义质量、成本或稳定性结论；
- GDU 与 Chunk/RAG、PageIndex、知识图谱或其他知识存储方法的优劣结论。

Fixed Adapter 的成功只证明 Builder 基础设施可复现，不能当作真实模型已学会理解文档。

## 5. 冻结外的设计文档

`GDU_BUILDER_MINIMAL_DESIGN_V0_DRAFT.md`、`GDU_BUILDER_INTERFACES_V0_DRAFT.md` 和 `GDU_BUILDER_STATE_MACHINE_TEST_DESIGN_V0_DRAFT.md` 保留为研究决策背景，不纳入本实现基线，不对外构成稳定 API 承诺。
