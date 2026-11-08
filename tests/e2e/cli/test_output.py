"""CLI-O01〜O22: 各形式・出力先、精度、保存失敗、再入力。"""

import copy
import json
import re
from typing import TYPE_CHECKING, cast

import pytest

from .support import (
    CLI,
    Document,
    assert_analysis,
    assert_input_error,
    deny_access,
    save_json,
    write_source,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("format_name", [None, "console", "json", "markdown"])
@pytest.mark.parametrize("destination", ["stdout", "new", "overwrite"])
@pytest.mark.parametrize(
    ("command", "state"),
    [
        ("analyze", "normal"),
        ("analyze", "empty"),
        ("analyze", "partial"),
        ("analyze", "unresolved"),
        ("compare", "normal"),
        ("compare", "empty"),
        ("compare", "partial"),
        ("compare", "unresolved"),
        ("compare", "incompatible"),
    ],
)
def test_output_success_or_failure_matrix(
    *,
    cli: CLI,
    command: str,
    format_name: str | None,
    destination: str,
    state: str,
) -> None:
    """CLI-O01〜O08/O11〜O15: 形式・出力先・状態の公開契約を検証。"""
    args = report_arguments(cli, command, state)

    if format_name is not None:
        args += ["--format", format_name]
    output = cli.cwd / "レポート.data"
    if destination != "stdout":
        if destination == "overwrite":
            _ = output.write_text("old report", encoding="utf-8")
        args += ["--output", output]
    process = cli.run(*args)
    assert (
        (process.returncode != 0) if state == "partial" else (process.returncode == 0)
    ), process.stderr
    if state == "partial":
        assert "SYNTAX_ERROR" in process.stderr
        assert "不正.py" in process.stderr
    if destination == "stdout":
        report = process.stdout
    else:
        assert process.stdout == ""
        report = output.read_text(encoding="utf-8")
        assert "old report" not in report
    if format_name == "json":
        document = json.loads(report)
        assert_json_report(document, command, state)
    else:
        assert_text_report(report, state, format_name)


def report_arguments(cli: CLI, command: str, state: str) -> list[str | Path]:
    root = cli.cwd / "対象 空白"
    root.mkdir()
    if state != "empty":
        _ = write_source(root, "正常.py", "def 計算():\n    return 1\n")
    if state == "partial":
        _ = write_source(root, "不正.py", "def broken(:\n")
    if state == "unresolved":
        _ = write_source(
            root, "dynamic.py", "import importlib\nimportlib.import_module(input())\n"
        )
    args: list[str | Path] = [command, root]
    if command == "compare":
        args.append(root)
    if state == "incompatible":
        before = cli.analyze(root)
        after = copy.deepcopy(before)
        for model in after["metadata"]["measurement_models"].values():
            model["definition_version"] = "unknown-definition"
        args = [
            "compare",
            "--before-result",
            save_json(cli.cwd / "before.json", before),
            "--after-result",
            save_json(cli.cwd / "after.json", after),
        ]
    return args


def assert_json_report(document: Document, command: str, state: str) -> None:
    expected_count = {
        "normal": 1,
        "empty": 0,
        "partial": 2,
        "unresolved": 2,
        "incompatible": 1,
    }[state]
    assert document["status"] == ("partial" if state == "partial" else "complete")
    analyses = (
        [document] if command == "analyze" else [document["before"], document["after"]]
    )
    for analysis in analyses:
        assert_analysis(analysis, expected_count)
        if state == "partial":
            assert analysis["errors"][0]["code"] == "SYNTAX_ERROR"
        if state == "unresolved":
            assert analysis["unresolved"]
        if state != "empty":
            assert analysis["details"]["functions"][0]["name"] == "計算"
    if command == "compare":
        assert document["type"] == "comparison"
        assert isinstance(document["metadata"]["settings"], dict)
        assert "differences" in document
        assert "incompatible_metrics" in document
        if state == "incompatible":
            assert not document["differences"] or not any(
                document["differences"].values()
            )
            assert all(item["reason"] for item in document["incompatible_metrics"])


def assert_text_report(report: str, state: str, format_name: str | None) -> None:
    assert ("partial" if state == "partial" else "complete") in report
    assert "対象 空白" in report
    assert "\x1b[" not in report
    if state == "partial":
        assert "SYNTAX_ERROR" in report
        assert "不正.py" in report
    if state == "empty":
        assert "N/A" in report
        assert re.search(r"\b0\b", report)
        if format_name == "markdown":
            assert "—" in report
    if state == "unresolved":
        assert "dynamic.py" in report
        assert re.search(r"unresolved|未解決", report, re.IGNORECASE)
    if state == "incompatible":
        assert re.search(r"incompatible|比較不能|互換", report, re.IGNORECASE)
    if format_name == "markdown":
        assert "|" in report


@pytest.mark.parametrize("command", ["analyze", "compare"])
@pytest.mark.parametrize(("format_name", "extension"), [("json", "md"), (None, "json")])
def test_output_success_extension_does_not_choose_format(
    *, cli: CLI, source: Path, command: str, format_name: str | None, extension: str
) -> None:
    """CLI-O04: 出力形式は拡張子によって推測しない。"""
    args: list[str | Path] = [command, source]
    if command == "compare":
        args.append(source)
    if format_name is not None:
        args += ["--format", format_name]
    output = cli.cwd / f"report.{extension}"
    process = cli.run(*args, "--output", output)
    assert process.returncode == 0, process.stderr
    assert process.stdout == ""
    text = output.read_text(encoding="utf-8")
    if format_name == "json":
        assert json.loads(text)["status"] == "complete"
    else:
        assert "complete" in text
        with pytest.raises(json.JSONDecodeError):
            _ = json.loads(text)


@pytest.mark.parametrize("format_name", ["console", "markdown", "json"])
@pytest.mark.parametrize(
    ("value", "display"), [(1.234, "1.23"), (1.235, "1.24"), (1.236, "1.24")]
)
def test_output_success_rounding(
    *, cli: CLI, source: Path, format_name: str, value: float, display: str
) -> None:
    """CLI-O09〜O10: JSON保持精度と人間向け四捨五入を区別する。"""
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    for document in (before, after):
        document["metrics"]["function_length"]["average"] = value
    first = save_json(cli.cwd / "before.json", before)
    second = save_json(cli.cwd / "after.json", after)
    process = cli.run(
        "compare",
        "--before-result",
        first,
        "--after-result",
        second,
        "--format",
        format_name,
    )
    assert process.returncode == 0, process.stderr
    if format_name == "json":
        assert (
            json.loads(process.stdout)["differences"]["function_length"]["average"][
                "before"
            ]
            == value
        )
    else:
        assert display in process.stdout
        assert str(value) not in process.stdout
    assert json.loads(first.read_text(encoding="utf-8")) == before
    assert json.loads(second.read_text(encoding="utf-8")) == after


@pytest.mark.parametrize("format_name", ["console", "markdown"])
def test_output_success_percentage_units(
    *, cli: CLI, source: Path, format_name: str
) -> None:
    """CLI-O10: 割合の差分は-5pt、変化率は-33.33%で表す。"""
    before = cli.analyze(source)
    after = copy.deepcopy(before)
    before["metrics"]["duplication_rate"]["value"] = 15
    after["metrics"]["duplication_rate"]["value"] = 10
    process = cli.run(
        "compare",
        "--before-result",
        save_json(cli.cwd / "before.json", before),
        "--after-result",
        save_json(cli.cwd / "after.json", after),
        "--format",
        format_name,
    )
    assert process.returncode == 0, process.stderr
    assert re.search(r"-5(?:\.0{1,2})?\s*pt", process.stdout)
    assert re.search(r"-33\.33\s*%", process.stdout)


@pytest.mark.parametrize("command", ["analyze", "compare"])
@pytest.mark.parametrize(
    "failure", ["missing_parent", "denied_directory", "existing_denied_file"]
)
def test_output_failure_preserves_existing(
    *, cli: CLI, source: Path, command: str, failure: str
) -> None:
    """CLI-O16〜O17: 実OSの保存失敗でstdoutは空、既存ファイルは維持。"""
    directory = cli.cwd / "output"
    directory.mkdir()
    output = directory / "report.json"
    original = None
    protected = None
    if failure == "missing_parent":
        output = directory / "missing" / "report.json"
    elif failure == "denied_directory":
        protected = directory
        original = deny_access(directory, "write")
    else:
        _ = output.write_text("existing report", encoding="utf-8")
        # 原子的置換でも失敗するよう、親ディレクトリの書き込みも禁止する。
        protected = directory
        original = deny_access(directory, "write")
    args = (command, source) if command == "analyze" else (command, source, source)
    try:
        process = cli.run(*args, "--format", "json", "--output", output)
        assert_input_error(process)
        assert process.stdout == ""
    finally:
        if protected is not None and original is not None:
            protected.chmod(original)
    if failure == "existing_denied_file":
        assert output.read_text(encoding="utf-8") == "existing report"


def reverse_keys(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: reverse_keys(item)
            for key, item in reversed(list(cast("dict[str, object]", value).items()))
        }
    if isinstance(value, list):
        return [reverse_keys(item) for item in cast("list[object]", value)]
    return value


@pytest.mark.parametrize("state", ["normal", "partial", "unresolved"])
def test_output_success_reordered_json_roundtrip(
    *, cli: CLI, tmp_path: Path, state: str
) -> None:
    """CLI-O18: キー順変更後も保存値・条件・詳細・失敗・未解決を保持。"""
    root = tmp_path / "src"
    _ = write_source(root, "main.py", "class C:\n    def f(self): return 1\n")
    if state == "partial":
        _ = write_source(root, "broken.py", "def broken(:\n")
    if state == "unresolved":
        _ = write_source(
            root, "dynamic.py", "import importlib\nimportlib.import_module(input())\n"
        )
    output = tmp_path / "saved.json"
    process = cli.run("analyze", root, "--format", "json", "--output", output)
    assert (
        (process.returncode != 0) if state == "partial" else (process.returncode == 0)
    ), process.stderr
    assert process.stdout == ""
    saved = json.loads(output.read_text(encoding="utf-8"))
    reordered = tmp_path / "reordered.json"
    _ = reordered.write_text(
        json.dumps(reverse_keys(saved), ensure_ascii=False), encoding="utf-8"
    )
    result = cli.json(
        "compare",
        "--before-result",
        output,
        "--after-result",
        reordered,
        partial=state == "partial",
    )
    assert result["before"] == result["after"] == saved


def test_output_success_omits_inapplicable_fields(*, cli: CLI, source: Path) -> None:
    """CLI-O22: 適用外集計・不要なdetailsを省き、計測不能nullは保持。"""
    _ = source.write_text("x = 1\n", encoding="utf-8")
    result = cli.analyze(source)
    assert set(result["metrics"]["sloc"]) <= {"total", "unavailable_reason"}
    assert result["metrics"]["sloc"]["total"] == 1
    complexity = result["metrics"]["cyclomatic_complexity"]
    assert complexity["total"] == 0
    assert complexity["average"] is None
    assert complexity["maximum"] is None
    assert complexity["unavailable_reason"]
    assert "details" not in complexity
