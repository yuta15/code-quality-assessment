"""CLI実行と公開JSONの検証に使うヘルパー。内部実装は参照しない。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

# 公開JSONは異種の値を持つため、境界で明示的にAnyを使用する。
type Document = dict[str, Any]

SCOPE_FIELDS = {
    "sloc": ("total",),
    "function_length": ("average", "maximum"),
    "function_count": ("total",),
    "class_count": ("total",),
    "cyclomatic_complexity": ("total", "average", "maximum"),
    "cognitive_complexity": ("total", "average", "maximum"),
    "nesting_depth": ("average", "maximum"),
    "cbo": ("average", "maximum"),
    "fan_out": ("average", "maximum"),
    "dependency_cycles": ("value",),
    "lcom4": ("average", "maximum"),
    "duplication_rate": ("value",),
}


def write_source(root: Path, name: str, source: str = "x = 1\n") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")
    return path


def save_json(path: Path, document: Document) -> Path:
    _ = path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


@dataclass
class CLI:
    executable: str
    cwd: Path
    env: dict[str, str]

    def run(
        self, *args: str | Path, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 -- 実際のCLIを引数配列で起動するE2Eテスト。
            [self.executable, *(str(arg) for arg in args)],
            cwd=cwd or self.cwd,
            env=self.env,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    def json(self, *args: str | Path, partial: bool = False) -> Document:
        process = self.run(*args, "--format", "json")
        assert (process.returncode != 0) if partial else (process.returncode == 0), (
            process.stderr
        )
        if partial:
            assert process.stderr.strip()
        document: Document = json.loads(process.stdout)
        assert document["status"] == ("partial" if partial else "complete")
        return document

    def analyze(self, target: Path, *options: str, partial: bool = False) -> Document:
        return self.json("analyze", target, *options, partial=partial)


def assert_input_error(process: subprocess.CompletedProcess[str]) -> None:
    assert process.returncode != 0
    assert process.stderr.strip()


def assert_analysis(document: Document, file_count: int) -> None:
    assert document["schema_version"]
    assert document["type"] == "analysis"
    assert document["scope"]["file_count"] == file_count
    assert document["scope"]["path"]
    assert {"files", "classes", "functions"} <= document["details"].keys()
    assert isinstance(document["errors"], list)
    assert isinstance(document["unresolved"], list)
    metadata = document["metadata"]
    assert metadata["tool_version"]
    assert isinstance(metadata["settings"], dict)
    for metric, fields in SCOPE_FIELDS.items():
        values = document["metrics"][metric]
        assert set(fields) <= values.keys()
        for field in fields:
            if values[field] is None:
                assert values["unavailable_reason"]
            else:
                assert type(values[field]) in (int, float)
        model = metadata["measurement_models"][metric]
        assert model["definition_version"]
        assert isinstance(model["settings"], dict)


def assert_metric(metrics: Document, name: str, **expected: float | None) -> None:
    for field, value in expected.items():
        actual = metrics[name][field]
        if value is None:
            assert actual is None
            assert metrics[name]["unavailable_reason"]
        else:
            assert type(actual) in (int, float)
            assert actual == pytest.approx(value)


def file_names(document: Document) -> set[str]:
    return {Path(item["path"]).name for item in document["details"]["files"]}


def single(document: Document, collection: str, name: str) -> Document:
    matches = [item for item in document["details"][collection] if item["name"] == name]
    assert len(matches) == 1
    return matches[0]


def assert_empty(document: Document) -> None:
    assert_analysis(document, 0)
    assert document["details"] == {"files": [], "classes": [], "functions": []}
    for metric, fields in SCOPE_FIELDS.items():
        for field in fields:
            value = 0 if field == "total" or metric == "dependency_cycles" else None
            assert_metric(document["metrics"], metric, **{field: value})


def deny_access(path: Path, mode: str) -> int:
    """権限を実際に変更し、OSで再現できる場合だけテストする。"""
    original = path.stat().st_mode
    path.chmod(0)
    try:
        if mode == "read":
            _ = path.read_bytes()
        else:
            probe = path / ".permission-probe"
            _ = probe.write_text("probe", encoding="utf-8")
            probe.unlink()
    except PermissionError:
        return original
    path.chmod(original)
    pytest.skip("実行ユーザーが権限制限を回避するため、OS権限による失敗を再現できない")
