# VocoType - 精准的离线语音输入法

<h2 align="center">您的声音，绝不离开电脑</h2>

**VocoType** 是一款专为注重隐私和效率的专业人士打造的、**完全免费**的桌面端语音输入法。所有识别均在本地完成，无惧断网，不上传任何数据。

这个 GitHub 项目是 VocoType 核心引擎的 **CLI (命令行) 开源版本**，主要面向开发者。

---

### **➡️ 想获得最佳体验？请立即下载免费桌面版！**

开箱即用，功能更完整，无需任何技术背景。

**[立即访问官网，下载免费、完整的 VocoType 桌面版](https://vocotype.com)**

## 功能简介

VocoType 是一款智能语音输入工具，通过快捷键即可将语音实时转换为文字并自动输入到当前应用。支持 AI 优化文本、自定义热词、数据采集与标注等功能，让语音输入更高效、更准确。

### 📹 演示视频

<video controls width="100%">
  <source src="https://s1.bib0.com/leilei/i/2025/11/04/5yba.mp4" type="video/mp4">
  您的浏览器不支持视频播放。
</video>

## 下载

| OS | Download |
|---|---|
| **Windows** | [![Setup](https://img.shields.io/badge/Setup-x64-blue)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_x64-setup.exe) |
| **macOS** | [![DMG](https://img.shields.io/badge/DMG-Apple%20Silicon-black)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_Universal.dmg) [![DMG](https://img.shields.io/badge/DMG-Intel-black)](https://github.com/233stone/vocotype-cli/releases/download/v1.5.4/VocoType_1.5.4_Universal.dmg) |

---

## 🤔 VocoType 为何与众不同？

| 特性 | ✅ **VocoType** | 传统云端输入法 | 操作系统自带 |
|:---|:---:|:---:|:---:|
| **隐私安全** | **本地离线，绝不上传** | ❌ 数据需上传云端 | ⚠️ 隐私政策复杂 |
| **网络依赖** | **完全无需联网** | ❌ 必须联网使用 | ❌ 强依赖网络 |
| **响应速度** | **0.1 秒级** | 慢，受网速影响 | 慢，受网速影响 |
| **定制化能力** | **强大的自定义词表** | 弱或无 | 基本没有 |

## ✅ 核心功能

- **系统级全局输入**：在任何软件、任何文本框内都能直接语音输入
- **100% 离线运行**：绝对的隐私和数据安全
- **旗舰级识别引擎**：FunASR Paraformer，精准识别中英混合内容
- **云端后端可选**：火山引擎 BigASR 流式识别，追求更高准确率时使用
- **AI 智能优化**：LLM 后处理自动修正口语词、语病、标点（支持 LM Studio 等本地模型）
- **自定义热词**：提升专业术语识别准确率
- **数据采集与标注**：内置数据集录制和 Web 标注工具，支持 ASR 模型微调

## 🏗️ 系统架构

```
麦克风 → AudioCapture → TranscriptionWorker → [LLM Refiner] → type_text → 剪贴板/键盘
              ↓                   ↓                                ↑
         audio buffer      FunASR / Volcengine              Dataset Recorder
```

**ASR 后端对比：**

| 维度 | FunASR（本地） | 火山引擎 BigASR（云端） |
|------|:---:|:---:|
| 网络要求 | 无 | 需要联网 |
| 模型下载 | ~500 MB | 无需下载 |
| 数据隐私 | 完全离线 | 音频发送至火山引擎 |
| 识别质量 | 高 | 旗舰级大模型 |

## 🛠️ CLI 版安装指南

### 环境依赖

- Python 3.12+
- macOS: 需授予终端麦克风和辅助功能权限
- 建议使用 `uv` 或 `venv` 创建虚拟环境

### 安装

```bash
# 克隆仓库
git clone https://github.com/233stone/vocotype-cli.git
cd vocotype-cli

# 安装依赖
make install

# 下载 ASR 模型（首次，约 500MB）
make download-models
```

### 使用

```bash
# 启动语音输入（按 Option_R 开始/停止录音）
make run

# 启动语音输入 + 保存数据集
make run-save

# 启动 Web 标注工具
make annotate

# 查看所有命令
make help
```

### 配置

创建 `config.json` 自定义配置（所有字段均有默认值）：

```json
{
  "hotkeys": { "toggle": "opt_r" },
  "backend": "funasr",
  "asr": { "hotword": "Kubernetes API Docker" },
  "llm": {
    "enabled": true,
    "base_url": "http://localhost:1234",
    "model": "your-model-name"
  }
}
```

详细配置说明见 `app/config.py` 中的 `DEFAULT_CONFIG`。

### 火山引擎云端后端（可选）

```json
{
  "backend": "volcengine",
  "volcengine": {
    "app_key": "YOUR_APP_KEY",
    "access_key": "YOUR_ACCESS_KEY"
  }
}
```

详见 [docs/volcengine.md](docs/volcengine.md)。

## 📚 文档

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构和设计决策 |
| [PLANS.md](PLANS.md) | 版本迭代计划 |
| [docs/llm-refiner.md](docs/llm-refiner.md) | LLM 后处理 prompt 设计和 API 格式 |
| [docs/plugin-guide.md](docs/plugin-guide.md) | 插件开发指南 |
| [docs/sft-guide.md](docs/sft-guide.md) | ASR 模型微调流程 |
| [docs/volcengine.md](docs/volcengine.md) | 火山引擎 ASR 接入说明 |

## 🎯 适用场景

| 用户 | 场景 |
|:---|:---|
| **作家与创作者** | 撰写文章、小说，整理会议纪要 |
| **法律 & 医疗人士** | 处理敏感信息，100% 离线确保数据安全 |
| **学生与学者** | 快速记录课堂笔记、整理访谈录音 |
| **开发者 & 程序员** | AI 结对编程、技术文档撰写，精准识别专业术语 |
| **游戏玩家** | 语音快速打字与队友交流 |

## 常见问题

**Q: 我的数据安全吗？**
> 100% 安全。使用本地 FunASR 后端时，所有语音识别均在本地离线完成，音频数据不会上传到任何服务器。

**Q: 首次运行需要下载什么？**
> 需要下载约 500MB 的 Paraformer ONNX 模型文件，之后完全离线运行。

**Q: 支持哪些操作系统？**
> macOS（推荐）和 Linux。Windows 支持有限（文本注入使用 pynput 逐字输入）。

## 📞 联系我们

- **Bug 与建议**：请使用 GitHub Issues
- **官网**：[https://vocotype.com](https://vocotype.com)

## 🙏 致谢

- **[FunASR](https://github.com/modelscope/FunASR)** — 阿里巴巴达摩院开源语音识别框架
- **[QuQu](https://github.com/yan5xu/ququ)** — 提供了重要的技术参考和灵感

## License

[LICENSE](LICENSE)
