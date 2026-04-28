# 插件开发指南

## 插件机制

vocotype-cli 采用 **回调链包装（wrap_result_handler）** 模式实现插件。核心思路：每个插件提供一个 `wrap_result_handler` 函数，接收原始回调并返回包装后的回调，形成洋葱式调用链。

```
原始 handler → LLM 精炼包装 → 数据集记录包装
                ↑ 最内层                ↑ 最外层
```

在 `main.py` 中按顺序包装：

```python
# 1. 基础 handler
worker.on_result = _make_result_handler(...)

# 2. LLM 精炼（修改 result.text 后传给内层）
refiner = create_refiner(config)
if refiner:
    worker.on_result = wrap_llm_handler(worker.on_result, refiner)

# 3. 数据集记录（先调内层 handler，再保存数据）
if args.save_dataset:
    worker.on_result = wrap_result_handler(worker.on_result, worker, dataset_dir)
```

后包装的先执行。上例中执行顺序为：数据集记录 → LLM 精炼 → 原始 handler。

## 编写新插件

### 1. 创建文件

在 `app/plugins/` 下新建 Python 文件，如 `my_plugin.py`。

### 2. 实现 wrap_result_handler

函数签名：

```python
def wrap_result_handler(handler: Callable, ...) -> Callable:
    """包装原始 handler，返回新的 handler。

    Args:
        handler: 上一层的 result handler
        ...: 插件所需的额外参数（config、worker 等）

    Returns:
        包装后的 handler，签名为 (result) -> None
    """
    def wrapped(result) -> None:
        # 在这里做你的事情
        return handler(result)
    return wrapped
```

`result` 是 `TranscriptionResult` 对象，常用属性：
- `result.text` — 识别文本（可读写）
- `result.error` — 错误信息（有值时应跳过处理）
- `result.duration` — 音频时长
- `result.confidence` — 置信度

### 3. 在 main.py 中注册

```python
from app.plugins.my_plugin import wrap_result_handler as wrap_my_plugin

# 在 handler 链中合适的位置包装
worker.on_result = wrap_my_plugin(worker.on_result, ...)
```

## 示例

### llm_refiner — 修改型插件

在传递给内层 handler **之前**修改 `result.text`：

```python
def wrap_result_handler(handler: Callable, refine: Callable[[str], str]) -> Callable:
    def wrapped(result) -> None:
        if not getattr(result, "error", None) and getattr(result, "text", ""):
            result.text = refine(result.text)  # 修改文本
        return handler(result)                  # 传给内层
    return wrapped
```

特点：通过 `create_refiner(config)` 工厂函数创建精炼器，配置关闭时返回 `None`，主程序据此决定是否包装。

### dataset_recorder — 旁路型插件

**先调用**内层 handler 确保正常输出，再做旁路保存：

```python
def wrap_result_handler(handler: Callable, worker, dataset_dir: str) -> Callable:
    def wrapped(result) -> None:
        handler_result = handler(result)  # 先执行原始逻辑
        try:
            # 保存音频 + 文本到 JSONL（失败不影响主流程）
            ...
        except Exception as exc:
            logger.error("保存数据集失败: %s", exc, exc_info=True)
        return handler_result
    return wrapped
```

特点：best-effort，异常被吞掉，不影响正常转录输出。

## 注意事项

1. **不要阻塞主流程** — handler 在转录线程中同步执行。如果插件耗时较长（如网络请求），设置合理的 timeout，或考虑异步处理。

2. **失败必须 fallback** — 插件失败不能导致整个转录链中断。两种策略：
   - 修改型：失败时保留原始 `result.text` 不变（参考 llm_refiner）
   - 旁路型：`try/except` 吞掉异常（参考 dataset_recorder）

3. **使用 logging 模块** — 统一用 `logger = logging.getLogger(__name__)` 记录日志，不要用 `print`。

4. **检查 result.error** — 处理前先判断 `getattr(result, "error", None)`，跳过失败的转录结果。

5. **配置驱动** — 插件的开关和参数放在 `config.json` 中，通过工厂函数或条件判断控制是否启用。
