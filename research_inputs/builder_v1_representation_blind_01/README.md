# Builder V1 Representation Blind 01

这是 Representation Compiler 的第一次受约束盲抽取实验。

- `input.json`：模型可见的三领域原文、布局说明、固定 Context 和允许的 Atom 词表；
- `gold.json`：只在模型返回后由本地评分器读取；
- `run_01/`：保存请求哈希、原始响应和评分结果，不保存 API Key。

本轮是“闭合 Atom 词表”实验：它检验原子化、证据引用、数值、极性、规范力和比较方向，不用来证明模型已经能开放发现任意 Atom。

输入与 Gold 分离是硬边界：远程请求由 `input.json` 构建，请求完成后才读取 `gold.json`。
