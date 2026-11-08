"""云端通信：上报名单 / 拉取权重 / 上报结果。

只用标准库 urllib；任何网络/鉴权失败都返回 None 或 False，
由上层决定降级（缓存 → 本地均权），绝不因云端不可用而崩溃。
"""
import json
import urllib.request
from urllib.parse import urlencode

from .config import ClientConfig

TIMEOUT = 5  # 秒；教室网络差时快速失败走降级


def _request(cfg: ClientConfig, method: str, path: str, payload=None, params=None,
             timeout=None):
    url = cfg.server + path
    if params:
        url += "?" + urlencode(params)
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-Client-Id", cfg.client_id)
        req.add_header("X-Key", cfg.key)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def upload_roster(cfg: ClientConfig, class_name: str, students) -> bool:
    """启动时上报名单（学号/姓名），服务端保留已配置权重。"""
    payload = {
        "class_name": class_name,
        "students": [{"student_no": s.student_no, "name": s.name} for s in students],
    }
    return _request(cfg, "POST", "/api/roster", payload) is not None


def pull_config(cfg: ClientConfig, class_name: str):
    """拉取该班名单+权重；失败返回 None。"""
    return _request(cfg, "GET", "/api/config", params={"class_name": class_name})


def cloud_draw(cfg: ClientConfig, class_name: str, mode: str, candidates, drawn):
    """请服务端决定抽到谁；开关关闭 / 网络失败时返回 None（调用方回退本地抽取）。

    超时压得比较短：这一步在点击瞬间同步执行，不能让老师干等着。
    """
    payload = {
        "class_name": class_name,
        "mode": mode,
        "candidates": [
            {"student_no": s.student_no, "name": s.name, "weight": float(s.weight)}
            for s in candidates
        ],
        "drawn": list(drawn),
    }
    resp = _request(cfg, "POST", "/api/draw", payload, timeout=1.5)
    if not resp or not resp.get("ok"):
        return None
    picked = (resp.get("pick") or {}).get("student_no")
    if not picked:
        return None
    for s in candidates:          # 返回原对象，保持权重等字段一致
        if s.student_no == picked:
            return s
    return None


def report_result(cfg: ClientConfig, class_name: str, student, mode: str,
                  drawn_at: str = None, session_id: str = None) -> bool:
    """每抽中一人上报一次；失败返回 False（UI 可选择提示，但不打断点名）。

    session_id 用于让服务端把同一次点名的多次抽取汇总成一条记录。
    """
    payload = {
        "class_name": class_name,
        "student_no": student.student_no,
        "name": student.name,
        "mode": mode,
    }
    if drawn_at:
        payload["drawn_at"] = drawn_at
    if session_id:
        payload["session_id"] = session_id
    return _request(cfg, "POST", "/api/result", payload) is not None
