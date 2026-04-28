"""Global hotkey management using pynput (macOS-safe replacement for keyboard lib)."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from pynput import keyboard


logger = logging.getLogger(__name__)

# Map config key names to pynput Key attributes
_SPECIAL_KEYS = {f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 21)}
_SPECIAL_KEYS.update({
    "esc": keyboard.Key.esc, "escape": keyboard.Key.esc,
    "space": keyboard.Key.space, "tab": keyboard.Key.tab,
    "enter": keyboard.Key.enter, "return": keyboard.Key.enter,
    "backspace": keyboard.Key.backspace, "delete": keyboard.Key.delete,
    "home": keyboard.Key.home, "end": keyboard.Key.end,
    "ctrl": keyboard.Key.ctrl, "ctrl_l": keyboard.Key.ctrl_l, "ctrl_r": keyboard.Key.ctrl_r,
    "alt": keyboard.Key.alt, "alt_l": keyboard.Key.alt_l, "alt_r": keyboard.Key.alt_r,
    "opt": keyboard.Key.alt, "opt_l": keyboard.Key.alt_l, "opt_r": keyboard.Key.alt_r,
    "option": keyboard.Key.alt, "option_l": keyboard.Key.alt_l, "option_r": keyboard.Key.alt_r,
    "shift": keyboard.Key.shift, "shift_l": keyboard.Key.shift_l, "shift_r": keyboard.Key.shift_r,
    "cmd": keyboard.Key.cmd, "cmd_l": keyboard.Key.cmd_l, "cmd_r": keyboard.Key.cmd_r,
})

# Modifier keys for combo detection
_MODIFIER_NAMES = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r",
                   "opt", "opt_l", "opt_r", "option", "option_l", "option_r",
                   "shift", "shift_l", "shift_r", "cmd", "cmd_l", "cmd_r"}


def _parse_combo(combo: str):
    """Parse a hotkey string like 'f2' or 'ctrl+shift+a' into (frozenset of modifier Keys, trigger key).

    A single modifier key (e.g. 'alt_r') is treated as the trigger with no extra modifiers.
    """
    parts = [p.strip().lower() for p in combo.split("+")]
    modifiers = set()
    trigger = None
    for part in parts:
        if part in _MODIFIER_NAMES:
            modifiers.add(_SPECIAL_KEYS[part])
        elif part in _SPECIAL_KEYS:
            trigger = _SPECIAL_KEYS[part]
        elif len(part) == 1:
            trigger = keyboard.KeyCode.from_char(part)
        else:
            raise ValueError(f"Unknown key: {part}")
    # Single modifier key (e.g. "alt_r") → use it as trigger, no modifiers required
    # Multi-modifier with no trigger (e.g. "cmd+alt_r") → last one is trigger, rest are modifiers
    if trigger is None and modifiers:
        last_key = _SPECIAL_KEYS[parts[-1]]
        modifiers.discard(last_key)
        trigger = last_key
    if trigger is None:
        raise ValueError(f"No trigger key found in combo: {combo}")
    return frozenset(modifiers), trigger


class HotkeyManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._combos: dict[str, tuple] = {}  # combo_str -> (modifiers, trigger, callback)
        self._pressed_modifiers: set = set()
        self._listener: Optional[keyboard.Listener] = None
        self._stop_event = threading.Event()

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        modifiers, trigger = _parse_combo(combo)
        with self._lock:
            self._combos[combo] = (modifiers, trigger, callback)
            logger.info("已注册热键 %s", combo)
            # Start listener on first registration
            if self._listener is None:
                self._listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release,
                )
                self._listener.daemon = True
                self._listener.start()

    def _on_press(self, key):
        # Track modifier state
        canonical = self._listener.canonical(key) if self._listener else key
        if canonical in _SPECIAL_KEYS.values() and any(canonical == _SPECIAL_KEYS.get(m) for m in _MODIFIER_NAMES):
            self._pressed_modifiers.add(canonical)

        # Check registered combos
        with self._lock:
            for combo_str, (modifiers, trigger, callback) in self._combos.items():
                if self._key_matches(key, trigger) and modifiers.issubset(self._pressed_modifiers):
                    try:
                        callback()
                    except Exception as exc:
                        logger.error("热键 %s 回调出错: %s", combo_str, exc)

    def _on_release(self, key):
        canonical = self._listener.canonical(key) if self._listener else key
        self._pressed_modifiers.discard(canonical)

    @staticmethod
    def _key_matches(pressed, target) -> bool:
        """Check if pressed key matches target, handling Key, KeyCode, and canonical forms."""
        if pressed == target:
            return True
        if hasattr(pressed, "char") and hasattr(target, "char"):
            return pressed.char == target.char
        return False

    def wait(self) -> None:
        """Block until cleanup is called. Replaces keyboard.wait()."""
        self._stop_event.wait()

    def unregister_all(self) -> None:
        with self._lock:
            self._combos.clear()
            logger.info("已移除所有热键")

    def cleanup(self) -> None:
        self.unregister_all()
        self._stop_event.set()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("已停止热键监听")
