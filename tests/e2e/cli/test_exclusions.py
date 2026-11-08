"""CLI-E01〜E09、PE01〜PE05: 選択条件は各ソースに独立して適用する。"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from .support import (
    CLI,
    assert_input_error,
    assert_metric,
    file_names,
    save_json,
    write_source,
)


@pytest.mark.parametrize(
    ("patterns", "remaining"),
    [
        (("*.py",), {"child.py", "deep.py", "nested.py"}),
        (("**/*.py",), set[str]()),
        (("**/generated/*.py",), {"root.py", "child.py", "deep.py"}),
        (("*.py", "**/generated/*.py", "generated/*.py"), {"child.py", "deep.py"}),
        (("sub",), {"root.py"}),
    ],
)
def test_analyze_success_exclude_globs(
    *, cli: CLI, tmp_path: Path, patterns: tuple[str, ...], remaining: set[str]
) -> None:
    """CLI-E01〜E04: glob・重複条件・ディレクトリ除外はcwdに依存しない。"""
    root = tmp_path / "project"
    for name in (
        "root.py",
        "sub/child.py",
        "sub/deeper/deep.py",
        "sub/generated/nested.py",
    ):
        _ = write_source(root, name)
    options = [arg for pattern in patterns for arg in ("--exclude", pattern)]
    result = cli.analyze(root, *options)
    assert file_names(result) == remaining
    assert result["scope"]["file_count"] == len(remaining)
    assert_metric(result["metrics"], "sloc", total=len(remaining))
    other = tmp_path / "other"
    other.mkdir()
    process = cli.run("analyze", root, *options, "--format", "json", cwd=other)
    assert process.returncode == 0, process.stderr
    assert file_names(json.loads(process.stdout)) == remaining


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
def test_analyze_success_gitignore(
    *,
    cli: CLI,
    rules: str,
    child_rules: str,
    remaining: set[str],
    use_gitignore: bool,
) -> None:
    """CLI-E05〜E06: 親・対象・子のignore、否定規則、親除外を検証。"""
    parent = cli.cwd / "repo"
    root = parent / "project"
    _ = write_source(parent, ".gitignore", "parent_ignored.py\n")
    _ = write_source(root, ".gitignore", rules)
    _ = write_source(root, "child/.gitignore", child_rules)
    for name in ("keep.py", "drop.py", "parent_ignored.py", "child/nested.py"):
        _ = write_source(root, name)
    options = ("--use-gitignore",) if use_gitignore else ()
    result = cli.analyze(root, *options)
    expected = (
        remaining
        if use_gitignore
        else {"keep.py", "drop.py", "parent_ignored.py", "nested.py"}
    )
    assert file_names(result) == expected
    assert result["scope"]["file_count"] == len(expected)


def test_analyze_success_ignores_git_private_rules(*, cli: CLI, tmp_path: Path) -> None:
    """CLI-E07: 未追跡ファイルを含め、info/exclude・global規則は使わない。"""
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git規則を隔離する一時リポジトリの作成にgitが必要")
    root = tmp_path / "repo"
    root.mkdir()
    process = subprocess.run(  # noqa: S603 -- 一時リポジトリのgit init。
        [git, "init", str(root)],
        env=cli.env,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert process.returncode == 0, process.stderr
    _ = write_source(root, ".git/info/exclude", "private.py\n")
    global_ignore = write_source(tmp_path, "global-ignore", "global.py\n")
    _ = write_source(
        Path(cli.env["HOME"]),
        ".gitconfig",
        f"[core]\n    excludesFile = {global_ignore}\n",
    )
    for name in ("private.py", "global.py", "untracked.py"):
        _ = write_source(root, name)
    result = cli.analyze(root, "--use-gitignore")
    assert file_names(result) == {"private.py", "global.py", "untracked.py"}


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_analyze_success_explicit_exclude_wins(
    *, cli: CLI, tmp_path: Path, use_gitignore: bool
) -> None:
    """CLI-E08: ignoreの否定規則も明示除外を上書きしない。"""
    _ = write_source(tmp_path, ".gitignore", "*.py\n!keep.py\n")
    _ = write_source(tmp_path, "keep.py")
    _ = write_source(tmp_path, "other.py")
    options = ["--exclude", "keep.py"]
    if use_gitignore:
        options.append("--use-gitignore")
    result = cli.analyze(tmp_path, *options)
    assert file_names(result) == (set() if use_gitignore else {"other.py"})


def test_analyze_success_excluded_files_do_not_affect_metrics(
    *, cli: CLI, tmp_path: Path
) -> None:
    """CLI-E09: 除外後の集合で重複・循環・エラー・合計を計測する。"""
    block = "".join(f"value_{i} = {i}\n" for i in range(20))
    _ = write_source(tmp_path, "a.py", "import b\n" + block)
    _ = write_source(tmp_path, "b.py", "import a\n" + block)
    _ = write_source(tmp_path, "broken.py", "def broken(:\n")
    result = cli.analyze(tmp_path, "--exclude", "b.py", "--exclude", "broken.py")
    assert file_names(result) == {"a.py"}
    assert not result["errors"]
    assert_metric(result["metrics"], "sloc", total=21)
    assert_metric(result["metrics"], "duplication_rate", value=0)
    assert_metric(result["metrics"], "dependency_cycles", value=0)
    assert_metric(result["metrics"], "fan_out", average=1, maximum=1)


@pytest.mark.parametrize("use_gitignore", [False, True])
def test_compare_success_selection_for_each_source(
    *, cli: CLI, tmp_path: Path, use_gitignore: bool
) -> None:
    """CLI-PE01〜PE02: 各側の基準位置と親・子のignoreを独立評価。"""
    roots = [tmp_path / side / "src" for side in ("before", "after")]
    for index, root in enumerate(roots):
        _ = write_source(root.parent, ".gitignore", f"ignored_{index}.py\n*.tmp\n")
        _ = write_source(root, "child/.gitignore", "*.py\n!keep.py\n")
        for name in (
            "keep.py",
            f"ignored_{index}.py",
            "child/keep.py",
            "child/drop.py",
            "generated/remove.py",
            "test_skip.py",
        ):
            _ = write_source(root, name)
    options = ["--exclude", "**/generated/*.py", "--exclude", "test_*.py"]
    if use_gitignore:
        options.append("--use-gitignore")
    result = cli.json("compare", *roots, *options)
    for index, side in enumerate(("before", "after")):
        analysis = result[side]
        assert analysis["scope"]["file_count"] == (2 if use_gitignore else 4)
        assert file_names(analysis) == (
            {"keep.py"}
            if use_gitignore
            else {"keep.py", "drop.py", f"ignored_{index}.py"}
        )


@pytest.mark.parametrize("saved_side", ["before", "after"])
@pytest.mark.parametrize(
    "options",
    [
        ("--exclude", "drop.py"),
        ("--use-gitignore",),
        ("--exclude", "drop.py", "--use-gitignore"),
    ],
)
def test_compare_success_selection_only_source(
    *, cli: CLI, tmp_path: Path, saved_side: str, options: tuple[str, ...]
) -> None:
    """CLI-PE03: 混在入力の選択条件は保存済みの値・条件に作用しない。"""
    root = tmp_path / "project"
    _ = write_source(root, ".gitignore", "drop.py\n")
    _ = write_source(root, "keep.py")
    _ = write_source(root, "drop.py")
    saved = cli.analyze(root)
    path = save_json(tmp_path / "saved.json", saved)
    result = cli.json("compare", root, f"--{saved_side}-result", path, *options)
    source_side = "after" if saved_side == "before" else "before"
    assert result[saved_side] == saved
    assert file_names(result[source_side]) == {"keep.py"}
    assert result[source_side]["scope"]["file_count"] == 1
    assert path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "options",
    [
        ("--exclude", "*.py"),
        ("--use-gitignore",),
        ("--exclude", "*.py", "--use-gitignore"),
    ],
)
def test_compare_failure_selection_without_source(
    *, cli: CLI, source: Path, options: tuple[str, ...]
) -> None:
    """CLI-PE04: 両側保存JSONと解析オプションの併用は入力エラー。"""
    saved = save_json(cli.cwd / "saved.json", cli.analyze(source))
    assert_input_error(
        cli.run("compare", "--before-result", saved, "--after-result", saved, *options)
    )


@pytest.mark.parametrize("exclude_all", [False, True])
def test_compare_success_excluding_syntax_error(
    *, cli: CLI, tmp_path: Path, exclude_all: bool
) -> None:
    """CLI-PE05: 選択後の空結果・構文不正の除外はcompleteで比較する。"""
    _ = write_source(tmp_path, "good.py")
    _ = write_source(tmp_path, "broken.py", "def broken(:\n")
    result = cli.json(
        "compare",
        tmp_path,
        tmp_path,
        "--exclude",
        "**/*.py" if exclude_all else "broken.py",
    )
    for side in ("before", "after"):
        assert result[side]["scope"]["file_count"] == (0 if exclude_all else 1)
        assert not result[side]["errors"]
