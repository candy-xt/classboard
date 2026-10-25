"""读取与主程序同目录的 students.json。

推荐格式：
{
  "class_name": "高一(3)班",
  "students": [{"student_no": "01", "name": "张三"}, ...]
}

也兼容纯列表格式（每项可带 class_name，取第一项的班级名）。
"""
import json
from pathlib import Path

from .config import read_text_any
from .models import Student


def load_roster(path) -> tuple:
    """返回 (class_name, [Student])。文件缺失/格式错误抛出带中文说明的异常。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到名单文件：{path}（应与主程序放在同一目录）")
    # 记事本改过的名单可能是 GBK，统一走编码兜底
    data = json.loads(read_text_any(path))

    if isinstance(data, dict):
        class_name = str(data.get("class_name", "")).strip()
        raw_students = data.get("students", [])
    elif isinstance(data, list):
        raw_students = data
        class_name = str(data[0].get("class_name", "")).strip() if data else ""
    else:
        raise ValueError("students.json 格式错误：应为对象或列表")

    if not class_name:
        raise ValueError("students.json 缺少 class_name（班级名称）")
    if not raw_students:
        raise ValueError("students.json 名单为空")

    students = []
    seen = set()
    for item in raw_students:
        no = str(item.get("student_no", "")).strip()
        name = str(item.get("name", "")).strip()
        if not no or not name:
            raise ValueError(f"名单项缺少 student_no 或 name：{item}")
        if no in seen:
            raise ValueError(f"学号重复：{no}")
        seen.add(no)
        students.append(Student(no, name))
    return class_name, students
