"""共用外觀：字型、顏色、圖示。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

ACCENT = "#E8673C"     # 主色：暖橘
RECORD = "#E5484D"
BUSY = "#3E7BFA"
OK = "#2F9E62"
WARN = "#D9822B"

STYLESHEET = f"""
QWidget {{ font-size: 10.5pt; }}
QPushButton {{ padding: 6px 14px; border-radius: 6px; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #D45A31; }}
QPushButton#primary:disabled {{ background: #E9B9A6; }}
QPushButton#record {{ background: {RECORD}; color: white; border: none; font-weight: 600; }}
QLabel#hint {{ color: #777; }}
QLabel#h1 {{ font-size: 13pt; font-weight: 700; }}
"""


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / rel


def app_font() -> QFont:
    f = QFont("Microsoft JhengHei UI")
    f.setPointSizeF(10.5)
    return f


def draw_icon(color: str = ACCENT, size: int = 64) -> QIcon:
    """畫一個麥克風圖示（不依賴圖檔）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    s = size / 64
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(24 * s, 12 * s, 16 * s, 26 * s), 8 * s, 8 * s)
    pen = QPen(QColor("white"), 4 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(QPointF(18 * s, 30 * s))
    path.cubicTo(QPointF(18 * s, 46 * s), QPointF(46 * s, 46 * s), QPointF(46 * s, 30 * s))
    p.drawPath(path)
    p.drawLine(QPointF(32 * s, 44 * s), QPointF(32 * s, 52 * s))
    p.end()
    return QIcon(pm)


def app_icon() -> QIcon:
    ico = resource_path("assets/icon.ico")
    if ico.exists():
        return QIcon(str(ico))
    return draw_icon()
