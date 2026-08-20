# API 配置目录

所有远程模型 API 配置集中放在这里。

## 文件说明

- `remote-adapter-v1.schema.json`：配置格式和安全限制；
- `disabled.example.json`：完全关闭远程 API 的最小配置；
- `aliyun-token-plan-deepseek-v4-flash.example.json`：当前阿里云百炼 Token Plan 配置；
- `API_USAGE_POLICY.md`：调用、Key 和额度边界。

## 更换地址或模型

编辑当前提供商 JSON：

- `base_url`：API 地址；
- `model`：模型 ID；
- `api_key_env`：保存 Key 的环境变量名称；
- `max_calls`：本轮最大调用次数。

## 填写 Key

不要把真实 Key 写入本目录或提交 Git。在 Codex 的 `gdu` 环境中增加：

```text
DASHSCOPE_API_KEY=你的阿里云百炼API Key
```

配置文件只保存环境变量名称，运行时才从环境中读取真实值。
