"""无边框圆角卡片窗口（Fluent 风格）。

外层半透明承载阴影，内部 QFrame 画圆角卡片；子类往 self.card_layout 里塞内容。
"""
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

from qfluentwidgets import isDarkTheme


class CardWindow(QWidget):
    def __init__(self, width=640, height=720, radius=14, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(width, height)
        self._radius = radius
        self._drag_pos = None

        dark = isDarkTheme()
        bg = "#2b2b2b" if dark else "#ffffff"
        border = "#3a3a3a" if dark else "#e3e6ec"

        self.card = QFrame(self)
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            f"#card {{ background: {bg}; border: 1px solid {border};"
            f" border-radius: {radius}px; }}"
        )
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 60 if not dark else 120))
        self.card.setGraphicsEffect(shadow)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(24, 20, 24, 20)
        self.card_layout.setSpacing(12)

        self._layout_outer = QVBoxLayout(self)
        self._layout_outer.setContentsMargins(16, 16, 16, 0)
        self._layout_outer.addWidget(self.card)
        # 卡片铺满窗口，会挡住父窗口的鼠标事件：把拖动逻辑装到卡片上
        self.card.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.card:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self._drag_pos is not None:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                return True
            if event.type() == QEvent.MouseButtonRelease:
                self._drag_pos = None
                return True
        return super().eventFilter(obj, event)

    def center_on_screen(self):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def show_animated(self, center=True):
        """淡入 + 上浮的弹出动画。

        纯窗口属性动画（pos / windowOpacity），不依赖 KWin 的窗口打开特效，
        所以 XWayland(xcb) 和 Windows 上表现一致。
        """
        if center:
            self.center_on_screen()
        target = self.pos()

        self.setWindowOpacity(0.0)
        self.move(target + QPoint(0, 14))
        self.show()

        self._anim_pos = QPropertyAnimation(self, b"pos", self)
        self._anim_pos.setDuration(200)
        self._anim_pos.setStartValue(target + QPoint(0, 14))
        self._anim_pos.setEndValue(target)
        self._anim_pos.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_opacity = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_opacity.setDuration(170)
        self._anim_opacity.setStartValue(0.0)
        self._anim_opacity.setEndValue(1.0)
        self._anim_opacity.setEasingCurve(QEasingCurve.OutCubic)

        self._anim = QParallelAnimationGroup(self)
        self._anim.addAnimation(self._anim_pos)
        self._anim.addAnimation(self._anim_opacity)
        self._anim.finished.connect(lambda: self.setWindowOpacity(1.0))
        self._anim.start()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
