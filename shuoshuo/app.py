"""主程式：系統匣圖示 + 快捷鍵口述流程。

流程：按快捷鍵 → 錄音 → 再按 → 辨識（Groq/本機）→ AI 潤飾（Groq/Gemini/Claude）→ 貼到游標處 → 存歷史。
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import APP_NAME, __version__, audio, config, hotkey, paste, polish, transcribe
from .history import History
from .ui import theme
from .ui.history_window import HistoryWindow
from .ui.meeting_window import MeetingWindow
from .ui.overlay import Overlay
from .ui.settings_dialog import SettingsDialog
from .ui.worker import run_async


def beep(kind: str) -> None:
    if sys.platform != "win32":
        return

    def _play():
        import winsound

        if kind == "start":
            winsound.Beep(880, 70)
        elif kind == "stop":
            winsound.Beep(660, 70)
        else:
            winsound.Beep(440, 150)

    threading.Thread(target=_play, daemon=True).start()


class Controller(QObject):
    toggle_requested = Signal()  # 從快捷鍵執行緒送來

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.s = config.Settings.load()
        self.history = History()
        self.overlay = Overlay()
        self.overlay.cancel_clicked.connect(self.cancel)
        self.rec = audio.Recorder(self.s.input_device)
        self.processing = False
        self._tick = QTimer(self, interval=100, timeout=self._update_overlay)
        self._windows: dict[str, object] = {}

        self.tray = QSystemTrayIcon(theme.app_icon())
        self.tray.setToolTip(f"{APP_NAME} — {hotkey.display_name(self.s.hotkey)} 開始口述")
        self.tray.activated.connect(self._tray_click)
        self._build_menu()
        self.tray.show()

        self.toggle_requested.connect(self.toggle)
        self.hk = hotkey.HotkeyListener(self.s.hotkey, self.toggle_requested.emit)
        try:
            self.hk.start()
        except Exception as e:
            QMessageBox.warning(None, APP_NAME, f"快捷鍵無法啟用：{e}")

        if not config.get_key("groq"):
            QTimer.singleShot(300, lambda: self.open_settings(welcome=True))
        else:
            self.tray.showMessage(
                APP_NAME, f"已在背景待命，按 {hotkey.display_name(self.s.hotkey)} 開始口述",
                theme.app_icon(), 3000,
            )

    # ---------- 選單 ----------
    def _build_menu(self):
        m = QMenu()
        self.act_toggle = QAction(f"開始口述（{hotkey.display_name(self.s.hotkey)}）", m)
        self.act_toggle.triggered.connect(self.toggle)
        m.addAction(self.act_toggle)
        m.addSeparator()

        style_menu = m.addMenu("潤飾風格")
        group = QActionGroup(style_menu)
        none = QAction("不潤飾（原始辨識）", style_menu, checkable=True)
        none.setChecked(not self.s.polish_enabled)
        none.triggered.connect(lambda: self._set_style(None))
        group.addAction(none)
        style_menu.addAction(none)
        style_menu.addSeparator()
        for name in polish.all_styles(self.s):
            a = QAction(name, style_menu, checkable=True)
            a.setChecked(self.s.polish_enabled and name == self.s.current_style)
            a.triggered.connect(lambda _=False, n=name: self._set_style(n))
            group.addAction(a)
            style_menu.addAction(a)

        eng_menu = m.addMenu("辨識引擎")
        eg = QActionGroup(eng_menu)
        for key, label in [("groq", "Groq 雲端"), ("local", "本機 Whisper")]:
            a = QAction(label, eng_menu, checkable=True)
            a.setChecked(self.s.engine == key)
            a.triggered.connect(lambda _=False, k=key: self._set_engine(k))
            eg.addAction(a)
            eng_menu.addAction(a)

        m.addSeparator()
        m.addAction("會議整理…", self.open_meeting)
        m.addAction("歷史紀錄…", self.open_history)
        m.addAction("設定…", self.open_settings)
        m.addSeparator()
        about = m.addAction(f"說說 v{__version__}")
        about.setEnabled(False)
        m.addAction("結束", self.quit)
        self.tray.setContextMenu(m)
        self._menu = m

    def _set_style(self, name: str | None):
        if name is None:
            self.s.polish_enabled = False
        else:
            self.s.polish_enabled = True
            self.s.current_style = name
        self.s.save()
        self.overlay.done(f"風格：{name or '不潤飾'}")

    def _set_engine(self, key: str):
        self.s.engine = key
        self.s.save()

    def _tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # 左鍵單擊
            self.toggle()

    # ---------- 視窗 ----------
    def _open(self, key: str, factory):
        w = self._windows.get(key)
        if w is None:
            w = factory()
            self._windows[key] = w
        w.show()
        w.raise_()
        w.activateWindow()

    def open_meeting(self):
        self._open("meeting", lambda: MeetingWindow(self.s, self.history))

    def open_history(self):
        self._open("history", lambda: HistoryWindow(self.s, self.history))

    def open_settings(self, welcome: bool = False):
        dlg = SettingsDialog(self.s, welcome=welcome)
        dlg.setWindowIcon(theme.app_icon())
        dlg.saved.connect(self._settings_saved)
        dlg.exec()

    def _settings_saved(self):
        self.rec.device = self.s.input_device
        try:
            self.hk.rebind(self.s.hotkey)
        except Exception as e:
            QMessageBox.warning(None, APP_NAME, f"快捷鍵無法啟用：{e}")
        self.tray.setToolTip(f"{APP_NAME} — {hotkey.display_name(self.s.hotkey)} 開始口述")
        self._build_menu()

    # ---------- 口述流程 ----------
    def toggle(self):
        if self.rec.recording:
            self.stop_and_process()
        elif self.processing:
            self.overlay.busy("還在處理上一段，請稍候…")
        else:
            self.start_recording()

    def start_recording(self):
        try:
            self.rec.start(audio.new_recording_path("rec"))
        except Exception as e:
            self.overlay.error(f"無法錄音：{e}")
            return
        if self.s.play_sounds:
            beep("start")
        self.act_toggle.setText("結束口述")
        self._tick.start()
        self._update_overlay()

    def _update_overlay(self):
        if self.rec.recording:
            self.overlay.recording(self.rec.elapsed, self.rec.level)

    def cancel(self):
        if self.rec.recording:
            path = self.rec.stop()
            self._tick.stop()
            self.act_toggle.setText(f"開始口述（{hotkey.display_name(self.s.hotkey)}）")
            if path:
                Path(path).unlink(missing_ok=True)
            self.overlay.error("已取消")

    def stop_and_process(self):
        path = self.rec.stop()
        self._tick.stop()
        self.act_toggle.setText(f"開始口述（{hotkey.display_name(self.s.hotkey)}）")
        if self.s.play_sounds:
            beep("stop")
        if not path:
            return
        duration = self.rec.duration
        if duration < 0.4:
            Path(path).unlink(missing_ok=True)
            self.overlay.error("錄音太短")
            return
        self.processing = True
        self.overlay.busy("辨識中…")
        s = self.s
        style = s.current_style if s.polish_enabled else ""

        def job(progress):
            x = audio.load_audio(path)
            raw, engine = transcribe.transcribe(x, s, progress)
            if not raw:
                return {"raw": "", "final": "", "engine": engine, "warn": "沒有聽到聲音"}
            final, warn = raw, ""
            if s.polish_enabled:
                progress("潤飾中…")
                try:
                    final = polish.polish(raw, s, style)
                except polish.PolishError as e:
                    warn = f"潤飾失敗，已貼上原文（{e}）"
            return {"raw": raw, "final": final, "engine": engine, "warn": warn}

        def done(r):
            self.processing = False
            if not r["final"]:
                self.overlay.error(r["warn"] or "沒有辨識到文字")
                Path(path).unlink(missing_ok=True)
                return
            paste.paste_text(r["final"], self.s.restore_clipboard)
            self.history.add(kind="dictation", style=style, engine=r["engine"],
                             raw=r["raw"], final=r["final"], duration=duration)
            Path(path).unlink(missing_ok=True)  # 成功就刪掉暫存錄音
            if r["warn"]:
                self.overlay.error(r["warn"])
            else:
                self.overlay.done("已貼上" + ("（本機辨識）" if r["engine"] == "local" and s.engine == "groq" else ""))

        def fail(err):
            self.processing = False
            if self.s.play_sounds:
                beep("error")
            # 失敗時保留錄音檔，可到「會議整理 → 匯入錄音檔」重試
            self.overlay.error(f"失敗：{err}（錄音已保留）")

        run_async(job, done, fail, self.overlay.busy)

    def quit(self):
        if self.rec.recording:
            self.rec.stop()
        self.hk.stop()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(theme.app_font())
    app.setStyleSheet(theme.STYLESHEET)
    app.setWindowIcon(theme.app_icon())

    lock = QLockFile(str(config.data_dir() / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "說說已經在執行中，請看右下角系統匣的圖示。")
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "找不到系統匣，無法執行。")
        return 1

    ctl = Controller(app)  # noqa: F841 — 需保留參照
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
