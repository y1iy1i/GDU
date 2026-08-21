# Builder V1 表示层盲测 02

## 目的

检验首轮盲测后形成的四类通用修复能否处理未见表达，而不是继续提高原题分数。

## 冻结内容

- `input.json`：4 个案例、11 个 Evidence Block、13 个允许 Atom；
- `gold.json`：模型调用后才允许评分器读取；
- 两个 `.sha256` 文件：证明输入和 Gold 没有在看到模型回答后被改写。

输入和 Gold 于远程生成前冻结。请求哈希为：

```text
5f388f82e24afb9bb5c013e71bf4d73b93c506f51d3d0958ae97de2d8006bf97
```

## 案例构成

| 案例 | 来源性质 | 检查重点 |
|---|---|---|
| `finance_table` | 使用已核实财务数值制作的冻结控制表格，不冒充PDF逐字转录 | 表头、单位、行列位置、负数与命题形式 |
| `pgkd_algorithm` | 项目已保存的论文算法证据 | 符号索引和算法字面对象 |
| `standard_metadata` | 项目已保存的标准正文与附录证据 | 跨页引用和规范力 |
| `comparison_control` | 冻结控制文本 | 阈值、相对比较、集合最值和来源明确的待定状态 |

控制案例与真实来源案例必须分开报告，不能把控制文本成绩冒充真实文档泛化成绩。

## 运行限制

- 固定模型：`deepseek-v4-flash-0731`；
- 一次运行最多一个远程请求；
- 不向模型提供 Gold；
- 不再提供 Evidence Block 之外的布局事实；
- 原始输出和原始评分一经生成不得覆盖。

## 安全运行

推荐在项目根目录创建 `.env`，内容只有：

```text
DASHSCOPE_API_KEY=你的真实Key
```

之后直接执行：

```bash
conda activate gdu
PYTHONPATH=src:. python scripts/run_builder_v1_representation_blind_02.py
```

也可以不创建 `.env`，改为只在当前终端临时输入：

```bash
conda activate gdu
read -s "DASHSCOPE_API_KEY?请粘贴 API Key："
export DASHSCOPE_API_KEY
PYTHONPATH=src:. python scripts/run_builder_v1_representation_blind_02.py
unset DASHSCOPE_API_KEY
```

两种方式都不会把Key写入实验输出。项目内的 `.env` 已被 Git 忽略，不能提交；`.env.example` 只保存占位符。
