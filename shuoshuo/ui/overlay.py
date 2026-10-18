"""螢幕下方的小提示條：錄音中／辨識中／已貼上。

設定為「不搶焦點」，這樣文字才會貼回原本的視窗。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from . import theme


class LevelBar(QWidget):
    def __init__(self):
        super().__init__()
        self.level = 0.0
        self.setFixedSize(46, 18)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bars = 5
        w = self.width() / bars
        for i in range(bars):
            on = self.level * bars > i
            h = 4 + (self.height() - 4) * (0.4 + 0.6 * ((i % 3) / 2))
            p.setBrush(QColor("white" if on else "#ffffff55"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(i * w + 2, (self.height() - h) / 2, w - 4, h), 2, 2)


class Overlay(QWidget):
    cancel_clicked = Signal()

    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._color = theme.RECORD
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 10, 8)
        lay.setSpacing(10)
        self.level = LevelBar()
        self.label = QLabel()
        self.label.setStyleSheet("color: white; font-weight: 600;")
        self.cancel = QPushButton("✕")
        self.cancel.setFixedSize(24, 24)
        self.cancel.setCursor(Qt.PointingHandCursor)
        self.cancel.setToolTip("取消這次錄音")
        self.cancel.setStyleSheet(
            "QPushButton{color:white;background:#ffffff33;border:none;border-radius:12px;padding:0}"
            "QPushButton:hover{background:#ffffff66}"
        )
        self.cancel.clicked.connect(self.cancel_clicked)
        lay.addWidget(self.level)
        lay.addWidget(self.label)
        lay.addWidget(self.cancel)
        self._hide_timer = QTimer(self, singleShot=True, timeout=self.hide)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        r = self.rect().adjusted(1, 1, -1, -1)
        p.drawRoundedRect(QRectF(r), r.height() / 2, r.height() / 2)

    def _place(self):
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - 40)

    def _show(self, color: str, text: str, level: bool, cancel: bool, auto_hide_ms: int = 0):
        self._hide_timer.stop()
        self._color = color
        self.label.setText(text)
        self.level.setVisible(level)
        self.cancel.setVisible(cancel)
        self._place()
        self.show()
        self.raise_()
        self.update()
        if auto_hide_ms:
            self._hide_timer.start(auto_hide_ms)

    # ---- 對外 ----
    def recording(self, seconds: float, level: float):
        m, s = divmod(int(seconds), 60)
        self.level.level = level
        self.level.update()
        if self.isVisible() and self._color == theme.RECORD:
            self.label.setText(f"錄音中 {m:02d}:{s:02d}　再按一次結束")
            return
        self._show(theme.RECORD, f"錄音中 {m:02d}:{s:02d}　再按一次結束", True, True)

    def busy(self, text: str):
        self._show(theme.BUSY, text, False, False)

    def done(self, text: str = "已貼上"):
        self._show(theme.OK, text, False, False, 1300)

    def error(self, text: str):
        self._show(theme.WARN, text, False, False, 5000)
