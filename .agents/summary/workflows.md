# Workflows

vocotype-cli 核心工作流文档。每个流程附 Mermaid 图和关键代码入口。

---

## 1. Startup Flow

`main.py:main()` 按顺序初始化所有子系统，最后阻塞等待热键事件。

```mermaid
flowchart TD
    A[parse_args] --> B[load_config]
    B --> C[ensure_logging_dir + setup_logging]
    C --> D[create TranscriptionWorker]
    D --> D1{backend?}
    D1 -->|funasr| D2[FunASRServer.initialize]
    D1 -->|volcengine| D3[VolcengineASRClient]
    D2 --> D4[start _transcription_worker_loop thread]
    D3 --> D4
    D4 --> E[_make_result_handler → base handler]
    E --> F{LLM enabled?}
    F -->|yes| F1[create_refiner → wrap_llm_handler]
    F -->|no| G
    F1 --> G{--save-dataset?}
    G -->|yes| G1[wrap_result_handler dataset_recorder]
    G -->|no| H
    G1 --> H[HotkeyManager.register toggle_combo]
    H --> I[hotkeys.wait — block main thread]
```

**关键入口：**
- `main.py:main()` — 启动编排
- `app/config.py:load_config()` — 配置加载与默认值合并
- `app/transcribe.py:TranscriptionWorker.__init__()` — 后端初始化 + 转录线程启动

---

## 2. Recording & Transcription

热键触发录音开关。录音期间 capture 线程持续填充缓冲区；停止后音频提交到异步转录队列。

```mermaid
sequenceDiagram
    participant U as User
    participant HK as HotkeyManager
    participant TW as TranscriptionWorker
    participant AC as AudioCapture
    participant Q as TranscriptionQueue
    participant WT as WorkerThread
    participant PC as PluginChain

    U->>HK: press toggle hotkey
    HK->>TW: _toggle() → start()
    TW->>AC: start() → open RawInputStream
    TW->>TW: spawn _capture_loop thread

    loop capture_loop
        AC-->>TW: queue.get(frame)
        TW->>TW: append frame to _buffer, track _session_bytes
    end

    U->>HK: press toggle hotkey
    HK->>TW: _toggle() → stop()
    TW->>AC: stop()
    TW->>TW: _combine_buffer() → np.concatenate
    TW->>Q: put_nowait(combined samples)

    WT->>Q: get(timeout=1.0)
    WT->>WT: _transcribe_once(samples)
    WT->>PC: on_result(TranscriptionResult)
    PC->>U: type_text → clipboard paste
```

**关键入口：**
- `main.py:_toggle()` — 防抖 + 录音开关
- `app/transcribe.py:TranscriptionWorker.start()` / `stop()` — 录音生命周期
- `app/transcribe.py:TranscriptionWorker._capture_loop()` — 音频帧采集
- `app/transcribe.py:TranscriptionWorker._transcription_worker_loop()` — 异步转录消费

---

## 3. Plugin Chain Execution

插件通过 `wrap_result_handler` 层层包装回调，形成洋葱模型。包装顺序决定执行顺序。

```mermaid
flowchart LR
    subgraph "包装顺序（main.py）"
        direction TB
        W1["① _make_result_handler → base"]
        W2["② wrap_llm_handler(base, refiner)"]
        W3["③ wrap_result_handler(②, worker, dir)"]
    end

    subgraph "运行时调用顺序"
        direction TB
        R1["Dataset Recorder (outer)"]
        R2["→ calls inner handler"]
        R3["LLM Refiner (middle)"]
        R4["→ result.text = refine(text)"]
        R5["→ calls inner handler"]
        R6["Base Handler (inner)"]
        R7["→ type_text()"]
        R8["← returns to Dataset Recorder"]
        R9["→ copy audio + append JSONL"]
    end

    R1 --> R2 --> R3 --> R4 --> R5 --> R6 --> R7 --> R8 --> R9
```

**执行语义：**
- **LLM Refiner**（中间层）：修改 `result.text` 后传递给内层
- **Dataset Recorder**（外层）：先调用内层 handler（确保文本已精炼+输出），再保存音频和文本

**关键入口：**
- `app/plugins/llm_refiner.py:wrap_result_handler()` — 文本精炼包装
- `app/plugins/dataset_recorder.py:wrap_result_handler()` — 数据集记录包装

---

## 4. LLM Refinement

ASR 原始文本经 LLM 去除口语词、修正语病，支持重试和安全回退。

```mermaid
flowchart TD
    A[输入 ASR text] --> B{text 为空?}
    B -->|yes| Z[返回原文]
    B -->|no| C[attempt = 0]
    C --> D[_call_llm: POST /v1/chat/completions]
    D -->|成功| E[strip prefix 'Output:' etc.]
    D -->|异常| F{attempt < 1 + max_retries?}
    F -->|yes| G[sleep 0.5×attempt] --> D
    F -->|no| Z
    E --> H{结果为空?}
    H -->|yes| Z
    H -->|no| I{len > text×2+20?}
    I -->|yes| Z
    I -->|no| J[返回精炼文本]
```

**校验规则：**
1. 空结果 → 回退原文
2. 输出长度 > 原文×2+20 → 疑似跑飞，回退原文
3. 去除 `Output:`/`精炼:`/`输出:` 等前缀

**关键入口：**
- `app/plugins/llm_refiner.py:create_refiner()` — 创建闭包
- `app/plugins/llm_refiner.py:refine()` — 重试+校验逻辑

---

## 5. Volcengine Streaming ASR

通过 WebSocket 二进制协议与火山引擎 BigASR 交互，并发发送音频和接收结果。

```mermaid
sequenceDiagram
    participant C as VolcengineASRClient
    participant WS as WebSocket Server

    C->>WS: connect (headers: app_key, access_key, request_id)
    C->>WS: FULL_CLIENT_REQUEST (JSON+gzip: format, sample_rate, model_name, enable_punc, enable_itn)
    WS-->>C: FULL_SERVER_RESPONSE (ACK)

    par 并发
        loop 每 chunk_ms 毫秒的音频
            C->>WS: AUDIO_ONLY_REQUEST (gzip PCM chunk)
        end
        C->>WS: AUDIO_ONLY_REQUEST (last chunk, NEG_SEQUENCE flag)
    and
        loop 接收中间结果
            WS-->>C: FULL_SERVER_RESPONSE (累积 text)
        end
        WS-->>C: FULL_SERVER_RESPONSE (is_last_package=true, final text)
    end

    Note over C: full_text = 最后一次收到的 text
```

**二进制协议：** 4 字节头 = version(4bit) + header_size(4bit) + msg_type(4bit) + flags(4bit) + serialization(4bit) + compression(4bit) + reserved(8bit)

**关键入口：**
- `app/volcengine_asr.py:VolcengineASRClient.transcribe()` — 同步入口（内部 asyncio）
- `app/volcengine_asr.py:VolcengineASRClient._async_transcribe()` — WebSocket 流式实现

---

## 6. Dataset Collection

`--save-dataset` 标志启用数据集记录器，每次转录后自动保存音频和文本对。

```mermaid
flowchart TD
    A["main.py: --save-dataset flag"] --> B["wrap_result_handler(handler, worker, dataset_dir)"]
    B --> C["mkdir dataset/audio/"]

    subgraph "每次转录完成"
        D[调用内层 handler] --> E{result.error?}
        E -->|yes| F[跳过]
        E -->|no| G[读取 worker.last_segment_path]
        G --> H[生成 ID: timestamp-uuid8]
        H --> I["atomic copy → dataset/audio/{id}.wav"]
        I --> J["append JSONL → dataset/dataset.jsonl"]
    end
```

**JSONL 记录格式：**
```json
{
  "id": "20260429_012000_123456-a1b2c3d4",
  "audio": "audio/20260429_012000_123456-a1b2c3d4.wav",
  "text": "精炼后文本",
  "raw_text": "ASR原始文本",
  "duration": 3.5,
  "sample_rate": 16000,
  "inference_latency": 0.82,
  "confidence": 0.95,
  "timestamp": "2026-04-29T01:20:00Z"
}
```

**关键入口：**
- `app/plugins/dataset_recorder.py:wrap_result_handler()` — 包装器工厂

---

## 7. Data Annotation

收集的数据集通过 Web UI 或 CLI 工具进行人工标注，用于后续 SFT 微调。

```mermaid
flowchart TD
    A["make annotate / make annotate-web"] --> B{模式?}
    B -->|CLI| C["tools/annotate.py"]
    B -->|Web| D["tools/annotate_web.py"]

    C --> E[逐条播放音频]
    E --> F[显示 ASR 文本，用户编辑]
    F --> G[标记 dirty/clean]

    D --> H[启动 Web 服务器]
    H --> I[浏览器打开标注界面]
    I --> J[播放音频 + 编辑文本 + 标记]

    G --> K["保存 → annotated.jsonl"]
    J --> K

    K --> L["SFT 训练流程"]
```

**SFT 完整流程：** 采集数据（`--save-dataset`）→ 标注（`make annotate`）→ 微调 Paraformer 模型

**关键入口：**
- `tools/annotate.py` — CLI 标注工具
- `tools/annotate_web.py` — Web 标注 UI

---

## 8. Session Size Limit

防止单次录音无限增长。capture 线程在每帧写入后检查累计字节数。

```mermaid
flowchart TD
    A["_capture_loop: 写入帧到 _buffer"] --> B["_session_bytes += frame.nbytes"]
    B --> C{"_session_bytes >= max_session_bytes?"}
    C -->|no| A
    C -->|yes| D{"_stop_requested already set?"}
    D -->|yes| A
    D -->|no| E["log warning: 达到上限"]
    E --> F["self.stop(_from_capture_thread=True)"]
    F --> G["break capture_loop"]
```

**要点：**
- 默认上限 20MB（`config.audio.max_session_bytes`）
- `_from_capture_thread=True` 避免 capture 线程 join 自己导致死锁
- 超限后自动提交转录，用户无需手动停止

**关键入口：**
- `app/transcribe.py:TranscriptionWorker._capture_loop()` — 大小检查逻辑

---

## 9. Graceful Shutdown

Ctrl+C 触发有序清理，确保队列中的转录任务尽量完成。

```mermaid
sequenceDiagram
    participant U as User
    participant M as main()
    participant TW as TranscriptionWorker
    participant Q as TranscriptionQueue
    participant WT as WorkerThread
    participant HK as HotkeyManager

    U->>M: Ctrl+C (KeyboardInterrupt)
    M->>TW: worker.stop()
    Note over TW: 停止录音，提交最后一段音频

    M->>TW: worker.cleanup()
    TW->>TW: _stop_transcription_worker(timeout=3.0)

    alt 队列非空
        TW->>Q: 等待队列清空（最多 3 秒）
        Q-->>WT: 处理剩余任务
    end

    TW->>Q: put(None) — 停止信号
    WT->>WT: 收到 None，退出循环
    TW->>WT: thread.join(timeout=2.0)
    TW->>TW: 清理 buffer + AudioCapture + ASR 后端

    M->>HK: hotkeys.cleanup()
    HK->>HK: unregister_all + stop listener + set stop_event

    M->>M: sys.exit(0)
```

**超时策略：**
- 队列排空等待：3 秒（超时则丢弃剩余任务并 warning）
- 线程 join：2 秒（超时则强制继续退出）
- 每个 cleanup 步骤独立 try/except，单步失败不阻塞后续清理

**关键入口：**
- `main.py:main()` — finally 块
- `app/transcribe.py:TranscriptionWorker.cleanup()` — 资源释放
- `app/transcribe.py:TranscriptionWorker._stop_transcription_worker()` — 队列排空逻辑
