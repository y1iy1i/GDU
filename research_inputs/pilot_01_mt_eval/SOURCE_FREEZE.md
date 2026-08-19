# Pilot 01 Source Freeze

> 状态：来源已冻结；仅完成物理结构扫描，尚未开始语义单元构建、GenerativePlan 恢复或 Schema 修改。  
> 冻结日期：2026-08-18

## 1. 文档身份

- 标题：What do Large Language Models Need for Machine Translation Evaluation?
- 作者：Shenbin Qian, Archchana Sindhujan, Minnie Kabra, Diptesh Kanojia, Constantin Orasan, Tharindu Ranasinghe, Frédéric Blain
- 出版：EMNLP 2024，ACL Anthology ID `2024.emnlp-main.214`
- 官方页面：https://aclanthology.org/2024.emnlp-main.214/
- 官方 PDF：https://aclanthology.org/2024.emnlp-main.214.pdf
- 本地原件：`paper.pdf`
- PDF SHA-256：`268ad0f67004844b252e80fee7f6f1724fc9a52506956f7e15b5cd2601371752`
- 文件大小：1,496,206 bytes
- PDF 物理页数：15
- 页面尺寸：A4，595.276 × 841.89 pt
- PDF 版本：1.5
- 加密：否

## 2. 冻结文本提取物

- 本地提取物：`paper.txt`
- 提取器：`pdfplumber 0.11.9`
- 提取参数：`x_tolerance=2`、`y_tolerance=2`
- 页面分隔：`\n\f\n`
- 文本字符数：62,349
- 文本 SHA-256：`34f1b86c82eb5eef5547bf6a7c09317b28ad51e3ed7cf985406104456f68ca63`

该 PDF 为双栏排版。冻结文本可用于检索和候选定位，但单纯按行读取可能交错左右栏，因此不能把文本行序直接当作权威物理阅读顺序。物理结构由标题字号检查、PDF 页面视觉抽查和原文内容共同确认；后续证据锚点仍以 PDF 物理页码、页内文本定位、短摘录和片段哈希为准。

## 3. 可观察物理结构

下列页码均为从 1 开始的 PDF 物理页码。

| 结构 | 起始物理页 |
|---|---:|
| Abstract | 1 |
| 1 Introduction | 1 |
| 2 Related Work | 2 |
| 3 Data | 2 |
| 4 Methodology | 3 |
| 4.1 Baselines | 3 |
| 4.2 Zero-shot Prompting | 3 |
| 4.3 CoT Prompting | 3 |
| 4.4 Few-shot Learning | 3 |
| 4.5 Model Selection | 3 |
| 4.6 Experimental Setup | 4 |
| 5 Results and Discussion | 5 |
| 5.1 Baselines | 5 |
| 5.2 Zero-shot Inference | 5 |
| 5.3 CoT and Few-shot Inference | 8 |
| 5.4 Discussion | 8 |
| 6 Conclusion and Future Work | 9 |
| Limitations and Ethical Considerations | 9 |
| Acknowledgements | 9 |
| References | 9 |
| Appendix A: Pearson's r and Kendall's τ Correlation Scores | 14 |

## 4. 初步适用性检查

- 完整论文，满足 8–20 页范围；
- 问题、数据、方法、实验、讨论、结论和限制结构完整；
- 方法设置与实验结果之间存在明确跨章节对应；
- 结果讨论、结论和限制之间存在支持与限定关系候选；
- 含多表格和双栏正文，可检验正文与非线性证据的混合锚定；
- 首轮走查只使用该 PDF 和冻结提取物，不使用第三方摘要或论文解读。

## 5. 当前未执行

- 未划分自适应语义单元；
- 未生成原子判断或局部功能；
- 未建立跨部分语义关系；
- 未恢复五问式 GenerativePlan；
- 未运行全局—局部定向回查；
- 未创建或修改 GDU Schema、示例和验证代码；
- 未调用付费模型。

## 6. 下一步

先讨论首轮走查的执行方式：人工基准走查、模型 Builder 直接走查，或先人工建立小型参照再运行 Builder。确定后再进入局部语义单元划分。
