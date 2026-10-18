"""歷史紀錄視窗：搜尋、複製、換風格重新潤飾、刪除。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import config, polish
from ..history import Entry, History
from . import theme
from .worker import run_async


class HistoryWindow(QWidget):
    def __init__(self, settings: config.Settings, history: History):
        super().__init__()
        self.s = settings
        self.h = history
        self.entries: list[Entry] = []
        self.setWindowTitle("說說 — 歷史紀錄")
        self.setWindowIcon(theme.app_icon())
        self.resize(820, 560)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋內容…")
        self.search.textChanged.connect(self.reload)
        self.kind = QComboBox()
        self.kind.addItem("全部", None)
        self.kind.addItem("口述", "dictation")
        self.kind.addItem("會議", "meeting")
        self.kind.currentIndexChanged.connect(self.reload)
        clear = QPushButton("全部清除")
        clear.clicked.connect(self._clear)
        top.addWidget(self.search, 1)
        top.addWidget(self.kind)
        top.addWidget(clear)
        root.addLayout(top)

        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["時間", "風格", "內容"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._show_selected)
        split.addWidget(self.table)

        detail = QWidget()
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(0, 0, 0, 0)
        self.show_raw = QCheckBox("顯示原始辨識文字")
        self.show_raw.toggled.connect(self._show_selected)
        self.meta = QLabel()
        self.meta.setObjectName("hint")
        hm = QHBoxLayout()
        hm.addWidget(self.meta, 1)
        hm.addWidget(self.show_raw)
        dv.addLayout(hm)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        dv.addWidget(self.text, 1)
        row = QHBoxLayout()
        copy = QPushButton("複製")
        copy.setObjectName("primary")
        copy.clicked.connect(self._copy)
        self.restyle = QComboBox()
        rp = QPushButton("用此風格重新潤飾")
        rp.clicked.connect(self._repolish)
        rm = QPushButton("刪除")
        rm.clicked.connect(self._delete)
        self.status = QLabel()
        self.status.setObjectName("hint")
        row.addWidget(copy)
        row.addSpacing(12)
        row.addWidget(self.restyle)
        row.addWidget(rp)
        row.addStretch()
        row.addWidget(self.status)
        row.addWidget(rm)
        dv.addLayout(row)
        split.addWidget(detail)
        split.setSizes([300, 260])
        root.addWidget(split, 1)

    def showEvent(self, e):
        self.restyle.clear()
        self.restyle.addItems(list(polish.all_styles(self.s)))
        self.reload()
        super().showEvent(e)

    def reload(self):
        self.entries = self.h.search(self.search.text().strip(), self.kind.currentData())
        self.table.setRowCount(len(self.entries))
        for r, e in enumerate(self.entries):
            preview = (e.final or e.raw).replace("\n", " ")[:80]
            style = "會議" if e.kind == "meeting" else (e.style or "原文")
            for c, val in enumerate([e.created[5:16], style, preview]):
                self.table.setItem(r, c, QTableWidgetItem(val))
        if self.entries:
            self.table.selectRow(0)
        else:
            self.text.clear()
            self.meta.clear()

    def _current(self) -> Entry | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        i = rows[0].row()
        return self.entries[i] if i < len(self.entries) else None

    def _show_selected(self):
        e = self._current()
        if not e:
            return
        self.text.setPlainText(e.raw if self.show_raw.isChecked() else (e.final or e.raw))
        eng = {"groq": "Groq 雲端", "gemini": "Gemini 雲端", "local": "本機"}.get(e.engine, e.engine)
        self.meta.setText(f"{e.created}　{eng}　{e.duration:.0f} 秒")

    def _copy(self):
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.status.setText("已複製")

    def _repolish(self):
        e = self._current()
        if not e or not e.raw:
            return
        style = self.restyle.currentText()
        self.status.setText("潤飾中…")

        def done(text):
            self.h.add(kind="dictation", style=style, engine=e.engine, raw=e.raw,
                       final=text, duration=e.duration)
            self.status.setText("已產生新版本（在最上面）")
            self.reload()

        run_async(lambda _p: polish.polish(e.raw, self.s, style), done,
                  lambda err: self.status.setText(f"失敗：{err}"))

    def _delete(self):
        e = self._current()
        if e:
            self.h.delete(e.id)
            self.reload()

    def _clear(self):
        if QMessageBox.question(self, "說說", "確定清除所有歷史紀錄？無法復原。") == QMessageBox.Yes:
            self.h.clear()
            self.reload()
