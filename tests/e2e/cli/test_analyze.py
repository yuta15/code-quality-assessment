"""CLI-A01〜A13: 対象選択、状態、診断、副作用。"""

import json
import os
from pathlib import Path

import pytest

from .support import (
    CLI,
    assert_analysis,
    assert_empty,
    assert_input_error,
    assert_metric,
    deny_access,
    file_names,
    write_source,
)


def test_analyze_success_single_file(*, cli: CLI, source: Path) -> None:
    """CLI-A01: 単一ファイルの計測値と実際の詳細をJSONで返す。"""
    result = cli.analyze(source)
    assert_analysis(result, 1)
    assert file_names(result) == {source.name}
    assert_metric(result["metrics"], "sloc", total=2)
    assert_metric(result["metrics"], "function_count", total=1)
    assert len(result["details"]["functions"]) == 1


def test_analyze_success_recursive_selection(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-A02: 非対応ファイルを除き孫ディレクトリまで探索する。"""
    root = tmp_path / "project"
    for name in ("a.py", "child/b.py", "child/grand/c.py", "notes.txt"):
        _ = write_source(root, name)
    result = cli.analyze(root)
    assert_analysis(result, 3)
    assert file_names(result) == {"a.py", "b.py", "c.py"}
    assert_metric(result["metrics"], "sloc", total=3)


def test_analyze_success_ignores_symlinks(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-A03: ファイル・ディレクトリ・循環リンクを追跡しない。"""
    root = tmp_path / "project"
    actual = write_source(root, "real.py")
    outside = write_source(tmp_path, "outside/hidden.py")
    try:
        (root / "alias.py").symlink_to(actual)
        (root / "linked").symlink_to(outside.parent, target_is_directory=True)
        (root / "cycle").symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"シンボリックリンクを作成できない環境: {error}")
    result = cli.analyze(root)
    assert_analysis(result, 1)
    assert file_names(result) == {"real.py"}


@pytest.mark.parametrize("relative", [False, True])
def test_analyze_success_path_and_cwd(
    *, cli: CLI, source: Path, relative: bool
) -> None:
    """CLI-A04: 非ASCII・空白入りパスを異なるcwdから指定できる。"""
    other = cli.cwd / "other"
    other.mkdir()
    target = os.path.relpath(source, other) if relative else source
    process = cli.run("analyze", target, "--format", "json", cwd=other)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert_analysis(result, 1)
    assert_metric(result["metrics"], "sloc", total=2)
    assert result["metrics"] == cli.analyze(source)["metrics"]


@pytest.mark.parametrize("kind", ["empty", "unsupported", "excluded"])
def test_analyze_success_no_targets(*, cli: CLI, tmp_path: Path, kind: str) -> None:
    """CLI-A05: 対象なしは0/nullを持つcompleteで、stdoutは単独JSON。"""
    root = tmp_path / "project"
    root.mkdir()
    options: tuple[str, ...] = ()
    if kind == "unsupported":
        _ = write_source(root, "notes.txt")
    if kind == "excluded":
        _ = write_source(root, "main.py")
        options = ("--exclude", "**/*.py")
    assert_empty(cli.analyze(root, *options))


def test_analyze_success_empty_file(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-A06: 空ファイル1件は対象0件と区別する。"""
    result = cli.analyze(write_source(tmp_path, "empty.py", ""))
    assert_analysis(result, 1)
    assert file_names(result) == {"empty.py"}
    assert_metric(result["metrics"], "sloc", total=0)
    assert_metric(result["metrics"], "duplication_rate", value=None)


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("missing", "TARGET_NOT_FOUND"),
        ("unsupported", "UNSUPPORTED_FILE_TYPE"),
        ("denied", "TARGET_ACCESS_DENIED"),
    ],
)
def test_analyze_failure_target(
    *, cli: CLI, tmp_path: Path, kind: str, code: str
) -> None:
    """CLI-A07: 致命的な対象エラーを対象パスとともにstderrへ出す。"""
    path = tmp_path / (
        "missing.py"
        if kind == "missing"
        else "target.txt"
        if kind == "unsupported"
        else "target.py"
    )
    original = None
    if kind != "missing":
        _ = path.write_text("x = 1\n", encoding="utf-8")
    if kind == "denied":
        original = deny_access(path, "read")
    try:
        process = cli.run("analyze", path, "--format", "json")
        assert_input_error(process)
        assert code in process.stderr
        assert path.name in process.stderr
    finally:
        if original is not None:
            path.chmod(original)


@pytest.mark.parametrize("failures", [("syntax",), ("read",), ("syntax", "read")])
def test_analyze_failure_partial(
    *, cli: CLI, tmp_path: Path, failures: tuple[str, ...]
) -> None:
    """CLI-A08〜A10: 全正常ファイルを集計し、複数の失敗を保持する。"""
    root = tmp_path / "project"
    _ = write_source(root, "good.py")
    _ = write_source(root, "another.py", "y = 2\nz = 3\n")
    expected: dict[str, str] = {}
    unreadable = None
    original = None
    if "syntax" in failures:
        _ = write_source(root, "broken.py", "def broken(:\n")
        expected["broken.py"] = "SYNTAX_ERROR"
    if "read" in failures:
        unreadable = write_source(root, "unreadable.py")
        original = deny_access(unreadable, "read")
        expected["unreadable.py"] = "FILE_READ_ERROR"
    try:
        result = cli.analyze(root, partial=True)
        assert_analysis(result, 2 + len(failures))
        assert file_names(result) == {"good.py", "another.py"}
        assert_metric(result["metrics"], "sloc", total=3)
        assert {Path(e["path"]).name: e["code"] for e in result["errors"]} == expected
        assert all(e["message"] for e in result["errors"])
    finally:
        if unreadable is not None and original is not None:
            unreadable.chmod(original)


def test_analyze_success_unresolved(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-A11: 動的importは未解決として保持し、ファイル解析はcomplete。"""
    path = write_source(
        tmp_path,
        "dynamic.py",
        "import importlib\nname = input()\nimportlib.import_module(name)\n",
    )
    result = cli.analyze(path)
    assert result["unresolved"]
    file_id = result["details"]["files"][0]["id"]
    assert any(
        u["metric"] == "fan_out" and u["target"] == file_id and u["reason"]
        for u in result["unresolved"]
    )
    assert_metric(result["metrics"], "fan_out", average=1, maximum=1)


def test_analyze_success_does_not_execute_source(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-A12: モジュール・デコレータ・クラス本体を実行せず入力を維持。"""
    marker = tmp_path / "executed"
    touch = f"    Path({str(marker)!r}).touch()\n"
    source = (
        "from pathlib import Path\n"
        + touch.lstrip()
        + "\ndef decorate(fn):\n"
        + touch
        + "    return fn\n\n@decorate\ndef f():\n    pass\n\nclass C:\n"
        + touch
    )
    path = write_source(tmp_path, "side_effect.py", source)
    before = path.read_bytes()
    _ = cli.analyze(path)
    assert not marker.exists()
    assert path.read_bytes() == before


def test_analyze_success_reproducible(*, cli: CLI, source: Path) -> None:
    """CLI-A13: 別対象の解析を挟んでも計測値が再現する。"""
    first = cli.analyze(source)
    _ = cli.analyze(write_source(cli.cwd, "other.py", "class Other: pass\n"))
    last = cli.analyze(source)
    assert last["metrics"] == first["metrics"]
