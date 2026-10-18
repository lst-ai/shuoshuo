"""PyInstaller 進入點，也可直接 python run.py 執行。"""
import sys


def _setup_log():
    # 打包成無主控台的 exe 時 sys.stdout / sys.stderr 是 None，
    # 任何 print、錯誤追蹤或下載進度條都會讓背景工作當掉。改寫到記錄檔。
    if sys.stderr is not None and sys.stdout is not None:
        return
    from shuoshuo.config import data_dir

    log = open(data_dir() / "shuoshuo.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


_setup_log()

from shuoshuo.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
