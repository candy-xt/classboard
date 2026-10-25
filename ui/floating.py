"""右下角悬浮球：图标 + "随机点名"，会话进行中变为"继续点名..."。"""
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMenu, QWidget

from qfluentwidgets import BodyLabel, FluentIcon, IconWidget


def _is_wayland() -> bool:
    """运行时判断：必须在 QApplication 创建之后调用，导入时为 False。"""
    try:
        return QGuiApplication.platformName().startswith("wayland")
    except Exception:
        return False


class FloatingButton(QWidget):
    clicked = Signal()
    quitRequested = Signal()
    moved = Signal(int, int)      # 拖动结束时发出，用于记住位置

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(42)
        self._hover = False
        self._pressed = False
        self._drag_offset = None
        self._press_pos = None
        self._dragged = False
        self._system_moving = False
        self._user_moved = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 18, 0)
        layout.setSpacing(8)
        self.icon = IconWidget()
        self.icon.setIcon(FluentIcon.PEOPLE)
        self.icon.setFixedSize(18, 18)
        self.label = BodyLabel("随机点名")
        # 图标和文字不接收鼠标事件，事件直接落到外层，才能拖动和点击
        self.icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon)
        layout.addWidget(self.label)

        # 拖动逻辑装在自己身上：按下/移动/释放都能收到
        self.setMouseTracking(True)
        self.installEventFilter(self)

        # 定期把自己提到最前，避免被别的窗口盖住
        self._keep_top = QTimer(self)
        self._keep_top.setInterval(1000)
        self._keep_top.timeout.connect(self._raise_self)
        self._keep_top.start()

    def _raise_self(self):
        try:
            self.raise_()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._raise_self()

    def eventFilter(self, obj, event):
        if obj is self:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._pressed = True
                self._dragged = False
                self._system_moving = False
                self._press_pos = event.globalPosition().toPoint()
                self._drag_offset = (event.globalPosition().toPoint()
                                     - self.frameGeometry().topLeft())
                return True
            if event.type() == QEvent.MouseMove and self._pressed:
                pos = event.globalPosition().toPoint()
                if (pos - self._press_pos).manhattanLength() > 6 and not self._dragged:
                    self._dragged = True
                    self._user_moved = True
                    # Wayland 下程序不能自己移动窗口，必须交给合成器拖；
                    # X11 / Windows 则直接自己 move，更跟手。
                    if _is_wayland():
                        handle = self.windowHandle()
                        if handle is not None and handle.startSystemMove():
                            self._system_moving = True
                if not self._system_moving:
                    self.move(pos - self._drag_offset)
                return True
            if event.type() == QEvent.MouseButtonRelease and self._pressed:
                was_pressed = self._pressed
                was_dragged = self._dragged
                self._pressed = False
                self._system_moving = False
                self._drag_offset = None
                if was_dragged:
                    # 拖完记住位置，下次启动直接回到这里
                    self.moved.emit(self.x(), self.y())
                elif was_pressed:
                    self.clicked.emit()
                return True
        return super().eventFilter(obj, event)

    # ---- 外观 ----
    def set_text(self, text: str):
        self.label.setText(text)
        self.adjustSize()
        # 用户拖过就保持原位，别再弹回右下角
        if not self._user_moved:
            self.move_to_bottom_right()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 21, 21)
        fill = QColor(255, 255, 255, 245 if not self._hover else 255)
        painter.fillPath(path, fill)
        painter.setPen(QColor(0, 0, 0, 30))
        painter.drawPath(path)
        painter.end()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = menu.addAction("退出 ClassBoard")
        action.triggered.connect(lambda: self.quitRequested.emit())
        menu.exec(event.globalPos())

    # ---- 位置 ----
    def move_to_bottom_right(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.adjustSize()
        self.move(
            area.right() - self.width() - 24,
            area.bottom() - self.height() - 24,
        )

    def restore_position(self, x: int, y: int) -> bool:
        """恢复到上次的位置；越界（换了分辨率）则退回默认位置。"""
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return False
        area = screen.availableGeometry()
        if not (area.left() - 50 <= x <= area.right() and
                area.top() - 50 <= y <= area.bottom()):
            return False
        self._user_moved = True
        self.move(x, y)
        return True
