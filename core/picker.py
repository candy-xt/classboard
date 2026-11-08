"""加权抽取。

要点：
- 权重是倍率，0 表示「排到最后」：只要还有人正权重，就抽不到他；
  等正权重的人抽完（或全都为 0）时，才在 0 权重的人里均匀抽
- 这样被锁 0 的同学不会「永远点不动」，老师也不会因为卡住而发现
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
        """抽一个人；无可抽时返回 None。

        权重 0 的人不会「永远抽不到」，而是被压到最后：
        只要还有正权重的人，就只在正权重里按比例抽；等这些人抽完了，
        才轮到 0 权重的人（彼此等概率）。
        """
        pool = self.pool()
        if not pool:
            return None

        weighted = [s for s in pool if float(s.weight) > 0]
        if weighted:
            weights = [float(s.weight) for s in weighted]
            total = sum(weights)
            r = self._rng.random() * total
            acc = 0.0
            for student, w in zip(weighted, weights):
                acc += w
                if r < acc:
                    self._drawn.append(student)
                    return student
            chosen = weighted[-1]        # 浮点误差兜底
        else:
            chosen = self._rng.choice(pool)   # 只剩 0 权重的人，均匀抽

        self._drawn.append(chosen)
        return chosen

    def record(self, student):
        """记录一个外部决定的结果（云端代抽），不参与本地随机。"""
        self._drawn.append(student)

    def reset(self):
        self._drawn = []
