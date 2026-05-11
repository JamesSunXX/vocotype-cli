# Agents

<!-- tags: navigation, agent-context, codebase-map -->

本文件是 AI agent 的导航入口。先读这里，再按需深入。

## 一句话

vocotype-cli：热键触发录音 → ASR 转文字 → 可选 LLM 精炼 → 注入到当前应用。支持 FunASR 本地离线和火山引擎云端两种后端。

## 快速定位

<!-- tags: task-routing -->

| 要做什么 | 读哪里 |
|---------|--------|
| 理解系统全貌 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 了解版本计划 | [PLANS.md](PLANS.md) |
| 修改 ASR 识别逻辑 | `app/transcribe.py`, `app/funasr_server.py` |
| 修改云端 ASR | `app/volcengine_asr.py`, [docs/volcengine.md](docs/volcengine.md) |
| 修改 LLM 后处理 | `app/plugins/llm_refiner.py`, [docs/llm-refiner.md](docs/llm-refiner.md) |
| 修改热键/输入 | `app/hotkeys.py`, `app/output.py` |
| 修改音频采集 | `app/audio_capture.py` |
| 添加新插件 | `app/plugins/`, [docs/plugin-guide.md](docs/plugin-guide.md) |
| 数据标注/SFT | `tools/`, [docs/sft-guide.md](docs/sft-guide.md) |
| 配置说明 | `app/config.py` 中的 `DEFAULT_CONFIG` |
| 运行项目 | `Makefile`（`make help` 查看所有命令） |
| 深入文档 | [.agents/summary/index.md](.agents/summary/index.md) |

## 目录结构

<!-- tags: directory-map -->

```
main.py                  # CLI 入口，组装各模块
app/
  config.py              # 配置加载与默认值（DEFAULT_CONFIG）
  audio_capture.py       # 麦克风采集（sounddevice，16kHz 单声道）
  transcribe.py          # 转录调度（录音→异步队列→识别→回调）
  funasr_server.py       # FunASR 本地 ASR（Paraformer ONNX）
  funasr_config.py       # 模型名称/版本，支持环境变量覆盖
  volcengine_asr.py      # 火山引擎云端 ASR（WebSocket 二进制协议）
  hotkeys.py             # 全局热键（pynput，支持修饰键组合）
  output.py              # 文本注入（macOS: pbcopy+osascript; 其他: pynput）
  wave_writer.py         # WAV 文件写入工具
  logging_config.py      # 日志配置（按日轮转，保留 3 天）
  download_models.py     # 模型并行下载（modelscope，离线优先）
  plugins/
    llm_refiner.py       # LLM 后处理（OpenAI 兼容 API，重试+防跑飞）
    dataset_recorder.py  # 数据集采集（音频+文本对，JSONL+WAV）
tools/
  annotate.py            # CLI 数据标注工具
  annotate_web.py        # Web 数据标注工具（http.server，非 Flask）
docs/                    # 详细指南
```

## 数据流

<!-- tags: architecture, data-flow -->

```
麦克风 → AudioCapture → TranscriptionWorker → [LLM Refiner] → type_text → 剪贴板/键盘
              ↓                   ↓                                ↑
         audio buffer      FunASR / Volcengine              Dataset Recorder
```

## 关键设计决策

<!-- tags: architecture, patterns -->

- **插件机制**：`wrap_result_handler` 回调链包装模式。后包装的先执行。插件失败时 fallback 到原文，不中断流程
- **线程模型**：主线程阻塞等待热键；capture 线程采集音频；transcription worker 线程从队列消费并转录。通过 `threading.Event` + `queue.Queue` 协调
- **ASR 后端**：`config["backend"]` 选择 `"funasr"`（本地 ONNX）或 `"volcengine"`（云端 WebSocket）。两者返回统一的 result dict
- **配置合并**：`DEFAULT_CONFIG` 深度合并用户 `config.json`，所有字段有默认值
- **macOS 文本注入**：优先 pbcopy + osascript 模拟 Cmd+V（支持中文），fallback 到 pynput 逐字输入

## 项目约定

<!-- tags: conventions -->

- **语言**：Python 3.12+，无类型检查（暂），日志用 `logging` 模块
- **配置**：单一 `config.json`，所有字段有默认值
- **插件**：通过 `wrap_result_handler` 包装回调链
- **音频**：统一 16kHz 单声道 int16 PCM WAV
- **提交**：功能用 `feat:`，修复用 `fix:`，重构用 `refactor:`
- **错误处理**：插件 best-effort，异常吞掉不阻塞主流程

## 知识库

<!-- tags: documentation -->

详细文档在 `docs/` 目录：

- [docs/llm-refiner.md](docs/llm-refiner.md) — LLM 后处理的 prompt 设计和 API 格式
- [docs/plugin-guide.md](docs/plugin-guide.md) — 如何编写新插件
- [docs/sft-guide.md](docs/sft-guide.md) — ASR 模型微调流程（数据采集→标注→训练）
- [docs/volcengine.md](docs/volcengine.md) — 火山引擎 ASR 接入说明

生成文档在 `.agents/summary/` 目录，入口：[.agents/summary/index.md](.agents/summary/index.md)

## Custom Instructions
<!-- This section is for human and agent-maintained operational knowledge.
     Add repo-specific conventions, gotchas, and workflow rules here.
     This section is preserved exactly as-is when re-running codebase-summary. -->
