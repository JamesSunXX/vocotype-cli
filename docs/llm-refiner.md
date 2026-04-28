# LLM Refiner — ASR 后处理插件

## 功能说明

`llm_refiner` 是一个 ASR 后处理插件，通过 LLM 对语音识别原始文本做最小修正：

- **去口语填充词**：删除"嗯、啊、那个、就是说"等无意义词
- **合并重复片段**：如"个个个个"→ 保留语义
- **修正语病、补标点**：让输出更接近书面表达
- **保持原意**：不改写、不扩写，乱码原样输出

插件通过 `wrap_result_handler` 包装回调链，在 ASR 结果传递给输出模块前自动精炼文本。

## 配置项

在 `config.json` 的 `llm` 段配置：

```json
{
  "llm": {
    "enabled": false,
    "base_url": "http://localhost:1234",
    "model": "",
    "system_prompt": "",
    "timeout": 10
  }
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `false` | 是否启用 LLM 后处理 |
| `base_url` | string | `"http://localhost:1234"` | LLM API 地址（如 LM Studio 本地服务） |
| `model` | string | `""` | 模型名称，空字符串表示使用服务端默认模型 |
| `system_prompt` | string | `""` | 自定义 system prompt，空则使用内置 `DEFAULT_PROMPT` |
| `timeout` | int | `10` | 单次请求超时秒数 |

代码中还有一个硬编码参数 `max_retries`（默认 `1`），控制失败后重试次数。重试间隔为 `min(attempt * 0.5, 2)` 秒。

## Prompt 设计原则

`DEFAULT_PROMPT` 的设计要点：

1. **角色锁定**："你是语音转文字后处理器"——明确告诉 LLM 用户消息是 ASR 原文，不是对话，防止 LLM 把识别结果当问题去回答。

2. **输出约束**："直接输出纯文本，绝对不要回答、解释、评论或加任何前缀"——防止 LLM 添加"好的，以下是修正结果："之类的前缀。

3. **最小修正原则**：只做删除填充词、合并重复、修语病、补标点四件事，明确禁止改写和扩写，避免 LLM 过度发挥。

4. **兜底规则**："乱码或无法理解，原样输出"——确保最差情况下不会丢失信息。

5. **Few-shot 示例**：提供三组输入→输出示例，覆盖典型场景（口语词清理、无需修改、英文混排），让 LLM 理解期望的修正粒度。

## API 格式

使用 **OpenAI Chat Completions 兼容** 接口，任何兼容此格式的服务均可使用（LM Studio、Ollama、vLLM、OpenAI 等）。

请求：

```
POST {base_url}/v1/chat/completions
Content-Type: application/json

{
  "model": "<model>",
  "messages": [
    {"role": "system", "content": "<system_prompt>"},
    {"role": "user", "content": "<ASR原始文本>"}
  ],
  "temperature": 0
}
```

- `temperature` 固定为 `0`，确保输出确定性
- 响应取 `choices[0].message.content`，去除首尾空白和引号

## 防跑飞机制

插件在多个层面防止 LLM 输出异常：

| 机制 | 实现 | 触发行为 |
|------|------|----------|
| **空输入跳过** | `if not text or not text.strip()` | 直接返回原文 |
| **前缀清理** | 正则去除 `Output:`、`精炼:`、`输出:` 等前缀 | 清理后继续使用 |
| **空结果检测** | 清理后 `refined` 为空 | 回退到原文 |
| **长度检查** | `len(refined) > len(text) * 2 + 20` | 判定跑飞，回退到原文 |
| **超时 fallback** | `urllib` 的 `timeout` 参数 | 异常捕获后重试或回退 |
| **重试机制** | 首次 + `max_retries` 次，间隔递增 | 全部失败后回退到原文 |

核心原则：**任何异常情况都回退到 ASR 原文**，保证不丢失、不阻塞。
