# Pilot 02 Source Freeze

> 状态：来源已按预注册顺序规则选定并冻结；只完成资格与物理结构检查，尚未建立 Gold、运行 Builder 或修改 Schema。  
> 冻结日期：2026-08-18

## 1. 确定性抽样记录

- 锚点：Pilot 01，ACL Anthology ID `2024.emnlp-main.214`。
- 官方顺序中的下一条：ACL Anthology ID `2024.emnlp-main.215`。
- 候选结果：`.215` 满足全部预注册纳入条件，因此立即停止扫描；未查看或比较 `.216` 及后续论文。
- 排除记录：无；锚点后的第一篇候选即被纳入。
- 选择依据仅限官方元数据与文档结构：NLP 实证研究、非机器翻译评价、篇幅相近、公开完整 PDF，具有方法、实验、结果、表图、限制及伦理讨论，核心结构不依赖外部补充材料。
- 未以结果方向、预期难度、标题吸引力或对 GDU 是否有利作为选择依据。

## 2. 文档身份

- 标题：Performance-Guided LLM Knowledge Distillation for Efficient Text Classification at Scale
- 作者：Flavio Di Palo, Prateek Singhi, Bilal H Fadlallah
- 出版：EMNLP 2024，ACL Anthology ID `2024.emnlp-main.215`
- 页码：3675–3687
- DOI：`10.18653/v1/2024.emnlp-main.215`
- 官方页面：https://aclanthology.org/2024.emnlp-main.215/
- 官方 PDF：https://aclanthology.org/2024.emnlp-main.215.pdf
- 本地原件：`paper.pdf`
- PDF SHA-256：`5cb57ed53d64000eeec1fb6225d83a90ea156ab622e2a3ec247a8a802eb79492`
- 文件大小：647,538 bytes
- PDF 物理页数：13
- 页面尺寸：A4，595.276 × 841.89 pt
- PDF 版本：1.5
- 加密：否

## 3. 冻结文本提取物

- 本地提取物：`paper.txt`
- 提取器：`pdfplumber 0.11.9`
- 提取方式：逐页 `extract_text(layout=True)`
- 页面分隔：`\n\f\n`
- 文本字符数：92,604
- 文本 SHA-256：`0d48cd07f01bb85233208b683381ede22f8fd11cbc8f775891f63961f459da9d`

该 PDF 为双栏排版，并含流程图、算法、表格和附录。冻结文本只用于检索和候选定位；文本行可能交错左右栏，也不能完整保存图表空间关系。正式理解、数值和证据必须回到 PDF 物理页核验。

## 4. 可观察物理结构

下列页码均为从 1 开始的 PDF 物理页码。

| 结构 | 起始物理页 |
|---|---:|
| Abstract | 1 |
| 1 Introduction | 1 |
| 2 Related Work | 2 |
| 3 Methods | 2 |
| 4 Datasets and Experiments | 3 |
| 5 Results and Discussion | 5 |
| 5.1 Comparative Analysis of Related Literature | 7 |
| 5.2 Ablation Study | 7 |
| 5.3 Cost and Latency Benchmarking | 8 |
| 6 Conclusion and Future Work | 8 |
| 7 Limitations | 9 |
| 8 Ethical Considerations | 9 |
| References | 9 |
| Appendix A: Prompt Details | 12 |
| Appendix B: Impact of Training Sample Size | 13 |

## 5. 资格检查结果

- 与 Pilot 01 同属 EMNLP 2024 主论文集和 NLP 实证研究，但任务已改为文本分类中的 LLM 知识蒸馏；
- 13 个物理页，与 Pilot 01 的 15 页复杂度接近；
- 具有研究动机、相关工作、方法、数据与实验、结果讨论、消融、成本与延迟、结论、限制和伦理风险；
- 含 3 个方法图／结果图、1 个算法和 6 张表，可执行跨载体冲突及证据核验；
- 数据—方法—实验—结果—限制之间存在可检查的跨章节功能链；
- 独立限制和潜在风险内容允许检验负面推断边界；
- PDF 13 页均已成功解析，前 9 页及后 4 页分别完成视觉拼页检查，未见缺页、截断或不可读页面。

## 6. 当前未执行

- 未建立或冻结 Pilot 02 Gold；
- 未划分正式语义单元或生成原子判断；
- 未恢复 GenerativePlan；
- 未运行 Protocol v2 Builder；
- 未创建盲工作区；
- 未创建或修改 GDU Schema；
- 未实现 Python Builder。

## 7. 下一步

在主研究任务中完整阅读权威 PDF，按照冻结的可行性决策门建立分为“关键项／支撑项”的 Pilot 02 Gold；由用户逐项审查并冻结后，才能创建独立盲工作区并运行 Builder。
