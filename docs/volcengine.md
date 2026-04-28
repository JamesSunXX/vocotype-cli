# 火山引擎 BigASR 流式识别

## 概述

Vocotype 支持火山引擎 BigASR 作为云端 ASR 后端，通过 WebSocket 流式发送音频并实时获取识别结果。相比本地 FunASR 方案，BigASR 在中文识别准确率上更优，且无需本地 GPU 资源。

官方文档：<https://www.volcengine.com/docs/6561/1354869>

## 开通步骤

1. 注册并登录 [火山引擎控制台](https://console.volcengine.com/)
2. 进入 [语音技术 → 应用管理](https://console.volcengine.com/speech/app)，创建应用
3. 获取 **App Key** 和 **Access Key**
4. 在 `config.json` 的 `volcengine` 段填入凭据，并将 `backend` 设为 `"volcengine"`

```json
{
  "backend": "volcengine",
  "volcengine": {
    "app_key": "你的 App Key",
    "access_key": "你的 Access Key"
  }
}
```

## 配置项

`config.json` 中 `volcengine` 段的完整字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `app_key` | string | `""` | 火山引擎应用的 App Key（必填） |
| `access_key` | string | `""` | 火山引擎应用的 Access Key（必填） |
| `resource_id` | string | `"volc.bigasr.sauc.duration"` | 资源 ID，默认按时长计费 |
| `url` | string | `"wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"` | WebSocket 端点，一般无需修改 |
| `model_name` | string | `"bigmodel"` | 识别模型名称 |
| `chunk_ms` | int | `100` | 每次发送的音频时长（毫秒），越小延迟越低 |
| `enable_punc` | bool | `true` | 是否自动添加标点 |
| `enable_itn` | bool | `true` | 是否启用数字/格式规范化（如"一百二"→"120"） |

> 仅当 `backend` 设为 `"volcengine"` 时，此配置段才生效。

## 工作原理

客户端与火山引擎服务端通过 WebSocket 二进制协议通信，流程如下：

1. **建立连接** — 携带 `X-Api-Access-Key`、`X-Api-App-Key`、`X-Api-Request-Id` 等 Header 连接 WebSocket 端点
2. **发送初始化请求** — `FULL_CLIENT_REQUEST` 包，包含音频格式（PCM/16kHz/单声道）和识别参数（模型、标点、ITN）
3. **接收初始化 ACK** — 服务端确认参数无误
4. **流式发送音频** — 将录音按 `chunk_ms` 切分为多个 `AUDIO_ONLY_REQUEST` 包，逐个发送；最后一个包设置 `is_last` 标志
5. **接收识别结果** — 服务端持续返回累积文本（每次返回的 `text` 是当前完整结果），直到收到 `is_last_package` 标志

所有 payload 均使用 JSON 序列化 + gzip 压缩。音频为 int16 PCM 格式。

## 与 FunASR 本地方案的对比

| 维度 | FunASR（本地） | 火山引擎 BigASR（云端） |
|------|---------------|----------------------|
| 延迟 | 取决于本地硬件，GPU 下较快 | 网络往返 + 服务端推理，通常 200-500ms |
| 准确率 | 开源模型，中文表现良好 | 商用大模型，中文准确率更高 |
| 隐私 | 音频不出本机，完全离线 | 音频上传至火山引擎服务器 |
| 部署成本 | 需要本地 GPU/CPU 资源 | 无需本地算力，按用量付费 |
| 网络依赖 | 无 | 需要稳定网络连接 |

**选择建议**：对隐私敏感或无网络环境选 FunASR；追求识别准确率或无 GPU 设备选火山引擎。
