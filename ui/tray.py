"""系统托盘：右键菜单可显示/隐藏悬浮窗，也可退出程序。"""
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSystemTrayIcon

from qfluentwidgets import Action, FluentIcon, RoundMenu

from .theme import BRAND


def _make_icon(size: int = 64) -> QIcon:
    """品牌色圆角底 + 白色人像，托盘小尺寸下也能看清。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(BRAND))
    painter.drawRoundedRect(0, 0, size, size, size * 0.28, size * 0.28)
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(QPointF(size * 0.5, size * 0.37), size * 0.13, size * 0.13)
    painter.drawRoundedRect(
        QRectF(size * 0.27, size * 0.55, size * 0.46, size * 0.27),
        size * 0.13, size * 0.13,
    )
    painter.end()
    return QIcon(pm)


class TrayIcon(QObject):
    toggleRequested = Signal()
    quitRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray = QSystemTrayIcon(_make_icon(), parent)
        self.tray.setToolTip("ClassBoard · 随机点名")

        self.menu = RoundMenu()
        self.act_toggle = Action(FluentIcon.VIEW, "隐藏悬浮窗")
        self.act_toggle.triggered.connect(lambda: self.toggleRequested.emit())
        self.menu.addAction(self.act_toggle)
        self.menu.addSeparator()
        self.act_quit = Action(FluentIcon.CLOSE, "退出 ClassBoard")
        self.act_quit.triggered.connect(lambda: self.quitRequested.emit())
        self.menu.addAction(self.act_quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:      # 左键单击托盘图标
            self.toggleRequested.emit()

    def set_ball_visible(self, visible: bool):
        self.act_toggle.setText("隐藏悬浮窗" if visible else "显示悬浮窗")

    def show(self):
        self.tray.show()

    def hide(self):
        self.tray.hide()
