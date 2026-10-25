"""点名配置卡：模式、滚动时长、名单勾选（公开去掉缺席者）。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    Slider,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    TitleLabel,
)

from .card import CardWindow

MODE_REPEAT = "repeat"
MODE_NO_REPEAT = "no_repeat"


class ConfigCard(CardWindow):
    """开始前配置；编辑模式下保留已抽取状态。"""

    started = Signal(str, float, set)   # mode, duration, excluded student_no
    cancelled = Signal()

    def __init__(self, class_name, students, mode=MODE_NO_REPEAT, duration=4.5,
                 excluded=None, drawn_nos=None, edit=False, parent=None):
        super().__init__(width=660, height=760, parent=parent)
        self.class_name = class_name
        self.students = list(students)
        self.mode = mode
        self.duration = duration
        self.excluded = set(excluded or ())
        self.drawn_nos = set(drawn_nos or ())
        self.edit = edit
        self._checkboxes = {}

        title = TitleLabel("修改配置" if edit else "点名配置")
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        sub = SubtitleLabel(f"{class_name} · 共 {len(self.students)} 人")
        sub.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.card_layout.addWidget(title)
        self.card_layout.addWidget(sub)

        # 抽选模式
        self.card_layout.addWidget(StrongBodyLabel("抽选模式"))
        self.segment = SegmentedWidget()
        self.segment.addItem(MODE_REPEAT, "重复抽选")
        self.segment.addItem(MODE_NO_REPEAT, "不重复抽选")
        self.segment.setCurrentItem(self.mode)
        self.segment.currentItemChanged.connect(self._on_mode_changed)
        self.card_layout.addWidget(self.segment)

        # 滚动时长
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = BodyLabel("滚动时长")
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.duration_label = CaptionLabel(f"{duration:.1f} 秒")
        self.duration_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.duration_label)
        self.card_layout.addLayout(row)

        self.slider = Slider(Qt.Horizontal)
        self.slider.setRange(10, 100)      # 1.0 ~ 10.0 秒
        self.slider.setSingleStep(5)
        self.slider.setValue(int(round(duration * 10)))
        self.slider.valueChanged.connect(
            lambda v: self.duration_label.setText(f"{v / 10.0:.1f} 秒"))
        self.duration_label.setText(f"{duration:.1f} 秒")
        self.card_layout.addWidget(self.slider)

        # 名单
        self.card_layout.addWidget(StrongBodyLabel("学生名单（取消勾选 = 本次不参与）"))
        self.table = self._build_table()
        self.card_layout.addWidget(self.table, 1)

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

    # ------------------------------------------------------------------
    def _build_table(self):
        table = TableWidget()
        table.setBorderVisible(True)
        if hasattr(table, "setBorderRadius"):
            table.setBorderRadius(8)
        table.setWordWrap(False)
        table.setRowCount(len(self.students))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["参与", "学号", "姓名"])
        table.verticalHeader().hide()
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setColumnWidth(0, 56)
        table.setColumnWidth(1, 80)

        for row, student in enumerate(self.students):
            checkbox = CheckBox()
            # 不重复模式下，已抽中的人不再出现在候选里
            locked = self.mode == MODE_NO_REPEAT and student.student_no in self.drawn_nos
            checkbox.setChecked(not locked and student.student_no not in self.excluded)
            checkbox.setEnabled(not locked)
            if locked:
                checkbox.setToolTip("已在本次抽取中抽到")
            table.setCellWidget(row, 0, checkbox)
            self._checkboxes[student.student_no] = checkbox

            no_item = QTableWidgetItem(student.student_no)
            name_item = QTableWidgetItem(student.name)
            no_item.setTextAlignment(Qt.AlignCenter)
            if locked:
                no_item.setForeground(Qt.gray)
                name_item.setForeground(Qt.gray)
            table.setItem(row, 1, no_item)
            table.setItem(row, 2, name_item)
        return table

    def _on_mode_changed(self, route):
        self.mode = route
        # 切到不重复时，已抽中的人自动置灰
        for row, student in enumerate(self.students):
            checkbox = self._checkboxes[student.student_no]
            locked = self.mode == MODE_NO_REPEAT and student.student_no in self.drawn_nos
            checkbox.setEnabled(not locked)
            if locked:
                checkbox.setChecked(False)

    def _on_start(self):
        excluded = {
            no for no, cb in self._checkboxes.items() if not cb.isChecked()
        }
        self.excluded = excluded
        self.started.emit(self.mode, self.slider.value() / 10.0, excluded)
