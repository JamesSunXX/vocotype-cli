# 文档审查笔记

## 一致性检查

### ✅ 通过

- **数据流描述一致**：architecture.md、workflows.md、components.md 中的数据流方向一致（Mic → AudioCapture → TranscriptionWorker → ASR → Plugin Chain → type_text）
- **插件机制描述一致**：所有文档统一使用 `wrap_result_handler` 模式描述，执行顺序说明一致
- **配置字段一致**：data_models.md 中的 DEFAULT_CONFIG 字段与 `app/config.py` 源码完全匹配
- **TranscriptionResult 字段一致**：interfaces.md 和 data_models.md 中的字段定义一致
- **ASR 后端对比一致**：architecture.md 和 dependencies.md 中的 FunASR vs Volcengine 对比信息一致
- **依赖版本一致**：dependencies.md 中的版本号与 requirements.txt 完全匹配

### ⚠️ 注意事项

- **Flask 依赖**：dependencies.md 将 Flask 列为可选依赖（annotate_web.py），但 `tools/annotate_web.py` 实际使用 `http.server` 标准库而非 Flask。建议从可选依赖中移除 Flask 条目
- **LLM max_retries 配置**：llm_refiner.py 中 `max_retries` 已可通过 `config.json` 的 `llm.max_retries` 配置，但 data_models.md 中的 llm 配置段未列出此字段。建议补充

## 完整性检查

### ✅ 覆盖充分

- 所有 13 个源码模块均有文档覆盖
- 所有 Makefile targets 均已记录
- 所有配置段（9 个）均有字段级文档
- 两种 ASR 后端均有详细说明
- 插件开发指南完整（接口、示例、注意事项）
- 数据标注和 SFT 工作流完整

### 📝 可改进区域

1. **测试覆盖**：项目当前无测试文件，文档中未提及测试策略。建议在后续版本中添加测试并更新文档
2. **Windows 支持**：output.py 有 macOS 特定逻辑（pbcopy/osascript），Windows 路径使用 pyperclip + pynput，但文档主要以 macOS 为视角。可补充 Windows/Linux 注意事项
3. **错误码/错误类型**：ASR result dict 的 `error` 字段是自由文本，无标准化错误码。如果后续需要程序化错误处理，建议定义错误枚举
4. **性能基准**：文档缺少性能数据（如不同音频长度的转录延迟、LLM 精炼耗时）。可从日志中提取典型值作为参考
5. **annotate_web.py 内部实现**：Web 标注工具使用原生 `http.server.HTTPServer`，非 Flask。文档中应明确这一点

## 建议修复

| 优先级 | 文件 | 修复内容 |
|--------|------|----------|
| 高 | dependencies.md | 移除 Flask 可选依赖条目，annotate_web.py 使用标准库 http.server |
| 中 | data_models.md | 在 llm 配置段补充 `max_retries` 字段（int, 默认 1） |
| 低 | dependencies.md | 补充 Windows/Linux 平台的系统依赖差异说明 |
