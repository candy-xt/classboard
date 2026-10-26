"""点名配置卡：左栏设置、右栏名单卡片（点一下切换是否参与）。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
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
    SegmentedWidget,
    Slider,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

from .card import CardWindow

MODE_REPEAT = "repeat"
MODE_NO_REPEAT = "no_repeat"


class StudentChip(QFrame):
    """名单里的一张学生小卡片：学号 + 姓名，点一下切换参与/不参与。"""

    toggled = Signal(str, bool)

    def __init__(self, student_no, name, checked=True, locked=False, parent=None):
        super().__init__(parent)
        self.student_no = student_no
        self._checked = checked
        self._locked = locked
        self.setObjectName("chip")
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.ArrowCursor if locked else Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        self.no_label = CaptionLabel(str(student_no))
        self.name_label = BodyLabel(str(name))
        self.no_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.no_label)
        layout.addWidget(self.name_label)
        layout.addStretch(1)
        self._apply_style()

    # ---- 状态 ----
    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool):
        if self._locked:
            return
        self._checked = bool(checked)
        self._apply_style()

    def set_locked(self, locked: bool):
        self._locked = bool(locked)
        self.setCursor(Qt.ArrowCursor if locked else Qt.PointingHandCursor)
        if locked:
            self._checked = False
        self._apply_style()

    def _apply_style(self):
        if self._locked:
            bg, border, fg, no_fg = "#f7f8fa", "#e9ebef", "#c2c6cd", "#ccd0d6"
        elif self._checked:
            bg, border, fg, no_fg = "#ffffff", "#cfe0f7", "#1f2329", "#8a8f99"
        else:
            bg, border, fg, no_fg = "#f2f3f5", "#e6e8eb", "#a6abb3", "#b6bbc3"
        self.setStyleSheet(
            f"#chip {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}")
        self.name_label.setStyleSheet(f"color: {fg}; background: transparent;")
        self.no_label.setStyleSheet(f"color: {no_fg}; background: transparent;")

    def mousePressEvent(self, event):
        if self._locked or event.button() != Qt.LeftButton:
            return
        self._checked = not self._checked
        self._apply_style()
        self.toggled.emit(self.student_no, self._checked)


class ConfigCard(CardWindow):
    """开始前配置；编辑模式下保留已抽取状态。"""

    started = Signal(str, float, set)   # mode, duration, excluded student_no
    cancelled = Signal()

    def __init__(self, class_name, students, mode=MODE_NO_REPEAT, duration=4.5,
                 excluded=None, drawn_nos=None, edit=False, parent=None):
        super().__init__(width=860, height=620, parent=parent)
        self.class_name = class_name
        self.students = list(students)
        self.mode = mode
        self.duration = duration
        self.excluded = set(excluded or ())
        self.drawn_nos = set(drawn_nos or ())
        self.edit = edit
        self._chips = {}

        title = TitleLabel("修改配置" if edit else "点名配置")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        sub = SubtitleLabel(f"{class_name} · 共 {len(self.students)} 人")
        sub.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.card_layout.addWidget(title)
        self.card_layout.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_left(), 0)
        body.addLayout(self._build_right(), 1)
        self.card_layout.addLayout(body, 1)

        # 按钮
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch(1)
        cancel = PushButton("取消")
        cancel.clicked.connect(self.cancelled.emit)
        start = PrimaryPushButton("开始抽取")
        start.clicked.connect(self._on_start)
        buttons.addWidget(cancel)
        buttons.addWidget(start)
        self.card_layout.addLayout(buttons)

        self._refresh_picked()

    # ------------------------------------------------------------------
    def _build_left(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(250)
        left = QVBoxLayout(box)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)

        left.addWidget(StrongBodyLabel("抽选模式"))
        self.segment = SegmentedWidget()
        self.segment.addItem(MODE_REPEAT, "重复抽选")
        self.segment.addItem(MODE_NO_REPEAT, "不重复抽选")
        self.segment.setCurrentItem(self.mode)
        self.segment.currentItemChanged.connect(self._on_mode_changed)
        left.addWidget(self.segment)

        left.addSpacing(10)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = BodyLabel("滚动时长")
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.duration_label = CaptionLabel(f"{self.duration:.1f} 秒")
        self.duration_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.duration_label)
        left.addLayout(row)

        self.slider = Slider(Qt.Horizontal)
        self.slider.setRange(10, 100)      # 1.0 ~ 10.0 秒
        self.slider.setSingleStep(5)
        self.slider.setValue(int(round(self.duration * 10)))
        self.slider.valueChanged.connect(
            lambda v: self.duration_label.setText(f"{v / 10.0:.1f} 秒"))
        left.addWidget(self.slider)

        hint = CaptionLabel("点名单里的卡片可取消参与")
        hint.setWordWrap(True)
        left.addWidget(hint)
        left.addStretch(1)
        return box

    def _build_right(self) -> QVBoxLayout:
        right = QVBoxLayout()
        right.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(StrongBodyLabel("学生名单"))
        head.addStretch(1)
        self.picked_label = CaptionLabel("")
        head.addWidget(self.picked_label)
        right.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }")

        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setAlignment(Qt.AlignTop)

        for i, student in enumerate(self.students):
            locked = self.mode == MODE_NO_REPEAT and student.student_no in self.drawn_nos
            chip = StudentChip(
                student.student_no, student.name,
                checked=not locked and student.student_no not in self.excluded,
                locked=locked,
            )
            chip.toggled.connect(self._on_chip_toggled)
            self._chips[student.student_no] = chip
            grid.addWidget(chip, i // 2, i % 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch((len(self.students) + 1) // 2, 1)   # 顶部对齐

        self.scroll.setWidget(holder)
        right.addWidget(self.scroll, 1)

        QScroller.grabGesture(self.scroll.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        return right

    # ------------------------------------------------------------------
    def _on_chip_toggled(self, _student_no, _checked):
        self._refresh_picked()

    def _refresh_picked(self):
        picked = sum(1 for c in self._chips.values() if c.is_checked())
        self.picked_label.setText(f"{picked} 人参与")

    def _on_mode_changed(self, route):
        self.mode = route
        # 切到不重复时，已抽中的人自动置灰
        for no, chip in self._chips.items():
            locked = self.mode == MODE_NO_REPEAT and no in self.drawn_nos
            chip.set_locked(locked)
        self._refresh_picked()

    def _on_start(self):
        excluded = {no for no, chip in self._chips.items() if not chip.is_checked()}
        self.excluded = excluded
        self.started.emit(self.mode, self.slider.value() / 10.0, excluded)
