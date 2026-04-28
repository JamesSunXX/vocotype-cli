# ASR 模型微调（SFT）指南

## 概述

VocoType 默认使用 FunASR Paraformer 通用中文模型。通用模型对个人口音、语速习惯和技术术语（如 API 名称、框架术语、缩写）的识别准确率有限。

通过 SFT（Supervised Fine-Tuning）微调，用你自己的语音数据训练模型，可以显著提升：

- **口音适应** — 适配个人发音习惯和语速
- **术语识别** — 正确识别 Kubernetes、FastAPI、PyTorch 等技术词汇
- **上下文理解** — 学习你常用的表达模式

目标：采集 **200–500 条**标注数据即可获得明显提升。

## 数据采集

### 启用数据集记录

使用 `--save-dataset` 参数启动，正常使用语音输入的同时自动保存每条音频和 ASR 识别结果：

```bash
# 直接运行
python main.py --save-dataset

# 或通过 Makefile
make run-save
```

数据默认保存到 `dataset/` 目录：

```
dataset/
├── audio/                    # WAV 音频文件（16kHz 单声道）
│   ├── 20260429_031200_123456-abcd1234.wav
│   └── ...
└── dataset.jsonl             # 每条记录一行 JSON
```

### 工作原理

`dataset_recorder` 插件以 AOP 方式包装 result handler。每次转录完成后：

1. 将音频片段复制到 `dataset/audio/`（原子写入，不影响正常流程）
2. 将转录记录追加到 `dataset.jsonl`

插件是 best-effort 的——保存失败只记日志，不影响正常语音输入。

### dataset.jsonl 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识（时间戳 + UUID） |
| `audio` | string | 音频文件相对路径 |
| `text` | string | ASR 识别文本（经后处理） |
| `raw_text` | string | ASR 原始文本 |
| `duration` | float | 音频时长（秒） |
| `sample_rate` | int | 采样率（16000） |
| `inference_latency` | float | 推理耗时（秒） |
| `confidence` | float | 置信度 |
| `timestamp` | string | 采集时间（ISO 8601） |

## 数据标注

ASR 识别结果不完美，需要人工校正后才能用于训练。

### Web 标注工具（推荐）

```bash
make annotate
# 或
python tools/annotate_web.py --port 8686
```

浏览器打开 `http://127.0.0.1:8686`，界面支持：

- **▶ 播放** — 回放音频
- **修正文本** — 编辑输入框中的 ASR 文本，按 Enter 或点"✓ 保存"
- **✗ 脏数据** — 标记噪音、无效音频（text 设为空，训练时过滤）
- **筛选** — 全部 / 待标注 / 已标注

### 命令行标注工具

```bash
python tools/annotate.py                    # 标注未完成的样本
python tools/annotate.py --all              # 重新标注全部
python tools/annotate.py --dataset-dir DIR  # 指定目录
```

命令行操作：回车=确认原文，`r`=重播，`s`=跳过，`d`=脏数据，`q`=退出。

### 标注输出格式

标注结果保存到 `dataset/annotated.jsonl`，每行一条：

```json
{
  "id": "20260429_031200_123456-abcd1234",
  "audio": "audio/20260429_031200_123456-abcd1234.wav",
  "original_text": "ASR 原始识别结果",
  "text": "人工校正后的文本",
  "duration": 3.2
}
```

| 字段 | 说明 |
|------|------|
| `id` | 与 dataset.jsonl 中的 id 对应 |
| `audio` | 音频文件相对路径 |
| `original_text` | ASR 原始识别文本 |
| `text` | 人工校正后的正确文本（空字符串表示脏数据） |
| `duration` | 音频时长（秒） |

### 标注建议

- 优先标注 ASR 识别错误的样本，正确的直接回车确认
- 技术术语保持一致的写法（如统一用 "Kubernetes" 而非混用 "k8s"）
- 脏数据（背景噪音、说话中断）直接标记，不要勉强标注

## 训练

### 前置条件

- Python 3.12+
- FunASR 库：`pip install funasr`
- 基础模型：`iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx`（训练需要非 ONNX 的 PyTorch 版本）

### 硬件要求

| 环境 | 配置 | 说明 |
|------|------|------|
| 本地 | Apple M4 Pro 64GB | 可训练，使用 MPS 加速 |
| 本地 | NVIDIA GPU 8GB+ | CUDA 加速 |
| 云端 | 任意 GPU 实例 | 数据量小，低配即可 |

### 基本流程

1. **准备数据** — 将 `annotated.jsonl` 转换为 FunASR 训练格式，过滤掉脏数据（text 为空的记录）

2. **下载 PyTorch 模型** — 训练需要非 ONNX 版本的 Paraformer：
   ```bash
   # FunASR 会自动下载到 ~/.cache/modelscope/
   # 模型名：iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
   ```

3. **配置训练参数** — 参考 FunASR finetune 文档，关键参数：
   ```yaml
   learning_rate: 1e-5        # SFT 用小学习率
   max_epoch: 5-10            # 数据量小，不宜过多
   batch_size: 4-8            # 根据显存调整
   ```

4. **启动训练**：
   ```bash
   funasr-train \
     --model iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch \
     --train_data dataset/train.jsonl \
     --val_data dataset/val.jsonl \
     --output_dir output/sft_model
   ```

5. **评估与部署** — 用验证集对比微调前后的字错率（CER），确认提升后替换模型

### 数据量参考

| 数据量 | 预期效果 |
|--------|---------|
| < 100 条 | 效果有限，可能过拟合 |
| 200–500 条 | **推荐范围**，术语和口音适应明显 |
| 500+ 条 | 更稳定，但边际收益递减 |

## 完整工作流

```
日常使用（--save-dataset）
    ↓
积累 200+ 条数据
    ↓
make annotate（Web 标注）
    ↓
标注校正 → annotated.jsonl
    ↓
数据转换 + 训练
    ↓
替换模型，验证效果
```
