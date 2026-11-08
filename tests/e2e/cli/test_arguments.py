"""CLI-V01〜V04: 不正なコマンド指定を黙って受け入れない。"""

from typing import TYPE_CHECKING

import pytest

from .support import CLI, assert_input_error

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "args",
    [
        ("unknown",),
        ("analyze", "SOURCE", "--unknown"),
        ("compare", "SOURCE", "SOURCE", "--unknown"),
        ("analyze",),
        ("analyze", "SOURCE", "--exclude"),
        ("analyze", "SOURCE", "--format"),
        ("analyze", "SOURCE", "--output"),
        ("compare", "SOURCE", "SOURCE", "--exclude"),
        ("compare", "SOURCE", "SOURCE", "--format"),
        ("compare", "SOURCE", "SOURCE", "--output"),
        ("compare", "SOURCE", "--before-result"),
        ("compare", "SOURCE", "--after-result"),
        ("analyze", "SOURCE", "SOURCE"),
        ("compare", "SOURCE", "SOURCE", "SOURCE"),
        ("analyze", "SOURCE", "--format", "yaml"),
        ("compare", "SOURCE", "SOURCE", "--format", "yaml"),
    ],
)
def test_command_failure_invalid_arguments(
    *, cli: CLI, source: Path, args: tuple[str, ...]
) -> None:
    """CLI-V01〜V04: 未知の指定・引数や値の不足・余剰・未対応形式は異常終了。"""
    assert_input_error(cli.run(*(source if arg == "SOURCE" else arg for arg in args)))
