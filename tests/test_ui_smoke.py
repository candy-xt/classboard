"""界面冒烟测试（offscreen，无显示器环境）。

QT_QPA_PLATFORM=offscreen uv run python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.models import Student  # noqa: E402
from core.session import Session  # noqa: E402
from ui.config_card import MODE_NO_REPEAT, ConfigCard  # noqa: E402
from ui.draw_window import DrawWindow  # noqa: E402
from ui.floating import FloatingButton  # noqa: E402
from ui.theme import apply_theme  # noqa: E402


def _students(n=20):
    return [Student(f"{i:02d}", f"同学{i:02d}") for i in range(1, n + 1)]


class TestUiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        apply_theme()

    def test_floating_button(self):
        ball = FloatingButton()
        ball.show()
        ball.set_text("继续点名...")
        self.assertEqual(ball.label.text(), "继续点名...")
        ball.close()

    def test_floating_children_are_transparent_to_mouse(self):
        """子控件若吃掉鼠标事件，悬浮球就既不能拖也不能点。"""
        ball = FloatingButton()
        self.assertTrue(ball.icon.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertTrue(ball.label.testAttribute(Qt.WA_TransparentForMouseEvents))
        ball.close()

    def test_floating_click_and_drag(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest

        ball = FloatingButton()
        ball.show()
        ball.move(100, 100)
        clicked = []
        ball.clicked.connect(lambda: clicked.append(1))

        # 点击图标所在位置也应触发
        QTest.mouseClick(ball, Qt.LeftButton, pos=ball.icon.geometry().center())
        self.assertEqual(len(clicked), 1)

        # 拖动：位置应改变，且不触发点击
        QTest.mousePress(ball, Qt.LeftButton, pos=QPoint(20, 20))
        QTest.mouseMove(ball, QPoint(60, 60))
        QTest.mouseRelease(ball, Qt.LeftButton, pos=QPoint(60, 60))
        self.assertNotEqual(ball.pos(), QPoint(100, 100))
        self.assertEqual(len(clicked), 1)   # 拖动不算点击
        ball.close()

    def test_config_card(self):
        card = ConfigCard("测试班", _students(), mode=MODE_NO_REPEAT)
        card.show()
        self.assertEqual(card.mode, MODE_NO_REPEAT)
        self.assertEqual(len(card._checkboxes), 20)
        # 取消勾选第 3 个学生
        card._checkboxes["03"].setChecked(False)
        card._on_start()
        self.assertIn("03", card.excluded)
        card.close()

    def test_draw_window_roll(self):
        students = _students()
        session = Session("测试班", students, mode=MODE_NO_REPEAT, duration=0.1)
        win = DrawWindow("测试班")
        win.set_info(session.mode, session.duration)
        win.set_pool(session.remaining)
        win.show()

        drawn = []
        win.drawn.connect(drawn.append)

        winner = session.draw()
        win.start_roll(winner, session.remaining, duration=0.5)
        self._wait_until(lambda: len(drawn) == 1)

        self.assertIsNotNone(winner)
        self.assertEqual(len(drawn), 1)
        self.assertEqual(len(win._cards), 1)
        self.assertEqual(win._cards[0].name.text(), winner.name)
        self.assertIn("人", win.count_label.text())
        # 抽中的人仍留在名单里（带高亮），等下一次抽取才移除
        self.assertIn(winner.student_no, {s.student_no for s in session.remaining})

        # 再抽一次：上一个人此时才从名单里消失
        winner2 = session.draw()
        self.assertNotIn(winner.student_no, {s.student_no for s in session.remaining})
        win.start_roll(winner2, session.remaining, duration=0.5)
        self._wait_until(lambda: len(drawn) == 2)
        self.assertEqual(len(win._cards), 2)
        self.assertEqual(win._cards[0].name.text(), winner2.name)

        win.clear_drawn()
        self.assertEqual(len(win._cards), 0)
        win.close()

    def test_reel_motion_is_continuous(self):
        """运动学曲线：加速→匀速→减速，速度连续、不超巡航速度、末速为 0。"""
        from ui.reel import ReelWidget

        reel = ReelWidget()
        reel.set_rows([(f"{i:02d}", f"同学{i:02d}") for i in range(1, 50)])
        target, duration = 37, 2.0
        plan = reel._build_plan(target, duration)

        # 1ms 步长采样，彻底避开 QTimer 的 16ms 台阶
        step = 0.001
        samples = int(duration / step) + 1
        positions = [reel._position_at(plan, i * step) for i in range(samples)]
        speeds = [(b - a) / step for a, b in zip(positions, positions[1:])]

        # 落点精确对齐目标行
        self.assertAlmostEqual(plan["p1"] % 49, target, places=9)
        self.assertAlmostEqual(positions[-1], plan["p1"], places=9)

        # 速度不超过设计巡航速度（暗箱补位会远超）
        self.assertLess(max(speeds), plan["vmax"] * 1.01,
                        f"出现超巡航速度: {max(speeds):.1f} > {plan['vmax']:.1f}")

        # 末速趋近 0：是滑停，不是急停
        self.assertLess(speeds[-1], plan["vmax"] * 0.01)

        # 全程单调前进，没有倒转
        self.assertTrue(all(s >= -1e-9 for s in speeds))

    def test_reel_stops_exactly_on_target_without_jump(self):
        """真实跑一轮：停稳后精确停在目标行，且结束即静止。"""
        from PySide6.QtTest import QTest

        from ui.reel import ReelWidget

        reel = ReelWidget()
        rows = [(f"{i:02d}", f"同学{i:02d}") for i in range(1, 50)]
        reel.set_rows(rows)
        target = 37
        reel.roll_to(target, duration=0.6)

        waited = 0
        while reel.rolling and waited < 8000:
            QTest.qWait(10)         # 真实等待，QTimer 才会推进
            waited += 10

        n = len(rows)
        self.assertFalse(reel.rolling)
        self.assertAlmostEqual(reel._pos % n, target % n, places=6)
        self.assertGreater(reel._pos, 0)

    def _wait_until(self, predicate, timeout_ms=5000):
        """跑事件循环直到条件满足（让卷轴动画真的停稳）。"""
        from PySide6.QtTest import QTest

        waited = 0
        while not predicate() and waited < timeout_ms:
            QTest.qWait(10)         # 真实等待，QTimer 才会推进
            waited += 10
        self.app.processEvents()

    def test_app_restores_saved_position(self):
        """拖过的位置要能记住，下次启动直接回到那里。"""
        import tempfile

        from core.config import save_window_position
        import main as app_main

        old_home = os.environ.get("CLASSBOARD_HOME")
        os.environ["CLASSBOARD_HOME"] = tempfile.mkdtemp()
        try:
            save_window_position("ball", 321, 234)
            app = app_main.App()
            self.assertEqual((app.ball.x(), app.ball.y()), (321, 234))
        finally:
            if old_home is None:
                os.environ.pop("CLASSBOARD_HOME", None)
            else:
                os.environ["CLASSBOARD_HOME"] = old_home

    def test_app_flow_from_ball_click(self):
        """点悬浮球 → 打开配置卡 → 开始 → 抽取界面。"""
        import tempfile

        from core.config import ClientConfig  # noqa: F401
        import main as app_main

        old_home = os.environ.get("CLASSBOARD_HOME")
        os.environ["CLASSBOARD_HOME"] = tempfile.mkdtemp()
        try:
            app = app_main.App()
            app._on_ball_clicked()
            self.assertIsNotNone(app.config_card)
            self.assertTrue(app.config_card.isVisible())

            # 确认配置 → 打开抽取界面
            card = app.config_card
            card._on_start()
            self.assertIsNotNone(app.session)
            self.assertIsNotNone(app.draw_window)
            self.assertTrue(app.session_active)

            # 抽一次（把滚动时长调短，测试跑得快）
            app.session.set_duration(0.2)
            app._on_roll()
            self._wait_until(lambda: len(app.draw_window._cards) == 1, timeout_ms=15000)
            self.assertEqual(len(app.draw_window._cards), 1)

            # 暂离 / 结束
            app._on_leave()
            self.assertEqual(app.ball.label.text(), "继续点名...")
            app._on_finish()
            self.assertEqual(app.ball.label.text(), "随机点名")
            self.assertFalse(app.session_active)
        finally:
            if old_home is None:
                os.environ.pop("CLASSBOARD_HOME", None)
            else:
                os.environ["CLASSBOARD_HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
