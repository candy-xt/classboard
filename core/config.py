"""隐蔽配置 ~/.classboard/config.txt 与白名单熔断。

文件格式（# 为注释）：
    SERVER=http://127.0.0.1:8317
    KEY=客户端密钥
    CLIENT_ID=这台机器的唯一ID
    WHITELIST=高一(3)班,高一(5)班

只有 students.json 里的班级名命中 WHITELIST，才启用云控；
否则（含配置缺失）一律纯本地均权，防止客户端被拷走后仍被远程控制。

测试可用环境变量 CLASSBOARD_HOME 覆盖配置目录。
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path


def config_dir() -> Path:
    return Path(os.environ.get("CLASSBOARD_HOME", str(Path.home() / ".classboard")))


@dataclass
class ClientConfig:
    server: str
    key: str
    client_id: str
    whitelist: list


def load_config(path=None):
    """读取配置；文件不存在返回 None。"""
    path = Path(path) if path else config_dir() / "config.txt"
    if not path.exists():
        return None
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip().upper()] = val.strip()
    whitelist = [
        x.strip()
        for x in values.get("WHITELIST", "").replace("，", ",").split(",")
        if x.strip()
    ]
    return ClientConfig(
        server=values.get("SERVER", "").rstrip("/"),
        key=values.get("KEY", ""),
        client_id=values.get("CLIENT_ID", ""),
        whitelist=whitelist,
    )


def cloud_enabled(cfg, class_name: str) -> bool:
    """云控总开关：配置齐全且班级名命中白名单。"""
    return bool(
        cfg
        and cfg.server
        and cfg.key
        and cfg.client_id
        and class_name in cfg.whitelist
    )


# ---- 窗口位置记忆（下次启动直接回到上次拖到的位置）----

def _ui_path() -> Path:
    return config_dir() / "ui.json"


def load_window_position(name: str = "ball"):
    """读取上次保存的窗口坐标；没有或损坏时返回 None。"""
    path = _ui_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pos = data.get(name)
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        try:
            return int(pos[0]), int(pos[1])
        except (TypeError, ValueError):
            return None
    return None


def save_window_position(name: str, x: int, y: int) -> None:
    """保存窗口坐标（失败不影响使用）。"""
    path = _ui_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        data[name] = [int(x), int(y)]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        pass
