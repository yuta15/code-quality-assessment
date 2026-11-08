"""API-L01〜L06: 保存JSONの読み込みと公開from_dictの構造検証。"""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.e2e.cli.test_compare import corrupt
from tests.e2e.cli.test_output import reverse_keys

from .support import PublicModel, deny_access, save_json

if TYPE_CHECKING:
    from types import ModuleType


@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.parametrize("relative", [False, True])
def test_load_analysis_result_success_paths(
    *,
    api: ModuleType,
    analysis: PublicModel,
    tmp_path: Path,
    as_string: bool,
    relative: bool,
) -> None:
    """API-L01: str・Path、相対・絶対、日本語・空白入り保存先を読み込む。"""
    path = save_json(tmp_path / "保存 結果.json", analysis.to_dict())
    target = Path(os.path.relpath(path)) if relative else path
    result = api.load_analysis_result(str(target) if as_string else target)
    assert asdict(result) == asdict(analysis)


@pytest.mark.parametrize("change", ["delete", "rewrite"])
def test_load_analysis_result_success_no_reanalysis(
    *, api: ModuleType, analysis: PublicModel, tmp_path: Path, change: str
) -> None:
    """API-L02: 元ソース削除・変更とキー順変更後も保存値・条件を復元する。"""
    document = analysis.to_dict()
    path = tmp_path / "saved.json"
    _ = path.write_text(
        json.dumps(reverse_keys(document), ensure_ascii=False), encoding="utf-8"
    )
    for source in (tmp_path / "project").rglob("*.py"):
        if change == "delete":
            source.unlink()
        else:
            _ = source.write_text("class Changed: pass\n", encoding="utf-8")
    result = api.load_analysis_result(path)
    assert asdict(result) == asdict(analysis)


@pytest.mark.parametrize("denied", [False, True])
def test_load_analysis_result_failure_file_access(
    *, api: ModuleType, source: Path, tmp_path: Path, denied: bool
) -> None:
    """API-L03: 存在しない保存先と読み込み不可はそれぞれ規定の例外。"""
    path = tmp_path / "saved.json"
    original = None
    if denied:
        _ = save_json(path, api.analyze(source).to_dict())
        original = deny_access(path, "read")
    try:
        with pytest.raises(PermissionError if denied else FileNotFoundError):
            _ = api.load_analysis_result(path)
    finally:
        if original is not None:
            path.chmod(original)


def test_load_analysis_result_failure_invalid_json(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-L04: 不正なJSONはValueErrorで拒否する。"""
    path = tmp_path / "invalid.json"
    _ = path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):  # noqa: PT011 -- 公開契約は例外型のみ。
        _ = api.load_analysis_result(path)


@pytest.mark.parametrize("entry", ["load", "from_dict"])
@pytest.mark.parametrize(
    "kind",
    [
        "comparison",
        "schema",
        "scope",
        "files_type",
        "aggregate",
        "aggregate_type",
        "duplicate_id",
        "file_id",
        "parent_id",
        "cycle_id",
    ],
)
def test_load_analysis_result_failure_structure(
    *, api: ModuleType, source: Path, tmp_path: Path, entry: str, kind: str
) -> None:
    """API-L04〜L05: 両入口で種別・必須集計・型・ID重複と参照不整合を拒否。"""
    analysis = api.analyze(source)
    document = (
        api.compare(analysis, analysis).to_dict()
        if kind == "comparison"
        else analysis.to_dict()
    )
    if kind != "comparison":
        corrupt(document, kind)
    if entry == "load":
        path = save_json(tmp_path / "invalid.json", document)
        with pytest.raises(ValueError):  # noqa: PT011 -- 公開契約は例外型のみ。
            _ = api.load_analysis_result(path)
    else:
        with pytest.raises(ValueError):  # noqa: PT011 -- 公開契約は例外型のみ。
            _ = api.AnalysisResult.from_dict(document)


@pytest.mark.parametrize("entry", ["load", "from_dict"])
def test_load_analysis_result_success_unknown_definition(
    *, api: ModuleType, source: Path, tmp_path: Path, entry: str
) -> None:
    """API-L06: 構造が有効な未知の定義版は読み込み、比較時に比較不能とする。"""
    before = api.analyze(source)
    document = before.to_dict()
    document["metadata"]["measurement_models"]["sloc"]["definition_version"] = (
        "unknown-definition"
    )
    after = (
        api.load_analysis_result(save_json(tmp_path / "unknown.json", document))
        if entry == "load"
        else api.AnalysisResult.from_dict(document)
    )
    result = api.compare(before, after)
    assert result.status == "complete"
    assert not result.differences.get("sloc")
    assert any(
        item.metric == "sloc" and item.reason for item in result.incompatible_metrics
    )
    assert result.differences["function_count"]["total"].difference == 0
