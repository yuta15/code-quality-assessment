"""API-P01〜P22: 公開結果の比較、互換性、入力保持。"""

import copy
from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from .support import SCOPE_FIELDS, PublicModel, save_json, write_source

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def assert_incompatible(result: PublicModel, metric: str) -> None:
    assert any(
        item.metric == metric and item.reason for item in result.incompatible_metrics
    )


@pytest.mark.parametrize(
    ("before_dir", "after_dir"),
    [(False, False), (True, True), (False, True), (True, False)],
)
def test_compare_success_source_scopes(
    *, api: ModuleType, tmp_path: Path, before_dir: bool, after_dir: bool
) -> None:
    """API-P01〜P02: 配置・名前・定義数の異なる入力をScope全体で比較。"""
    before = write_source(tmp_path, "before/old.py", "def old(): pass\n")
    after = write_source(
        tmp_path,
        "after/nested/new.py",
        "class New: pass\ndef new(): pass\ndef extra(): pass\n",
    )
    result = api.compare(
        api.analyze(before.parent if before_dir else before),
        api.analyze(after.parent.parent if after_dir else after),
    )
    item = result.differences["sloc"]["total"]
    assert result.status == "complete"
    assert (item.before, item.after, item.difference, item.change_rate) == (
        1,
        3,
        2,
        200,
    )
    assert result.differences["function_count"]["total"].difference == 1


def test_compare_success_identical(*, api: ModuleType, source: Path) -> None:
    """API-P03: 同条件の全項目は差分0、0分母・計測不能はnullと理由。"""
    before, after = api.analyze(source), api.analyze(source)
    result = api.compare(before, after)
    for metric, fields in SCOPE_FIELDS.items():
        for field in fields:
            value = getattr(before.metrics[metric], field)
            item = result.differences.get(metric, {}).get(field)
            if value is not None:
                assert item is not None
            if item is not None:
                assert item.difference == (None if value is None else 0)
                assert item.change_rate == (None if value in (None, 0) else 0)
            if value in (None, 0):
                assert_incompatible(result, metric)


@pytest.mark.parametrize(
    ("before_value", "after_value", "expected"),
    [
        (10, 5, (-5, -50)),
        (5, 10, (5, 100)),
        (5, 5, (0, 0)),
        (0, 5, (5, None)),
        (5, 0, (-5, -100)),
        (0, 0, (0, None)),
        (5, 15, (10, 200)),
    ],
)
def test_compare_success_arithmetic(
    *,
    api: ModuleType,
    source: Path,
    before_value: int,
    after_value: int,
    expected: tuple[int, int | None],
) -> None:
    """API-P04: 増減・同値・0分母・100%超の変化率を仕様値で検証。"""
    before = api.analyze(source)
    after = copy.deepcopy(before)
    before.metrics["sloc"].total = before_value
    after.metrics["sloc"].total = after_value
    result = api.compare(before, after)
    item = result.differences["sloc"]["total"]
    assert (item.before, item.after) == (before_value, after_value)
    assert (item.difference, item.change_rate) == expected
    if expected[1] is None:
        assert_incompatible(result, "sloc")


@pytest.mark.parametrize(
    ("before_value", "after_value"), [(None, 5), (5, None), (None, None)]
)
def test_compare_success_unavailable(
    *, api: ModuleType, source: Path, before_value: int | None, after_value: int | None
) -> None:
    """API-P05: nullを0へ変換せず、差分・変化率をnullとし理由を残す。"""
    before = api.analyze(source)
    after = copy.deepcopy(before)
    for result, value in ((before, before_value), (after, after_value)):
        result.metrics["function_length"].average = value
        if value is None:
            result.metrics["function_length"].unavailable_reason = "NO_FUNCTIONS"
    result = api.compare(before, after)
    item = result.differences.get("function_length", {}).get("average")
    if item is not None:
        assert item.difference is None
        assert item.change_rate is None
    assert_incompatible(result, "function_length")


@pytest.mark.parametrize("reverse", [False, True])
def test_compare_success_percentage_precision(
    *, api: ModuleType, source: Path, reverse: bool
) -> None:
    """API-P06〜P07: 割合差分はptで、入れ替え後は新しいBeforeが基準。"""
    before = api.analyze(source)
    after = copy.deepcopy(before)
    before.metrics["duplication_rate"].value = 15
    after.metrics["duplication_rate"].value = 10
    before.metrics["function_length"].average = 1.23456
    after.metrics["function_length"].average = 2.34567
    if reverse:
        before, after = after, before
    result = api.compare(before, after)
    item = result.differences["duplication_rate"]["value"]
    assert item.difference == (5 if reverse else -5)
    assert item.change_rate == pytest.approx(50 if reverse else -100 / 3)
    length = result.differences["function_length"]["average"]
    assert length.difference == pytest.approx(-1.11111 if reverse else 1.11111)
    assert length.change_rate == pytest.approx(
        (-1.11111 / 2.34567 if reverse else 1.11111 / 1.23456) * 100
    )


def test_compare_success_all_scope_items(*, api: ModuleType, source: Path) -> None:
    """API-P08: 全Scope指標の全集計項目を独立した比較項目として保持。"""
    before = api.analyze(source)
    after = copy.deepcopy(before)
    for index, (metric, fields) in enumerate(SCOPE_FIELDS.items(), start=1):
        for field in fields:
            setattr(before.metrics[metric], field, index)
            setattr(after.metrics[metric], field, index + 1)
    result = api.compare(before, after)
    for index, (metric, fields) in enumerate(SCOPE_FIELDS.items(), start=1):
        assert set(result.differences[metric]) == set(fields)
        for field in fields:
            item = result.differences[metric][field]
            assert (item.before, item.after, item.difference) == (index, index + 1, 1)
            assert item.change_rate == pytest.approx(100 / index)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_metric",
        "tool_version",
        "definition",
        "threshold",
        "missing_model",
        "unknown_setting",
    ],
)
def test_compare_success_compatibility(
    *, api: ModuleType, source: Path, kind: str
) -> None:
    """API-P09〜P12: 互換性を指標単位で判定し、共通の互換指標は比較継続。"""
    before = api.analyze(source)
    after = copy.deepcopy(before)
    model = after.metadata.measurement_models["duplication_rate"]
    if kind == "missing_metric":
        del after.metrics["duplication_rate"]
    elif kind == "tool_version":
        after.metadata.tool_version = "999.0.0"
    elif kind == "definition":
        model.definition_version = "unknown-definition"
    elif kind == "threshold":
        model.settings["minimum_match_tokens"] = 51
    elif kind == "missing_model":
        del after.metadata.measurement_models["duplication_rate"]
    else:
        model.settings["unknown-setting"] = True
    result = api.compare(before, after)
    assert result.differences["sloc"]["total"].difference == 0
    if kind == "tool_version":
        assert result.differences["duplication_rate"]["value"].difference == 0
    else:
        assert not result.differences.get("duplication_rate")
        assert_incompatible(result, "duplication_rate")


def test_compare_success_scope_settings_differ(
    *, api: ModuleType, tmp_path: Path
) -> None:
    """API-P13: 除外条件・ファイル数の違いを許可し、各側の条件を保持。"""
    _ = write_source(tmp_path, "a.py")
    _ = write_source(tmp_path, "b.py")
    before = api.analyze(tmp_path)
    after = api.analyze(tmp_path, exclude=("b.py",))
    result = api.compare(before, after)
    assert result.before.scope.file_count == len({"a.py", "b.py"})
    assert result.after.scope.file_count == 1
    assert result.before.metadata == before.metadata
    assert result.after.metadata == after.metadata
    assert result.differences["sloc"]["total"].difference == -1


@pytest.mark.parametrize("kind", ["disjoint", "unknown_definitions"])
@pytest.mark.parametrize("partial", [False, True])
def test_compare_success_no_comparable(
    *, api: ModuleType, source: Path, kind: str, partial: bool
) -> None:
    """API-P14/P16: 比較可能0件でも両側と理由を保持し解析状態を反映。"""
    if partial:
        _ = write_source(source.parent, "broken.py", "def broken(:\n")
    before = api.analyze(source.parent if partial else source)
    after = copy.deepcopy(before)
    if kind == "disjoint":
        before.metrics = {"sloc": before.metrics["sloc"]}
        after.metrics = {"function_count": after.metrics["function_count"]}
    else:
        for model in after.metadata.measurement_models.values():
            model.definition_version = "unknown-definition"
    result = api.compare(before, after)
    assert not result.differences or not any(result.differences.values())
    assert result.incompatible_metrics
    assert all(item.reason for item in result.incompatible_metrics)
    assert result.status == ("partial" if partial else "complete")
    assert result.before == before
    assert result.after == after


@pytest.mark.parametrize(
    ("before_partial", "after_partial"),
    [(False, False), (False, True), (True, False), (True, True)],
)
def test_compare_success_partial_states(
    *, api: ModuleType, tmp_path: Path, before_partial: bool, after_partial: bool
) -> None:
    """API-P15/P20: complete/partial全組合せで成功値・両側エラーを保持。"""
    roots = [tmp_path / side for side in ("before", "after")]
    results: list[PublicModel] = []
    for root, partial in zip(roots, (before_partial, after_partial), strict=True):
        _ = write_source(root, "good.py")
        if partial:
            _ = write_source(root, "broken.py", "def broken(:\n")
        results.append(api.analyze(root))
    result = api.compare(*results)
    assert result.status == (
        "partial" if before_partial or after_partial else "complete"
    )
    assert result.differences["sloc"]["total"].difference == 0
    assert result.before.errors == results[0].errors
    assert result.after.errors == results[1].errors


def test_compare_success_unresolved_cbo(*, api: ModuleType, source: Path) -> None:
    """API-P17/P20: CBO確定値3→2と未解決5件を保持し、未解決だけではpartialにしない。"""
    before = api.analyze(write_source(source.parent, "classes.py", "class C: pass\n"))
    after = copy.deepcopy(before)
    before.metrics["cbo"].average = 3
    after.metrics["cbo"].average = 2
    class_id = after.details.classes[0].id
    after.unresolved = [
        api.UnresolvedReference(
            metric="cbo", target=class_id, reason=f"Unresolved reference {i}"
        )
        for i in range(5)
    ]
    result = api.compare(before, after)
    assert result.status == "complete"
    assert result.differences["cbo"]["average"].difference == -1
    assert result.before.unresolved == []
    assert result.after.unresolved == after.unresolved


@pytest.mark.parametrize("nonempty", [False, True])
def test_compare_success_empty_scope(
    *, api: ModuleType, tmp_path: Path, nonempty: bool
) -> None:
    """API-P18: 空同士・空対非空の0/null規則を適用する。"""
    root = tmp_path / "empty"
    root.mkdir()
    after = write_source(tmp_path, "nonempty.py") if nonempty else root
    result = api.compare(api.analyze(root), api.analyze(after))
    assert result.status == "complete"
    assert result.before.scope.file_count == 0
    assert result.after.scope.file_count == int(nonempty)
    assert result.differences["sloc"]["total"].difference == int(nonempty)


@pytest.mark.parametrize("combination", ["saved_saved", "saved_live", "live_saved"])
@pytest.mark.parametrize("change", ["delete", "rewrite"])
def test_compare_success_restored_input(
    *,
    api: ModuleType,
    analysis: PublicModel,
    tmp_path: Path,
    combination: str,
    change: str,
) -> None:
    """API-P19: 保存結果と通常解析の両方向、ソース削除・変更後も保存値を使う。"""
    saved = save_json(tmp_path / "result.json", analysis.to_dict())
    live = copy.deepcopy(analysis)
    for path in (tmp_path / "project").rglob("*.py"):
        if change == "delete":
            path.unlink()
        else:
            _ = path.write_text("class Changed: pass\n", encoding="utf-8")
    restored = api.load_analysis_result(saved)
    before = live if combination == "live_saved" else restored
    after = live if combination == "saved_live" else api.load_analysis_result(saved)
    result = api.compare(before, after)
    assert result.before == analysis
    assert result.after == analysis


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("invalid", [{}, "source.py", None, 1, []])
def test_compare_failure_input_type(
    *, api: ModuleType, source: Path, side: str, invalid: object
) -> None:
    """API-P21: AnalysisResult以外を両側それぞれでTypeErrorとする。"""
    valid = api.analyze(source)
    args = (invalid, valid) if side == "before" else (valid, invalid)
    with pytest.raises(TypeError):
        _ = api.compare(*args)


@pytest.mark.parametrize("incompatible", [False, True])
def test_compare_success_preserves_inputs(
    *, api: ModuleType, analysis: PublicModel, incompatible: bool
) -> None:
    """API-P22: 正常・空・partial・未解決・非互換の入力と入れ子を変更しない。"""
    before = analysis
    after = copy.deepcopy(before)
    if incompatible:
        for model in after.metadata.measurement_models.values():
            model.definition_version = "unknown-definition"
    snapshots = (copy.deepcopy(asdict(before)), copy.deepcopy(asdict(after)))
    _ = api.compare(before, after)
    assert asdict(before) == snapshots[0]
    assert asdict(after) == snapshots[1]
