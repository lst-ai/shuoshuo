"""在背景執行緒跑耗時工作，結果透過 Qt 訊號回到主執行緒。"""
from __future__ import annotations

import threading
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

_alive: set["Worker"] = set()


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)


def run_async(
    fn: Callable[[Callable[[str], None]], Any],
    done: Callable[[Any], None],
    fail: Callable[[str], None],
    progress: Callable[[str], None] | None = None,
) -> None:
    """fn 會收到一個 progress(msg) 函式。"""
    w = Worker()
    _alive.add(w)
    w.finished.connect(done)
    w.failed.connect(fail)
    if progress:
        w.progress.connect(progress)

    def cleanup(*_):
        _alive.discard(w)

    w.finished.connect(cleanup)
    w.failed.connect(cleanup)

    def target():
        try:
            result = fn(w.progress.emit)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            w.failed.emit(str(e) or e.__class__.__name__)
        else:
            w.finished.emit(result)

    threading.Thread(target=target, daemon=True).start()
