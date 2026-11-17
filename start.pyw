"""Windows 上无控制台启动入口。

双击本文件即可运行：.pyw 在 Windows 上默认关联 pythonw.exe，
不会弹出黑色终端窗口。需要机器上装好 Python 和项目依赖
（PySide6、qfluentwidgets、requests 等）。

Linux / macOS 上也可以 `python3 start.pyw` 跑，只是不隐藏终端。

出问题时不会闪退得无声无息：异常会写进项目目录的
classboard-error.log，同时照常抛出。
"""
import os
import sys
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)                      # 相对路径（名单、日志）都以项目目录为准
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from main import main               # noqa: E402


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_path = os.path.join(HERE, "classboard-error.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        raise
