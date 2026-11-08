"""API-A01〜A15/M07: 公開入口の入力・状態・例外・副作用。"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .support import assert_empty, assert_metric, deny_access, file_names, write_source

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize("as_string", [False, True])
def test_analyze_success_path_types(
    *, api: ModuleType, source: Path, as_string: bool
) -> None:
    """API-A01/A05: str・Pathと日本語・空白入りパスを受け付ける。"""
    result = api.analyze(str(source) if as_string else source)
    assert result.status == "complete"
    assert result.scope.file_count == 1
    assert file_names(result) == {source.name}
    assert_metric(result.metrics, "sloc", total=2)
    assert_metric(result.metrics, "function_count", total=1)
    assert len(result.details.functions) == 1


def test_analyze_success_recursive_selection(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-A02: 孫階層までPythonだけを探索して集計する。"""
    for name in ("a.py", "child/b.py", "child/grand/c.py", "notes.txt"):
        _ = write_source(tmp_path, name)
    result = api.analyze(tmp_path)
    assert result.scope.file_count == len({"a.py", "b.py", "c.py"})
    assert file_names(result) == {"a.py", "b.py", "c.py"}
    assert_metric(result.metrics, "sloc", total=3)


def test_analyze_success_ignores_symlinks(*, api: ModuleType, tmp_path: Path) -> None:
    """API-A03: ファイル・ディレクトリ・循環リンクを追跡しない。"""
    actual = write_source(tmp_path, "project/real.py")
    outside = write_source(tmp_path, "outside/hidden.py")
    root = actual.parent
    try:
        (root / "alias.py").symlink_to(actual)
        (root / "linked").symlink_to(outside.parent, target_is_directory=True)
        (root / "cycle").symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"リンクを作成できない環境: {error}")
    result = api.analyze(root)
    assert result.scope.file_count == 1
    assert file_names(result) == {"real.py"}


@pytest.mark.parametrize("relative", [False, True])
def test_analyze_success_other_cwd(
    *, api: ModuleType, source: Path, monkeypatch: pytest.MonkeyPatch, relative: bool
) -> None:
    """API-A04: 異なるcwdから相対・絶対パスで同じ値を取得する。"""
    expected = api.analyze(source)
    other = source.parent.parent / "other"
    other.mkdir()
    target = os.path.relpath(source, other) if relative else source
    monkeypatch.chdir(other)
    actual = api.analyze(target)
    assert actual.metrics == expected.metrics
    assert actual.scope.file_count == expected.scope.file_count == 1
    assert file_names(actual) == file_names(expected)


@pytest.mark.parametrize("kind", ["empty", "unsupported", "excluded"])
def test_analyze_success_empty_scope(
    *, api: ModuleType, tmp_path: Path, kind: str
) -> None:
    """API-A06: 対象なしは0/nullと理由を持つcomplete。"""
    if kind == "unsupported":
        _ = write_source(tmp_path, "notes.txt")
    if kind == "excluded":
        _ = write_source(tmp_path, "main.py")
    result = api.analyze(tmp_path, exclude=("**/*.py",) if kind == "excluded" else ())
    assert_empty(result)


def test_analyze_success_empty_file(*, api: ModuleType, tmp_path: Path) -> None:
    """API-A07: 空ファイル1件と対象0件を区別する。"""
    result = api.analyze(write_source(tmp_path, "empty.py", ""))
    assert result.scope.file_count == 1
    assert file_names(result) == {"empty.py"}
    assert_metric(result.metrics, "sloc", total=0)
    assert_metric(result.metrics, "duplication_rate", value=None)


@pytest.mark.parametrize(
    ("kind", "exception"),
    [
        ("missing", FileNotFoundError),
        ("denied", PermissionError),
        ("unsupported", ValueError),
    ],
)
def test_analyze_failure_target(
    *, api: ModuleType, tmp_path: Path, kind: str, exception: type[Exception]
) -> None:
    """API-A08〜A10: 存在しない・アクセス不可・非対応の対象は規定例外。"""
    path = tmp_path / ("target.txt" if kind == "unsupported" else "target.py")
    original = None
    if kind != "missing":
        _ = path.write_text("x = 1\n", encoding="utf-8")
    if kind == "denied":
        original = deny_access(path, "read")
    try:
        with pytest.raises(exception):
            _ = api.analyze(path)
    finally:
        if original is not None:
            path.chmod(original)


@pytest.mark.parametrize("failures", [("syntax",), ("read",), ("syntax", "read")])
def test_analyze_failure_partial(
    *, api: ModuleType, tmp_path: Path, failures: tuple[str, ...]
) -> None:
    """API-A11〜A13/M07: 全成功分と各失敗を保持し、選択件数に失敗分も含む。"""
    _ = write_source(tmp_path, "good.py")
    _ = write_source(tmp_path, "another.py", "y = 2\nz = 3\n")
    expected: dict[str, str] = {}
    unreadable = None
    original = None
    if "syntax" in failures:
        _ = write_source(tmp_path, "broken.py", "def broken(:\n")
        expected["broken.py"] = "SYNTAX_ERROR"
    if "read" in failures:
        unreadable = write_source(tmp_path, "unreadable.py")
        original = deny_access(unreadable, "read")
        expected["unreadable.py"] = "FILE_READ_ERROR"
    try:
        result = api.analyze(tmp_path)
        assert result.status == "partial"
        assert result.scope.file_count == 2 + len(failures)
        assert file_names(result) == {"good.py", "another.py"}
        assert_metric(result.metrics, "sloc", total=3)
        assert {
            Path(error.path).name: error.code for error in result.errors
        } == expected
        assert all(error.message for error in result.errors)
    finally:
        if unreadable is not None and original is not None:
            unreadable.chmod(original)


@pytest.mark.parametrize("location", ["module", "decorator", "class"])
def test_analyze_success_no_execution(
    *, api: ModuleType, tmp_path: Path, location: str
) -> None:
    """API-A14: モジュール・デコレータ・クラス本体の実行もソース変更もしない。"""
    marker = tmp_path / "executed"
    operation = f"Path({str(marker)!r}).touch()\n"
    bodies = {
        "module": operation,
        "class": "class C:\n    " + operation,
        "decorator": "def decorate(fn):\n    "
        + operation
        + "    raise RuntimeError()\n@decorate\ndef f(): pass\n",
    }
    path = write_source(
        tmp_path, "side_effect.py", "from pathlib import Path\n" + bodies[location]
    )
    before = path.read_bytes()
    result = api.analyze(path)
    assert result.status == "complete"
    assert not marker.exists()
    assert path.read_bytes() == before


def test_analyze_success_reproducible(*, api: ModuleType, source: Path) -> None:
    """API-A15: 別対象を解析しても同じ条件の計測値が再現する。"""
    first = api.analyze(source)
    _ = api.analyze(
        write_source(source.parent.parent, "other.py", "class Other: pass\n")
    )
    last = api.analyze(source)
    assert first.metrics == last.metrics
    assert first.scope.file_count == last.scope.file_count == 1
