"""CLI-M01/O20/I01〜I02: 公開JSONの詳細参照とAPIとの整合性。"""

import importlib
from typing import TYPE_CHECKING

import pytest

from .support import CLI, assert_metric, single, write_source

if TYPE_CHECKING:
    from pathlib import Path


def test_analyze_success_definition_identity(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-M01/API-M03/O20: 再定義・ネストの一意ID、位置、直接親を保持。"""
    source = (
        "@decorate\n"
        "class 外側:\n"
        "    @staticmethod\n"
        "    def method():\n"
        "        def inner(): pass\n"
        "        class Local: pass\n"
        "    class Nested:\n"
        "        async def run(self): pass\n"
        "def same(): pass\n"
        "def same(): pass\n"
        "class Repeated: pass\n"
        "class Repeated: pass\n"
    )
    result = cli.analyze(write_source(tmp_path, "定義.py", source))
    details = result["details"]
    assert len(details["classes"]) == source.count("class ")
    assert len(details["functions"]) == source.count("def ")
    records = details["classes"] + details["functions"]
    ids = [record["id"] for record in details["files"] + records]
    assert len(ids) == len(set(ids))
    file_id = details["files"][0]["id"]
    assert all(record["file_id"] == file_id for record in records)
    outer = single(result, "classes", "外側")
    method = single(result, "functions", "method")
    inner = single(result, "functions", "inner")
    local = single(result, "classes", "Local")
    nested = single(result, "classes", "Nested")
    run = single(result, "functions", "run")
    assert outer["parent_id"] is None
    assert method["parent_id"] == outer["id"]
    assert inner["parent_id"] == local["parent_id"] == method["id"]
    assert nested["parent_id"] == outer["id"]
    assert run["parent_id"] == nested["id"]
    positions = {
        (record["name"], record["line"], record["column"]) for record in records
    }
    assert positions == {
        ("外側", 2, 0),
        ("method", 4, 4),
        ("inner", 5, 8),
        ("Local", 6, 8),
        ("Nested", 7, 4),
        ("run", 8, 8),
        ("same", 9, 0),
        ("same", 10, 0),
        ("Repeated", 11, 0),
        ("Repeated", 12, 0),
    }
    assert_metric(result["metrics"], "function_count", total=5)
    assert_metric(result["metrics"], "class_count", total=5)
    assert_metric(outer["metrics"], "function_count", total=1)
    assert_metric(nested["metrics"], "function_count", total=1)


@pytest.mark.parametrize("state", ["normal", "empty", "partial", "unresolved"])
def test_analyze_success_api_agrees(*, cli: CLI, tmp_path: Path, state: str) -> None:
    """CLI-I01: 正常・空・partial・未解決で仕様値と公開APIの値が一致。"""
    api = importlib.import_module("cqa")
    root = tmp_path / "project"
    root.mkdir()
    if state != "empty":
        _ = write_source(root, "main.py", "def f():\n    return 1\n")
    if state == "partial":
        _ = write_source(root, "broken.py", "def broken(:\n")
    if state == "unresolved":
        _ = write_source(
            root, "dynamic.py", "import importlib\nimportlib.import_module(input())\n"
        )
    actual = cli.analyze(root, partial=state == "partial")
    expected = api.analyze(root).to_dict()
    for result in (actual, expected):
        assert_metric(
            result["metrics"], "function_count", total=0 if state == "empty" else 1
        )
        assert result["status"] == ("partial" if state == "partial" else "complete")
        assert bool(result["unresolved"]) == (state == "unresolved")
    assert actual["metrics"] == expected["metrics"]
    assert actual["scope"]["file_count"] == expected["scope"]["file_count"]


def test_compare_success_api_agrees(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-I02: 差分・変化率・比較不能・状態を仕様値とAPI双方で確認。"""
    api = importlib.import_module("cqa")
    before = write_source(tmp_path, "before.py", "def before(): pass\n")
    after = write_source(tmp_path, "after.py", "def after():\n    return 1\n")
    actual = cli.json("compare", before, after)
    expected = api.compare(api.analyze(before), api.analyze(after)).to_dict()
    for result in (actual, expected):
        assert result["status"] == "complete"
        assert result["differences"]["sloc"]["total"] == {
            "before": 1,
            "after": 2,
            "difference": 1,
            "change_rate": 100,
        }
    assert actual["differences"] == expected["differences"]
    assert {item["metric"] for item in actual["incompatible_metrics"]} == {
        item["metric"] for item in expected["incompatible_metrics"]
    }


def test_analyze_success_measurement_levels(*, cli: CLI) -> None:
    """CLI-M01/API-M02: Function・Class・File・Scopeの適用集計値を取得。"""
    path = write_source(
        cli.cwd, "levels.py", "class C:\n    def f(self):\n        return self.x\n"
    )
    result = cli.analyze(path)
    function = single(result, "functions", "f")["metrics"]
    class_metrics = single(result, "classes", "C")["metrics"]
    file_metrics = result["details"]["files"][0]["metrics"]
    for metrics in (function,):
        assert_metric(metrics, "function_length", value=2)
        assert_metric(metrics, "cyclomatic_complexity", value=1)
        assert_metric(metrics, "cognitive_complexity", value=0)
        assert_metric(metrics, "nesting_depth", value=0)
    for metrics in (class_metrics, file_metrics, result["metrics"]):
        assert_metric(metrics, "function_count", total=1)
        assert_metric(metrics, "function_length", average=2, maximum=2)
        assert_metric(metrics, "cyclomatic_complexity", total=1, average=1, maximum=1)
        assert_metric(metrics, "cognitive_complexity", total=0, average=0, maximum=0)
        assert_metric(metrics, "nesting_depth", average=0, maximum=0)
    assert_metric(class_metrics, "cbo", value=0)
    assert_metric(class_metrics, "lcom4", value=1)
    for metrics in (file_metrics, result["metrics"]):
        assert_metric(metrics, "sloc", total=3)
        assert_metric(metrics, "class_count", total=1)
        assert_metric(metrics, "cbo", average=0, maximum=0)
        assert_metric(metrics, "lcom4", average=1, maximum=1)
        assert_metric(metrics, "duplication_rate", value=0)
    assert_metric(file_metrics, "fan_out", value=0)
    assert_metric(result["metrics"], "fan_out", average=0, maximum=0)
    assert_metric(result["metrics"], "dependency_cycles", value=0)
