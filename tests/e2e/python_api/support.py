"""公開モデルの属性と仕様に基づく期待値を検証する補助処理。"""

from pathlib import Path
from typing import Any

import pytest

from tests.e2e.cli.support import SCOPE_FIELDS, deny_access, save_json, write_source

__all__ = [
    "SCOPE_FIELDS",
    "assert_empty",
    "assert_metric",
    "deny_access",
    "file_names",
    "save_json",
    "single",
    "write_source",
]

# 未実装の公開パッケージはfixtureで遅延importし、モデル型は専用テストで検証する。
type PublicModel = Any


def assert_metric(
    metrics: dict[str, PublicModel], name: str, **expected: float | None
) -> None:
    for field, value in expected.items():
        actual = getattr(metrics[name], field)
        if value is None:
            assert actual is None
            assert metrics[name].unavailable_reason
        else:
            assert type(actual) in (int, float)
            assert actual == pytest.approx(value)


def single(result: PublicModel, collection: str, name: str) -> PublicModel:
    matches = [
        item for item in getattr(result.details, collection) if item.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def file_names(result: PublicModel) -> set[str]:
    return {Path(item.path).name for item in result.details.files}


def assert_empty(result: PublicModel) -> None:
    assert result.status == "complete"
    assert result.scope.file_count == 0
    assert result.details.files == []
    assert result.details.classes == []
    assert result.details.functions == []
    for metric, fields in SCOPE_FIELDS.items():
        for field in fields:
            value = 0 if field == "total" or metric == "dependency_cycles" else None
            assert_metric(result.metrics, metric, **{field: value})
