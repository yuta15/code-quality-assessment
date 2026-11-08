"""API-E01〜E13: 公開analyzeの除外条件。"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .support import assert_metric, file_names, write_source

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize(
    ("patterns", "remaining"),
    [
        (
            ("*.py",),
            {
                "child.py",
                "deep.py",
                "generated_root.py",
                "generated_child.py",
                "generated_deep.py",
            },
        ),
        (("**/*.py",), set[str]()),
        (("**/generated/*.py",), {"root.py", "child.py", "deep.py"}),
        (("*.py", "**/generated/*.py", "generated/*.py"), {"child.py", "deep.py"}),
        (("sub",), {"root.py", "generated_root.py"}),
    ],
)
def test_analyze_success_globs(
    *, api: ModuleType, tmp_path: Path, patterns: tuple[str, ...], remaining: set[str]
) -> None:
    """API-E01〜E03: globの階層・ゼロ階層・複数条件・ディレクトリ除外。"""
    for name in (
        "root.py",
        "sub/child.py",
        "sub/deep/deep.py",
        "generated/generated_root.py",
        "sub/generated/generated_child.py",
        "sub/deep/generated/generated_deep.py",
    ):
        _ = write_source(tmp_path, name)
    result = api.analyze(tmp_path, exclude=patterns)
    assert result.scope.file_count == len(remaining)
    assert file_names(result) == remaining
    assert_metric(result.metrics, "sloc", total=len(remaining))


def test_analyze_success_exclude_independent_of_cwd(
    *, api: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API-E04: globの基準はcwdでなく解析対象ディレクトリ。"""
    root = tmp_path / "project"
    _ = write_source(root, "main.py")
    _ = write_source(root, "sub/keep.py")
    first = api.analyze(root, exclude=("*.py",))
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    second = api.analyze(root, exclude=("*.py",))
    assert file_names(first) == file_names(second) == {"keep.py"}
    assert first.metrics == second.metrics


@pytest.mark.parametrize(
    ("rules", "child_rules", "remaining"),
    [
        ("drop.py\n", "", {"keep.py", "nested.py"}),
        ("*.py\n!keep.py\n", "", {"keep.py"}),
        ("*.py\n", "!nested.py\n", {"nested.py"}),
        ("child/\n!child/nested.py\n", "", {"keep.py", "drop.py"}),
    ],
)
@pytest.mark.parametrize("use_gitignore", [False, True])
def test_analyze_success_gitignore(  # noqa: PLR0913 -- fixturesとignoreの独立した条件。
    *,
    api: ModuleType,
    rules: str,
    child_rules: str,
    remaining: set[str],
    use_gitignore: bool,
    tmp_path: Path,
) -> None:
    """API-E05〜E09: 親・対象・子の規則、否定規則、親の除外を確認。"""
    root = tmp_path / "repo/project"
    _ = write_source(root.parent, ".gitignore", "parent_ignored.py\n")
    _ = write_source(root, ".gitignore", rules)
    _ = write_source(root, "child/.gitignore", child_rules)
    for name in ("keep.py", "drop.py", "parent_ignored.py", "child/nested.py"):
        _ = write_source(root, name)
    result = api.analyze(root, use_gitignore=use_gitignore)
    assert file_names(result) == (
        remaining
        if use_gitignore
        else {"keep.py", "drop.py", "parent_ignored.py", "nested.py"}
    )
    if not use_gitignore:
        default = api.analyze(root)
        explicit = api.analyze(root, exclude=(), use_gitignore=False)
        assert default.metrics == explicit.metrics == result.metrics
        assert file_names(default) == file_names(explicit) == file_names(result)


def test_analyze_success_git_private_rules_not_applied(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-E10〜E11: 未追跡ファイルを含め、info/excludeとglobal規則を無視。"""
    git = shutil.which("git")
    if git is None:
        pytest.skip("隔離したGitリポジトリの作成にgitが必要")
    root = tmp_path / "repo"
    root.mkdir()
    process = subprocess.run(  # noqa: S603 -- 実プロセスによるE2E検証。
        [git, "init", str(root)], capture_output=True, timeout=10, check=False
    )
    assert process.returncode == 0, process.stderr
    _ = write_source(root, ".git/info/exclude", "private.py\n")
    global_ignore = write_source(tmp_path, "global-ignore", "global.py\n")
    _ = write_source(
        Path(os.environ["HOME"]),
        ".gitconfig",
        f"[core]\n    excludesFile = {global_ignore}\n",
    )
    for name in ("private.py", "global.py", "untracked.py"):
        _ = write_source(root, name)
    assert file_names(api.analyze(root, use_gitignore=True)) == {
        "private.py",
        "global.py",
        "untracked.py",
    }


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_analyze_success_explicit_exclude_wins(
    *, api: ModuleType, tmp_path: Path, use_gitignore: bool
) -> None:
    """API-E12: ignoreの否定規則も明示除外を上書きしない。"""
    _ = write_source(tmp_path, ".gitignore", "*.py\n!keep.py\n")
    _ = write_source(tmp_path, "keep.py")
    _ = write_source(tmp_path, "other.py")
    result = api.analyze(tmp_path, exclude=("keep.py",), use_gitignore=use_gitignore)
    assert file_names(result) == (set() if use_gitignore else {"other.py"})


def test_analyze_success_excluded_metrics(*, api: ModuleType, tmp_path: Path) -> None:
    """API-E13: 除外後の集合で重複・循環・エラー・合計を計測する。"""
    block = "".join(f"value_{i} = {i}\n" for i in range(20))
    _ = write_source(tmp_path, "a.py", "import b\n" + block)
    _ = write_source(tmp_path, "b.py", "import a\n" + block)
    _ = write_source(tmp_path, "broken.py", "def broken(:\n")
    result = api.analyze(tmp_path, exclude=("b.py", "broken.py"))
    assert result.status == "complete"
    assert file_names(result) == {"a.py"}
    assert result.errors == []
    assert_metric(result.metrics, "sloc", total=21)
    assert_metric(result.metrics, "duplication_rate", value=0)
    assert_metric(result.metrics, "dependency_cycles", value=0)
    assert_metric(result.metrics, "fan_out", average=1, maximum=1)
