# Agents

本文件是 AI agent 的导航入口。先读这里，再按需深入。

## 快速定位

| 要做什么 | 读哪里 |
|---------|--------|
| 理解系统全貌 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 了解版本计划 | [PLANS.md](PLANS.md) |
| 修改 ASR 识别逻辑 | `app/transcribe.py`, `app/funasr_server.py` |
| 修改云端 ASR | `app/volcengine_asr.py`, [docs/guides/volcengine.md](docs/guides/volcengine.md) |
| 修改 LLM 后处理 | `app/plugins/llm_refiner.py`, [docs/guides/llm-refiner.md](docs/guides/llm-refiner.md) |
| 修改热键/输入 | `app/hotkeys.py`, `app/output.py` |
| 修改音频采集 | `app/audio_capture.py` |
| 添加新插件 | `app/plugins/`, [docs/guides/plugin-guide.md](docs/guides/plugin-guide.md) |
| 数据标注/SFT | `tools/`, [docs/guides/sft-guide.md](docs/guides/sft-guide.md) |
| 配置说明 | `app/config.py` 中的 `DEFAULT_CONFIG` |
| 运行项目 | `Makefile`（`make help` 查看所有命令） |

## 项目约定

- **语言**：Python 3.12+，无类型检查（暂），日志用 `logging` 模块
- **配置**：单一 `config.json`，所有字段有默认值
- **插件**：通过 `wrap_result_handler` 包装回调链
- **音频**：统一 16kHz 单声道 WAV
- **提交**：功能用 `feat:`，修复用 `fix:`，重构用 `refactor:`

## 知识库

详细文档在 `docs/` 目录：

**指南** (`docs/guides/`)：
- [docs/guides/llm-refiner.md](docs/guides/llm-refiner.md) — LLM 后处理的 prompt 设计和 API 格式
- [docs/guides/plugin-guide.md](docs/guides/plugin-guide.md) — 如何编写新插件
- [docs/guides/sft-guide.md](docs/guides/sft-guide.md) — ASR 模型微调流程（数据采集→标注→训练）
- [docs/guides/volcengine.md](docs/guides/volcengine.md) — 火山引擎 ASR 接入说明

**版本规划** (`docs/plans/`)：见 [PLANS.md](PLANS.md)
