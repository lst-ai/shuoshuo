"""把文字貼到目前游標所在處：放進剪貼簿 → 送出 Ctrl+V → 還原剪貼簿。

必須在 Qt 主執行緒呼叫。
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication


def _send_ctrl_v() -> None:
    from pynput.keyboard import Controller, Key

    kb = Controller()
    # 先放開可能還按著的修飾鍵（快捷鍵剛按完時）
    for k in (Key.alt, Key.alt_l, Key.alt_r, Key.shift, Key.ctrl_r):
        try:
            kb.release(k)
        except Exception:
            pass
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")


def paste_text(text: str, restore: bool = True) -> None:
    cb = QGuiApplication.clipboard()
    old = cb.text() if restore else None
    cb.setText(text)

    def do_paste():
        _send_ctrl_v()
        if restore and old is not None:
            QTimer.singleShot(800, lambda: cb.setText(old))

    QTimer.singleShot(80, do_paste)
