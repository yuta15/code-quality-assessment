"""API-I01〜I02: CLIと公開APIを仕様由来の期待値でも検証。"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .support import PublicModel, assert_metric, write_source

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def cli_executable() -> str:
    executable = shutil.which("cqa")
    if executable is None:
        pytest.fail(
            "CLIとの整合性確認にはインストール済みcqaコマンドが必要です。",
            pytrace=False,
        )
    return executable


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_analyze_success_cli_consistency(
    *, api: ModuleType, analysis: PublicModel, cli_executable: str, use_gitignore: bool
) -> None:
    """API-I01: 正常・空・partial・未解決の状態・計測値・失敗・未解決が一致。"""
    root = Path(analysis.scope.path)
    _ = write_source(root, "excluded.py", "class Excluded: pass\n")
    _ = write_source(root, ".gitignore", "excluded.py\n")
    result = api.analyze(root, exclude=("excluded.py",), use_gitignore=use_gitignore)
    args = [
        cli_executable,
        "analyze",
        str(root),
        "--exclude",
        "excluded.py",
        "--format",
        "json",
    ]
    if use_gitignore:
        args.append("--use-gitignore")
    process = subprocess.run(  # noqa: S603 -- 実プロセスによるE2E検証。
        args, capture_output=True, encoding="utf-8", timeout=30, check=False
    )
    document = json.loads(process.stdout)
    assert (
        (process.returncode != 0)
        if result.status == "partial"
        else (process.returncode == 0)
    ), process.stderr
    assert result.status == document["status"] == analysis.status
    assert_metric(
        result.metrics,
        "function_count",
        total=0 if analysis.scope.file_count == 0 else 1,
    )
    assert document["metrics"]["function_count"]["total"] == (
        0 if analysis.scope.file_count == 0 else 1
    )
    assert document["metrics"] == result.to_dict()["metrics"]
    assert document["scope"]["file_count"] == result.scope.file_count
    assert {error["code"] for error in document["errors"]} == {
        error.code for error in result.errors
    }
    assert sorted(item["metric"] for item in document["unresolved"]) == sorted(
        item.metric for item in result.unresolved
    )


def test_compare_success_cli_consistency(
    *, api: ModuleType, tmp_path: Path, cli_executable: str
) -> None:
    """API-I02: 差分・変化率・比較不能・状態がCLIと一致し、独立期待値も満たす。"""
    before = write_source(tmp_path, "before.py", "def old(): pass\n")
    after = write_source(tmp_path, "after.py", "def new():\n    return 1\n")
    result = api.compare(api.analyze(before), api.analyze(after))
    process = subprocess.run(  # noqa: S603 -- 実プロセスによるE2E検証。
        [cli_executable, "compare", str(before), str(after), "--format", "json"],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    document = json.loads(process.stdout)
    assert document["status"] == result.status == "complete"
    expected = {"before": 1, "after": 2, "difference": 1, "change_rate": 100}
    assert document["differences"]["sloc"]["total"] == expected
    assert result.to_dict()["differences"]["sloc"]["total"] == expected
    assert document["differences"] == result.to_dict()["differences"]
    assert {
        (item["metric"], item["aggregation"])
        for item in document["incompatible_metrics"]
    } == {(item.metric, item.aggregation) for item in result.incompatible_metrics}
