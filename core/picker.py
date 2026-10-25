"""加权抽取。

要点：
- 权重是倍率，0 表示永不被抽中，负数按 0 处理
- 重复模式：每次在全体中按 w/Σw 抽
- 不重复模式：抽中者移出候选池，剩余人在新权重和下重新归一化
- 抽取在调用瞬间完成，UI 的滚动动画只是演出
"""
import random

from .models import Student


class Picker:
    def __init__(self, students, repeat: bool = True, rng=None, excluded=None):
        self._all = list(students)
        self._repeat = repeat
        self._rng = rng or random.Random()
        self._drawn = []
        self._excluded = set(excluded or ())

    @property
    def all_students(self):
        return list(self._all)

    @property
    def drawn(self):
        """按抽取先后顺序（新→旧由 UI 决定展示方向）。"""
        return list(self._drawn)

    @property
    def repeat(self):
        return self._repeat

    @property
    def excluded(self):
        return set(self._excluded)

    def set_repeat(self, repeat: bool):
        """切换重复/不重复模式（已抽中的记录保留）。"""
        self._repeat = repeat

    def set_excluded(self, student_nos):
        """从候选池中排除这些人（公开勾选缺席者）；已抽中记录保留。"""
        self._excluded = set(student_nos)

    def pool(self):
        """当前候选池。"""
        pool = [s for s in self._all if s.student_no not in self._excluded]
        if self._repeat:
            return pool
        drawn = {s.student_no for s in self._drawn}
        return [s for s in pool if s.student_no not in drawn]

    def pick(self):
        """抽一个人；无可抽或总权重为 0 时返回 None。"""
        pool = self.pool()
        if not pool:
            return None
        weights = [max(float(s.weight), 0.0) for s in pool]
        total = sum(weights)
        if total <= 0:
            return None
        r = self._rng.random() * total
        acc = 0.0
        for student, w in zip(pool, weights):
            acc += w
            if r < acc:
                self._drawn.append(student)
                return student
        chosen = pool[-1]  # 浮点误差兜底
        self._drawn.append(chosen)
        return chosen

    def reset(self):
        self._drawn = []
