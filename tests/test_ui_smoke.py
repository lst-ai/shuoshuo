"""在無螢幕環境建立每個視窗，確認沒有程式錯誤。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")


def test_windows_build(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from shuoshuo import config
    from shuoshuo.history import History
    from shuoshuo.ui import theme
    from shuoshuo.ui.history_window import HistoryWindow
    from shuoshuo.ui.meeting_window import MeetingWindow
    from shuoshuo.ui.overlay import Overlay
    from shuoshuo.ui.settings_dialog import SettingsDialog

    s = config.Settings()
    h = History(tmp_path / "h.db")
    h.add(raw="原文", final="潤飾", style="日常", duration=2)

    hw = HistoryWindow(s, h)
    hw.show()
    assert hw.table.rowCount() == 1

    mw = MeetingWindow(s, h)
    mw.show()
    mw.md_edit.setPlainText("# 會議紀錄：測試\n- 一")
    assert "測試" in mw.preview.toPlainText()
    mw._load_recent()
    assert "潤飾" in mw.transcript.toPlainText()

    dlg = SettingsDialog(s, welcome=True)
    dlg.vocab.setPlainText("雲林縣\n\n方舟計畫")
    dlg.repl.setPlainText("雲林線 = 雲林縣")
    out = dlg._collect()
    assert out.vocabulary == ["雲林縣", "方舟計畫"]
    assert out.replacements == {"雲林線": "雲林縣"}
    assert s.vocabulary == []  # 取消時不影響原設定

    ov = Overlay()
    ov.recording(65, 0.5)
    assert "01:05" in ov.label.text()
    ov.busy("辨識中…")
    ov.done()
    assert not theme.draw_icon().isNull()

    # 測試結束前依序關閉並釋放視窗，避免程式結束時 Qt 物件釋放順序錯亂而當掉
    for w in (hw, mw, dlg, ov):
        w.close()
        w.deleteLater()
    app.processEvents()
    h._db.close()
