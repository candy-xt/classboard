"""客户端核心单元测试：python3 -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cloud, net  # noqa: E402
from core.config import ClientConfig, cloud_enabled, load_config  # noqa: E402
from core.models import Student  # noqa: E402
from core.picker import Picker  # noqa: E402
from core.roster import load_roster  # noqa: E402


class TestRoster(unittest.TestCase):
    def _write(self, data):
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "students.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_object_format(self):
        path = self._write({"class_name": "高一(3)班",
                            "students": [{"student_no": "01", "name": "张三"}]})
        class_name, students = load_roster(path)
        self.assertEqual(class_name, "高一(3)班")
        self.assertEqual(students[0].name, "张三")
        self.assertEqual(students[0].weight, 1.0)

    def test_list_format(self):
        path = self._write([{"student_no": "01", "name": "张三", "class_name": "高一(5)班"}])
        class_name, students = load_roster(path)
        self.assertEqual(class_name, "高一(5)班")
        self.assertEqual(len(students), 1)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_roster(Path("/tmp/does-not-exist-students.json"))

    def test_missing_class_name(self):
        path = self._write({"students": [{"student_no": "01", "name": "张三"}]})
        with self.assertRaises(ValueError):
            load_roster(path)

    def test_duplicate_student_no(self):
        path = self._write({"class_name": "A班", "students": [
            {"student_no": "01", "name": "张三"}, {"student_no": "01", "name": "李四"}]})
        with self.assertRaises(ValueError):
            load_roster(path)


class TestConfig(unittest.TestCase):
    def test_parse_and_whitelist(self):
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "config.txt"
        path.write_text(
            "# 注释\nSERVER=http://127.0.0.1:8317/\nKEY=abc\nCLIENT_ID=PC-01\n"
            "WHITELIST=高一(3)班，高一(5)班\n",
            encoding="utf-8",
        )
        cfg = load_config(path)
        self.assertEqual(cfg.server, "http://127.0.0.1:8317")
        self.assertEqual(cfg.client_id, "PC-01")
        self.assertEqual(cfg.whitelist, ["高一(3)班", "高一(5)班"])
        self.assertTrue(cloud_enabled(cfg, "高一(3)班"))
        self.assertFalse(cloud_enabled(cfg, "高一(4)班"))

    def test_missing_config(self):
        self.assertIsNone(load_config(Path("/tmp/nope-config.txt")))
        self.assertFalse(cloud_enabled(None, "高一(3)班"))

    def test_incomplete_config_not_enabled(self):
        cfg = ClientConfig(server="", key="k", client_id="c", whitelist=["高一(3)班"])
        self.assertFalse(cloud_enabled(cfg, "高一(3)班"))


class TestPicker(unittest.TestCase):
    def setUp(self):
        self.students = [
            Student("01", "张三", 1.0),
            Student("02", "李四", 0.0),   # 永不抽中
            Student("03", "王五", 3.0),
        ]

    def test_zero_weight_never_picked(self):
        picker = Picker(self.students, repeat=True)
        for _ in range(500):
            self.assertNotEqual(picker.pick().student_no, "02")

    def test_no_repeat_has_no_duplicates(self):
        picker = Picker(self.students, repeat=False)
        picked = [picker.pick().student_no for _ in range(2)]
        self.assertEqual(len(picked), len(set(picked)))
        self.assertNotIn("02", picked)  # 权重 0 的人抽不到
        self.assertIsNone(picker.pick())  # 池子空了

    def test_all_zero_weight_returns_none(self):
        picker = Picker([Student("01", "张三", 0.0)], repeat=True)
        self.assertIsNone(picker.pick())

    def test_negative_weight_treated_as_zero(self):
        picker = Picker([Student("01", "张三", -5.0), Student("02", "李四", 1.0)],
                         repeat=True)
        for _ in range(200):
            self.assertNotEqual(picker.pick().student_no, "01")

    def test_reset_clears_drawn(self):
        picker = Picker(self.students, repeat=False)
        picker.pick()
        self.assertEqual(len(picker.drawn), 1)
        picker.reset()
        self.assertEqual(len(picker.drawn), 0)

    def test_higher_weight_picked_more_often(self):
        picker = Picker([Student("01", "张三", 0.1), Student("02", "李四", 5.0)], repeat=True)
        counts = {"01": 0, "02": 0}
        for _ in range(2000):
            counts[picker.pick().student_no] += 1
        self.assertGreater(counts["02"], counts["01"] * 10)


class TestCloudFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["CLASSBOARD_HOME"] = self.tmp
        self.cfg = ClientConfig(
            server="http://127.0.0.1:8317", key="k", client_id="PC-01",
            whitelist=["高一(3)班"])
        self.local = [Student("01", "张三"), Student("02", "李四")]

    def tearDown(self):
        os.environ.pop("CLASSBOARD_HOME", None)

    def test_not_in_whitelist_uses_local_equal_weights(self):
        cfg = ClientConfig(server="http://x", key="k", client_id="c", whitelist=["其他班"])
        students, source = cloud.resolve_students(cfg, "高一(3)班", self.local)
        self.assertEqual(source, "local")
        self.assertTrue(all(s.weight == 1.0 for s in students))

    def test_cloud_then_cache_then_local(self):
        remote = {"class": "高一(3)班", "students": [
            {"student_no": "01", "name": "张三", "weight": 0.3},
            {"student_no": "02", "name": "李四", "weight": 1.0}]}
        original = net.pull_config

        net.pull_config = lambda cfg, name: remote
        students, source = cloud.resolve_students(self.cfg, "高一(3)班", self.local)
        self.assertEqual(source, "cloud")
        self.assertEqual(students[0].weight, 0.3)

        # 断网 → 用缓存
        net.pull_config = lambda cfg, name: None
        students, source = cloud.resolve_students(self.cfg, "高一(3)班", self.local)
        self.assertEqual(source, "cache")
        self.assertEqual(students[0].weight, 0.3)

        # 缓存也没有 → 本地均权
        for f in Path(self.tmp).glob("cache_*.json"):
            f.unlink()
        students, source = cloud.resolve_students(self.cfg, "高一(3)班", self.local)
        self.assertEqual(source, "local")
        self.assertTrue(all(s.weight == 1.0 for s in students))

        net.pull_config = original


if __name__ == "__main__":
    unittest.main()


class TestWindowPosition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["CLASSBOARD_HOME"] = self.tmp

    def tearDown(self):
        os.environ.pop("CLASSBOARD_HOME", None)

    def test_save_and_load(self):
        from core.config import load_window_position, save_window_position
        self.assertIsNone(load_window_position("ball"))
        save_window_position("ball", 123, 456)
        self.assertEqual(load_window_position("ball"), (123, 456))
        # 换名字互不影响
        save_window_position("other", 1, 2)
        self.assertEqual(load_window_position("ball"), (123, 456))
        self.assertEqual(load_window_position("other"), (1, 2))

    def test_corrupted_file_is_ignored(self):
        from core.config import load_window_position
        (Path(self.tmp) / "ui.json").write_text("{不是json", encoding="utf-8")
        self.assertIsNone(load_window_position("ball"))
