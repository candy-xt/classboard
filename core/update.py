"""客户端自动更新：检查 → 下载 → 解压 → 重启时替换并启动。

只支持 Windows 的自我替换：程序退出后由一个临时 bat 覆盖安装目录，
再把新 exe 拉起来。学生名单和 ~/.classboard 不在更新包里，不受影响。
"""
import json
import os
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
        out = entries[0]

    # 保护教室本地数据：更新包里就算误带了名单/配置，也一律丢掉，
    # 否则 xcopy 会把学生们真实的名单覆盖掉。
    for name in ("students.json", "students.example.json.bak", ".classboard"):
        p = out / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    return out


def _write_bat(bat_path, src_dir, target_dir, exe_name, pid):
    """生成替换脚本。

    Windows 上正在运行的 exe 和被加载的 dll 都是锁死的，所以必须：
      1. 等到本进程真的退出（按 PID 判断，最多等 30 秒）
      2. 再复制，失败就重试 5 次（杀毒软件、索引服务可能短暂占用）
      3. 无论复制成没成功都要把程序拉起来，不能让人开着空文件夹
    """
    script = f"""@echo off
setlocal
set "SRC={src_dir}"
set "DST={target_dir}"
set "EXE={exe_name}"
set "PID={pid}"

rem ---- 1. 等原进程退出（按 PID，避免同名进程干扰）----
set /a tries=0
:wait
tasklist /fi "pid eq %PID%" 2>nul | find "%PID%" >nul
if errorlevel 1 goto copy
set /a tries+=1
if %tries% geq 30 goto copy
timeout /t 1 /nobreak >nul
goto wait

rem ---- 2. 复制（失败重试）----
:copy
set /a n=0
:trycopy
xcopy /e /y /q "%SRC%\\*" "%DST%\\" >nul
if not errorlevel 1 goto done
set /a n+=1
if %n% geq 5 goto fail
timeout /t 2 /nobreak >nul
goto trycopy

:done
start "" "%DST%\\%EXE%"
del "%~f0"
exit /b 0

:fail
start "" "%DST%\\%EXE%"
del "%~f0"
exit /b 1
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
    """写下替换脚本并启动它；调用方随后应立即退出程序。

    替换目标就是当前 exe 所在的目录，原地覆盖，不会换位置。
    """
    if sys.platform != "win32":
        return False
    target_dir = Path(sys.executable).parent
    exe_name = Path(sys.executable).name
    bat = Path(workdir) / "apply_update.bat"
    if not _write_bat(bat, Path(src_dir), target_dir, exe_name, os.getpid()):
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
