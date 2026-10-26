"""抽取界面：左侧老虎机滚动，右侧已抽取列表，底部三个按钮。"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

from .card import CardWindow
from .reel import ReelWidget

# 底部按钮配色（Fluent 的 PushButton 是 QPushButton 子类，直接覆盖样式表即可）
_RED_BTN = """
PushButton {
    background-color: #d13438; color: #ffffff;
    border: 1px solid #c22b2f; border-radius: 5px; padding: 5px 16px;
}
PushButton:hover { background-color: #e04448; }
PushButton:pressed { background-color: #a82226; }
PushButton:disabled { background-color: #e2a1a3; color: #f7f7f7; border-color: #e2a1a3; }
"""

_BLUE_BTN = """
PushButton {
    background-color: #0f62fe; color: #ffffff;
    border: 1px solid #0b57e0; border-radius: 5px; padding: 5px 16px;
}
PushButton:hover { background-color: #2f78ff; }
PushButton:pressed { background-color: #0a4fd0; }
PushButton:disabled { background-color: #a3c0ff; color: #f7f7f7; border-color: #a3c0ff; }
"""


class DrawnCard(QFrame):
    """右侧已抽取卡片：姓名 + 学号。"""

    def __init__(self, student, parent=None):
        super().__init__(parent)
        self.setObjectName("drawnCard")
        self.setStyleSheet(
            "#drawnCard { background: #f2f6fc; border: 1px solid #dbe6f7;"
            " border-radius: 10px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        self.name = StrongBodyLabel(student.name)
        self.no = CaptionLabel(f"学号 {student.student_no}")
        layout.addWidget(self.name)
        layout.addWidget(self.no)


class DrawWindow(CardWindow):
    drawn = Signal(object)         # 抽中的人
    rollRequested = Signal()       # 点击"开始抽选"
    finished = Signal()            # 结束本次抽取
    leaveRequested = Signal()      # 暂离
    editRequested = Signal()       # 修改配置

    def __init__(self, class_name, parent=None):
        super().__init__(width=820, height=520, parent=parent)
        self.class_name = class_name
        self._cards = []
        self._snapshot = []
        self._pending = None
        self._chaining = False

        title = TitleLabel("随机点名")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.subtitle = SubtitleLabel(class_name)
        self.subtitle.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.card_layout.addWidget(title)
        self.card_layout.addWidget(self.subtitle)

        body = QHBoxLayout()
        body.setSpacing(16)

        # 左：老虎机（卷轴居中，按钮紧贴卷轴下方）
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addStretch(1)
        self.reel = ReelWidget()
        self.reel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.reel.stopped.connect(self._on_reel_stopped)
        left.addWidget(self.reel)

        roll_row = QHBoxLayout()
        roll_row.setContentsMargins(0, 0, 0, 0)
        roll_row.setSpacing(10)
        self.btn_roll = PrimaryPushButton("开始抽选")
        self.btn_roll.clicked.connect(self.rollRequested.emit)
        self.roll_hint = CaptionLabel("点击后名单滚动，停下即为抽中结果")
        self.roll_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        roll_row.addStretch(1)
        roll_row.addWidget(self.btn_roll)
        roll_row.addWidget(self.roll_hint)
        roll_row.addStretch(1)
        left.addLayout(roll_row)
        left.addStretch(1)
        body.addLayout(left, 2)

        # 右：已抽取
        right = QVBoxLayout()
        right.setSpacing(6)
        head = QHBoxLayout()
        title_right = StrongBodyLabel("已抽取")
        title_right.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.count_label = CaptionLabel("0 人")
        self.count_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        head.addWidget(title_right)
        head.addStretch(1)
        head.addWidget(self.count_label)
        right.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.holder = QWidget()
        self.grid = QGridLayout(self.holder)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.grid.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.holder)
        right.addWidget(self.scroll, 1)
        body.addLayout(right, 1)

        self.card_layout.addLayout(body, 1)

        # 底部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.btn_finish = PushButton("重置并关闭")
        self.btn_finish.setStyleSheet(_RED_BTN)
        self.btn_finish.clicked.connect(self.finished.emit)
        self.btn_leave = PushButton('暂离（临时关闭本窗口，点击“继续点名”重新打开）')
        self.btn_leave.setStyleSheet(_BLUE_BTN)
        self.btn_leave.clicked.connect(self.leaveRequested.emit)
        self.btn_edit = PushButton("修改配置")
        self.btn_edit.clicked.connect(self.editRequested.emit)
        toolbar.addWidget(self.btn_finish)
        toolbar.addWidget(self.btn_leave)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_edit)
        self.card_layout.addLayout(toolbar)

        self._empty_hint = BodyLabel("还没有抽过任何人")
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self.grid.addWidget(self._empty_hint, 0, 0, 1, 2)

        # 触摸屏拖动滚动（Windows 上触摸会被合成为鼠标事件，所以用鼠标拖拽手势）
        QScroller.grabGesture(self.scroll.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)

    # ------------------------------------------------------------------
    def set_pool(self, students):
        """刷新左侧候名单（顺序打乱，看起来更随机）。"""
        self._snapshot = [(s.student_no, s.name) for s in students]
        self.reel.shuffle_rows(self._snapshot)

    def set_info(self, mode: str, duration: float):
        mode_text = "重复抽选" if mode == "repeat" else "不重复抽选"
        self.subtitle.setText(f"{self.class_name} · {mode_text} · 滚动 {duration:.1f} 秒")

    def start_roll(self, winner, pool_snapshot, duration):
        """点击瞬间结果已定，这里只负责演出。

        名单重新打乱后滚动，用「加速→匀速→匀减速」的连续曲线在
        duration 秒内精确停在中奖者那一行并保持高亮。
        """
        self._pending = winner
        self._snapshot = [(s.student_no, s.name) for s in pool_snapshot]
        shuffled = self.reel.shuffle_rows(self._snapshot)
        index = -1
        for i, (no, _) in enumerate(shuffled):
            if no == winner.student_no:
                index = i
                break
        self.btn_roll.setEnabled(False)
        self.btn_finish.setEnabled(False)
        if index < 0:            # 名单已空等情况，直接归档
            self._on_reel_stopped()
            return
        self.reel.roll_to(index, duration)

    def begin_chain(self):
        """连抽模式：整轮结束前不允许重复点开始。"""
        self._chaining = True
        self.btn_roll.setEnabled(False)
        self.btn_finish.setEnabled(True)

    def end_chain(self):
        self._chaining = False
        self.btn_roll.setEnabled(True)
        self.btn_finish.setEnabled(True)

    def _on_reel_stopped(self):
        """卷轴停稳：把中奖者放进右侧列表并通知外部。"""
        winner = self._pending
        self._pending = None
        if not self._chaining:
            self.btn_roll.setEnabled(True)
        self.btn_finish.setEnabled(True)
        if winner is None:
            return
        self._add_card(winner)
        self.drawn.emit(winner)

    def _add_card(self, student):
        card = DrawnCard(student)
        self._cards.insert(0, card)
        self._rebuild_grid()
        self.count_label.setText(f"{len(self._cards)} 人")

    def _rebuild_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        if not self._cards:
            self.grid.addWidget(self._empty_hint, 0, 0, 1, 2)
            return
        for i, card in enumerate(self._cards):
            self.grid.addWidget(card, i // 2, i % 2)

    def clear_drawn(self):
        self._cards = []
        self._rebuild_grid()
        self.count_label.setText("0 人")

    def closeEvent(self, event):
        self.reel.stop_now()
        super().closeEvent(event)
