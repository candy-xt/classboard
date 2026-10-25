"""ClassBoard 客户端入口。

流程：读本地名单 → 后台与云端同步（名单+权重）→ 右下角悬浮球
→ 点球开配置卡 → 开始时再拉一次云端名单 → 抽取界面 → 每抽中一人后台上报。
"""
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

# Linux + Wayland 下，原生 Wayland 客户端既不能自己移动窗口，也没有置顶协议，
# 会导致悬浮球拖不动、压不住别的窗口。这种情况下自动退到 XWayland(xcb)。
# Windows 不受影响；想强制用原生 Wayland 可设 CLASSBOARD_PLATFORM=wayland。
_forced = os.environ.get("CLASSBOARD_PLATFORM")
if _forced:
    os.environ["QT_QPA_PLATFORM"] = _forced
elif sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM"):
    if os.environ.get("WAYLAND_DISPLAY") or "wayland" in os.environ.get("XDG_SESSION_TYPE", ""):
        os.environ["QT_QPA_PLATFORM"] = "xcb"

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QApplication

from core import cloud, net
from core.config import cloud_enabled, load_config, load_window_position, save_window_position
from core.roster import load_roster
from core.session import Session
from ui.config_card import MODE_NO_REPEAT, MODE_REPEAT, ConfigCard
from ui.draw_window import DrawWindow
from ui.floating import FloatingButton
from ui.theme import apply_theme
from ui.tray import TrayIcon


def app_dir() -> Path:
    """名单文件所在目录：打包后是 exe 同目录，开发时是项目目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


class Signals(QObject):
    synced = Signal(list, str)      # 名单(含权重), 来源
    reported = Signal(bool)


class SyncTask(QRunnable):
    """后台拉取云端名单与权重。"""

    def __init__(self, cfg, class_name, students, signals):
        super().__init__()
        self.cfg, self.class_name, self.students = cfg, class_name, students
        self.signals = signals

    def run(self):
        students, source = cloud.sync_startup(self.cfg, self.class_name, self.students)
        self.signals.synced.emit(students, source)


class PullTask(QRunnable):
    """点击"开始"时再拉一次云端名单。"""

    def __init__(self, cfg, class_name, students, signals):
        super().__init__()
        self.cfg, self.class_name, self.students = cfg, class_name, students
        self.signals = signals

    def run(self):
        students, source = cloud.resolve_students(self.cfg, self.class_name, self.students)
        self.signals.synced.emit(students, source)


class ReportTask(QRunnable):
    """每抽中一人上报一次（失败不打断点名）。"""

    def __init__(self, cfg, class_name, student, mode, session_id=None):
        super().__init__()
        self.cfg, self.class_name, self.student = cfg, class_name, student
        self.mode, self.session_id = mode, session_id

    def run(self):
        net.report_result(
            self.cfg, self.class_name, self.student, self.mode,
            drawn_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id=self.session_id,
        )


class App(QObject):
    def __init__(self):
        super().__init__()
        self.qapp = QApplication.instance() or QApplication(sys.argv)
        apply_theme()

        # 优先用同目录的真实名单；没有则退回示例名单（方便新克隆直接跑起来）
        roster_path = app_dir() / "students.json"
        if not roster_path.exists():
            roster_path = app_dir() / "students.example.json"
        self.class_name, self.students = load_roster(roster_path)
        self.cfg = load_config()
        self.cloud_on = cloud_enabled(self.cfg, self.class_name)
        self.source = "local"

        self.session: Session = None
        self.draw_window: DrawWindow = None
        self.config_card: ConfigCard = None
        self.session_active = False
        self.pool = QThreadPool()
        self.signals = Signals()
        self.signals.synced.connect(self._on_synced)

        self.ball = FloatingButton()
        self.ball.clicked.connect(self._on_ball_clicked)
        self.ball.quitRequested.connect(self.quit)
        self.ball.moved.connect(self._save_ball_position)
        self.ball.show()
        self.ball.move_to_bottom_right()
        # 恢复上次拖到的位置
        saved = load_window_position("ball")
        if saved and not self.ball.restore_position(*saved):
            self.ball.move_to_bottom_right()

        self.tray = TrayIcon()
        self.tray.toggleRequested.connect(self._toggle_ball)
        self.tray.quitRequested.connect(self.quit)
        self.tray.show()

        if self.cloud_on:
            self.pool.start(SyncTask(self.cfg, self.class_name, self.students, self.signals))
        else:
            print(f"[ClassBoard] 本地模式启动（{self.class_name}，{len(self.students)} 人）")

    # ------------------------------------------------------------------
    def _on_synced(self, students, source):
        self.students = students
        self.source = source
        print(f"[ClassBoard] 名单已同步（{len(students)} 人）")

    def _save_ball_position(self, x, y):
        save_window_position("ball", x, y)

    def _on_ball_clicked(self):
        if self.session_active and self.draw_window is not None:
            # 会话还在：恢复抽取界面（原地淡入，不重新居中）
            self.draw_window.show_animated(center=False)
            self.draw_window.raise_()
            self.draw_window.activateWindow()
            return
        self._open_config(edit=False)

    def _open_config(self, edit: bool):
        if self.config_card is not None:
            self.config_card.close()
            self.config_card.deleteLater()
            self.config_card = None

        if edit and self.session is not None:
            mode = self.session.mode
            duration = self.session.duration
            excluded = set(self.session.excluded)
            drawn_nos = {s.student_no for s in self.session.drawn}
        else:
            mode = MODE_NO_REPEAT
            duration = 4.5
            excluded = set()
            drawn_nos = set()

        card = ConfigCard(
            self.class_name, self.students, mode=mode, duration=duration,
            excluded=excluded, drawn_nos=drawn_nos, edit=edit,
        )
        card.started.connect(lambda m, d, ex: self._on_config_confirmed(m, d, ex, edit))
        card.cancelled.connect(self._close_config)
        self.config_card = card
        card.show_animated()

    def _close_config(self):
        if self.config_card is not None:
            self.config_card.close()
            self.config_card.deleteLater()
            self.config_card = None

    def _on_config_confirmed(self, mode, duration, excluded, edit):
        self._close_config()
        if edit and self.session is not None:
            # 编辑已有会话：保留已抽取记录
            self.session.set_mode(mode)
            self.session.set_duration(duration)
            self.session.set_excluded(excluded)
            self._refresh_draw_window()
            return
        # 新会话：先从云端拉一次名单
        if self.cloud_on:
            self.pool.start(PullTask(self.cfg, self.class_name, self.students, self.signals))
        self._start_session(mode, duration, excluded)

    def _start_session(self, mode, duration, excluded):
        self.session = Session(self.class_name, self.students, mode=mode,
                               duration=duration, excluded=excluded)
        if self.draw_window is None:
            self.draw_window = DrawWindow(self.class_name)
            self.draw_window.rollRequested.connect(self._on_roll)
            self.draw_window.drawn.connect(self._on_drawn)
            self.draw_window.finished.connect(self._on_finish)
            self.draw_window.leaveRequested.connect(self._on_leave)
            self.draw_window.editRequested.connect(lambda: self._open_config(edit=True))
        self._refresh_draw_window()
        if self.draw_window.isVisible():
            # 修改配置后确认：窗口本来就在，别重播弹出动画
            self.draw_window.raise_()
        else:
            self.draw_window.show_animated()
        self.session_active = True
        self.ball.set_text("继续点名...")

    def _refresh_draw_window(self):
        if self.draw_window is None or self.session is None:
            return
        self.draw_window.set_info(self.session.mode, self.session.duration)
        self.draw_window.set_pool(self.session.remaining)
    # ------------------------------------------------------------------
    def _on_roll(self):
        if self.session is None:
            return
        if not self.session.remaining:
            return
        # 点击瞬间结果已定；上一轮高亮的人此时才从名单里消失
        winner = self.session.draw()
        if winner is None:
            return
        self.draw_window.start_roll(winner, self.session.remaining, self.session.duration)

    def _on_drawn(self, student):
        """卷轴停稳：上报结果。名单保持不动，高亮留在中奖者身上。"""
        if self.cloud_on and self.cfg is not None:
            self.pool.start(ReportTask(
                self.cfg, self.class_name, student, self.session.mode,
                session_id=self.session.session_id))

    def _on_finish(self):
        """结束本次抽取：固化结果并回到初始状态。"""
        if self.session is not None:
            self.session.reset()
        if self.draw_window is not None:
            self.draw_window.clear_drawn()
            self.draw_window.hide()
        self.session_active = False
        self.ball.set_text("随机点名")

    def _on_leave(self):
        """暂离：保留已抽取和配置，悬浮球变为"继续点名..."。"""
        if self.draw_window is not None:
            self.draw_window.hide()
        self.ball.set_text("继续点名...")

    def _toggle_ball(self):
        """托盘菜单 / 单击托盘图标：显示或隐藏悬浮窗。"""
        if self.ball.isVisible():
            self.ball.hide()
            self.tray.set_ball_visible(False)
        else:
            self.ball.show()
            self.ball.raise_()
            self.tray.set_ball_visible(True)

    def quit(self):
        self.tray.hide()
        self.pool.waitForDone(3000)
        self.qapp.quit()


def main():
    app = App()
    sys.exit(app.qapp.exec())


if __name__ == "__main__":
    main()
