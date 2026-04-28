# Architecture

本文档是系统架构地图，帮助人和 agent 快速定位代码。不是教程，不是 API 文档。

## 一句话

vocotype-cli 是一个本地语音输入工具：热键触发录音 → ASR 转文字 → 可选 LLM 精炼 → 注入到当前应用。

## 数据流

```
麦克风 → AudioCapture → TranscriptionWorker → [LLM Refiner] → type_text → 剪贴板/键盘
              ↓                   ↓
         audio buffer      FunASR / Volcengine
```

## 目录结构

```
main.py                  # CLI 入口，组装各模块
app/
  config.py              # 配置加载与默认值
  audio_capture.py       # 麦克风采集（sounddevice）
  transcribe.py          # 转录调度（管理录音→识别→回调的生命周期）
  funasr_server.py       # FunASR 本地 ASR 后端
  funasr_config.py       # 模型名称/版本配置
  volcengine_asr.py      # 火山引擎云端 ASR 后端
  hotkeys.py             # 全局热键监听（pynput）
  output.py              # 文本注入（剪贴板粘贴 / pynput 模拟键入）
  wave_writer.py         # WAV 文件写入
  logging_config.py      # 日志配置
  download_models.py     # 模型下载脚本
  plugins/
    llm_refiner.py       # LLM 后处理插件（去口语词、修语病）
    dataset_recorder.py  # 数据集采集插件（保存音频+文本对）
tools/
  annotate.py            # CLI 数据标注工具
  annotate_web.py        # Web 数据标注工具（浏览器 UI）
```

## 核心模块职责

### AudioCapture
管理麦克风流。start() 开始采集到内部 queue，stop() 停止，flush() 清空缓冲。处理设备选择、采样率适配和 resample。

### TranscriptionWorker
核心调度器。持有 AudioCapture，管理录音→转录的完整生命周期。后台线程池处理转录任务，通过 on_result 回调返回结果。支持 funasr 和 volcengine 两种后端。

### HotkeyManager
全局热键监听。注册热键组合 → 按下时触发回调。基于 pynput。

### 插件机制
插件通过 `wrap_result_handler` 模式工作：包装 on_result 回调，在 ASR 结果和最终输出之间插入处理逻辑。链式组合：`ASR → LLM Refiner → Dataset Recorder → type_text`。

## ASR 后端

| 后端 | 模式 | 配置键 |
|------|------|--------|
| FunASR (Paraformer ONNX) | 本地离线 | `backend: "funasr"` |
| 火山引擎 BigASR | 云端流式 WebSocket | `backend: "volcengine"` |

## 配置

单一 `config.json`，通过 `load_config()` 加载并与 `DEFAULT_CONFIG` 合并。关键配置段：`hotkeys`、`audio`、`asr`、`volcengine`、`llm`、`output`。

## 不变量

- 所有音频处理使用 16kHz 单声道
- 插件不能阻塞主线程（转录在后台线程池）
- 插件失败时 fallback 到原文，不中断流程
- config.json 中未设置的字段使用 DEFAULT_CONFIG 默认值
