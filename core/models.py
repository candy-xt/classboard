"""数据模型。"""
from dataclasses import dataclass


@dataclass
class Student:
    student_no: str
    name: str
    weight: float = 1.0
