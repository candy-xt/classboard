#!/usr/bin/env bash
# ClassBoard 客户端启动脚本
#
# Linux 说明：Wayland 下客户端无法自己移动窗口、也没有"置顶"能力，
# 所以在 Linux 上默认走 XWayland(xcb)，置顶和拖动才正常。
# Windows 上忽略本脚本，直接双击 exe 即可。
set -e
cd "$(dirname "$0")"

if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$QT_QPA_PLATFORM" ]; then
  export QT_QPA_PLATFORM=xcb
  echo "[ClassBoard] 检测到 Wayland，切换到 XWayland(xcb) 以支持置顶和拖动"
fi

if [ -x .venv/bin/python ]; then
  exec .venv/bin/python main.py "$@"
else
  exec uv run python main.py "$@"
fi
