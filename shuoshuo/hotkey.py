"""全域快捷鍵（按一下切換錄音）。"""
from __future__ import annotations

from typing import Callable


class HotkeyListener:
    def __init__(self, combo: str, on_trigger: Callable[[], None]):
        self.combo = combo
        self.on_trigger = on_trigger
        self._listener = None

    def start(self) -> None:
        from pynput import keyboard

        self.stop()
        self._listener = keyboard.GlobalHotKeys({self.combo: self.on_trigger})
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def rebind(self, combo: str) -> None:
        self.combo = combo
        self.start()


def validate_combo(combo: str) -> bool:
    try:
        from pynput import keyboard

        keyboard.HotKey.parse(combo)
        return True
    except Exception:
        return False


# 給設定畫面用：顯示名稱 → pynput 格式
PRESETS = {
    "Ctrl + Alt + 空白鍵": "<ctrl>+<alt>+<space>",
    "Ctrl + Shift + 空白鍵": "<ctrl>+<shift>+<space>",
    "F9": "<f9>",
    "F10": "<f10>",
    "Ctrl + Alt + S": "<ctrl>+<alt>+s",
    "右 Alt + 空白鍵": "<alt_gr>+<space>",
}


def display_name(combo: str) -> str:
    for k, v in PRESETS.items():
        if v == combo:
            return k
    return combo
