"""老虎机式滚动名单（左侧主视觉）。

动画是**时间驱动**的：加速 → 匀速 → 匀减速，速度全程连续，末速为 0，
落点精确对齐中奖者那一行。距离和速度互相反推，所以不会出现
"快停下时突然跳一大段"的痕迹。

- 只有 3 行可见，中间一行是"光标"（高亮）
- 左列学号、右列姓名
"""
import random

from PySide6.QtCore import QElapsedTimer, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .theme import BRAND

ROW_H = 44
VISIBLE_ROWS = 3

# 时长分配：加速 22% / 匀速 40% / 减速 38%
_ACC_RATIO = 0.22
_DEC_RATIO = 0.38
# 期望的巡航速度（行/秒），只用来估算"这一轮该滚多远"
_TARGET_SPEED = 24.0


class ReelWidget(QWidget):
    stopped = Signal()   # 减速停稳时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []          # [(学号, 姓名)]
        self._pos = 0.0          # 中心位置（行号，可为小数）
        self._rolling = False
        self._plan = None        # 本轮滚动的运动学参数
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(ROW_H * VISIBLE_ROWS)

    # ------------------------------------------------------------------
    def set_rows(self, rows):
        """换一批名单（顺序由调用方打乱）。"""
        self._rows = list(rows)
        self._pos = 0.0
        self._rolling = False
        self._plan = None
        self._timer.stop()
        self.update()

    def shuffle_rows(self, rows):
        """打乱顺序后展示：看起来更像真实随机。"""
        shuffled = list(rows)
        random.shuffle(shuffled)
        self.set_rows(shuffled)
        return shuffled

    def roll_to(self, index: int, duration: float):
        """在 duration 秒内滚到指定行并停稳。

        全程一条连续曲线：匀加速 → 匀速 → 匀减速。
        末速为 0，位置精确等于目标行，所以落点毫无"补位"感。
        """
        n = len(self._rows)
        if n == 0:
            return
        self._plan = self._build_plan(index % n, duration)
        self._rolling = True
        self._clock.restart()
        self._timer.start()

    def stop_now(self):
        self._timer.stop()
        self._rolling = False
        self._plan = None

    @property
    def rolling(self) -> bool:
        return self._rolling

    # ------------------------------------------------------------------
    def _build_plan(self, index: int, duration: float):
        n = len(self._rows)
        d = max(0.5, float(duration))

        # 匀加速 + 匀减速的平均速度只有 vmax/2，所以总距离 = vmax * d * factor
        factor = 1 - (_ACC_RATIO + _DEC_RATIO) / 2

        p0 = float(round(self._pos))
        base = (index - p0) % n
        if base == 0:                 # 已经在目标行上，至少多转一圈
            base = n

        ideal = _TARGET_SPEED * d * factor
        k = max(0, round((ideal - base) / n))
        total = base + k * n
        if total < ideal * 0.55:      # 太短就再转一圈，别"蹭"一下就停
            total += n

        vmax = total / (d * factor)
        t_acc = _ACC_RATIO * d
        t_cruise = (1 - _ACC_RATIO - _DEC_RATIO) * d
        t_dec = _DEC_RATIO * d

        return {
            "p0": p0,
            "p1": p0 + total,
            "d": d,
            "vmax": vmax,
            "t_acc": t_acc,
            "t_cruise": t_cruise,
            "t_dec": t_dec,
            "d_acc": 0.5 * vmax * t_acc,
            "d_cruise": vmax * t_cruise,
        }

    def _position_at(self, plan, t: float) -> float:
        """t 秒时卷轴应处的位置（行号）。运动学与绘制完全解耦。"""
        p0 = plan["p0"]
        vmax = plan["vmax"]
        t_acc = plan["t_acc"]
        t_cruise = plan["t_cruise"]
        t_dec = plan["t_dec"]

        if t <= 0:
            return p0
        if t >= plan["d"]:
            return plan["p1"]
        if t < t_acc:                                   # 匀加速
            return p0 + 0.5 * (vmax / t_acc) * t * t
        if t < t_acc + t_cruise:                        # 匀速
            return p0 + plan["d_acc"] + vmax * (t - t_acc)
        tau = t - t_acc - t_cruise                      # 匀减速，末速为 0
        return (p0 + plan["d_acc"] + plan["d_cruise"]
                + vmax * tau - 0.5 * (vmax / t_dec) * tau * tau)

    def _tick(self):
        plan = self._plan
        if plan is None:
            return

        t = self._clock.elapsed() / 1000.0
        if t >= plan["d"]:
            self._pos = plan["p1"]
            self._timer.stop()
            self._rolling = False
            self._plan = None
            self.update()
            self.stopped.emit()
            return

        self._pos = self._position_at(plan, t)
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        if not self._rows:
            painter.setPen(QColor("#8a8f99"))
            painter.drawText(self.rect(), Qt.AlignCenter, "名单为空")
            painter.end()
            return

        font = QFont(self.font())
        font.setPointSize(13)
        painter.setFont(font)

        height = self.height()
        center_line = height / 2
        base = int(self._pos)
        n = len(self._rows)

        for k in range(-1, VISIBLE_ROWS + 1):
            raw = base + k
            idx = raw % n          # 循环滚动：一直转也不会滚出名单
            no, name = self._rows[idx]
            y = center_line - ROW_H / 2 + (raw - self._pos) * ROW_H
            if y > height or y + ROW_H < 0:
                continue

            is_center = abs(raw - self._pos) < 0.5
            if is_center:
                painter.fillRect(QRect(8, int(y), self.width() - 16, ROW_H),
                                 QColor(BRAND))
                text_color = QColor("#ffffff")
                sub_color = QColor(230, 238, 250)
            else:
                text_color = QColor("#1f2329")
                sub_color = QColor("#8a8f99")

            # 左：学号（右对齐）；右：姓名（左对齐）
            painter.setPen(sub_color)
            painter.drawText(QRect(24, int(y), self.width() // 2 - 40, ROW_H),
                             Qt.AlignVCenter | Qt.AlignRight, str(no))
            painter.setPen(text_color)
            painter.drawText(QRect(self.width() // 2 + 8, int(y),
                                   self.width() // 2 - 40, ROW_H),
                             Qt.AlignVCenter | Qt.AlignLeft, str(name))

        # 上下边缘渐隐，做出卷轴质感
        fade_h = ROW_H // 2
        top = QLinearGradient(0, 0, 0, fade_h)
        top.setColorAt(0, QColor(255, 255, 255, 220))
        top.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRect(0, 0, self.width(), fade_h), top)
        bottom = QLinearGradient(0, height - fade_h, 0, height)
        bottom.setColorAt(0, QColor(255, 255, 255, 0))
        bottom.setColorAt(1, QColor(255, 255, 255, 220))
        painter.fillRect(QRect(0, height - fade_h, self.width(), fade_h), bottom)
        painter.end()
