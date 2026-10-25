"""一次点名会话：模式、滚动时长、排除名单、抽取与已抽取列表。

UI 只负责"演出"，结果在 draw() 调用瞬间就定下来了。
当前抽中的人会留在展示名单里（带高亮），直到下一次抽取开始才被移除。
"""
import uuid

from .picker import Picker


class Session:
    def __init__(self, class_name, students, mode="no_repeat", duration=4.5, excluded=None):
        self.class_name = class_name
        self.mode = mode
        self.duration = float(duration)
        # 一次点名会话一个 ID：服务端按这个 ID 把多次抽取汇总成一条记录
        self.session_id = uuid.uuid4().hex[:12]
        self.picker = Picker(students, repeat=(mode == "repeat"), excluded=excluded)
        self._current = None

    @property
    def students(self):
        return self.picker.all_students

    @property
    def drawn(self):
        return self.picker.drawn

    @property
    def current(self):
        """当前高亮显示的人（尚未从名单移除）。"""
        return self._current

    @property
    def remaining(self):
        """展示用名单：候选池 + 当前高亮的人。"""
        pool = self.picker.pool()
        if self._current is not None:
            if all(s.student_no != self._current.student_no for s in pool):
                return pool + [self._current]
        return pool

    @property
    def excluded(self):
        return self.picker.excluded

    def set_mode(self, mode: str):
        self.mode = mode
        self.picker.set_repeat(mode == "repeat")

    def set_duration(self, seconds):
        self.duration = float(seconds)

    def set_excluded(self, student_nos):
        self.picker.set_excluded(student_nos)

    def draw(self):
        """抽一个人：点击瞬间就定结果；无可抽时返回 None。

        上一轮高亮的人此时才真正从名单里消失。
        """
        self._current = None
        winner = self.picker.pick()
        self._current = winner
        return winner

    def reset(self):
        """结束本次抽取：清空已抽取记录，回到初始状态。"""
        self.picker.reset()
        self._current = None
