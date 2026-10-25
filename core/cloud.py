"""名单与权重的来源决策：云端 → 本地缓存 → 本地均权。

缓存放在 ~/.classboard/cache_<hash>.json，客户端断网时沿用上次云端下发的权重；
没有缓存则退回本地全员 1.0，保证离线也能正常点名。
"""
import hashlib
import json
from pathlib import Path

from . import net
from .config import cloud_enabled, config_dir
from .models import Student


def _cache_path(class_name: str) -> Path:
    digest = hashlib.sha1(class_name.encode("utf-8")).hexdigest()[:12]
    return config_dir() / f"cache_{digest}.json"


def _save_cache(class_name: str, students) -> None:
    try:
        path = _cache_path(class_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "class_name": class_name,
                    "students": [
                        {"student_no": s.student_no, "name": s.name, "weight": s.weight}
                        for s in students
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _load_cache(class_name: str):
    path = _cache_path(class_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    students = []
    for item in data.get("students", []):
        try:
            students.append(
                Student(str(item["student_no"]), str(item["name"]), float(item.get("weight", 1.0)))
            )
        except (KeyError, TypeError, ValueError):
            continue
    return students or None


def resolve_students(cfg, class_name: str, local_students, online: bool = True):
    """返回 (students, source)，source ∈ {'cloud', 'cache', 'local'}。"""
    local = [Student(s.student_no, s.name, 1.0) for s in local_students]
    if not cloud_enabled(cfg, class_name):
        return local, "local"
    if online:
        remote = net.pull_config(cfg, class_name)
        if remote:
            students = []
            for row in remote.get("students") or []:
                try:
                    students.append(
                        Student(str(row["student_no"]), str(row["name"]), float(row.get("weight", 1.0)))
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            if students:
                _save_cache(class_name, students)
                return students, "cloud"
    cached = _load_cache(class_name)
    if cached:
        return cached, "cache"
    return local, "local"


def sync_startup(cfg, class_name: str, students, online: bool = True):
    """启动时：云控开启则先上报名单，再决定本次使用的名单与权重。"""
    if cloud_enabled(cfg, class_name) and online:
        net.upload_roster(cfg, class_name, students)
    return resolve_students(cfg, class_name, students, online=online)
