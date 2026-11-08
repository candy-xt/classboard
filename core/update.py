"""客户端自动更新：检查 → 下载 → 解压 → 重启时替换并启动。

只支持 Windows 的自我替换：程序退出后由一个临时 bat 覆盖安装目录，
再把新 exe 拉起来。学生名单和 ~/.classboard 不在更新包里，不受影响。
"""
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

VERSION = "0.1.0"


def _request(cfg, path, timeout):
    import urllib.request

    req = urllib.request.Request(cfg.server + path)
    req.add_header("X-Client-Id", cfg.client_id)
    req.add_header("X-Key", cfg.key)
    return urllib.request.urlopen(req, timeout=timeout)


def check(cfg, timeout=6):
    """询问服务端是否有新版本；失败返回 None。"""
    try:
        with _request(cfg, f"/api/update/check?current={VERSION}", timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def download(cfg, dest_path, timeout=120):
    """下载更新包；成功返回 Path，失败 None。"""
    dest = Path(dest_path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with _request(cfg, "/api/update/download", timeout) as resp:
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        return dest if dest.stat().st_size > 0 else None
    except Exception:
        return None


def prepare(zip_path, workdir):
    """把更新包解压到 workdir/new，返回真正的程序目录。"""
    out = Path(workdir) / "new"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out)

    entries = [p for p in out.iterdir()]
    # 包里若套了一层目录（如 ClassBoard/），下钻一层
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return out


def _write_bat(bat_path, src_dir, target_dir, exe_name):
    script = f"""@echo off
timeout /t 2 /nobreak >nul
:wait
tasklist /fi "imagename eq {exe_name}" 2>nul | find /i "{exe_name}" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)
xcopy /e /y /q "{src_dir}\\*" "{target_dir}\\" >nul
start "" "{target_dir}\\{exe_name}"
del "%~f0"
"""
    # 中文 Windows 的 cmd 按 ANSI 读脚本，路径可能含中文
    for encoding in ("gbk", "utf-8"):
        try:
            bat_path.write_text(script, encoding=encoding)
            return True
        except UnicodeEncodeError:
            continue
    return False


def apply_and_restart(src_dir, workdir):
    """写下替换脚本并启动它；调用方随后应立即退出程序。"""
    if sys.platform != "win32":
        return False
    target_dir = Path(sys.executable).parent
    exe_name = Path(sys.executable).name
    bat = Path(workdir) / "apply_update.bat"
    if not _write_bat(bat, Path(src_dir), target_dir, exe_name):
        return False
    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=(subprocess.DETACHED_PROCESS
                           | subprocess.CREATE_NEW_PROCESS_GROUP),
            close_fds=True,
        )
        return True
    except Exception:
        return False


def workdir():
    """更新包临时目录（固定在临时目录下，便于清理）。"""
    path = Path(tempfile.gettempdir()) / "ClassBoard_update"
    path.mkdir(parents=True, exist_ok=True)
    return path
