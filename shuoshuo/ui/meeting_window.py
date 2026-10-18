"""會議整理：現場錄音／匯入錄音檔／帶入口述 → 逐字稿 → 會議紀錄。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import audio, config, polish, transcribe
from ..export import markdown_to_docx
from ..history import History
from . import theme
from .worker import run_async

AUDIO_FILTER = "錄音檔 (*.wav *.mp3 *.m4a *.mp4 *.aac *.flac *.ogg *.wma *.webm);;所有檔案 (*.*)"


class MeetingWindow(QWidget):
    def __init__(self, settings: config.Settings, history: History):
        super().__init__()
        self.s = settings
        self.h = history
        self.rec = audio.Recorder()
        self.audio_path = ""
        self.duration = 0.0
        self.engine = ""
        self.minutes_md = ""
        self.busy = False
        self.setWindowTitle("說說 — 會議整理")
        self.setWindowIcon(theme.app_icon())
        self.resize(900, 680)

        root = QVBoxLayout(self)
        title = QLabel("① 取得逐字稿")
        title.setObjectName("h1")
        root.addWidget(title)
        src = QHBoxLayout()
        self.rec_btn = QPushButton("● 開始錄音")
        self.rec_btn.setObjectName("record")
        self.rec_btn.clicked.connect(self._toggle_record)
        imp = QPushButton("匯入錄音檔…")
        imp.clicked.connect(self._import)
        recent = QPushButton("帶入最近的口述")
        recent.clicked.connect(self._load_recent)
        self.imp_btn, self.recent_btn = imp, recent
        self.rec_label = QLabel()
        src.addWidget(self.rec_btn)
        src.addWidget(imp)
        src.addWidget(recent)
        src.addWidget(self.rec_label, 1)
        root.addLayout(src)

        split = QSplitter()
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("逐字稿（可直接修改，也可貼上）"))
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText("錄音或匯入後，辨識結果會出現在這裡。")
        lv.addWidget(self.transcript, 1)
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("補充說明（選填）：例如 115學年度第1次課發會，主席王校長")
        lv.addWidget(self.extra)
        title2 = QLabel("② 產生會議紀錄")
        title2.setObjectName("h1")
        lv.addWidget(title2)
        self.gen_btn = QPushButton("產生會議紀錄")
        self.gen_btn.setObjectName("primary")
        self.gen_btn.clicked.connect(self._generate)
        lv.addWidget(self.gen_btn)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.out_tabs = QTabWidget()
        self.preview = QTextBrowser()
        self.md_edit = QPlainTextEdit()
        self.md_edit.textChanged.connect(self._md_changed)
        self.out_tabs.addTab(self.preview, "預覽")
        self.out_tabs.addTab(self.md_edit, "編輯")
        rv.addWidget(self.out_tabs, 1)
        row = QHBoxLayout()
        cp = QPushButton("複製")
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.md_edit.toPlainText()))
        docx = QPushButton("另存 Word")
        docx.clicked.connect(self._save_docx)
        md = QPushButton("另存文字檔")
        md.clicked.connect(self._save_md)
        row.addWidget(cp)
        row.addWidget(docx)
        row.addWidget(md)
        row.addStretch()
        rv.addLayout(row)
        split.addWidget(right)
        split.setSizes([430, 470])
        root.addWidget(split, 1)

        self.status = QLabel()
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        self._tick = QTimer(self, interval=500, timeout=self._update_rec)

    # ---------- 錄音 ----------
    def _toggle_record(self):
        if self.rec.recording:
            path = self.rec.stop()
            self._tick.stop()
            self.rec_btn.setText("● 開始錄音")
            self.duration = self.rec.duration
            self.rec_label.setText(f"錄音已存：{path.name}")
            self._transcribe_file(str(path))
        else:
            if self.busy:
                return
            if self.transcript.toPlainText().strip() and QMessageBox.question(
                self, "說說", "開始新錄音會取代目前的逐字稿，確定嗎？"
            ) != QMessageBox.Yes:
                return
            self.rec.device = self.s.input_device
            try:
                self.rec.start(audio.new_recording_path("meeting"))
            except Exception as e:
                QMessageBox.warning(self, "說說", f"無法開始錄音：{e}")
                return
            self.rec_btn.setText("■ 結束錄音")
            self.imp_btn.setEnabled(False)
            self.recent_btn.setEnabled(False)
            self._tick.start()

    def _update_rec(self):
        sec = int(self.rec.elapsed)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        bars = "▮" * int(self.rec.level * 10)
        self.rec_label.setText(f"錄音中 {h:02d}:{m:02d}:{s:02d}　{bars}")

    def closeEvent(self, e):
        if self.rec.recording:
            if QMessageBox.question(self, "說說", "還在錄音，要結束錄音並關閉嗎？（錄音檔會保留）") != QMessageBox.Yes:
                e.ignore()
                return
            self.rec.stop()
            self._tick.stop()
            self.rec_btn.setText("● 開始錄音")
        super().closeEvent(e)

    # ---------- 匯入 ----------
    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇錄音檔", "", AUDIO_FILTER)
        if path:
            self.rec_label.setText(Path(path).name)
            self._transcribe_file(path)

    def _load_recent(self):
        items = list(reversed(self.h.recent_dictations(20)))
        if not items:
            self.status.setText("還沒有口述紀錄。")
            return
        text = "\n".join(e.final or e.raw for e in items)
        self.transcript.setPlainText(text)
        self.audio_path, self.engine, self.duration = "", "", sum(e.duration for e in items)
        self.status.setText(f"已帶入最近 {len(items)} 則口述，可刪改後產生會議紀錄。")

    def _set_busy(self, on: bool):
        self.busy = on
        for b in (self.imp_btn, self.recent_btn, self.gen_btn):
            b.setEnabled(not on)
        self.rec_btn.setEnabled(not on)

    def _transcribe_file(self, path: str):
        self._set_busy(True)
        self.audio_path = path
        self.status.setText("讀取錄音檔…")

        def job(progress):
            x = audio.load_audio(path)
            self.duration = len(x) / audio.SAMPLE_RATE
            mins = self.duration / 60
            progress(f"辨識中（共 {mins:.0f} 分鐘）…")
            return transcribe.transcribe(x, self.s, progress)

        def done(result):
            text, engine = result
            self.engine = engine
            self._set_busy(False)
            if not text:
                self.status.setText("沒有辨識到語音，請確認錄音內容或麥克風。")
                return
            # 長錄音一句一行比較好讀
            self.transcript.setPlainText(text.replace("。", "。\n").replace("\n\n", "\n"))
            self.status.setText(f"辨識完成（{len(text)} 字）。可先修正逐字稿，再按「產生會議紀錄」。")

        def fail(err):
            self._set_busy(False)
            self.status.setText(f"辨識失敗：{err}")

        run_async(job, done, fail, self.status.setText)

    # ---------- 會議紀錄 ----------
    def _generate(self):
        text = self.transcript.toPlainText().strip()
        if not text:
            self.status.setText("請先錄音、匯入或貼上逐字稿。")
            return
        self._set_busy(True)
        self.status.setText("Claude 整理會議紀錄中，長會議約需 1 分鐘…")

        def done(md):
            self._set_busy(False)
            self.minutes_md = md
            self.md_edit.setPlainText(md)
            self.out_tabs.setCurrentIndex(0)
            self.h.add(kind="meeting", style="會議紀錄", engine=self.engine, raw=text,
                       final=md, duration=self.duration, audio_path=self.audio_path)
            self.status.setText("完成，已存入歷史紀錄。")

        def fail(err):
            self._set_busy(False)
            self.status.setText(f"整理失敗：{err}")

        run_async(lambda _p: polish.meeting_minutes(text, self.s, self.extra.text()), done, fail)

    def _md_changed(self):
        self.preview.setMarkdown(self.md_edit.toPlainText())

    def _default_name(self, ext: str) -> str:
        first = self.md_edit.toPlainText().strip().splitlines()[:1]
        name = first[0].lstrip("# ").replace("會議紀錄：", "").strip() if first else "會議紀錄"
        safe = "".join(c for c in name if c not in '\\/:*?"<>|')[:40] or "會議紀錄"
        return str(Path.home() / "Documents" / f"{safe}{ext}")

    def _save_docx(self):
        if not self.md_edit.toPlainText().strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, "另存 Word", self._default_name(".docx"), "Word (*.docx)")
        if path:
            try:
                markdown_to_docx(self.md_edit.toPlainText(), path)
                self.status.setText(f"已存：{path}")
            except Exception as e:
                QMessageBox.warning(self, "說說", f"存檔失敗：{e}")

    def _save_md(self):
        if not self.md_edit.toPlainText().strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, "另存文字檔", self._default_name(".md"),
                                              "Markdown (*.md);;純文字 (*.txt)")
        if path:
            Path(path).write_text(self.md_edit.toPlainText(), encoding="utf-8")
            self.status.setText(f"已存：{path}")
