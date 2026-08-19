# GDU SourceReader v0 验证报告

日期：2026-08-19

状态：最小契约与真实 PDF 烟雾测试通过，尚未冻结。

## 1. 契约测试

`tests/test_source_reader_v0.py` 包含 12 个测试：

- 11 个不依赖真实 PDF 库的确定性契约测试；
- 1 个使用 pypdf/reportlab 生成两页 PDF 的真实往返测试。

覆盖 PDF 身份、预登记哈希、页范围、去重、文件变化、导航隔离、摘录核验、片段哈希、空文本页、视觉载体拒绝、技术故障和请求身份。

## 2. 分环境验证

Anaconda 环境执行全项目：

```bash
/opt/anaconda3/bin/python3 -m unittest discover -s tests -v
```

结果：74 个测试中 73 个通过，真实 pypdf 往返测试因该环境未安装 pypdf/reportlab而按设计跳过。

工作区 PDF 环境单独执行真实往返：

```bash
<workspace-python> \
  -m unittest tests.test_source_reader_v0.PypdfBackendIntegrationTests -v
```

结果：1 个真实两页 PDF 往返测试通过。因此 74 个唯一测试均已在具备相应依赖的环境中通过。

## 3. 三轮 Pilot 只读烟雾验证

使用真实 PypdfBackend 只读取三份 Pilot PDF 的身份和物理第 1 页：

| Pilot | 页数 | SourceReader 哈希前缀 | 与冻结记录 |
|---|---:|---|---|
| Pilot 01 | 15 | `268ad0f67004` | 一致 |
| Pilot 02 | 13 | `5cb57ed53d64` | 一致 |
| Pilot 03 | 237 | `fbb9875c7eca` | 一致 |

三份第 1 页均返回可提取文本，没有修改 PDF，也没有写入 Pilot 目录。

## 4. 其他验证

- Python compileall：通过；
- 设计、Schema、Validator、Build Log 四组冻结基线哈希：全部通过；
- 网络与模型 API：未使用；
- 新依赖安装：未执行。

## 5. 结论边界

可以得出：SourceReader v0 能稳定识别 PDF、按物理页读取文本层并验证文字证据片段。

不能得出：它已经理解表格、图片、扫描页或长文档结构。Orchestrator 文本接线已经验证，但视觉载体与自动选页仍需分别研究。
