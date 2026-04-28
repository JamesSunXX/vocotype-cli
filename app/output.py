"""Cross-platform text injection utilities."""

from __future__ import annotations

import logging
import platform
import subprocess
import time

logger = logging.getLogger(__name__)

_IS_MACOS = platform.system() == "Darwin"


def type_text(text: str, append_newline: bool = False, method: str = "auto") -> None:
    if not text:
        return

    payload = text + ("\n" if append_newline else "")
    logger.debug("注入文本: %s", payload)

    method = (method or "auto").lower()

    if _IS_MACOS:
        # macOS: 剪贴板粘贴最可靠（支持中文），pynput.type() 对中文不可靠
        if method == "type":
            order = [_type_with_pynput, _paste_via_clipboard]
        else:
            order = [_paste_via_clipboard, _type_with_pynput]
    else:
        order = [_type_with_pynput, _paste_via_clipboard]

    for fn in order:
        if fn(payload):
            return

    logger.error("所有文本注入方式均失败: %s", payload)


def _paste_via_clipboard(payload: str) -> bool:
    """Copy to clipboard and simulate paste."""
    try:
        if _IS_MACOS:
            # 保存原剪贴板
            prev = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2).stdout
            # 写入新内容
            subprocess.run(["pbcopy"], input=payload, text=True, timeout=2, check=True)
            # 用 osascript 模拟 Cmd+V（线程安全，不依赖 RunLoop）
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
                timeout=3, check=True,
            )
            # 等粘贴完成后再恢复剪贴板
            time.sleep(0.15)
            subprocess.run(["pbcopy"], input=prev, text=True, timeout=2)
        else:
            import pyperclip
            prev = pyperclip.paste()
            pyperclip.copy(payload)
            _emit_paste()
            time.sleep(0.1)
            pyperclip.copy(prev)
        logger.info("文本已通过剪贴板注入 (%d 字符)", len(payload))
        return True
    except Exception as exc:
        logger.warning("剪贴板注入失败: %s", exc)
        return False


def _type_with_pynput(payload: str) -> bool:
    """Use pynput to type text character by character."""
    try:
        from pynput.keyboard import Controller
        kb = Controller()
        kb.type(payload)
        return True
    except Exception as exc:
        logger.warning("pynput 输入失败: %s", exc)
        return False


def _emit_paste() -> None:
    """Simulate Cmd+V (macOS) or Ctrl+V (others)."""
    from pynput.keyboard import Controller, Key
    kb = Controller()
    modifier = Key.cmd if _IS_MACOS else Key.ctrl
    with kb.pressed(modifier):
        kb.tap('v')
